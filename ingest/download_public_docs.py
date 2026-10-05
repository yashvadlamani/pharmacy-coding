"""Download the public prototype data and optionally upload it to Azure Blob Storage.

Usage:
    python ingest/download_public_docs.py                # download into ./data
    python ingest/download_public_docs.py --upload       # also upload to the storage account

The 25 plans are pinned in ingest/plans.csv. Sources:
  CMS Exchange Public Use Files       SBC links and the published cost sharing (the answer key)
  Insurer machine-readable files      drug-level formulary per plan (tier, prior authorization, step therapy,
                                      quantity limit), found through the CMS Machine Readable URL file
  CMS Medicare Part D Spending by Drug  the most commonly dispensed drugs
  NLM RxNav                           RxNorm ids for those drugs
  Medicaid NADAC                      unit prices for the member cost examples
Requires curl, and the Azure CLI (logged in) for --upload.
"""
import argparse
import csv
import datetime
import hashlib
import json
import subprocess
import urllib.parse
import urllib.request
import zipfile
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit

YEAR = "2026"
PUF_BASE = f"https://download.cms.gov/marketplace-puf/{YEAR}"
PUFS = ["plan-attributes-puf", "benefits-and-cost-sharing-puf", "machine-readable-url-puf"]
# Each insurer's drug and plan files, as listed in the index the insurer registers with CMS
# (machine-readable-url-puf). Anthem publishes one drug file per formulary; this one holds the New Hampshire plans.
ISSUERS = {
    "46944": ("al-bcbs-alabama", "https://www.bcbsal.org/cms/data/drugs.json", "https://www.bcbsal.org/cms/data/plans.json"),
    "32225": ("mt-mountain-health-coop",
              "https://cbg.adaptiverx.com/web/json?key=8F02B26A288102C27BAC82D14C006C6FC54D480F80409B68D6FCC2EC70CFBF62",
              "https://rmm.mhc.coop/plans_providers/32225_MT_Plans_2026.json"),
    "57601": ("nh-anthem", "https://fm.formularynavigator.com/jsonFiles/publish/143/37/drugs.json",
              "https://www22.elevancehealth.com/cms/PLANS_NH.json"),
    "96751": ("nh-anthem", "https://fm.formularynavigator.com/jsonFiles/publish/143/37/drugs.json",
              "https://www22.elevancehealth.com/cms/PLANS_NH.json"),
    "38166": ("wi-security-health-plan", "https://shp-web-public.s3.amazonaws.com/PRD/exchange/drugs.json",
              "https://shp-web-public.s3.amazonaws.com/PRD/exchange/plans.json"),
}
SPENDING_URL = ("https://data.cms.gov/sites/default/files/2026-06/98218f98-166c-4723-8438-c344a4ef96a6/"
                "DSD_PTD_RY26_P04_V10_DY24_BGM.csv")
SPENDING_YEAR = "2024"
TOP_DRUGS = 200
RXNAV = "https://rxnav.nlm.nih.gov/REST"
NADAC = "https://data.medicaid.gov/api/1/datastore/query/fbb83258-11c7-47f5-8b18-5f8e79f7e704/0"  # NADAC 2026
STORAGE_ACCOUNT = "pharmcodingf946de69"
CONTAINER = "prototype-docs"
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/126 Safari/537.36"

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
manifest = []


def fetch(url, dest, expect_pdf=True):
    """Download url to dest; returns False if a PDF was expected and something else came back."""
    dest.parent.mkdir(parents=True, exist_ok=True)
    if not dest.exists():
        # some insurers publish links with a mixed-case host that curl fails on; hosts are case-insensitive
        parts = urlsplit(url if "://" in url else "https://" + url)
        url = urlunsplit(parts._replace(netloc=parts.netloc.lower()))
        subprocess.run(["curl", "-sL", "--max-time", "600", "-A", USER_AGENT, "-o", str(dest), url], check=False)
    ok = dest.exists() and dest.stat().st_size > 0 and (not expect_pdf or dest.read_bytes()[:5] == b"%PDF-")
    if not ok:
        dest.unlink(missing_ok=True)
    return ok


def get_json(url):
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(request, timeout=90) as response:
        return json.load(response)


def record(path, kind, source_url, **extra):
    digest = hashlib.sha256()
    with open(DATA / path, "rb") as f:
        while chunk := f.read(1 << 20):
            digest.update(chunk)
    manifest.append({
        "path": path, "kind": kind, "source_url": source_url, "bytes": (DATA / path).stat().st_size,
        "sha256": digest.hexdigest(), "downloaded": datetime.date.today().isoformat(), **extra,
    })


def read_puf(name):
    """Yield the header, then each row, of the CSV inside a downloaded Public Use File zip."""
    with zipfile.ZipFile(DATA / f"raw/cms-puf/{YEAR}/{name}.zip") as z:
        with z.open(z.namelist()[0]) as f:
            text = (line.decode("utf-8-sig", errors="replace") for line in f)
            reader = csv.DictReader(text)
            yield reader.fieldnames
            yield from reader


