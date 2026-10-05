"""Unit tests for the rule-based parts of the pipeline. None of them makes a network call."""
from pharmacy_coding import accounts, fit, formulary, validate
from pharmacy_coding.extract import verify_citation
from pharmacy_coding.fields import BY_NAME, FIELDS, describe


def item(name, status="value", **values):
    base = {"field": name, "kind": BY_NAME[name].kind, "status": status, "amount": None, "copay": None,
            "coinsurance_pct": None, "deductible_applies": None, "flag": None, "quote": "", "page": 1,
            "confidence": 0.95, "note": "", "citation_valid": True, "needs_review": False}
    return {**base, **values}


def plan(**overrides):
    """A complete plan where every field is not stated unless overridden."""
    fields = {f.name: item(f.name, "not_found", citation_valid=False, needs_review=True) for f in FIELDS}
    fields.update(overrides)
    return fields


DRUGS = {
    "formulary_id": "TEST1",
    "tiers": formulary.describe_tiers(["TIER-ONE", "TIER-TWO", "TIER-THREE", "TIER-FOUR"]),
    "drugs": [["1", "atorvastatin 20 MG Oral Tablet", "TIER-ONE", False, False, False],
              ["2", "atorvastatin 40 MG Oral Tablet", "TIER-TWO", False, False, True],
              ["3", "apixaban 5 MG Oral Tablet [Eliquis]", "TIER-TWO", False, False, False],
              ["4", "semaglutide Pen Injector [Ozempic]", "TIER-THREE", True, False, True]],
}


def test_describe_puts_values_in_plain_words():
    assert describe(item("generic_retail", copay=10, deductible_applies=False)) == "$10 copay, deductible does not apply"
    assert describe(item("specialty_retail", coinsurance_pct=40, deductible_applies=True)) == "40% coinsurance, after deductible"
    assert describe(item("rx_deductible_individual", "not_applicable")) == "None"
    assert describe(item("mail_days_supply", amount=90)) == "90 days"


def test_citation_must_be_in_the_document_and_numbers_must_match():
    pages = [{"page": 2, "text": "Generic drugs\nRetail: $10 copayment/prescription"}]
    assert verify_citation("Generic drugs ... $10 copayment/prescription", 2, pages) == (True, 2)
    assert verify_citation("Generic drugs ... $15 copayment/prescription", 2, pages)[0] is False


def test_numbered_tiers_map_to_drug_classes_by_tier_count():
    assert [formulary.tier_class(f"TIER-{n}", 4) for n in ("ONE", "TWO", "THREE", "FOUR")] == \
        ["generic", "preferred_brand", "nonpreferred_brand", "specialty"]
    assert formulary.tier_class("TIER-TWO", 6) == "generic" and formulary.tier_class("TIER-SIX", 6) == "specialty"


def test_named_tiers_map_to_drug_classes():
    assert formulary.tier_class("ZERO-COST-SHARE-PREVENTIVE-DRUGS") == "preventive"
    assert formulary.tier_class("NON-PREFERRED-GENERIC-AND-PREFERRED-BRAND") == "preferred_brand"
    assert formulary.tier_class("NON-PREFERRED-GENERIC-AND-NON-PREFERRED-BRAND") == "nonpreferred_brand"
    assert formulary.tier_class("SPECIALTY-DRUGS") == "specialty"


def test_a_preventive_tier_full_of_prior_authorization_is_flagged():
    tiers = formulary.describe_tiers(["ZERO-COST-SHARE-PREVENTIVE-DRUGS", "PREFERRED-GENERIC"])
    suspect = [["1", "etanercept", "ZERO-COST-SHARE-PREVENTIVE-DRUGS", True, False, False],
               ["2", "atorvastatin", "PREFERRED-GENERIC", False, False, False]]
    assert len(formulary.warnings(tiers, suspect)) == 1
    plausible = [["1", "aspirin", "ZERO-COST-SHARE-PREVENTIVE-DRUGS", False, False, False]]
    assert formulary.warnings(tiers, plausible) == []


