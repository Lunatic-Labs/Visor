from pathlib import Path

from visor.models import Course, Section
from visor.seed import load

DATA = Path(__file__).resolve().parents[2] / "data" / "sample"


def test_health(client):
    assert client.get("/api/health").json == {"status": "ok"}


def test_seed_is_idempotent(app):
    before = (Course.query.count(), Section.query.count())
    counts = load(DATA)
    assert all(v == 0 for v in counts.values())
    assert (Course.query.count(), Section.query.count()) == before


def test_sections_include_lab_meeting(client):
    secs = {s["label"]: s for s in client.get("/api/terms/2027SP/sections").json}
    assert len(secs["CS 3113-01"]["meetings"]) == 2
    assert secs["CS 3213-01"]["full"] is True
    assert secs["CS 3213-02"]["full"] is False


def test_planted_conflicts_are_found(client):
    pairs = {frozenset((c["a"], c["b"])) for c in client.get("/api/terms/2027SP/conflicts").json}
    assert frozenset({"CS 3233-01", "CS 3433-01"}) in pairs
    assert frozenset({"CS 4123-01", "SENG 3233-01"}) in pairs
    assert frozenset({"CS 3113-01", "PH 2414-01"}) in pairs
    # back-to-back is allowed
    assert frozenset({"MA 2314-01", "CS 2113-01"}) not in pairs


def test_conflicts_for_chosen_sections(client):
    r = client.get("/api/terms/2027SP/conflicts?sections=CS 3233-01,CS 3433-02")
    assert r.json == []


def test_unknown_term_404(client):
    assert client.get("/api/terms/1999FA/sections").status_code == 404


def test_prereq_check(client):
    r = client.get("/api/courses/CS/3433/prereq-check?completed=CS 1213")
    assert r.json == {"course": "CS 3433", "missing": [["MA 2314"]]}


def test_exactly_the_planted_conflicts(client):
    """Guards the sample data: only the 3 documented conflicts should exist."""
    pairs = {frozenset((c["a"], c["b"])) for c in client.get("/api/terms/2027SP/conflicts").json}
    assert pairs == {
        frozenset({"CS 3233-01", "CS 3433-01"}),
        frozenset({"CS 4123-01", "SENG 3233-01"}),
        frozenset({"CS 3113-01", "PH 2414-01"}),
    }
