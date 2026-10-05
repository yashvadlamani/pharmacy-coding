"""Step 4. Validate a plan: reconcile it with its documents, list what the client still has to decide,
and work out what members would pay for common prescriptions.

Conflicts and failed checks block client confirmation until the rep records an answer.
"""
import csv
import re

from . import config, formulary as formularies
from .fields import AMOUNT, BY_NAME, COST_SHARE, FIELDS, MAIL_FIELD, RETAIL_FIELD, describe
from .fit import CUSTOM, NOT_SUPPORTED

# ACA maximum out-of-pocket limits for plan year 2026 (self-only, family). Reported as a warning, not a failure.
ACA_OOP_LIMIT = {"oop_max_individual": 10600, "oop_max_family": 21200}

# What to ask the client when the documents are silent on a field.
MISSING_QUESTIONS = {
    "overall_deductible_individual": "What is the plan's overall deductible for an individual?",
    "overall_deductible_family": "What is the plan's overall deductible for a family?",
    "rx_deductible_individual": "Is there a separate pharmacy deductible, and if so how much for an individual?",
    "rx_deductible_family": "Is there a separate pharmacy deductible, and if so how much for a family?",
    "oop_max_individual": "What is the individual out-of-pocket limit that drug costs count toward?",
    "oop_max_family": "What is the family out-of-pocket limit that drug costs count toward?",
    "generic_mail": "What does a member pay for a generic drug by mail order?",
    "preferred_brand_mail": "What does a member pay for a preferred brand drug by mail order?",
    "nonpreferred_brand_mail": "What does a member pay for a non-preferred brand drug by mail order?",
    "retail_days_supply": "What is the largest days supply allowed for one retail fill?",
    "mail_days_supply": "What is the largest days supply allowed for one mail order fill?",
    "mail_order_available": "Is mail order offered, and is it optional or mandatory for maintenance drugs?",
    "specialty_pharmacy_required": "Must specialty drugs be filled at a designated specialty pharmacy?",
    "prior_auth_drugs": "Which prior authorization and step therapy programs apply?",
}
# Decisions a Summary of Benefits and Coverage never states; every plan needs them before coding.
STANDING_QUESTIONS = [
    ("standing:coupons", "Do manufacturer copay coupon amounts count toward the deductible and out-of-pocket limit?"),
    ("standing:brand_penalty", "When a member asks for a brand with a generic available, do they pay the brand "
                               "copay only, or the copay plus the cost difference?"),
    ("standing:exclusions", "Are weight-loss, fertility and erectile dysfunction drugs covered or excluded?"),
    ("standing:carryover", "For a mid-year start, does deductible and out-of-pocket credit carry over from the prior carrier?"),
]


def _numbers(text, suffix=""):
    """Dollar or percent figures in a passage: _numbers('$1,500 then 20%') -> {1500.0}; with '%' -> {20.0}."""
    pattern = r"(\d[\d,]*(?:\.\d+)?)\s*%" if suffix == "%" else r"\$\s*(\d[\d,]*(?:\.\d+)?)"
    return {float(n.replace(",", "")) for n in re.findall(pattern, text)}


def reconcile(item):
    """Check that the figures read appear in the passage cited from the document. Returns a list of problems.
    A value the model worked out from a rule (it says so in its note) is not expected to appear verbatim."""
    if item["status"] != "value" or item["kind"] not in (AMOUNT, COST_SHARE):
        return []
    quote, problems = item["quote"], []
    if item["kind"] == AMOUNT and float(item["amount"]) not in _numbers(quote):
        problems.append(f"${item['amount']:,.0f} does not appear in the cited passage")
    if item["kind"] == COST_SHARE:
        if item["copay"] and float(item["copay"]) not in _numbers(quote):
            problems.append(f"${item['copay']:,.0f} copay does not appear in the cited passage")
        if item["coinsurance_pct"] and float(item["coinsurance_pct"]) not in _numbers(quote, "%"):
            problems.append(f"{item['coinsurance_pct']:g}% coinsurance does not appear in the cited passage")
    return problems


def _value(fields, name):
    item = fields[name]
    return float(item["amount"]) if item["status"] == "value" else None


