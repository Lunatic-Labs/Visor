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
    assert body["candidates"][0]["id"] == body["equivalency"]["id"]


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


def test_summary_matches_the_list(client):
    s = client.get("/api/equivalencies/summary").json
    rows = client.get("/api/equivalencies").json
    for status in ("confirmed", "proposed", "rejected"):
        assert s[status] == sum(q["status"] == status for q in rows)
    assert s["electives"] == sum(q["status"] == "confirmed" and q["kind"] == "elective" for q in rows)
    assert s["schools"] == len(client.get("/api/schools").json)
    assert s["pending_reviews"] == sum(q["pending_reviews"] for q in rows)
    assert s["top_schools"] and s["top_schools"][0]["confirmed"] >= s["top_schools"][-1]["confirmed"]


# --- flag, create, confirm ----------------------------------------------------------------------

def test_flag_creates_pending_review(client):
    q = _lookup(client, "Volunteer", "CIS", "2350").json["equivalency"]
    r = client.post(f"/api/equivalencies/{q['id']}/flag",
                    json={"reviewer": "prof@example.edu", "notes": "Same as CS 2113?"})
    assert r.status_code == 201
    assert r.json["decision"] == "pending" and r.json["requested_by"] == "registrar"
    assert _lookup(client, "Volunteer", "CIS", "2350").json["equivalency"]["pending_reviews"] == 1


def test_confirm_a_proposed_candidate_from_the_ui_flow(client):
    """What TransferLookup's 'Confirm this match' button does: PUT the candidate's id, decided_by
    required, then the next lookup comes back confirmed."""
    candidate_id = _lookup(client, "Columbia", "CSCI", "1020").json["candidates"][0]["id"]
    r = client.put(f"/api/equivalencies/{candidate_id}", json={"status": "confirmed", "decided_by": "Ms. Hood"})
    assert r.status_code == 200
    body = _lookup(client, "Columbia", "CSCI", "1020").json
    assert body["status"] == "confirmed"
    assert body["equivalency"]["decided_by"] == "Ms. Hood"


def test_make_primary_swaps_the_confirmed_match(client):
    before = _lookup(client, "Nashville", "CISP", "1010").json
    old = before["equivalency"]
    other_course = next(c for c in client.get("/api/courses").json if c["id"] != old["course"]["id"])
    alt = client.post("/api/equivalencies", json={
        "external_course_id": before["external_course"]["id"], "course_id": other_course["id"],
        "status": "proposed",
    }).json

    assert client.post(f"/api/equivalencies/{alt['id']}/make-primary", json={}).status_code == 400
    r = client.post(f"/api/equivalencies/{alt['id']}/make-primary", json={"decided_by": "Ms. Hood"})
    assert r.status_code == 200 and r.json["status"] == "confirmed"

    after = _lookup(client, "Nashville", "CISP", "1010").json
    assert after["equivalency"]["id"] == alt["id"] and after["equivalency"]["decided_by"] == "Ms. Hood"
    assert [a["id"] for a in after["alternates"]] == [old["id"]]
    demoted = next(q for q in client.get("/api/equivalencies").json if q["id"] == old["id"])
    assert demoted["status"] == "proposed" and "Replaced as the primary match by Ms. Hood" in demoted["notes"]


