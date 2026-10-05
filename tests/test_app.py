"""Workspace tests that need no Azure access: highlighting and the sign-in gate."""
from app import highlight


def test_highlight_marks_the_quote_across_line_breaks():
    html = highlight("Generic drugs\n$10 copayment\nNot covered", "Generic drugs $10 copayment")
    assert html == "<mark>Generic drugs\n$10 copayment</mark>\nNot covered"


def test_highlight_marks_separate_pieces_of_a_joined_quote():
    html = highlight("Generic drugs (Tier 1)\nRetail\n$5 copayment", "Generic drugs (Tier 1) ... $5 copayment")
    assert html.count("<mark>") == 2 and "<mark>5 copayment</mark>" in html


def test_highlight_escapes_document_text():
    assert "<script>" not in highlight("<script>alert(1)</script> $40 copay", "$40 copay")


def client(monkeypatch, password="test-only-value"):
    from werkzeug.security import generate_password_hash

    import app as workspace
    monkeypatch.setenv("WORKSPACE_PASSWORD_HASH", generate_password_hash(password))
    return workspace.app.test_client()


def test_pages_redirect_to_login_when_signed_out(monkeypatch):
    c = client(monkeypatch)
    response = c.get("/plan/ABC?field=generic_retail")
    assert response.status_code == 302 and response.headers["Location"].startswith("/login?next=")
    assert c.post("/plan/ABC/signoff", data={"kind": "coder", "action": "approve"}).status_code == 302
    assert c.get("/plan/ABC/handoff.json").status_code == 302
    assert c.get("/healthz").status_code == 200


def test_wrong_password_is_refused(monkeypatch):
    c = client(monkeypatch)
    assert c.post("/login", data={"password": "nope"}).status_code == 401
    assert c.get("/").headers["Location"].startswith("/login")


def test_no_password_configured_means_nobody_signs_in(monkeypatch):
    import app as workspace
    monkeypatch.delenv("WORKSPACE_PASSWORD_HASH", raising=False)
    assert workspace.app.test_client().post("/login", data={"password": ""}).status_code == 401


def test_sign_in_only_follows_paths_on_this_site(monkeypatch):
    c = client(monkeypatch)
    response = c.post("/login", data={"password": "test-only-value", "next": "//evil.example"})
    assert response.status_code == 302 and response.headers["Location"] == "/"
