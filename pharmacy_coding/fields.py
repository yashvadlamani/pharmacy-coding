"""The pharmacy plan-level fields the prototype reads for every plan."""
from dataclasses import dataclass

AMOUNT = "amount"          # a dollar figure: deductible, out-of-pocket limit, per-fill maximum
COST_SHARE = "cost_share"  # what the member pays for a fill: copay and/or coinsurance
FLAG = "flag"              # yes/no
NUMBER = "number"          # a count of days

GENERIC, PREFERRED, NON_PREFERRED, SPECIALTY = "generic", "preferred_brand", "nonpreferred_brand", "specialty"


@dataclass(frozen=True)
class Field:
    name: str
    kind: str
    code: str         # short code used to build placeholder platform codes
    label: str        # what a rep sees
    description: str  # what the model is asked for


FIELDS = [
    Field("overall_deductible_individual", AMOUNT, "DED-IND", "Overall deductible, individual",
          "The plan's overall in-network deductible, individual"),
    Field("overall_deductible_family", AMOUNT, "DED-FAM", "Overall deductible, family",
          "The plan's overall in-network deductible, family"),
    Field("rx_deductible_individual", AMOUNT, "RXD-IND", "Separate pharmacy deductible, individual",
          "A deductible that applies only to prescription drugs, individual; not the overall deductible"),
    Field("rx_deductible_family", AMOUNT, "RXD-FAM", "Separate pharmacy deductible, family",
          "A deductible that applies only to prescription drugs, family; not the overall deductible"),
    Field("oop_max_individual", AMOUNT, "OOP-IND", "Out-of-pocket limit, individual",
          "In-network out-of-pocket limit that prescription drug costs count toward, individual"),
    Field("oop_max_family", AMOUNT, "OOP-FAM", "Out-of-pocket limit, family",
          "In-network out-of-pocket limit that prescription drug costs count toward, family"),
    Field("generic_retail", COST_SHARE, "GEN-R30", "Generic, retail 30-day", "Generic drugs at a retail pharmacy"),
    Field("preferred_brand_retail", COST_SHARE, "PBR-R30", "Preferred brand, retail 30-day",
          "Preferred brand drugs at a retail pharmacy"),
    Field("nonpreferred_brand_retail", COST_SHARE, "NPB-R30", "Non-preferred brand, retail 30-day",
          "Non-preferred brand drugs at a retail pharmacy"),
    Field("specialty_retail", COST_SHARE, "SPC-R30", "Specialty, 30-day", "Specialty drugs"),
    Field("generic_mail", COST_SHARE, "GEN-M90", "Generic, mail order", "Generic drugs by mail order"),
    Field("preferred_brand_mail", COST_SHARE, "PBR-M90", "Preferred brand, mail order",
          "Preferred brand drugs by mail order"),
    Field("nonpreferred_brand_mail", COST_SHARE, "NPB-M90", "Non-preferred brand, mail order",
          "Non-preferred brand drugs by mail order"),
    Field("specialty_max_per_fill", AMOUNT, "SPC-MAX", "Specialty maximum per fill",
          "Dollar cap on what the member pays for one specialty prescription (for example 'up to $650')"),
    Field("retail_days_supply", NUMBER, "DS-RTL", "Retail days supply",
          "Largest days supply one retail fill covers at the stated retail cost share"),
    Field("mail_days_supply", NUMBER, "DS-MAIL", "Mail order days supply",
          "Largest days supply one mail order fill covers"),
    Field("mail_order_available", FLAG, "MAIL", "Mail order offered",
          "True when the document describes a mail order (home delivery) benefit"),
    Field("specialty_pharmacy_required", FLAG, "SPC-PHARM", "Specialty drugs must use a specialty pharmacy",
          "True when specialty drugs must be filled through a designated specialty pharmacy"),
    Field("prior_auth_drugs", FLAG, "PA", "Some drugs need prior authorization",
          "True when the document says some prescription drugs require prior authorization or step therapy"),
]
BY_NAME = {f.name: f for f in FIELDS}

# cost-share field that prices a fill, by drug class and channel
RETAIL_FIELD = {GENERIC: "generic_retail", PREFERRED: "preferred_brand_retail",
                NON_PREFERRED: "nonpreferred_brand_retail", SPECIALTY: "specialty_retail"}
MAIL_FIELD = {GENERIC: "generic_mail", PREFERRED: "preferred_brand_mail", NON_PREFERRED: "nonpreferred_brand_mail"}


def describe(item):
    """An extracted field's value in plain words."""
    status = item["status"]
    if status == "not_found":
        return "Not stated"
    if status == "not_applicable":
        return "None" if BY_NAME[item["field"]].kind == AMOUNT else "Not applicable"
    if status == "not_covered":
        return "Not covered"
    if status == "no_charge":
        return "No charge" + (", after deductible" if item.get("deductible_applies") else "")
    kind = BY_NAME[item["field"]].kind
    if kind == AMOUNT:
        return f"${item['amount']:,.0f}"
    if kind == NUMBER:
        return f"{item['amount']:g} days"
    if kind == FLAG:
        return "Yes" if item["flag"] else "No"
    parts = []
    if item["copay"]:
        parts.append(f"${item['copay']:,.0f} copay")
    if item["coinsurance_pct"]:
        parts.append(f"{item['coinsurance_pct']:g}% coinsurance")
    text = " + ".join(parts)
    if item["deductible_applies"] is True:
        text += ", after deductible"
    elif item["deductible_applies"] is False:
        text += ", deductible does not apply"
    return text