def test_a_drug_is_represented_by_its_lowest_tier_entry():
    found = formulary.status(DRUGS, ["1", "2"])
    assert (found["tier"], found["class"], found["ql"], found["entries"]) == ("Tier 1", "generic", False, 2)
    assert formulary.status(DRUGS, ["999"]) is None


def test_search_matches_every_word():
    rows, total = formulary.search(DRUGS, "atorvastatin 40")
    assert total == 1 and rows[0]["rxcui"] == "2"


def test_disruption_separates_serious_changes_from_quantity_limits():
    proposed = {**DRUGS, "drugs": [["1", "atorvastatin 20 MG Oral Tablet", "TIER-ONE", False, False, True],
                                   ["3", "apixaban 5 MG Oral Tablet [Eliquis]", "TIER-THREE", False, False, False]]}
    drugs = [{"name": "Atorvastatin", "rxcuis": ["1"]}, {"name": "Apixaban", "rxcuis": ["3"]},
             {"name": "Semaglutide", "rxcuis": ["4"]}, {"name": "Unlisted", "rxcuis": ["999"]}]
    rows = {r["name"]: r for r in formulary.disruption(DRUGS, proposed, drugs)}
    assert rows["Atorvastatin"]["impact"] == "limit"
    assert rows["Apixaban"]["impact"] == "worse" and "Preferred brand to Non-preferred brand" in rows["Apixaban"]["changes"]
    assert rows["Semaglutide"]["changes"] == ["Not on the proposed formulary"]
    assert "Unlisted" not in rows


def test_fit_ratings():
    fields = plan(generic_retail=item("generic_retail", copay=10),
                  generic_mail=item("generic_mail", copay=25),
                  preferred_brand_retail=item("preferred_brand_retail", copay=65),
                  nonpreferred_brand_retail=item("nonpreferred_brand_retail", copay=250, coinsurance_pct=50),
                  specialty_retail=item("specialty_retail", coinsurance_pct=60))
    assert fit.rate(fields["generic_retail"], fields)[0] == fit.STANDARD
    assert fit.rate(fields["generic_mail"], fields)[0] == fit.STANDARD  # 2.5 times retail
    assert fit.rate(fields["preferred_brand_retail"], fields)[0] == fit.CONFIGURABLE
    assert fit.rate(fields["nonpreferred_brand_retail"], fields)[0] == fit.CUSTOM
    assert fit.rate(fields["specialty_retail"], fields)[0] == fit.NOT_SUPPORTED
    assert fit.rate(fields["mail_days_supply"], fields)[0] == fit.UNCLEAR


def test_placeholder_codes():
    assert fit.code(item("generic_retail", copay=10, deductible_applies=True)) == "RX-GEN-R30-CP0010-AD"
    assert fit.code(item("specialty_retail", coinsurance_pct=40)) == "RX-SPC-R30-CI040"
    assert fit.code(item("overall_deductible_individual", amount=1500)) == "RX-DED-IND-01500"
    assert fit.code(item("mail_days_supply", "not_found")) is None


def test_drugs_after_the_deductible_need_a_shared_accumulator_unless_there_is_a_pharmacy_deductible():
    shared = plan(generic_retail=item("generic_retail", copay=10, deductible_applies=True))
    assert fit.shares_medical_deductible(shared)
    own = plan(generic_retail=item("generic_retail", copay=10, deductible_applies=True),
               rx_deductible_individual=item("rx_deductible_individual", amount=250))
    assert not fit.shares_medical_deductible(own)


def test_price_applies_deductible_then_copay_then_capped_coinsurance():
    copay = item("preferred_brand_retail", copay=40, deductible_applies=True)
    assert validate.price(copay, 500, 300)[0] == 340
    assert validate.price(copay, 500, 0)[0] == 40
    assert validate.price(copay, 20, 0)[0] == 20  # the drug costs less than the copay
    specialty = item("specialty_retail", coinsurance_pct=50, deductible_applies=False)
    assert validate.price(specialty, 6000, 1000, max_per_fill=650)[0] == 650
    assert validate.price(item("generic_mail", "not_found"), 30, 0)[0] is None