def consistency(fields):
    """Rules that hold for any plan design, whatever the document says."""
    checks = []
    pairs = [("overall_deductible_family", "overall_deductible_individual", "Family deductible is below the individual deductible"),
             ("rx_deductible_family", "rx_deductible_individual", "Family pharmacy deductible is below the individual one"),
             ("oop_max_family", "oop_max_individual", "Family out-of-pocket limit is below the individual limit"),
             ("oop_max_individual", "overall_deductible_individual", "Out-of-pocket limit is below the deductible")]
    for larger, smaller, message in pairs:
        a, b = _value(fields, larger), _value(fields, smaller)
        if a is not None and b is not None and a < b:
            checks.append({"check": "consistency", "field": larger, "status": "fail",
                           "detail": f"{message} (${a:,.0f} vs ${b:,.0f})"})
    for name, limit in ACA_OOP_LIMIT.items():
        amount = _value(fields, name)
        if amount is not None and amount > limit:
            checks.append({"check": "aca_limit", "field": name, "status": "warn",
                           "detail": f"${amount:,.0f} is above the 2026 ACA limit of ${limit:,.0f}"})
    for cheaper, dearer in (("generic_retail", "preferred_brand_retail"), ("preferred_brand_retail", "nonpreferred_brand_retail")):
        a, b = fields[cheaper], fields[dearer]
        copay_only = all(i["status"] == "value" and i["copay"] and not i["coinsurance_pct"] for i in (a, b))
        if copay_only and a["copay"] > b["copay"]:
            checks.append({"check": "tier_order", "field": dearer, "status": "warn",
                           "detail": f"{BY_NAME[dearer].label} copay is lower than {BY_NAME[cheaper].label}"})
    return checks


