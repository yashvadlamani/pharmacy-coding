"""Azure Table Storage: client answers, plan sign-offs and the audit trail.

  answers       PartitionKey = plan id, RowKey = question id; the client's answer as recorded by the rep
  signoffs      PartitionKey = plan id, RowKey = "client" or "coder"; the latest sign-off of each kind
  audittrail    PartitionKey = plan id, RowKey = timestamp; one row per action, never updated
"""
import uuid
from datetime import datetime, timezone
from functools import lru_cache

from azure.data.tables import TableServiceClient

from . import config

ANSWERS, SIGNOFFS, AUDIT = "answers", "signoffs", "audittrail"
CLIENT, CODER = "client", "coder"


@lru_cache(maxsize=None)
def _table(name):
    service = TableServiceClient.from_connection_string(config.setting("AZURE_STORAGE_CONNECTION_STRING"))
    return service.create_table_if_not_exists(name)


def _log(plan_id, target, action, who, detail):
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    _table(AUDIT).create_entity({"PartitionKey": plan_id, "RowKey": f"{now}-{uuid.uuid4().hex[:6]}",
                                 "target": target, "action": action, "who": who, "detail": detail, "timestamp": now})
    return now


def record_answer(plan_id, question_id, answer, who):
    now = _log(plan_id, question_id, "answer", who, answer)
    _table(ANSWERS).upsert_entity({"PartitionKey": plan_id, "RowKey": question_id, "answer": answer, "who": who,
                                   "timestamp": now})


def answers(plan_id):
    """{question id: answer row} for one plan."""
    return {row["RowKey"]: dict(row) for row in _table(ANSWERS).query_entities(f"PartitionKey eq '{plan_id}'")}


def answered():
    """{plan id: {answered question ids}} across all plans."""
    out = {}
    for row in _table(ANSWERS).list_entities(select=["PartitionKey", "RowKey"]):
        out.setdefault(row["PartitionKey"], set()).add(row["RowKey"])
    return out


def record_signoff(plan_id, kind, action, who, note=""):
    """action is "confirm" or "reopen" for the client sign-off, "approve" or "return" for the coder's."""
    now = _log(plan_id, kind, action, who, note)
    _table(SIGNOFFS).upsert_entity({"PartitionKey": plan_id, "RowKey": kind, "action": action, "who": who,
                                    "note": note, "timestamp": now})


def signoffs(plan_id=None):
    """{plan id: {kind: row}} for every plan, or {kind: row} for one plan."""
    if plan_id:
        return {row["RowKey"]: dict(row) for row in _table(SIGNOFFS).query_entities(f"PartitionKey eq '{plan_id}'")}
    out = {}
    for row in _table(SIGNOFFS).list_entities():
        out.setdefault(row["PartitionKey"], {})[row["RowKey"]] = dict(row)
    return out


def audit(plan_id):
    """Every action taken on a plan, newest first."""
    rows = _table(AUDIT).query_entities(f"PartitionKey eq '{plan_id}'")
    return sorted((dict(row) for row in rows), key=lambda row: row["RowKey"], reverse=True)
