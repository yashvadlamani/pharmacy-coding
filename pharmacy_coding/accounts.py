"""Accounts and the plans attached to them, as the sales team sees them.

The prototype has no real accounts, so accounts.csv holds fictional ones that group the public plans.
"""
import csv

from . import config
from .tables import CLIENT, CODER

# Where a plan stands, listed from most to least in need of the rep's attention.
RETURNED = "Returned by coding"
BLOCKED = "Needs client answer"
READY = "Ready to confirm"
WITH_CODING = "With coding"
APPROVED = "Approved for load"
ORDER = [RETURNED, BLOCKED, READY, WITH_CODING, APPROVED]

# The plan summary a rep reads: (heading, [field, ...]) in the order a client would ask about them.
SUMMARY_SECTIONS = [
    ("Deductibles and out-of-pocket limit", ["overall_deductible_individual", "overall_deductible_family",
                                             "rx_deductible_individual", "rx_deductible_family",
                                             "oop_max_individual", "oop_max_family"]),
    ("What members pay at retail", ["generic_retail", "preferred_brand_retail", "nonpreferred_brand_retail",
                                    "specialty_retail", "specialty_max_per_fill", "retail_days_supply"]),
    ("Mail order", ["mail_order_available", "generic_mail", "preferred_brand_mail", "nonpreferred_brand_mail",
                    "mail_days_supply"]),
    ("Rules", ["specialty_pharmacy_required", "prior_auth_drugs"]),
]


def load(path=None):
    """{account_id: account} with each account's plans in file order as [{"plan_id", "role"}]."""
    accounts = {}
    with open(path or config.PACKAGE / "accounts.csv", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            account = accounts.setdefault(row["account_id"], {
                "account_id": row["account_id"], "name": row["account_name"], "state": row["state"],
                "employees": int(row["employees"]), "sales_rep": row["sales_rep"], "stage": row["stage"],
                "effective_date": row["effective_date"], "plans": []})
            account["plans"].append({"plan_id": row["plan_id"], "role": row["role"]})
    return accounts


def account_of(plan_id, accounts=None):
    """The account a plan belongs to, or None."""
    return next((a for a in (accounts or load()).values() if any(p["plan_id"] == plan_id for p in a["plans"])), None)


def open_questions(questions, answers):
    """Questions the rep has not recorded an answer to."""
    return [q for q in questions if q["id"] not in answers]


def plan_status(signoffs, blocking_open):
    """signoffs is {kind: row} for the plan; blocking_open the number of unanswered blocking questions."""
    coder, client = (signoffs.get(CODER) or {}).get("action"), (signoffs.get(CLIENT) or {}).get("action")
    if client == "confirm":
        if coder == "approve":
            return APPROVED
        if coder == "return":
            return RETURNED
        return WITH_CODING
    return BLOCKED if blocking_open else READY


def rollup(statuses):
    """An account is only as far along as its least advanced plan."""
    return min(statuses, key=ORDER.index) if statuses else READY