def load_intake(path=None):
    """{plan id: {field: row}} from the client intake form (synthetic in the prototype)."""
    out = {}
    with open(path or config.PACKAGE / "intake.csv", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            out.setdefault(row["plan_id"], {})[row["field"]] = row
    return out


def intake_conflicts(fields, intake):
    """Fields where the client's intake form and the plan document disagree."""
    conflicts = []
    for name, row in intake.items():
        item = fields[name]
        if item["status"] == "not_found":
            continue
        if BY_NAME[name].kind == COST_SHARE:
            same = (float(row["copay"] or 0), float(row["coinsurance_pct"] or 0)) == \
                   (float(item["copay"] or 0), float(item["coinsurance_pct"] or 0))
        else:
            same = float(row["amount"] or 0) == float(item["amount"] or 0)
        if not same:
            conflicts.append((name, row["client_value"]))
    return conflicts


def price(item, allowed, deductible, max_per_fill=None):
    """Member cost for one fill. deductible is what is left to meet (0 once met). Returns (cost or None, explanation)."""
    if item["status"] == "not_covered":
        return float(allowed), "Not covered: member pays the full price"
    if item["status"] not in ("value", "no_charge"):
        return None, "To be confirmed: the plan document does not state this cost share"

    cost, remaining, steps = 0.0, float(allowed), []
    if item["deductible_applies"] and deductible:
        paid = min(remaining, deductible)
        cost, remaining = cost + paid, remaining - paid
        steps.append(f"${paid:,.2f} toward the deductible")
    if item["status"] == "value" and item["copay"] and remaining:
        paid = min(remaining, float(item["copay"]))
        cost, remaining = cost + paid, remaining - paid
        steps.append(f"${paid:,.2f} copay" + (" (drug costs less than the copay)" if paid < item["copay"] else ""))
    if item["status"] == "value" and item["coinsurance_pct"]:
        paid = remaining * float(item["coinsurance_pct"]) / 100
        if max_per_fill is not None and paid > max_per_fill:
            paid = max_per_fill
            steps.append(f"{item['coinsurance_pct']:g}% coinsurance, capped at ${max_per_fill:,.0f} per fill")
        else:
            steps.append(f"{item['coinsurance_pct']:g}% of ${remaining:,.2f}")
        cost += paid
    return round(cost, 2), "; ".join(steps) or "No charge"


def load_scenarios(path=None):
    with open(path or config.PACKAGE / "scenarios.csv", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def member_costs(fields, formulary, scenarios, scenario_drugs):
    """What a member pays for each example prescription, before and after the deductible is met.

    Each example doubles as a test claim for the coding handoff: the expected result is either the member
    cost or the reject the pharmacy would see.
    """
    # a pharmacy-only deductible takes the place of the overall one for drug claims
    deductible = _value(fields, "rx_deductible_individual") or _value(fields, "overall_deductible_individual") or 0.0
    max_per_fill = _value(fields, "specialty_max_per_fill")
    rows = []
    for scenario in scenarios:
        drug = scenario_drugs[scenario["id"]]
        allowed = round(drug["unit_price"] * float(scenario["quantity"]), 2)
        row = {"id": scenario["id"], "label": scenario["label"], "channel": scenario["channel"], "allowed": allowed,
               "price_source": drug["price_source"], "tier": None, "notes": [], "first_fill": None,
               "after_deductible": None, "explanation": "", "reject": None}
        on_formulary = formularies.status(formulary, drug["rxcuis"]) if formulary else None
        if on_formulary is None:
            row.update(first_fill=allowed, after_deductible=allowed, reject="70 Product/Service Not Covered",
                       explanation="Not on the plan's formulary: the claim rejects and the member pays the full price")
            rows.append(row)
            continue
        row["tier"] = f"{on_formulary['tier']} ({on_formulary['class_label']})"
        if on_formulary["pa"]:
            row["notes"].append("Needs prior authorization first; without one the claim rejects (75)")
        if on_formulary["st"]:
            row["notes"].append("Step therapy applies")
        if on_formulary["ql"]:
            row["notes"].append("Quantity limit applies; a quantity above it rejects (76)")
        if on_formulary["class"] == formularies.PREVENTIVE:
            row.update(first_fill=0.0, after_deductible=0.0, explanation="$0 preventive drug list")
            rows.append(row)
            continue
        by_channel = MAIL_FIELD if scenario["channel"] == "mail" else RETAIL_FIELD
        name = by_channel.get(on_formulary["class"])
        if name is None:
            row["explanation"] = "Specialty drugs are not filled by mail order"
            rows.append(row)
            continue
        cap = max_per_fill if on_formulary["class"] == "specialty" else None
        row["field"] = name
        row["first_fill"], row["explanation"] = price(fields[name], allowed, deductible, cap)
        row["after_deductible"], _ = price(fields[name], allowed, 0.0, cap)
        rows.append(row)
    return rows


def validate(extraction, coded, formulary, scenario_drugs, intake=None, scenarios=None):
    """Run every check for one plan and build the rep's view of it."""
    fields = {item["field"]: item for item in extraction["fields"]}
    mapped = {row["field"]: row for row in coded["fields"]}
    checks, questions = consistency(fields), []

    for name, item in fields.items():
        for problem in reconcile(item):
            status = "warn" if item["note"] else "fail"  # a noted value was worked out, not copied
            checks.append({"check": "reconciliation", "field": name, "status": status, "detail": problem})
        if item["status"] != "not_found" and not item["citation_valid"]:
            checks.append({"check": "citation", "field": name, "status": "fail",
                           "detail": "The cited passage was not found in the document"})
    for name, client_value in intake_conflicts(fields, intake or {}):
        detail = f"The intake form says {client_value}; the plan document says {describe(fields[name])}"
        checks.append({"check": "intake_conflict", "field": name, "status": "fail", "detail": detail})
        questions.append({"id": f"conflict:{name}", "kind": "conflict", "field": name, "blocking": True,
                          "text": f"{BY_NAME[name].label}: {detail}. Which is correct?"})

    failed_fields = {c["field"] for c in checks if c["status"] == "fail"}
    for field in FIELDS:
        item, fit = fields[field.name], mapped[field.name]
        if item["status"] == "not_found" and field.name in MISSING_QUESTIONS:
            questions.append({"id": f"missing:{field.name}", "kind": "missing", "field": field.name, "blocking": False,
                              "text": MISSING_QUESTIONS[field.name]})
        elif item["status"] != "not_found" and field.name not in failed_fields and (
                item["needs_review"] or not item["citation_valid"]):
            text = f"Please confirm {field.label.lower()}: we read {describe(item)}"
            if item["note"]:
                text += f" ({item['note'].rstrip('.')})"
            questions.append({"id": f"confirm:{field.name}", "kind": "confirm", "field": field.name,
                              "blocking": False, "text": text + "."})
        if fit["fit"] in (CUSTOM, NOT_SUPPORTED):
            questions.append({"id": f"fit:{field.name}", "kind": "fit", "field": field.name,
                              "blocking": fit["fit"] == NOT_SUPPORTED,
                              "text": f"{field.label} ({fit['value']}) is rated {fit['fit'].lower()}: {fit['fit_reason']}. "
                                      "Does the client need this exactly, or will a standard design do?"})
    questions += [{"id": qid, "kind": "standing", "field": None, "blocking": False, "text": text}
                  for qid, text in STANDING_QUESTIONS]

    costs = member_costs(fields, formulary, load_scenarios() if scenarios is None else scenarios, scenario_drugs)

    view = {}
    for field in FIELDS:
        item, fit = fields[field.name], mapped[field.name]
        reasons = [c["detail"] for c in checks if c["field"] == field.name]
        view[field.name] = {"label": field.label, "value": describe(item), "fit": fit["fit"],
                            "fit_reason": fit["fit_reason"], "code": fit["code"], "reasons": reasons,
                            "attention": bool(reasons) or item["needs_review"], "page": item["page"],
                            "quote": item["quote"], "confidence": item["confidence"], "note": item["note"]}
    failed = sum(c["status"] == "fail" for c in checks)
    return {
        "doc_id": extraction["doc_id"],
        "checks": checks,
        "questions": questions,
        "member_costs": costs,
        "fields": view,
        "plan_wide": [mapped[name] for name in ("accumulators", "formulary_tiers") if name in mapped],
        "formulary_warnings": formulary.get("warnings", []) if formulary else [],
        "summary": {"failed": failed, "warnings": sum(c["status"] == "warn" for c in checks),
                    "questions": len(questions), "blocking": sum(q["blocking"] for q in questions),
                    "fit": coded["summary"]},
    }
