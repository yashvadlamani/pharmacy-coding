"""Score extracted fields against the values published in the CMS Exchange Public Use Files."""
import csv
import re
from collections import defaultdict

from . import config, store
from .fields import AMOUNT, FIELDS, FLAG

GOLDEN = config.DATA / "golden" / "2026"

# field -> BenefitName in the Benefits and Cost Sharing file (retail, in-network)
BENEFIT_NAMES = {
    "generic_retail": "Generic Drugs",
    "preferred_brand_retail": "Preferred Brand Drugs",
    "nonpreferred_brand_retail": "Non-Preferred Brand Drugs",
    "specialty_retail": "Specialty Drugs",
}
# field -> (column saying whether drug and medical accumulators are integrated, column suffix) in the Plan
# Attributes file. Integrated plans report one figure under TEHB (total); the others report the medical
# accumulator under MEHB and the drug accumulator under DEHB.
OVERALL_COLUMNS = {
    "overall_deductible_individual": ("MedicalDrugDeductiblesIntegrated", "DedInnTier1Individual"),
    "overall_deductible_family": ("MedicalDrugDeductiblesIntegrated", "DedInnTier1FamilyPerGroup"),
    "oop_max_individual": ("MedicalDrugMaximumOutofPocketIntegrated", "InnTier1IndividualMOOP"),
    "oop_max_family": ("MedicalDrugMaximumOutofPocketIntegrated", "InnTier1FamilyPerGroupMOOP"),
}
SEPARATE_COLUMNS = {"rx_deductible_individual": "DEHBDedInnTier1Individual",
                    "rx_deductible_family": "DEHBDedInnTier1FamilyPerGroup"}


def _dollars(text):
    """Dollar figure in a published value such as "$1,500" or "$3000 per group"; None when there is none."""
    match = re.search(r"\$\s*([\d,]+(?:\.\d+)?)", text or "")
    return float(match.group(1).replace(",", "")) if match else None


def _percent(text):
    match = re.search(r"([\d.]+)\s*%", text or "")
    return float(match.group(1)) if match else None


def golden_plan(plan_id):
    """Expected value per field for the plan's standard on-exchange variant. A plan with no separate
    pharmacy deductible is published as integrated, blank or $0; all are scored as $0."""
    variant = f"{plan_id}-01"
    with open(GOLDEN / "plan-attributes.csv", encoding="utf-8") as f:
        attributes = next(r for r in csv.DictReader(f) if r["PlanId"] == variant)
    with open(GOLDEN / "benefits-and-cost-sharing.csv", encoding="utf-8") as f:
        benefits = {r["BenefitName"]: r for r in csv.DictReader(f) if r["PlanId"] == variant}

    expected = {}
    for field, (integrated_column, column) in OVERALL_COLUMNS.items():
        integrated = attributes[integrated_column] == "Yes"
        value = _dollars(attributes[("TEHB" if integrated else "MEHB") + column])
        if value is None:
            value = _dollars(attributes[("MEHB" if integrated else "TEHB") + column])
        expected[field] = ("amount", value)
    for field, column in SEPARATE_COLUMNS.items():
        integrated = attributes["MedicalDrugDeductiblesIntegrated"] == "Yes"
        expected[field] = ("amount", 0.0 if integrated else _dollars(attributes[column]) or 0.0)
    if _dollars(attributes["SpecialtyDrugMaximumCoinsurance"]) is not None:
        expected["specialty_max_per_fill"] = ("amount", _dollars(attributes["SpecialtyDrugMaximumCoinsurance"]))
    for field, name in BENEFIT_NAMES.items():
        row = benefits.get(name)
        if row is None:
            continue
        if row["IsCovered"] != "Covered":
            expected[field] = ("not_covered",)
        else:
            expected[field] = ("cost_share", _dollars(row["CopayInnTier1"]) or 0.0, _percent(row["CoinsInnTier1"]) or 0.0)
    return expected


def actual_value(item):
    """Extracted field in the same shape as the golden value."""
    if item["kind"] == FLAG:
        return ("flag", item["flag"] if item["status"] == "value" else None)
    if item["kind"] == AMOUNT:
        if item["status"] == "value":
            return ("amount", float(item["amount"]))
        no_deductible = item["status"] == "not_applicable" and item["field"].startswith("rx_deductible")
        return ("amount", 0.0 if no_deductible else None)
    if item["status"] == "not_covered":
        return ("not_covered",)
    return ("cost_share", float(item["copay"] or 0), float(item["coinsurance_pct"] or 0))


