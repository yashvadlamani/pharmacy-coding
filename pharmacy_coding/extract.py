"""Step 2. Extract the pharmacy plan design from an ingested document, each field with a citation and confidence."""
import json
import re

from openai import AzureOpenAI

from . import config, store
from .fields import AMOUNT, BY_NAME, COST_SHARE, FIELDS, FLAG, NUMBER

REVIEW_THRESHOLD = 0.8      # fields below this confidence are flagged for the reviewer
UNCITED_CONFIDENCE = 0.3    # ceiling for a field whose quote is not in the document
MAX_RUNS, MIN_RUN = 4, 2  # a quote may be up to 4 runs of page text, each at least 2 words
SBC_SECTIONS_USED = {"header", "important_questions", "common_medical_events"}
STATUSES = ["value", "no_charge", "not_covered", "not_applicable", "not_found"]

SYSTEM_PROMPT = """You extract prescription drug benefit terms from health plan documents for a pharmacy
benefit sales team. Return every requested field exactly once. Use only what the document states; never guess.

Document text is split by markers like [[page 3]]; report that page number for each field.

Rules
- Report what the member pays at a standard in-network pharmacy. Read the column headings first: never combine
  values from different columns, and never use the out-of-network column.
- If the plan has several in-network pharmacy levels, use the lowest-cost (preferred) level, lower the
  confidence and say so in "note".
- amount fields: put the dollar figure in "amount". A stated $0 is status "value" with amount 0.
  overall_deductible fields: the plan's overall in-network deductible, whether or not drugs are subject to it.
  rx_deductible fields: only a deductible that applies to prescription drugs alone, usually given under "Are
  there other deductibles for specific services?". When the document shows there is none, the status is
  "not_applicable"; quote the passage that shows it. Never put the overall deductible here.
  specialty_max_per_fill: only a stated dollar cap on one specialty fill; otherwise "not_found".
- number fields: put the number of days in "amount".
- cost_share fields: "copay" is dollars the member pays per fill, "coinsurance_pct" is the percent the member
  pays. Both can be set ("$250 copay then 20%"). "No charge", "covered at 100%", "$0" or "0%" is status
  "no_charge". "Not covered" is status "not_covered".
  Retail fields are one fill of up to a 30-day supply at a retail pharmacy. Mail fields are one mail order
  (home delivery) fill, usually up to 90 days. When a row gives one value without naming a channel, use it for
  the retail field and report the mail field as "not_found" unless the document says the value also applies
  to mail order. When mail order cost is given as a rule ("three times the retail copay"), work it out, lower
  the confidence and explain in "note".
  Drug fields are defined by drug class, not tier number. When tiers are only numbered: with four tiers they are
  generic, preferred brand, non-preferred brand, specialty; with five or six tiers, tiers 1-2 are generic (use
  tier 1), tier 3 preferred brand, tier 4 non-preferred brand, tier 5 specialty. When a generic tier is split
  (1a/1b), use the standard generic tier, not the "typically lower cost" one. In all of these cases set
  confidence to 0.7 or less and explain the choice in "note".
- deductible_applies: true if the member pays this only after meeting the deductible, false if the document
  says the deductible does not apply, null if it is not clear. Decide from the drug row itself and from the
  answer to "Are there services covered before you meet your deductible?". The sentence "All copayment and
  coinsurance costs shown in this chart are after your deductible has been met, if a deductible applies" is
  printed on every summary and decides nothing by itself.
  If prescription drugs are listed as covered before the deductible, deductible_applies is false for the drug
  fields. A drug field that is subject only to a separate prescription drug deductible has deductible_applies
  true.
- flag fields: "flag" is true or false as the document states. If silent, status "not_found".
- quote: copy text exactly as it appears on one page, at most 150 characters: the drug class or question,
  then the value. If other text sits between them, join the two pieces with " ... ". Do not reword anything.
- confidence: 0 to 1. Lower it when wording is ambiguous, values conflict, or several tiers make the choice unclear.
- status "not_found" when the document does not state the field; leave the numbers null.
"""


def _schema():
    nullable_number = {"type": ["number", "null"]}
    item = {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "field": {"type": "string", "enum": [f.name for f in FIELDS]},
            "status": {"type": "string", "enum": STATUSES},
            "amount": nullable_number,
            "copay": nullable_number,
            "coinsurance_pct": nullable_number,
            "deductible_applies": {"type": ["boolean", "null"]},
            "flag": {"type": ["boolean", "null"]},
            "quote": {"type": "string"},
            "page": {"type": ["integer", "null"]},
            "confidence": {"type": "number"},
            "note": {"type": "string"},
        },
    }
    item["required"] = list(item["properties"])
    return {
        "name": "pharmacy_fields",
        "strict": True,
        "schema": {
            "type": "object",
            "additionalProperties": False,
            "properties": {"fields": {"type": "array", "items": item}},
            "required": ["fields"],
        },
    }


