"""API tests for transfer equivalencies (KAN-38). Fixture data: data/equivalencies/."""
from pathlib import Path

import pytest

from visor.models import Equivalency, EquivalencyReview, ExternalCourse, School
from visor.seed import load_equivalencies

EQUIV_DATA = Path(__file__).resolve().parents[2] / "data" / "equivalencies"


def _school_id(client, name_part):
    return next(s["id"] for s in client.get("/api/schools").json if name_part in s["name"])


def _lookup(client, school, subject, number, **extra):
    return client.post("/api/equivalencies/lookup",
                       json={"school_id": _school_id(client, school), "subject": subject, "number": number,
                             **extra})


# --- seed ---------------------------------------------------------------------------------------

def test_seed_loads_and_is_idempotent(app):
    before = (School.query.count(), ExternalCourse.query.count(), Equivalency.query.count(),
              EquivalencyReview.query.count())
    assert before == (3, 20, 15, 1)
    assert all(v == 0 for v in load_equivalencies(EQUIV_DATA).values())
    assert (School.query.count(), ExternalCourse.query.count(), Equivalency.query.count(),
            EquivalencyReview.query.count()) == before


# --- schools ------------------------------------------------------------------------------------

def test_schools_sorted_by_name(client):
    names = [s["name"] for s in client.get("/api/schools").json]
    assert names == sorted(names) and len(names) == 3


def test_school_courses_search(client):
    sid = _school_id(client, "Nashville")
    all_courses = client.get(f"/api/schools/{sid}/courses").json
    assert len(all_courses) == 8
    hits = client.get(f"/api/schools/{sid}/courses?q=calc").json  # title match, incl. "Calculus-Based Physics"
    assert {(c["subject"], c["number"]) for c in hits} == {("MATH", "1910"), ("MATH", "1920"), ("PHYS", "2110")}
    assert [c["number"] for c in client.get(f"/api/schools/{sid}/courses?q=cisp").json] == ["1010", "1020"]


def test_school_courses_unknown_school_404(client):
    r = client.get("/api/schools/999/courses")
    assert r.status_code == 404 and r.json == {"error": "unknown school"}


# --- lookup: the three statuses -----------------------------------------------------------------

def test_lookup_confirmed_direct(client):
    r = _lookup(client, "Nashville", "CISP", "1010")
    assert r.status_code == 200
    body = r.json
    assert body["status"] == "confirmed"
    assert body["equivalency"]["course"]["code"] == "CS 1113"
    assert body["equivalency"]["kind"] == "direct"
    assert body["external_course"]["title"] == "Computer Science I"
    assert body["candidates"] == []


def test_lookup_confirmed_elective_and_none(client):
    elective = _lookup(client, "Nashville", "ENGL", "1010").json
    assert elective["status"] == "confirmed"
    assert elective["equivalency"]["kind"] == "elective" and elective["equivalency"]["course"] is None
    none = _lookup(client, "Volunteer", "PHED", "1110").json
    assert none["status"] == "confirmed" and none["equivalency"]["kind"] == "none"


def test_lookup_proposed_has_candidates_and_pending_review(client):
    body = _lookup(client, "Columbia", "CSCI", "1020").json
    assert body["status"] == "proposed"
    assert body["equivalency"]["confidence"] == pytest.approx(0.78)
    assert body["equivalency"]["pending_reviews"] == 1
    assert [c["course"]["code"] for c in body["candidates"]] == ["CS 1213"]


def test_lookup_rejected_only_is_unknown(client):
    body = _lookup(client, "Columbia", "CSCI", "2020").json
    assert body["status"] == "unknown" and body["equivalency"] is None


def test_lookup_case_and_whitespace_insensitive(client):
    assert _lookup(client, "Nashville", " cisp ", " 1010 ").json["status"] == "confirmed"


def test_lookup_new_course_is_recorded_as_unknown(app, client):
    before = ExternalCourse.query.count()
    body = _lookup(client, "Volunteer", "CIS", "9999", title="Special Topics").json
    assert body["status"] == "unknown"
    assert body["external_course"]["title"] == "Special Topics"
    assert ExternalCourse.query.count() == before + 1
    # a second lookup reuses the row
    _lookup(client, "Volunteer", "CIS", "9999")
    assert ExternalCourse.query.count() == before + 1


