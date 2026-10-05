"""Step 5 and 6. The sales team's workspace: accounts, their pharmacy plans, and the handoff to coding.

Reps read each plan in plain words with its source, see how it fits what the platform administers, record the
client's answers to open questions, compare plans, and confirm. A confirmed plan becomes a coding package that
a benefit coder approves or returns.

Reads pipeline outputs from Azure Blob Storage and stores answers, sign-offs and the audit trail in Azure Table
Storage. Run locally with `flask run`; on Azure App Service it is served by gunicorn as `app:app`.

The whole site sits behind one shared password. Two settings are required:
  WORKSPACE_PASSWORD_HASH   a werkzeug password hash (never the password itself)
  FLASK_SECRET_KEY          random string that signs the session cookie
"""
import os
import re
from datetime import date, timedelta
from functools import lru_cache

from flask import Flask, abort, jsonify, make_response, redirect, render_template, request, session, url_for
from markupsafe import Markup, escape
from werkzeug.security import check_password_hash

from pharmacy_coding import accounts, formulary, store, tables
from pharmacy_coding.fit import ORDER as FIT_ORDER

app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET_KEY") or os.urandom(32)
app.config.update(SESSION_COOKIE_HTTPONLY=True, SESSION_COOKIE_SAMESITE="Lax",
                  SESSION_COOKIE_SECURE=bool(os.environ.get("WEBSITE_HOSTNAME")),  # set on App Service, where HTTPS is forced
                  PERMANENT_SESSION_LIFETIME=timedelta(hours=12))
OPEN_ENDPOINTS = {"login", "healthz", "static"}
COMMON_DRUGS_SHOWN = 40


@lru_cache(maxsize=64)
def document(plan_id):
    return store.read_json(f"ingested/{plan_id}.json")  # never changes once ingested


@lru_cache(maxsize=1)
def top_drugs():
    return store.read_json("reference/top-drugs.json", [])


def highlight(text, quote):
    """Page text as HTML with the quoted passage marked. Matching ignores spacing and punctuation,
    and a quote made of separate pieces is marked piece by piece."""
    words = re.findall(r"[A-Za-z0-9]+", quote)
    spans, start = [], 0
    while start < len(words):
        for length in range(len(words) - start, 1, -1):
            pattern = r"[^A-Za-z0-9]*".join(re.escape(w) for w in words[start:start + length])
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                spans.append(match.span())
                start += length
                break
        else:
            start += 1
    out, position = [], 0
    for lo, hi in sorted(spans):
        if lo >= position:
            out += [escape(text[position:lo]), Markup("<mark>"), escape(text[lo:hi]), Markup("</mark>")]
            position = hi
    out.append(escape(text[position:]))
    return Markup("").join(out)


@app.before_request
def require_login():
    if request.endpoint not in OPEN_ENDPOINTS and not session.get("signed_in"):
        return redirect(url_for("login", next=request.full_path.rstrip("?")))


@app.route("/login", methods=["GET", "POST"])
def login():
    password_hash = os.environ.get("WORKSPACE_PASSWORD_HASH", "")
    error = None if password_hash else "No password is configured for this site, so nobody can sign in."
    if request.method == "POST" and password_hash:
        if check_password_hash(password_hash, request.form.get("password", "")):
            session.clear()
            session["signed_in"] = True
            session.permanent = True
            target = request.form.get("next", "")
            # only follow a path on this site, never a full URL
            return redirect(target if target.startswith("/") and not target.startswith("//") else url_for("index"))
        error = "That password is not correct."
    return render_template("login.html", error=error, next=request.values.get("next", "")), 401 if error else 200


