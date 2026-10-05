"""Drug-level layer. Formularies come from the machine-readable drug files that exchange insurers publish
(one entry per RxNorm drug with its tier and prior authorization, step therapy and quantity limit flags).

Each formulary is stored once in Azure Blob Storage as formulary/<formulary id>.json:
  {"formulary_id", "issuer", "tiers": {label: {"rank", "class", "display"}}, "warnings": [text, ...],
   "drugs": [[rxcui, name, tier label, prior_auth, step_therapy, quantity_limit], ...]}
"""
import json
import re
from functools import lru_cache

from . import store
from .fields import GENERIC, NON_PREFERRED, PREFERRED, SPECIALTY

PREVENTIVE = "preventive"
CLASS_ORDER = [PREVENTIVE, GENERIC, PREFERRED, NON_PREFERRED, SPECIALTY]
CLASS_LABEL = {PREVENTIVE: "$0 preventive", GENERIC: "Generic", PREFERRED: "Preferred brand",
               NON_PREFERRED: "Non-preferred brand", SPECIALTY: "Specialty"}
NUMBER_WORDS = {"ONE": 1, "TWO": 2, "THREE": 3, "FOUR": 4, "FIVE": 5, "SIX": 6, "SEVEN": 7}
PREVENTIVE_PA_LIMIT = 0.25  # a $0 preventive list where more drugs than this need prior authorization is suspect


def _tier_number(label):
    match = re.match(r"TIER-([A-Z]+)", label)
    return NUMBER_WORDS.get(match.group(1)) if match else None


def tier_class(label, tier_count=4):
    """The drug class a tier label stands for. Numbered tiers follow the usual layouts: up to four tiers are
    generic, preferred brand, non-preferred brand, specialty; five or six put two generic tiers first."""
    number = _tier_number(label)
    if number:
        if tier_count <= 4:
            return [GENERIC, PREFERRED, NON_PREFERRED, SPECIALTY][min(number, 4) - 1]
        return {1: GENERIC, 2: GENERIC, 3: PREFERRED, 4: NON_PREFERRED}.get(number, SPECIALTY)
    if "ZERO" in label or "PREVENTIVE" in label:
        return PREVENTIVE
    if "SPECIALTY" in label:
        return SPECIALTY
    if "NON-PREFERRED-BRAND" in label:
        return NON_PREFERRED
    if "BRAND" in label:
        return PREFERRED
    return GENERIC


def describe_tiers(labels):
    """{label: {"rank", "class", "display"}} for the tier labels one formulary uses."""
    numbers = [n for n in map(_tier_number, labels) if n]
    count = max(numbers) if numbers else len(labels)
    tiers = {}
    for label in labels:
        number, cls = _tier_number(label), tier_class(label, count)
        display = f"Tier {number}" if number else label.replace("-", " ").capitalize()
        tiers[label] = {"rank": number or CLASS_ORDER.index(cls), "class": cls, "display": display}
    return dict(sorted(tiers.items(), key=lambda tier: tier[1]["rank"]))


def warnings(tiers, drugs):
    """Signs that a published drug file's tier labels cannot be taken at face value."""
    out = []
    for label, tier in tiers.items():
        listed = [d for d in drugs if d[2] == label]
        share = sum(d[3] for d in listed) / len(listed) if listed else 0
        if tier["class"] == PREVENTIVE and share > PREVENTIVE_PA_LIMIT:
            out.append(f"The insurer's published file lists {len(listed):,} drugs under \"{tier['display']}\", and "
                       f"{share:.0%} of them need prior authorization. A $0 preventive list rarely does, so the tier "
                       "labels in this file look unreliable. Confirm tiers against the insurer's printed formulary.")
    return out