@pytest.mark.parametrize("payload", [{}, {"school_id": "1", "subject": "X", "number": "1"},
                                     {"school_id": 1, "subject": "X"}])
def test_lookup_validation(client, payload):
    r = client.post("/api/equivalencies/lookup", json=payload)
    assert r.status_code == 400 and "error" in r.json


def test_lookup_unknown_school_404(client):
    r = client.post("/api/equivalencies/lookup", json={"school_id": 999, "subject": "X", "number": "1"})
    assert r.status_code == 404


# --- list ---------------------------------------------------------------------------------------

def test_list_filters(client):
    assert len(client.get("/api/equivalencies").json) == 15
    proposed = client.get("/api/equivalencies?status=proposed").json
    assert {q["external_course"]["number"] for q in proposed} == {"1020", "2350"}
    sid = _school_id(client, "Volunteer")
    assert len(client.get(f"/api/equivalencies?school_id={sid}").json) == 3
    assert client.get("/api/equivalencies?status=bogus").status_code == 400


# --- flag, create, confirm ----------------------------------------------------------------------

def test_flag_creates_pending_review(client):
    q = _lookup(client, "Volunteer", "CIS", "2350").json["equivalency"]
    r = client.post(f"/api/equivalencies/{q['id']}/flag",
                    json={"reviewer": "prof@example.edu", "notes": "Same as CS 2113?"})
    assert r.status_code == 201
    assert r.json["decision"] == "pending" and r.json["requested_by"] == "registrar"
    assert _lookup(client, "Volunteer", "CIS", "2350").json["equivalency"]["pending_reviews"] == 1


def test_flag_requires_reviewer_and_known_id(client):
    assert client.post("/api/equivalencies/1/flag", json={}).status_code == 400
    assert client.post("/api/equivalencies/999/flag", json={"reviewer": "x"}).status_code == 404


def test_unknown_to_flagged_flow(client):
    """What the UI does for an unknown course: create a proposed row with no course, then flag it."""
    unknown = _lookup(client, "Volunteer", "COMM", "2025").json
    created = client.post("/api/equivalencies", json={"external_course_id": unknown["external_course"]["id"]})
    assert created.status_code == 201
    assert created.json["status"] == "proposed" and created.json["course"] is None
    flagged = client.post(f"/api/equivalencies/{created.json['id']}/flag", json={"reviewer": "comm-dept"})
    assert flagged.status_code == 201


def test_confirm_requires_a_person(client):
    q = _lookup(client, "Volunteer", "CIS", "2350").json["equivalency"]
    r = client.put(f"/api/equivalencies/{q['id']}", json={"status": "confirmed"})
    assert r.status_code == 400 and "decided_by" in r.json["error"]
    r = client.put(f"/api/equivalencies/{q['id']}", json={"status": "confirmed", "decided_by": "S. Hood"})
    assert r.status_code == 200 and r.json["decided_at"] is not None
    assert _lookup(client, "Volunteer", "CIS", "2350").json["status"] == "confirmed"


def test_only_one_confirmed_per_external_course(client):
    ext_id = _lookup(client, "Nashville", "CISP", "1010").json["external_course"]["id"]
    r = client.post("/api/equivalencies", json={"external_course_id": ext_id, "kind": "elective",
                                                "status": "confirmed", "decided_by": "someone"})
    assert r.status_code == 409


def test_create_validates_enums_and_course(client):
    ext_id = _lookup(client, "Volunteer", "MATH", "1920").json["external_course"]["id"]
    assert client.post("/api/equivalencies", json={"external_course_id": ext_id, "kind": "maybe"}
                       ).status_code == 400
    assert client.post("/api/equivalencies", json={"external_course_id": ext_id, "course_id": 9999}
                       ).status_code == 400
    assert client.post("/api/equivalencies", json={}).status_code == 400


def test_existing_endpoints_still_work(client):
    assert client.get("/api/health").json == {"status": "ok"}
    assert len(client.get("/api/terms").json) == 2