@app.post("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


@app.post("/reviewer")
def set_reviewer():
    response = make_response(redirect(request.form.get("next") or url_for("index")))
    response.set_cookie("reviewer", request.form.get("name", "").strip()[:60], max_age=60 * 60 * 24 * 90,
                        httponly=True, samesite="Lax")
    return response


def reviewer():
    return request.cookies.get("reviewer", "").strip()


def days_until(date_text):
    return (date.fromisoformat(date_text) - date.today()).days


def plan_rows():
    """{plan id: index line} for every processed plan, with its status and count of unanswered questions."""
    plans = {p["plan_id"]: p for p in store.read_json("index.json", [])}
    signoffs, answered = tables.signoffs(), tables.answered()
    for plan_id, plan in plans.items():
        done = answered.get(plan_id, set())
        plan["open"] = len(set(plan["question_ids"]) - done)
        plan["status"] = accounts.plan_status(signoffs.get(plan_id, {}), len(set(plan["blocking_ids"]) - done))
        plan["worst_fit"] = next((rating for rating in FIT_ORDER if plan["fit"].get(rating)), "Standard")
    return plans


def plan_state(plan_id):
    """Everything the plan pages need: validated record, answers, sign-offs and current status."""
    validated = store.read_json(f"validated/{plan_id}.json")
    if validated is None:
        abort(404)
    answers, signoffs = tables.answers(plan_id), tables.signoffs(plan_id)
    for question in validated["questions"]:
        question["answer"] = answers.get(question["id"])
    still_open = accounts.open_questions(validated["questions"], answers)
    blocking = [q for q in still_open if q["blocking"]]
    meta = next((p for p in store.read_json("index.json", []) if p["plan_id"] == plan_id), {"plan_id": plan_id})
    account = accounts.account_of(plan_id)
    role = next((p["role"] for p in account["plans"] if p["plan_id"] == plan_id), "") if account else ""
    return {"validated": validated, "answers": answers, "signoffs": signoffs, "open": still_open,
            "blocking": blocking, "meta": meta, "account": account, "role": role,
            "status": accounts.plan_status(signoffs, len(blocking))}


@app.get("/")
def index():
    """Every account, how far its plans have got, and how close its effective date is."""
    plans = plan_rows()
    rows = []
    for account in accounts.load().values():
        mine = [plans[p["plan_id"]] for p in account["plans"] if p["plan_id"] in plans]
        rows.append({**account, "plan_count": len(mine), "status": accounts.rollup([p["status"] for p in mine]),
                     "open": sum(p["open"] for p in mine),
                     "custom": sum(p["fit"].get("Custom", 0) + p["fit"].get("Not supported", 0) for p in mine),
                     "days": days_until(account["effective_date"])})
    rows.sort(key=lambda a: (accounts.ORDER.index(a["status"]), a["effective_date"], a["name"]))
    return render_template("index.html", accounts=rows, reviewer=reviewer())


@app.get("/account/<account_id>")
def account(account_id):
    record = accounts.load().get(account_id)
    if record is None:
        abort(404)
    plans = plan_rows()
    mine = [{**plans[p["plan_id"]], "role": p["role"]} for p in record["plans"] if p["plan_id"] in plans]
    current = next((p for p in mine if p["role"] == "Current plan"), None)
    return render_template("account.html", account=record, plans=mine, current=current,
                           days=days_until(record["effective_date"]),
                           status=accounts.rollup([p["status"] for p in mine]), reviewer=reviewer())


@app.get("/plan/<plan_id>")
def plan(plan_id):
    """One plan in plain words, with its source, fit ratings, open questions and member cost examples."""
    state = plan_state(plan_id)
    fields = state["validated"]["fields"]
    sections = [(heading, [{"name": name, **fields[name]} for name in names])
                for heading, names in accounts.SUMMARY_SECTIONS]

    # the source pane shows the page cited by the selected field, with the quote marked
    pages = document(plan_id)["pages"]
    selected = request.args.get("field")
    chosen = fields.get(selected)
    page_number = request.args.get("page", type=int) or (chosen and chosen["page"]) or 1
    page_number = min(max(page_number, 1), len(pages))
    page_text = pages[page_number - 1]["text"]
    source = highlight(page_text, chosen["quote"]) if chosen and chosen["page"] == page_number else escape(page_text)
    return render_template("plan.html", sections=sections, selected=selected, source=source, page_number=page_number,
                           page_count=len(pages), audit=tables.audit(plan_id), reviewer=reviewer(),
                           error=request.args.get("error"), **state)


@app.post("/plan/<plan_id>/answer")
def answer(plan_id):
    validated = store.read_json(f"validated/{plan_id}.json")
    question_id, text = request.form.get("question", ""), request.form.get("answer", "").strip()[:500]
    if validated is None or question_id not in {q["id"] for q in validated["questions"]}:
        abort(400)
    if not reviewer():
        return redirect(url_for("plan", plan_id=plan_id, error="name") + "#questions")
    if text:
        tables.record_answer(plan_id, question_id, text, reviewer())
    return redirect(url_for("plan", plan_id=plan_id) + "#questions")


@app.post("/plan/<plan_id>/signoff")
def signoff(plan_id):
    """The rep records the client's confirmation (or reopens the plan); the coder approves or returns it."""
    state = plan_state(plan_id)
    kind, action = request.form.get("kind"), request.form.get("action")
    back = "handoff" if kind == tables.CODER else "plan"
    if (kind, action) not in {(tables.CLIENT, "confirm"), (tables.CLIENT, "reopen"),
                              (tables.CODER, "approve"), (tables.CODER, "return")}:
        abort(400)
    if not reviewer():
        return redirect(url_for(back, plan_id=plan_id, error="name"))
    confirmed = (state["signoffs"].get(tables.CLIENT) or {}).get("action") == "confirm"
    if (kind, action) == (tables.CLIENT, "confirm") and state["blocking"]:
        return redirect(url_for("plan", plan_id=plan_id, error="blocking") + "#questions")  # the confirmation gate
    if kind == tables.CODER and not confirmed:
        return redirect(url_for("handoff", plan_id=plan_id, error="unconfirmed"))  # the load gate
    tables.record_signoff(plan_id, kind, action, reviewer(), request.form.get("note", "").strip()[:500])
    return redirect(url_for(back, plan_id=plan_id))


@app.get("/plan/<plan_id>/drugs")
def drugs(plan_id):
    """Look up any drug on the plan's formulary, and see how it treats the most commonly dispensed drugs."""
    state = plan_state(plan_id)
    drug_list = formulary.load(state["meta"]["formulary_id"])
    query = request.args.get("q", "").strip()
    results, total = formulary.search(drug_list, query) if query else ([], 0)
    common = []
    for drug in top_drugs()[:COMMON_DRUGS_SHOWN]:
        common.append({"name": drug["name"], "claims": drug["claims"], "status": formulary.status(drug_list, drug["rxcuis"])})
    return render_template("drugs.html", query=query, results=results, total=total, common=common,
                           tiers=drug_list["tiers"], drug_count=len(drug_list["drugs"]),
                           warnings=drug_list.get("warnings", []),
                           restrictions=formulary.restrictions, reviewer=reviewer(), **state)


@app.get("/compare")
def compare():
    """Two plans side by side: plan design, what changes for commonly used drugs, and member cost examples."""
    a_id, b_id = request.args.get("a", ""), request.args.get("b", "")
    a, b = plan_state(a_id), plan_state(b_id)
    lines = []
    for heading, names in accounts.SUMMARY_SECTIONS:
        for name in names:
            left, right = a["validated"]["fields"][name], b["validated"]["fields"][name]
            lines.append({"heading": heading, "label": left["label"], "a": left["value"], "b": right["value"],
                          "differs": left["value"] != right["value"]})
    costs = [{"label": x["label"], "a": x, "b": y}
             for x, y in zip(a["validated"]["member_costs"], b["validated"]["member_costs"])]
    rows = formulary.disruption(formulary.load(a["meta"]["formulary_id"]), formulary.load(b["meta"]["formulary_id"]),
                                top_drugs())
    order = ["worse", "limit", "better", "same"]
    counts = {impact: sum(r["impact"] == impact for r in rows) for impact in order}
    changed = sorted((r for r in rows if r["impact"] != "same"), key=lambda r: (order.index(r["impact"]), -r["claims"]))
    return render_template("compare.html", a=a, b=b, lines=lines, costs=costs, changed=changed, counts=counts,
                           drug_total=len(rows), restrictions=formulary.restrictions, reviewer=reviewer())


def package(plan_id, state):
    """The coding handoff: every confirmed value with its placeholder code, source and fit, the client's
    answers, and the test claims with their expected results."""
    validated = state["validated"]
    client = state["signoffs"].get(tables.CLIENT) or {}
    return {
        "plan_id": plan_id,
        "plan_name": state["meta"].get("plan_name"),
        "account": state["account"] and {k: state["account"][k] for k in ("account_id", "name", "effective_date")},
        "formulary_id": state["meta"].get("formulary_id"),
        "status": state["status"],
        "client_confirmation": {k: client.get(k) for k in ("action", "who", "timestamp", "note")} if client else None,
        "fields": [{"field": name, "label": f["label"], "value": f["value"], "code": f["code"], "fit": f["fit"],
                    "fit_reason": f["fit_reason"], "source_page": f["page"], "source_quote": f["quote"],
                    "confidence": f["confidence"]} for name, f in validated["fields"].items()],
        "plan_wide": validated["plan_wide"],
        "formulary_warnings": validated["formulary_warnings"],
        "client_answers": [{"question": q["text"], "answer": q["answer"]["answer"], "recorded_by": q["answer"]["who"],
                            "recorded": q["answer"]["timestamp"]} for q in validated["questions"] if q["answer"]],
        "unanswered_questions": [q["text"] for q in state["open"]],
        "test_claims": [{"scenario": c["label"], "channel": c["channel"], "drug_price": c["allowed"], "tier": c["tier"],
                         "expected_member_pay_first_fill": c["first_fill"],
                         "expected_member_pay_after_deductible": c["after_deductible"],
                         "expected_reject": c["reject"], "notes": c["notes"]} for c in validated["member_costs"]],
    }


@app.get("/plan/<plan_id>/handoff")
def handoff(plan_id):
    state = plan_state(plan_id)
    return render_template("handoff.html", package=package(plan_id, state), reviewer=reviewer(),
                           error=request.args.get("error"), **state)


@app.get("/plan/<plan_id>/handoff.json")
def handoff_json(plan_id):
    response = jsonify(package(plan_id, plan_state(plan_id)))
    response.headers["Content-Disposition"] = f'attachment; filename="{plan_id}-coding-package.json"'
    return response


@app.get("/healthz")
def healthz():
    return "ok"