def build(drug_file, plan_id, formulary_id, issuer):
    """Compact formulary for one plan from an insurer's machine-readable drug file."""
    with open(drug_file, encoding="utf-8-sig") as f:
        entries = json.load(f)
    drugs = []
    for entry in entries:
        for plan in entry.get("plans", []):
            if plan.get("plan_id") == plan_id:
                drugs.append([str(entry["rxnorm_id"]), re.sub(r"\s+", " ", entry["drug_name"]).strip(),
                              plan["drug_tier"], bool(plan.get("prior_authorization")),
                              bool(plan.get("step_therapy")), bool(plan.get("quantity_limit"))])
                break
    drugs.sort(key=lambda d: d[1].lower())
    tiers = describe_tiers(sorted({d[2] for d in drugs}))
    return {"formulary_id": formulary_id, "issuer": issuer, "source_plan": plan_id, "tiers": tiers,
            "warnings": warnings(tiers, drugs), "drugs": drugs}


@lru_cache(maxsize=32)
def load(formulary_id):
    return store.read_json(f"formulary/{formulary_id}.json")


def _row(formulary, drug):
    rxcui, name, label, pa, st, ql = drug
    tier = formulary["tiers"][label]
    return {"rxcui": rxcui, "name": name, "tier": tier["display"], "rank": tier["rank"], "class": tier["class"],
            "class_label": CLASS_LABEL[tier["class"]], "pa": pa, "st": st, "ql": ql}


def search(formulary, text, limit=60):
    """Formulary entries whose name contains every word typed."""
    words = text.lower().split()
    hits = [d for d in formulary["drugs"] if words and all(w in d[1].lower() for w in words)]
    return [_row(formulary, d) for d in hits[:limit]], len(hits)


def status(formulary, rxcuis):
    """How a formulary treats a drug given as a set of RxNorm ids (all strengths and forms).

    The entry on the lowest tier, with the fewest restrictions, represents the drug. Returns None when
    none of the ids is on the formulary.
    """
    wanted = set(rxcuis)
    rows = [_row(formulary, d) for d in formulary["drugs"] if d[0] in wanted]
    if not rows:
        return None
    best = min(rows, key=lambda r: (CLASS_ORDER.index(r["class"]), r["rank"], r["pa"] + r["st"] + r["ql"]))
    return {**best, "entries": len(rows)}


def restrictions(row):
    names = [text for key, text in (("pa", "prior authorization"), ("st", "step therapy"), ("ql", "quantity limit"))
             if row[key]]
    return ", ".join(names)


def disruption(current, proposed, drugs):
    """Compare two formularies on a list of commonly used drugs: [{"name", "rxcuis", "claims"}, ...].

    Returns one row per drug that is on at least one of them, with what changes for a member who moves from
    the current formulary to the proposed one. impact is "worse" (loses coverage, moves to a costlier class,
    gains prior authorization or step therapy), "limit" (only gains a quantity limit), "better" or "same".
    """
    rows = []
    for drug in drugs:
        a, b = status(current, drug["rxcuis"]), status(proposed, drug["rxcuis"])
        if a is None and b is None:
            continue
        changes, impact = [], "same"
        if a and not b:
            changes, impact = ["Not on the proposed formulary"], "worse"
        elif b and not a:
            changes, impact = ["Newly covered"], "better"
        else:
            move = CLASS_ORDER.index(b["class"]) - CLASS_ORDER.index(a["class"])
            if move:
                changes.append(f"{a['class_label']} to {b['class_label']}")
                impact = "worse" if move > 0 else "better"
            for key, text in (("pa", "prior authorization"), ("st", "step therapy"), ("ql", "quantity limit")):
                if b[key] and not a[key]:
                    changes.append(f"Adds {text}")
                    impact = "limit" if key == "ql" and impact in ("same", "limit") else "worse"
                elif a[key] and not b[key]:
                    changes.append(f"Removes {text}")
                    impact = "better" if impact == "same" else impact
        rows.append({"name": drug["name"], "claims": drug.get("claims", 0), "current": a, "proposed": b,
                     "changes": changes, "impact": impact})
    return rows