def _client():
    return AzureOpenAI(
        azure_endpoint=config.setting("AZURE_AI_ENDPOINT"),
        api_key=config.setting("AZURE_AI_KEY"),
        api_version="2024-10-21",
    )


def _tokens(text):
    """Words and whole numbers of a passage, as a space-delimited string. PDF extraction mangles line breaks,
    spacing and punctuation, so citations are compared word by word; $125 and 20% stay single tokens, which
    means a quote with a changed number never matches."""
    found = re.findall(r"\$?\d[\d,]*(?:\.\d+)?%?|[a-z]+", text.lower())
    return " " + " ".join(token.replace(",", "") for token in found) + " "


def _covered(piece, text):
    """True when piece is made of at most MAX_RUNS runs of consecutive words that each appear on the page.
    Table cells are extracted out of reading order, so a label and its value are often not adjacent."""
    words = piece.split()
    for _ in range(MAX_RUNS):
        if not words:
            return True
        shortest = min(MIN_RUN, len(words))
        length = next((n for n in range(len(words), shortest - 1, -1)
                       if " " + " ".join(words[:n]) + " " in text), 0)
        if not length:
            return False
        words = words[length:]
    return not words


def verify_citation(quote, page, pages):
    """Return (found, page). A quote may be pieces joined by "..."; every piece must be on the same page.
    Looks on the cited page first, then anywhere in the document."""
    pieces = [_tokens(piece) for piece in re.split(r"\.\.\.|…", quote)]
    pieces = [piece for piece in pieces if piece.strip()]
    if not pieces:
        return False, page
    ordered = sorted(pages, key=lambda p: p["page"] != page)
    for candidate in ordered:
        text = _tokens(candidate["text"])
        if all(_covered(piece, text) for piece in pieces):
            return True, candidate["page"]
    return False, page


def _clean(item, pages):
    """Keep only the numbers that belong to the field's kind, verify the citation, set the review flag."""
    kind = BY_NAME[item["field"]].kind
    if kind not in (AMOUNT, NUMBER):
        item["amount"] = None
    if kind != COST_SHARE:
        item["copay"] = item["coinsurance_pct"] = item["deductible_applies"] = None
    if kind != FLAG:
        item["flag"] = None
    if kind == COST_SHARE and item["status"] == "value" and not item["copay"] and not item["coinsurance_pct"]:
        item["status"] = "no_charge"
    if kind in (AMOUNT, NUMBER) and item["status"] == "value" and item["amount"] is None:
        item["status"] = "not_found"
    if kind == FLAG and item["status"] == "value" and item["flag"] is None:
        item["status"] = "not_found"
    if item["status"] != "value":
        item["amount"] = item["copay"] = item["coinsurance_pct"] = None

    item["kind"] = kind
    item["citation_valid"], item["page"] = verify_citation(item["quote"], item["page"], pages)
    if item["status"] == "not_found":
        item["citation_valid"] = False
        item["confidence"] = min(item["confidence"], UNCITED_CONFIDENCE)
    elif not item["citation_valid"]:
        item["confidence"] = min(item["confidence"], UNCITED_CONFIDENCE)
    item["needs_review"] = item["confidence"] < REVIEW_THRESHOLD
    return item


def extract(document):
    """Run the LLM over the document's benefit sections and return one cleaned record per field."""
    names = SBC_SECTIONS_USED if document.doc_type == "sbc" else None
    text = document.section_text(names)
    field_list = "\n".join(f"- {f.name} ({f.kind}): {f.description}" for f in FIELDS)
    response = _client().chat.completions.create(
        model=config.setting("AZURE_OPENAI_DEPLOYMENT"),
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": f"Fields to extract:\n{field_list}\n\nDocument ({document.doc_type}):\n\n{text}"},
        ],
        response_format={"type": "json_schema", "json_schema": _schema()},
    )
    returned = {item["field"]: item for item in json.loads(response.choices[0].message.content)["fields"]}

    fields = []
    for f in FIELDS:
        item = returned.get(f.name) or {
            "field": f.name, "status": "not_found", "amount": None, "copay": None, "coinsurance_pct": None,
            "deductible_applies": None, "flag": None, "quote": "", "page": None, "confidence": 0.0,
            "note": "not returned by the model",
        }
        fields.append(_clean(item, document.pages))
    return {
        "doc_id": document.doc_id,
        "doc_type": document.doc_type,
        "model": response.model,
        "usage": {"input_tokens": response.usage.prompt_tokens, "output_tokens": response.usage.completion_tokens},
        "fields": fields,
    }


def save(result):
    store.write_json(f"extracted/{result['doc_id']}.json", result)