def score(plan_ids, complexity):
    """Compare every extracted plan with its golden values. Returns (rows, mismatches, citation stats)."""
    rows, mismatches = [], []
    cited = total_values = 0
    for plan_id in plan_ids:
        extraction = store.read_json(f"extracted/{plan_id}.json")
        if extraction is None:
            continue
        expected = golden_plan(plan_id)
        for item in extraction["fields"]:
            if item["status"] != "not_found":
                total_values += 1
                cited += item["citation_valid"]
            if item["field"] not in expected:
                continue
            want, got = expected[item["field"]], actual_value(item)
            correct = want == got
            rows.append({"plan": plan_id, "field": item["field"], "complexity": complexity[plan_id],
                         "correct": correct, "needs_review": item["needs_review"]})
            if not correct:
                mismatches.append({"plan": plan_id, "field": item["field"], "expected": want, "extracted": got,
                                   "quote": item["quote"], "confidence": item["confidence"]})
    return rows, mismatches, (cited, total_values)


def _pct(rows):
    return f"{100 * sum(r['correct'] for r in rows) / len(rows):.1f}%" if rows else "n/a"


def _show(value):
    if value[0] == "flag":
        return {True: "yes", False: "no", None: "not stated"}[value[1]]
    if value[0] == "amount":
        return "not stated" if value[1] is None else f"${value[1]:,.0f}"
    if value[0] == "not_covered":
        return "not covered"
    parts = ([f"${value[1]:,.0f} copay"] if value[1] else []) + ([f"{value[2]:g}%"] if value[2] else [])
    return " + ".join(parts) or "no charge"


def report(plan_ids, complexity):
    """Build the accuracy report as markdown."""
    rows, mismatches, (cited, total_values) = score(plan_ids, complexity)
    plans = sorted({r["plan"] for r in rows})
    by_field, by_plan = defaultdict(list), defaultdict(list)
    for r in rows:
        by_field[r["field"]].append(r)
        by_plan[r["plan"]].append(r)
    flagged_wrong = sum(1 for r in rows if not r["correct"] and r["needs_review"])
    wrong = sum(1 for r in rows if not r["correct"])
    unscored = [f.name for f in FIELDS if f.name not in by_field]

    out = ["# Extraction accuracy report", "",
           f"Scored {len(rows)} plan-level fields across {len(plans)} plans against the values published in the CMS "
           "Exchange Public Use Files (plan year 2026). Fields with no published value are not scored: "
           + ", ".join(f"`{name}`" for name in unscored) + ".", "",
           "Drug-level data (tier, prior authorization, step therapy, quantity limit) is taken directly from the "
           "insurers' machine-readable formulary files in this draft, so it is not an extraction result and is "
           "not scored here.", "",
           "## Summary", "", "| Measure | Result |", "| --- | --- |",
           f"| Field accuracy, all plans | {_pct(rows)} |",
           f"| Field accuracy, simple plans | {_pct([r for r in rows if r['complexity'] == 'simple'])} |",
           f"| Field accuracy, moderate plans | {_pct([r for r in rows if r['complexity'] == 'moderate'])} |",
           f"| Extracted values with a citation found in the document | {cited} of {total_values} |",
           f"| Plans with every scored field correct | {sum(all(r['correct'] for r in v) for v in by_plan.values())} of {len(plans)} |",
           f"| Wrong fields that were flagged for confirmation | {flagged_wrong} of {wrong} |",
           "", "## Accuracy by field", "", "| Field | Correct | Accuracy |", "| --- | --- | --- |"]
    for f in FIELDS:
        if f.name in by_field:
            group = by_field[f.name]
            out.append(f"| {f.name} | {sum(r['correct'] for r in group)} of {len(group)} | {_pct(group)} |")
    out += ["", "## Accuracy by plan", "", "| Plan | Complexity | Correct | Accuracy |", "| --- | --- | --- | --- |"]
    for plan in plans:
        group = by_plan[plan]
        out.append(f"| {plan} | {complexity[plan]} | {sum(r['correct'] for r in group)} of {len(group)} | {_pct(group)} |")
    out += ["", "## Mismatches", "", "| Plan | Field | Published value | Extracted | Confidence | Cited passage |",
            "| --- | --- | --- | --- | --- | --- |"]
    for m in mismatches:
        quote = re.sub(r"\s+", " ", m["quote"]).replace("|", "/")[:90]
        out.append(f"| {m['plan']} | {m['field']} | {_show(m['expected'])} | {_show(m['extracted'])} | "
                   f"{m['confidence']:.2f} | {quote} |")
    return "\n".join(out) + "\n"