def related(rxcui):
    """{term type: [(rxcui, name), ...]} for the concepts RxNorm relates to one concept."""
    result = get_json(f"{RXNAV}/rxcui/{rxcui}/related.json?tty=IN+MIN+SCD+SBD+GPCK+BPCK")
    groups = result.get("relatedGroup", {}).get("conceptGroup", [])
    return {g["tty"]: [(p["rxcui"], p["name"]) for p in g.get("conceptProperties", [])] for g in groups}


def rxnorm_products(term, single_ingredient):
    """RxNorm ids of every strength and form of a drug named as an ingredient, a salt or a brand."""
    found = get_json(f"{RXNAV}/approximateTerm.json?maxEntries=1&term={urllib.parse.quote(term)}")
    candidates = found.get("approximateGroup", {}).get("candidate") or []
    if not candidates:
        return []
    groups = related(candidates[0]["rxcui"])
    if not groups.get("SCD") and not groups.get("SBD"):
        # a salt form ("atorvastatin calcium") links to products only through its base ingredient
        parents = groups.get("MIN") or groups.get("IN") or []
        if len(parents) != 1:
            return []
        groups = related(parents[0][0])
    products = [p for tty in ("SCD", "SBD", "GPCK", "BPCK") for p in groups.get(tty, [])]
    if single_ingredient:  # an ingredient is also related to its combination products; leave those out
        products = [p for p in products if " / " not in p[1]]
    return sorted({rxcui for rxcui, _ in products})


def top_drugs():
    """The most dispensed drugs in Medicare Part D by generic name, with their RxNorm product ids."""
    claims = defaultdict(float)
    with open(DATA / f"raw/part-d-spending/spending-by-drug-{SPENDING_YEAR}.csv", encoding="utf-8-sig") as f:
        for row in csv.DictReader(f):
            if row["Mftr_Name"].strip() == "Overall" and row[f"Tot_Clms_{SPENDING_YEAR}"].strip():
                claims[row["Gnrc_Name"].strip()] += float(row[f"Tot_Clms_{SPENDING_YEAR}"])
    ranked = sorted(claims.items(), key=lambda item: -item[1])[:TOP_DRUGS]

    def resolve(item):
        name, count = item
        try:
            rxcuis = rxnorm_products(name, single_ingredient="/" not in name and "-" not in name)
        except Exception as error:  # one failed lookup should not stop the download
            print(f"RxNav lookup failed for {name}: {error}")
            rxcuis = []
        return {"name": name.title(), "claims": int(count), "rxcuis": rxcuis}

    with ThreadPoolExecutor(5) as pool:
        drugs = list(pool.map(resolve, ranked))
    return [d for d in drugs if d["rxcuis"]]