def test_member_costs_follow_the_formulary():
    fields = plan(overall_deductible_individual=item("overall_deductible_individual", amount=1000),
                  generic_retail=item("generic_retail", copay=10, deductible_applies=False),
                  nonpreferred_brand_retail=item("nonpreferred_brand_retail", copay=80, deductible_applies=True))
    scenarios = [{"id": "g", "label": "Generic", "channel": "retail", "quantity": "30"},
                 {"id": "o", "label": "Ozempic", "channel": "retail", "quantity": "3"},
                 {"id": "h", "label": "Humira", "channel": "retail", "quantity": "2"}]
    prices = {"g": {"rxcuis": ["1"], "unit_price": 0.5, "price_source": "test"},
              "o": {"rxcuis": ["4"], "unit_price": 300, "price_source": "test"},
              "h": {"rxcuis": ["999"], "unit_price": 3000, "price_source": "test"}}
    generic, ozempic, humira = validate.member_costs(fields, DRUGS, scenarios, prices)
    assert (generic["first_fill"], generic["after_deductible"]) == (10, 10)
    assert (ozempic["first_fill"], ozempic["after_deductible"]) == (900, 80) and "75" in ozempic["notes"][0]
    assert humira["reject"].startswith("70") and humira["first_fill"] == 6000


def test_consistency_rules():
    fields = plan(overall_deductible_individual=item("overall_deductible_individual", amount=3000),
                  overall_deductible_family=item("overall_deductible_family", amount=2000),
                  oop_max_individual=item("oop_max_individual", amount=12000))
    checks = {(c["check"], c["field"], c["status"]) for c in validate.consistency(fields)}
    assert ("consistency", "overall_deductible_family", "fail") in checks
    assert ("aca_limit", "oop_max_individual", "warn") in checks


def test_validate_raises_conflicts_missing_items_and_custom_designs_as_questions():
    fields = plan(generic_retail=item("generic_retail", copay=10, quote="Generic drugs $10 copay"),
                  nonpreferred_brand_retail=item("nonpreferred_brand_retail", copay=250, coinsurance_pct=50,
                                                 quote="$250 copay then 50%"))
    extraction = {"doc_id": "P1", "fields": list(fields.values())}
    coded = fit.map_plan(extraction, DRUGS)
    intake = {"generic_retail": {"client_value": "$15 copay", "copay": "15", "coinsurance_pct": "", "amount": ""}}
    result = validate.validate(extraction, coded, DRUGS, {}, intake, scenarios=[])
    by_id = {q["id"]: q for q in result["questions"]}
    assert by_id["conflict:generic_retail"]["blocking"] and "$15 copay" in by_id["conflict:generic_retail"]["text"]
    assert "missing:mail_days_supply" in by_id and "fit:nonpreferred_brand_retail" in by_id
    assert "missing:specialty_max_per_fill" not in by_id  # no cap is a normal answer, not a gap
    assert result["summary"]["blocking"] == 1 and result["summary"]["failed"] == 1


def test_plan_status_and_account_rollup():
    confirm, approve = {"client": {"action": "confirm"}}, {"client": {"action": "confirm"}, "coder": {"action": "approve"}}
    assert accounts.plan_status({}, 2) == accounts.BLOCKED
    assert accounts.plan_status({}, 0) == accounts.READY
    assert accounts.plan_status(confirm, 0) == accounts.WITH_CODING
    assert accounts.plan_status(approve, 0) == accounts.APPROVED
    assert accounts.plan_status({"client": {"action": "reopen"}, "coder": {"action": "approve"}}, 0) == accounts.READY
    assert accounts.rollup([accounts.APPROVED, accounts.BLOCKED]) == accounts.BLOCKED


def test_every_account_plan_is_pinned():
    with open("ingest/plans.csv", encoding="utf-8") as f:
        pinned = {line.split(",")[0] for line in f.read().splitlines()[1:]}
    listed = [p["plan_id"] for a in accounts.load().values() for p in a["plans"]]
    assert set(listed) == pinned and len(listed) == len(pinned)