def test_unknown_course_flagged_then_answer_logged_so_nobody_asks_again(client):
    """Unknown -> flag for a professor -> professor says yes -> registrar logs it -> the next
    lookup, by anyone, comes back approved with the note about who decided."""
    ext = _lookup(client, "Volunteer", "CSCI", "7777", title="Intro to Algorithms").json["external_course"]
    placeholder = client.post("/api/equivalencies", json={
        "external_course_id": ext["id"], "kind": "direct", "course_id": None, "status": "proposed",
        "notes": "No match on file; flagged from Look Up",
    }).json
    assert client.post(f"/api/equivalencies/{placeholder['id']}/flag",
                       json={"reviewer": "Dr. Nordstrom"}).status_code == 201
    still_open = _lookup(client, "Volunteer", "CSCI", "7777").json
    assert still_open["status"] == "proposed" and still_open["candidates"] == []
    assert still_open["equivalency"]["pending_reviews"] == 1

    course_id = next(c["id"] for c in client.get("/api/courses?q=2113").json)
    r = client.put(f"/api/equivalencies/{placeholder['id']}", json={
        "kind": "direct", "course_id": course_id, "status": "confirmed", "decided_by": "Ms. Hood",
        "notes": "Dr. Nordstrom approved by email, 10/22",
    })
    assert r.status_code == 200

    later = _lookup(client, "Volunteer", "CSCI", "7777").json
    assert later["status"] == "confirmed"
    assert later["equivalency"]["course"]["code"] == "CS 2113"
    assert later["equivalency"]["decided_by"] == "Ms. Hood"
    assert "Dr. Nordstrom approved by email" in later["equivalency"]["notes"]


def test_create_manual_mapping_for_an_unknown_course(client):
    """What the 'unknown' result's inline form does: look up (recording the external course),
    then POST a confirmed direct mapping against a real Lipscomb course id."""
    ext = _lookup(client, "Volunteer", "CIS", "9999", title="Special Topics").json["external_course"]
    course_id = next(c["id"] for c in client.get("/api/courses?q=1113").json)
    r = client.post("/api/equivalencies", json={
        "external_course_id": ext["id"], "kind": "direct", "course_id": course_id,
        "status": "confirmed", "decided_by": "Ms. Hood",
    })
    assert r.status_code == 201
    body = _lookup(client, "Volunteer", "CIS", "9999").json
    assert body["status"] == "confirmed" and body["equivalency"]["course"]["code"] == "CS 1113"


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


# --- approve for both -----------------------------------------------------------------------------

def _add_alternate(client, school, subject, number):
    """A proposed second match for a course that already has a confirmed one."""
    before = _lookup(client, school, subject, number).json
    current = before["equivalency"]
    other = next(c for c in client.get("/api/courses").json if c["id"] != current["course"]["id"])
    alt = client.post("/api/equivalencies", json={
        "external_course_id": before["external_course"]["id"], "course_id": other["id"], "status": "proposed",
    }).json
    return current, alt, other


def test_approve_also_counts_the_course_as_both(client):
    current, alt, other = _add_alternate(client, "Nashville", "CISP", "1010")
    assert client.post(f"/api/equivalencies/{alt['id']}/approve-also", json={}).status_code == 400
    r = client.post(f"/api/equivalencies/{alt['id']}/approve-also", json={"decided_by": "Ms. Hood"})
    assert r.status_code == 200 and r.json["status"] == "confirmed" and r.json["decided_by"] == "Ms. Hood"
    assert "Approved to count alongside" in r.json["notes"]

    body = _lookup(client, "Nashville", "CISP", "1010").json
    assert body["status"] == "confirmed"
    assert body["equivalency"]["id"] == current["id"]  # the first approval stays first
    assert [q["course"]["code"] for q in body["also_counts_as"]] == [other["code"]]
    assert body["alternates"] == []


def test_also_counts_as_is_empty_for_a_single_match(client):
    assert _lookup(client, "Nashville", "CISP", "1010").json["also_counts_as"] == []


def test_an_approved_row_can_still_be_edited_when_another_is_approved_too(client):
    current, alt, _ = _add_alternate(client, "Nashville", "CISP", "1010")
    client.post(f"/api/equivalencies/{alt['id']}/approve-also", json={"decided_by": "Ms. Hood"})
    r = client.put(f"/api/equivalencies/{current['id']}", json={"notes": "checked again"})
    assert r.status_code == 200 and r.json["status"] == "confirmed"