def scenario_drugs():
    """RxNorm ids and a NADAC unit price for each member cost example in pharmacy_coding/scenarios.csv."""
    with open(ROOT / "pharmacy_coding/scenarios.csv", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    out = {}
    for row in rows:
        query = {"conditions[0][property]": "ndc_description", "conditions[0][value]": row["nadac_description"],
                 "conditions[0][operator]": "like" if "%" in row["nadac_description"] else "=",
                 "sort[0][property]": "as_of_date", "sort[0][order]": "desc", "limit": 1}
        price, source = float(row["fallback_unit_price"]), "illustrative"
        try:
            results = get_json(f"{NADAC}?{urllib.parse.urlencode(query)}")["results"]
            if results:
                price = float(results[0]["nadac_per_unit"])
                source = f"NADAC {results[0]['ndc_description']} as of {results[0]['as_of_date']}"
        except Exception as error:
            print(f"NADAC lookup failed for {row['label']}: {error}")
        out[row["id"]] = {"rxcuis": rxnorm_products(row["term"], row["single_ingredient"] == "yes"),
                          "unit_price": price, "price_source": source}
    return out


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--upload", action="store_true", help="upload ./data to Azure Blob Storage")
    args = parser.parse_args()

    for name in PUFS:
        path = f"raw/cms-puf/{YEAR}/{name}.zip"
        url = f"{PUF_BASE}/{name}.zip"
        if not fetch(url, DATA / path, expect_pdf=False):
            raise SystemExit(f"could not download {url}")
        record(path, "cms-puf", url)

    with open(ROOT / "ingest/plans.csv", encoding="utf-8") as f:
        pinned = {r["plan_id"]: r["complexity"] for r in csv.DictReader(f)}

    # one row per plan: the on-exchange standard variant
    attributes = read_puf("plan-attributes-puf")
    attr_fields = next(attributes)
    plans, attr_rows = {}, []
    for row in attributes:
        if row["StandardComponentId"] in pinned:
            attr_rows.append(row)
            if "On Exchange" in row["CSRVariationType"]:
                plans.setdefault(row["StandardComponentId"], row)
    missing = set(pinned) - set(plans)
    if missing:
        raise SystemExit(f"plans not found in the Plan Attributes file: {sorted(missing)}")

    for plan_id, row in sorted(plans.items()):
        folder = ISSUERS[row["IssuerId"]][0]
        url = row["URLForSummaryofBenefitsCoverage"]
        path = f"raw/sbc/{YEAR}/{folder}/{plan_id}_sbc.pdf"
        if fetch(url, DATA / path):
            record(path, "sbc", url, plan_id=plan_id, issuer=row["IssuerMarketPlaceMarketingName"],
                   state=row["StateCode"], plan_name=row["PlanMarketingName"], metal=row["MetalLevel"],
                   plan_type=row["PlanType"], complexity=pinned[plan_id])
        else:
            print(f"MISSING SBC {plan_id} {url}")

    for folder, drugs_url, plans_url in sorted(set(ISSUERS.values())):
        for name, url in (("drugs", drugs_url), ("plans", plans_url)):
            path = f"raw/formulary/{YEAR}/{folder}/{name}.json"
            if fetch(url, DATA / path, expect_pdf=False):
                record(path, f"machine-readable-{name}", url)
            else:
                print(f"MISSING {name} file for {folder} {url}")

    path = f"raw/part-d-spending/spending-by-drug-{SPENDING_YEAR}.csv"
    if not fetch(SPENDING_URL, DATA / path, expect_pdf=False):
        raise SystemExit(f"could not download {SPENDING_URL}")
    record(path, "part-d-spending", SPENDING_URL)

    reference = DATA / "reference"
    reference.mkdir(parents=True, exist_ok=True)
    for name, build, source in (("top-drugs.json", top_drugs, "Part D Spending by Drug + RxNav"),
                                ("scenario-drugs.json", scenario_drugs, "RxNav + NADAC")):
        if not (reference / name).exists():
            (reference / name).write_text(json.dumps(build(), indent=1), encoding="utf-8")
        record(f"reference/{name}", "reference", f"derived: {source}")

    # answer key: the published values for the pinned plans only
    golden = DATA / f"golden/{YEAR}"
    golden.mkdir(parents=True, exist_ok=True)
    with open(golden / "plan-attributes.csv", "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, attr_fields)
        writer.writeheader()
        writer.writerows(attr_rows)
    record(f"golden/{YEAR}/plan-attributes.csv", "golden", "derived from plan-attributes-puf.zip", rows=len(attr_rows))

    benefits = read_puf("benefits-and-cost-sharing-puf")
    with open(golden / "benefits-and-cost-sharing.csv", "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, next(benefits))
        writer.writeheader()
        count = 0
        for row in benefits:
            if row["StandardComponentId"] in pinned and "Drugs" in row["BenefitName"]:
                writer.writerow(row)
                count += 1
    record(f"golden/{YEAR}/benefits-and-cost-sharing.csv", "golden",
           "derived from benefits-and-cost-sharing-puf.zip (drug rows)", rows=count)

    sbc_paths = {m["plan_id"]: m for m in manifest if m["kind"] == "sbc"}
    columns = ["StandardComponentId", "StateCode", "IssuerId", "IssuerMarketPlaceMarketingName", "PlanMarketingName",
               "MetalLevel", "PlanType", "FormularyId", "IsHSAEligible", "MedicalDrugDeductiblesIntegrated"]
    with open(golden / "selected-plans.csv", "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(columns + ["complexity", "sbc_path", "sbc_source_url", "drug_file"])
        for plan_id, row in sorted(plans.items()):
            sbc = sbc_paths.get(plan_id, {})
            writer.writerow([row[c] for c in columns] + [pinned[plan_id], sbc.get("path", ""), sbc.get("source_url", ""),
                                                         f"raw/formulary/{YEAR}/{ISSUERS[row['IssuerId']][0]}/drugs.json"])
    record(f"golden/{YEAR}/selected-plans.csv", "golden", "derived", rows=len(plans))

    fields = ["path", "kind", "source_url", "bytes", "sha256", "downloaded", "plan_id", "issuer", "state",
              "plan_name", "metal", "plan_type", "complexity", "rows"]
    with open(DATA / "manifest.csv", "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fields)
        writer.writeheader()
        writer.writerows(sorted(manifest, key=lambda m: m["path"]))
    print(f"{len(manifest) + 1} files in {DATA}, {len(sbc_paths)} of {len(pinned)} SBCs")

    if args.upload:
        subprocess.run(f'az storage blob upload-batch --account-name {STORAGE_ACCOUNT} -d {CONTAINER} '
                       f'-s "{DATA}" --auth-mode key --overwrite -o none', shell=True, check=True)
        print(f"uploaded to {STORAGE_ACCOUNT}/{CONTAINER}")


if __name__ == "__main__":
    main()
