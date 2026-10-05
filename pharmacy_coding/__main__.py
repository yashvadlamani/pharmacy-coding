"""Command line for the prototype pipeline.

    python -m pharmacy_coding formularies          # build each plan's drug-level formulary from the public drug files
    python -m pharmacy_coding run                  # ingest, extract, fit-check and validate all pinned plans
    python -m pharmacy_coding run --plan <id>      # one plan
    python -m pharmacy_coding run --skip-existing  # reuse saved extractions; redo the fit check and validation
    python -m pharmacy_coding evaluate             # accuracy report against the published values
"""
import argparse
import csv
import json
from concurrent.futures import ThreadPoolExecutor

from . import config, evaluate, extract, fit, formulary, ingest, store, validate


def pinned_plans():
    """{plan_id: row} from the golden dataset's selected-plans.csv."""
    with open(evaluate.GOLDEN / "selected-plans.csv", encoding="utf-8") as f:
        return {r["StandardComponentId"]: r for r in csv.DictReader(f)}


def build_formularies(plans):
    """One compact formulary per FormularyId, plus the reference drug lists, into Blob Storage."""
    done = set()
    for plan_id, row in plans.items():
        if row["FormularyId"] in done:
            continue
        done.add(row["FormularyId"])
        built = formulary.build(config.DATA / row["drug_file"], plan_id, row["FormularyId"],
                                row["IssuerMarketPlaceMarketingName"])
        store.write_json(f"formulary/{row['FormularyId']}.json", built)
        print(f"{row['FormularyId']}: {len(built['drugs'])} drugs, tiers "
              + ", ".join(f"{t['display']}={t['class']}" for t in built["tiers"].values()))
    for name in ("top-drugs", "scenario-drugs"):
        text = (config.DATA / f"reference/{name}.json").read_text(encoding="utf-8")
        store.write_json(f"reference/{name}.json", json.loads(text))


def run_document(path, doc_id, skip_existing=False):
    """Steps 1 and 2 for one document."""
    existing = store.read_json(f"extracted/{doc_id}.json") if skip_existing else None
    if existing:
        return existing
    document = ingest.ingest(path, doc_id)
    ingest.save(document)
    extraction = extract.extract(document)
    extract.save(extraction)
    return extraction


def finish_plan(extraction, row, scenario_drugs, intake):
    """Steps 3 and 4 for one plan; returns its line in the index the workspace lists plans from."""
    plan_id = extraction["doc_id"]
    drugs = formulary.load(row["FormularyId"])
    coded = fit.map_plan(extraction, drugs)
    store.write_json(f"coded/{plan_id}.json", coded)
    result = validate.validate(extraction, coded, drugs, scenario_drugs, intake.get(plan_id))
    store.write_json(f"validated/{plan_id}.json", result)
    return {"plan_id": plan_id, "issuer": row["IssuerMarketPlaceMarketingName"], "state": row["StateCode"],
            "plan_name": row["PlanMarketingName"], "metal": row["MetalLevel"], "complexity": row["complexity"],
            "formulary_id": row["FormularyId"], "question_ids": [q["id"] for q in result["questions"]],
            "blocking_ids": [q["id"] for q in result["questions"] if q["blocking"]], **result["summary"]}


def main():
    parser = argparse.ArgumentParser(prog="pharmacy_coding", description=__doc__.splitlines()[0])
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("formularies", help="build the drug-level formularies")
    run = commands.add_parser("run", help="ingest, extract, fit-check and validate plans")
    run.add_argument("--plan", help="a plan id from the pinned set")
    run.add_argument("--skip-existing", action="store_true", help="reuse saved extractions")
    run.add_argument("--workers", type=int, default=5)
    commands.add_parser("evaluate", help="write the accuracy report")
    args = parser.parse_args()

    plans = pinned_plans()
    if args.command == "formularies":
        build_formularies(plans)
        return
    if args.command == "evaluate":
        text = evaluate.report(list(plans), {p: r["complexity"] for p, r in plans.items()})
        out = config.ROOT / "docs" / "accuracy-report.md"
        out.write_text(text, encoding="utf-8", newline="\n")
        print(text.split("## Accuracy by plan")[0])
        print(f"Full report: {out}")
        return

    chosen = [args.plan] if args.plan else list(plans)
    jobs = [(config.DATA / plans[p]["sbc_path"], p) for p in chosen]
    with ThreadPoolExecutor(args.workers) as pool:
        extractions = list(pool.map(lambda job: run_document(*job, skip_existing=args.skip_existing), jobs))

    scenario_drugs, intake = store.read_json("reference/scenario-drugs.json"), validate.load_intake()
    index = {p["plan_id"]: p for p in store.read_json("index.json", [])}
    for extraction in extractions:
        line = finish_plan(extraction, plans[extraction["doc_id"]], scenario_drugs, intake)
        index[line["plan_id"]] = line
        print(f"{line['plan_id']}: {line['questions']} questions ({line['blocking']} blocking), "
              f"{line['failed']} failed checks, fit " + ", ".join(f"{k} {v}" for k, v in line["fit"].items() if v))
    store.write_json("index.json", sorted(index.values(), key=lambda p: p["plan_id"]))


if __name__ == "__main__":
    main()