def test_a_second_approval_by_accident_is_still_blocked(client):
    _, alt, _ = _add_alternate(client, "Nashville", "CISP", "1010")
    r = client.put(f"/api/equivalencies/{alt['id']}", json={"status": "confirmed", "decided_by": "Ms. Hood"})
    assert r.status_code == 409 and "approve-also" in r.json["error"]


def test_use_instead_after_both_leaves_only_the_chosen_one(client):
    current, alt, other = _add_alternate(client, "Nashville", "CISP", "1010")
    client.post(f"/api/equivalencies/{alt['id']}/approve-also", json={"decided_by": "Ms. Hood"})
    client.post(f"/api/equivalencies/{current['id']}/make-primary", json={"decided_by": "Ms. Hood"})
    body = _lookup(client, "Nashville", "CISP", "1010").json
    assert body["equivalency"]["id"] == current["id"] and body["also_counts_as"] == []
    assert [q["id"] for q in body["alternates"]] == [alt["id"]]


def test_summary_counts_both_approvals(client):
    before = client.get("/api/equivalencies/summary").json
    _, alt, _ = _add_alternate(client, "Nashville", "CISP", "1010")
    client.post(f"/api/equivalencies/{alt['id']}/approve-also", json={"decided_by": "Ms. Hood"})
    after = client.get("/api/equivalencies/summary").json
    assert after["confirmed"] == before["confirmed"] + 1 and after["proposed"] == before["proposed"]


# --- adding a school and course by hand ------------------------------------------------------------

def test_create_school_and_it_appears_in_the_list(client):
    r = client.post("/api/schools", json={"name": "  University of   Tennessee, Knoxville ", "state": "tn"})
    assert r.status_code == 201
    assert r.json["name"] == "University of Tennessee, Knoxville" and r.json["state"] == "TN"
    assert r.json["kind"] == "university"
    assert any(s["id"] == r.json["id"] for s in client.get("/api/schools").json)


def test_create_school_is_idempotent_ignoring_case(client):
    first = client.post("/api/schools", json={"name": "Example Community College"})
    again = client.post("/api/schools", json={"name": "example community college"})
    assert first.status_code == 201 and again.status_code == 200 and again.json["id"] == first.json["id"]
    assert first.json["kind"] == "community_college"


def test_create_school_validation(client):
    assert client.post("/api/schools", json={}).status_code == 400
    assert client.post("/api/schools", json={"name": "x" * 121}).status_code == 400
    assert client.post("/api/schools", json={"name": "Somewhere", "state": "Tennessee"}).status_code == 400


def test_add_a_course_at_a_new_school_by_hand(client):
    """What the Library's 'Add equivalency' form does, end to end."""
    school = client.post("/api/schools", json={"name": "Example State University", "state": "TN"}).json
    looked = client.post("/api/equivalencies/lookup", json={
        "school_id": school["id"], "subject": "math", "number": "1910", "title": "Calculus I", "credits": "4"}).json
    assert looked["status"] == "unknown"
    assert looked["external_course"]["title"] == "Calculus I" and looked["external_course"]["credits"] == 4
    course_id = next(c["id"] for c in client.get("/api/courses?q=1314").json)
    r = client.post("/api/equivalencies", json={
        "external_course_id": looked["external_course"]["id"], "kind": "direct", "course_id": course_id,
        "status": "confirmed", "decided_by": "Ms. Hood", "notes": "Math dept approved by email"})
    assert r.status_code == 201
    later = client.post("/api/equivalencies/lookup",
                        json={"school_id": school["id"], "subject": "MATH", "number": "1910"}).json
    assert later["status"] == "confirmed" and later["equivalency"]["course"]["code"] == "MA 1314"


def test_lookup_rejects_bad_credits(client):
    sid = _school_id(client, "Nashville")
    r = client.post("/api/equivalencies/lookup", json={"school_id": sid, "subject": "X", "number": "1", "credits": "four"})
    assert r.status_code == 400
