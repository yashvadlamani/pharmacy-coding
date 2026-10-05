"""Step 3. Map each extracted field to a placeholder platform code and rate how easily it can be administered.

The standard offering catalog (catalog.csv) and the rules below are placeholders that show the mechanism.
In production both are replaced by the firm's own catalog and rules, owned by the coding and clinical teams.
"""
import csv
from functools import lru_cache

from . import config
from .fields import AMOUNT, BY_NAME, COST_SHARE, FLAG, NUMBER, describe

STANDARD, CONFIGURABLE, CUSTOM, NOT_SUPPORTED, UNCLEAR = "Standard", "Configurable", "Custom", "Not supported", "Unclear"
ORDER = [NOT_SUPPORTED, CUSTOM, UNCLEAR, CONFIGURABLE, STANDARD]  # most to least in need of a rep's attention
MAX_COINSURANCE = 50
MAIL_MULTIPLES = (2, 2.5, 3)
MAX_MAIL_DAYS = 90


@lru_cache(maxsize=1)
def catalog():
    """{field: {"copay": {values}, "coinsurance": {values}}} standard values from the placeholder catalog."""
    out = {}
    with open(config.PACKAGE / "catalog.csv", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            out[row["field"]] = {key: {float(v) for v in row[key].split("|") if v} for key in ("copay", "coinsurance")}
    return out


def _amount(value, width=5):
    return f"{round(float(value)):0{width}d}"


def code(item):
    """Placeholder platform code for a field, or None when there is nothing to code."""
    field, status = BY_NAME[item["field"]], item["status"]
    prefix = f"RX-{field.code}"
    if status == "not_found":
        return None
    if status == "not_applicable":
        return f"{prefix}-NA"
    if status == "not_covered":
        return f"{prefix}-NC"
    if status == "no_charge":
        return f"{prefix}-CP0000" + ("-AD" if item.get("deductible_applies") else "")
    if field.kind == AMOUNT:
        return f"{prefix}-{_amount(item['amount'])}"
    if field.kind == NUMBER:
        return f"{prefix}-{_amount(item['amount'], 3)}"
    if field.kind == FLAG:
        return f"{prefix}-{'Y' if item['flag'] else 'N'}"
    parts = [prefix]
    if item["copay"]:
        parts.append(f"CP{_amount(item['copay'], 4)}")
    if item["coinsurance_pct"]:
        parts.append(f"CI{_amount(item['coinsurance_pct'], 3)}")
    if item["deductible_applies"]:
        parts.append("AD")
    return "-".join(parts)


def _rate_cost_share(item, fields):
    name, copay, coinsurance = item["field"], item["copay"] or 0, item["coinsurance_pct"] or 0
    if item["status"] == "not_covered":
        return CONFIGURABLE, "Drug class excluded from coverage"
    if item["status"] == "no_charge":
        return STANDARD, "No member cost share"
    if coinsurance > MAX_COINSURANCE:
        return NOT_SUPPORTED, (f"{coinsurance:g}% coinsurance is above the {MAX_COINSURANCE}% the platform administers; "
                               f"nearest supported design is {MAX_COINSURANCE}%")
    if copay and coinsurance:
        return CUSTOM, "A copay and coinsurance on the same fill needs custom cost-share logic"
    if name.endswith("_mail") and copay:
        retail = fields.get(name.replace("_mail", "_retail"))
        if retail and retail["status"] == "value" and retail["copay"] and not retail["coinsurance_pct"]:
            multiple = copay / retail["copay"]
            if any(abs(multiple - m) < 0.01 for m in MAIL_MULTIPLES):
                return STANDARD, f"Mail order copay is {multiple:g} times retail"
            return CONFIGURABLE, f"Mail order copay is {multiple:.2g} times retail; standard is 2, 2.5 or 3 times"
        return CONFIGURABLE, "Mail order cost share set independently of retail"
    standard = catalog().get(name.replace("_mail", "_retail"), {"copay": set(), "coinsurance": set()})
    if copay:
        return (STANDARD, "Standard copay") if copay in standard["copay"] else (CONFIGURABLE, "Non-standard copay amount")
    return ((STANDARD, "Standard coinsurance") if coinsurance in standard["coinsurance"]
            else (CONFIGURABLE, "Non-standard coinsurance percentage"))


def rate(item, fields):
    """(rating, reason) for one field. fields is {name: item} for the whole plan."""
    field = BY_NAME[item["field"]]
    if field.name == "specialty_max_per_fill" and item["status"] != "value":
        return STANDARD, "No per-fill maximum stated"
    if item["status"] == "not_found":
        return UNCLEAR, "The documents do not state this"
    if not item["citation_valid"] or item["needs_review"]:
        return UNCLEAR, "The value was read with low confidence and needs confirming"
    if field.kind == COST_SHARE:
        return _rate_cost_share(item, fields)
    if field.name.startswith("rx_deductible"):
        return ((CONFIGURABLE, "Separate pharmacy deductible") if item["status"] == "value" and item["amount"]
                else (STANDARD, "No separate pharmacy deductible"))
    if field.name == "specialty_max_per_fill":
        return CONFIGURABLE, "Per-fill maximum on specialty coinsurance"
    if field.name == "mail_days_supply" and item["status"] == "value" and item["amount"] > MAX_MAIL_DAYS:
        return NOT_SUPPORTED, f"Mail order above {MAX_MAIL_DAYS} days is not administered; nearest is {MAX_MAIL_DAYS} days"
    if field.name == "retail_days_supply" and item["status"] == "value" and item["amount"] > 34:
        return CONFIGURABLE, "Extended days supply at retail"
    return STANDARD, "Standard parameter"


def formulary_fit(formulary):
    """Fit rating for the plan's formulary structure."""
    count = len([t for t in formulary["tiers"].values() if t["class"] != "preventive"])
    if count > 5:
        return CUSTOM, f"{count} cost-share tiers; standard formularies have up to five"
    if count > 4:
        return CONFIGURABLE, f"{count} cost-share tiers"
    return STANDARD, f"{count} cost-share tiers"


def shares_medical_deductible(fields):
    """True when a drug cost share applies after a deductible and the plan has no pharmacy-only deductible,
    so pharmacy claims must count toward the medical deductible."""
    separate = fields["rx_deductible_individual"]
    has_separate = separate["status"] == "value" and separate["amount"]
    after = any(i["deductible_applies"] for i in fields.values() if BY_NAME[i["field"]].kind == COST_SHARE)
    return after and not has_separate


def map_plan(extraction, formulary=None):
    """Code and rate every field of one plan, then the plan-wide items: accumulators and formulary structure."""
    fields = {item["field"]: item for item in extraction["fields"]}
    rows = []
    for item in extraction["fields"]:
        rating, reason = rate(item, fields)
        rows.append({"field": item["field"], "value": describe(item), "code": code(item), "fit": rating,
                     "fit_reason": reason})
    if shares_medical_deductible(fields):
        rows.append({"field": "accumulators", "value": "Drugs count toward the medical deductible",
                     "code": "RX-ACC-INT", "fit": CONFIGURABLE,
                     "fit_reason": "Needs a shared accumulator feed with the medical carrier"})
    else:
        rows.append({"field": "accumulators", "value": "Pharmacy deductible stands alone", "code": "RX-ACC-STD",
                     "fit": STANDARD, "fit_reason": "No deductible is shared with medical"})
    if formulary:
        rating, reason = formulary_fit(formulary)
        rows.append({"field": "formulary_tiers", "value": f"{len(formulary['tiers'])} tiers on formulary "
                     f"{formulary['formulary_id']}", "code": f"RX-FRM-{formulary['formulary_id']}", "fit": rating,
                     "fit_reason": reason})
    counts = {rating: sum(r["fit"] == rating for r in rows) for rating in ORDER}
    return {"doc_id": extraction["doc_id"], "fields": rows, "summary": counts}
