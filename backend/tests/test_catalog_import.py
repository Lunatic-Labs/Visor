"""HTTP upload endpoint for catalog/section CSVs (KAN-25)."""
import io

from visor.models import Course, Section


def _csv(text: str, name: str):
    return (io.BytesIO(text.encode()), name)


def test_upload_courses_only(app, client):
    resp = client.post("/api/import/catalog", data={
        "courses": _csv("subject,number,title,credits\nCS,4999,Capstone,3\n", "courses.csv"),
    }, content_type="multipart/form-data")
    assert resp.status_code == 200
    body = resp.json
    assert body["ok"] is True
    assert body["counts"]["courses"] == 1
    assert Course.query.filter_by(subject="CS", number="4999").one().title == "Capstone"


def test_bad_row_reported_but_good_row_still_saved(app, client):
    resp = client.post("/api/import/catalog", data={
        "courses": _csv("subject,number,title,credits\nCS,4999,Capstone,three\nCS,4998,Independent Study,3\n",
                        "courses.csv"),
    }, content_type="multipart/form-data")
    body = resp.json
    assert body["ok"] is False
    assert len(body["errors"]) == 1
    assert "credits 'three' is not a whole number" in body["errors"][0]
    assert body["counts"]["courses"] == 1
    assert Course.query.filter_by(subject="CS", number="4998").first() is not None
    assert Course.query.filter_by(subject="CS", number="4999").first() is None


def test_uploading_only_sections_uses_existing_courses_and_terms(app, client):
    """The registrar shouldn't have to re-upload courses.csv just to add a term's sections."""
    resp = client.post("/api/import/catalog", data={
        "sections": _csv("term,course,section,capacity,enrolled,days,start,end\n"
                         "2027SP,CS 1113,02,30,0,TR,09:00,10:15\n", "sections.csv"),
    }, content_type="multipart/form-data")
    body = resp.json
    assert body["ok"] is True
    assert body["counts"]["sections"] == 1
    assert Section.query.filter_by(section_no="02").join(Course).filter(Course.subject == "CS",
                                                                        Course.number == "1113").count() == 1


def test_no_files_is_400(app, client):
    resp = client.post("/api/import/catalog", data={}, content_type="multipart/form-data")
    assert resp.status_code == 400


def test_dry_run_saves_nothing(app, client):
    resp = client.post("/api/import/catalog?dry_run=1", data={
        "courses": _csv("subject,number,title,credits\nCS,4999,Capstone,3\n", "courses.csv"),
    }, content_type="multipart/form-data")
    assert resp.json["counts"]["courses"] == 1
    assert Course.query.filter_by(subject="CS", number="4999").first() is None
