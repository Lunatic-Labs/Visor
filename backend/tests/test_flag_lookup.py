"""Flag a course for review straight from a lookup, including unknowns (KAN-47)."""
from visor.auth import TOKEN_ENV
from visor.models import Equivalency


def _school_id(client, name_part):
    return next(s["id"] for s in client.get("/api/schools").json if name_part in s["name"])


def _body(client, school, subject, number, **extra):
    return {"school_id": _school_id(client, school), "subject": subject, "number": number, **extra}


def test_flag_unknown_creates_placeholder_and_review(client):
    before = Equivalency.query.count()
    r = client.post("/api/equivalencies/lookup/flag",
                    json=_body(client, "Volunteer", "COMM", "2025", reviewer="comm-dept", notes="Public speaking?"))
    assert r.status_code == 201
    eq = r.json["equivalency"]
    assert eq["status"] == "proposed" and eq["course"] is None and eq["pending_reviews"] == 1
    assert r.json["review"]["reviewer"] == "comm-dept" and r.json["review"]["decision"] == "pending"
    assert Equivalency.query.count() == before + 1


def test_lookup_after_flag_is_still_unknown_but_shows_the_review(client):
    client.post("/api/equivalencies/lookup/flag", json=_body(client, "Volunteer", "COMM", "2025", reviewer="x"))
    r = client.post("/api/equivalencies/lookup", json=_body(client, "Volunteer", "COMM", "2025")).json
    assert r["status"] == "unknown"
    assert r["equivalency"]["pending_reviews"] == 1 and r["candidates"] == []


def test_flagging_twice_reuses_the_placeholder(client):
    body = _body(client, "Volunteer", "COMM", "2025", reviewer="a")
    first = client.post("/api/equivalencies/lookup/flag", json=body).json
    second = client.post("/api/equivalencies/lookup/flag", json={**body, "reviewer": "b"}).json
    assert first["equivalency"]["id"] == second["equivalency"]["id"]
    assert second["equivalency"]["pending_reviews"] == 2


def test_flag_course_never_seen_before_records_it(client):
    r = client.post("/api/equivalencies/lookup/flag",
                    json=_body(client, "Columbia", "ZZZ", "9999", title="Mystery Course", reviewer="x"))
    assert r.status_code == 201
    assert r.json["external_course"]["title"] == "Mystery Course"


def test_flag_proposed_attaches_to_the_existing_row(client):
    proposed = client.post("/api/equivalencies/lookup", json=_body(client, "Volunteer", "CIS", "2350")).json
    r = client.post("/api/equivalencies/lookup/flag", json=_body(client, "Volunteer", "CIS", "2350", reviewer="x"))
    assert r.status_code == 201
    assert r.json["equivalency"]["id"] == proposed["equivalency"]["id"]


def test_flag_confirmed_is_409(client):
    r = client.post("/api/equivalencies/lookup/flag", json=_body(client, "Nashville", "CISP", "1010", reviewer="x"))
    assert r.status_code == 409


def test_flag_needs_reviewer_and_valid_course(client):
    assert client.post("/api/equivalencies/lookup/flag",
                       json=_body(client, "Volunteer", "COMM", "2025")).status_code == 400
    assert client.post("/api/equivalencies/lookup/flag", json={"reviewer": "x"}).status_code == 400


def test_flag_lookup_needs_token_in_production(app, client, monkeypatch):
    monkeypatch.setitem(app.config, "TESTING", False)
    monkeypatch.delenv(TOKEN_ENV, raising=False)
    r = client.post("/api/equivalencies/lookup/flag", json=_body(client, "Volunteer", "COMM", "2025", reviewer="x"))
    assert r.status_code == 403
