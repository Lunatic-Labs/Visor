"""SIS export importer (KAN-42). Every school, course, and count below is made up; the real export
never goes in the repo."""
import csv

import pytest
from openpyxl import Workbook

from visor.models import Course, Equivalency, ExternalCourse, School
from visor.sis_import import (COLUMNS, REGISTRAR_SIS, build_plan, is_elective_code, load_sis_equivalencies,
                              parse_rows, read_export, school_kind, split_code)

HEADER = ["Id", *COLUMNS.values()]
# Id, school code, school, ext code, ext title, ext credits, min grade, lip code, lip title, lip credits, times
FAKE = [
    (1, 900001, "Example Community College", "ENGL 1010", "Composition I", 3, "C  ", "EN1113      ",
     "Freshman Composition", 3, 12),
    (1, 900001, "Example Community College", "ENGL1010", "Composition I", 3, "C  ", "EN1113.01   ",
     "Freshman Composition (honors)", 3, 4),
    (1, 900001, "Example Community College", "HIST 2010", "Survey of US History", 3, "C  ", "HI2213",
     "History of the United States I", 3, 6),
    (1, 900001, "Example Community College", "ARTH 1030", "Art Appreciation", 3, "C* ", "AR1XXT",
     "Art Elective", 3, 5),
    (2, 900002, "Sample State University", "AR-2201-0399-03", "Drawing Studio", 2.67, "C  ", "AR1013",
     "Drawing I", 3, 3),
    (2, 900002, "Sample State University", "PSYCHOLOGY110", "General Psychology", 3.33, "C  ", "PS1113",
     "Introduction to Psychology", 3, 7),
    (2, 900002, "Sample State University", 3750100, "Seminar", 1, "", "TRACC", "Transfer credit", 1, 3),
]


def write_xlsx(path, rows=FAKE, header=HEADER, extra_sheet=True):
    wb = Workbook()
    ws = wb.active
    ws.title = "Sheet1"
    ws.append(header)
    for r in rows:
        ws.append(list(r))
    if extra_sheet:  # the real export has a second sheet holding the SQL query
        wb.create_sheet("Query").append(["select ..."])
    wb.save(path)
    return path


@pytest.fixture()
def export(tmp_path):
    return write_xlsx(tmp_path / "export.xlsx")


def test_split_code():
    assert split_code("ENGL 1010") == ("ENGL", "1010")
    assert split_code("engl1010") == ("ENGL", "1010")
    assert split_code("AR-2201-0399-03") == ("AR", "2201-0399-03")
    assert split_code("PSYCHOLOGY110") == ("PSYCHOLOGY", "110")
    assert split_code("CORE 301V") == ("CORE", "301V")
    assert split_code(3750100) == ("", "3750100")
    assert split_code("EN1113.01") == ("EN", "1113.01")
    assert split_code("TRACC") == ("TRACC", "")


def test_elective_codes_and_school_kind():
    assert is_elective_code("EN2XXT") and is_elective_code("PH1XXX") and is_elective_code("RTC12XT")
    assert is_elective_code("TRACC")
    assert not is_elective_code("EN1113.01") and not is_elective_code("CS1113")
    assert school_kind("Nashville State Community College") == "community_college"
    assert school_kind("Belmont University") == "university"


def test_plan_groups_and_ranks(export):
    plan = build_plan(parse_rows(read_export(export)))
    assert plan.summary() == {
        "rows_schools": 2, "rows_external_courses": 6, "rows_lipscomb_courses": 5, "confirmed": 6,
        "proposed_alternates": 1, "multi_mapped_external_courses": 1, "electives": 2,
    }
    engl = next(e for e in plan.externals if (e.subject, e.number) == ("ENGL", "1010"))
    # 'ENGL 1010' and 'ENGL1010' are the same course; the most-used mapping comes first
    assert [m.lip_code for m in engl.mappings] == ["EN1113", "EN1113.01"]
    assert engl.total_times == 16
    drawing = next(e for e in plan.externals if e.subject == "AR")
    assert drawing.credits == 2.67


def test_missing_column_is_an_error(tmp_path):
    path = write_xlsx(tmp_path / "bad.xlsx", header=[h for h in HEADER if h != COLUMNS["times"]])
    with pytest.raises(ValueError, match="TimesTransferred"):
        parse_rows(read_export(path))


def test_load_into_db(app, export):
    counts = load_sis_equivalencies(export)
    assert counts == {"schools": 2, "external_courses": 6, "lipscomb_courses": 5, "confirmed": 6,
                      "proposed_alternates": 1, "skipped_existing": 0}

    school = School.query.filter_by(name="Example Community College").one()
    assert school.kind == "community_college"
    engl = ExternalCourse.query.filter_by(school_id=school.id, subject="ENGL", number="1010").one()
    rows = Equivalency.query.filter_by(external_course_id=engl.id).order_by(Equivalency.id).all()
    assert [(q.status, q.course.code) for q in rows] == [("confirmed", "EN 1113"), ("proposed", "EN 1113.01")]
    assert rows[0].decided_by == REGISTRAR_SIS and rows[0].source == "sis_import"
    assert rows[1].decided_by is None and rows[1].confidence == 0.25

    elective = Equivalency.query.join(ExternalCourse).filter(ExternalCourse.subject == "ARTH").one()
    assert elective.kind == "elective" and elective.course_id is None and "AR1XXT" in elective.notes
    assert Course.query.filter_by(subject="AR", number="1XXT").first() is None


def test_only_one_confirmed_per_external_course(app, export):
    load_sis_equivalencies(export)
    for ext in ExternalCourse.query.filter_by(catalog_year="SIS"):
        confirmed = [q for q in Equivalency.query.filter_by(external_course_id=ext.id) if q.status == "confirmed"]
        assert len(confirmed) == 1


def test_import_is_idempotent(app, export):
    load_sis_equivalencies(export)
    before = Equivalency.query.count()
    again = load_sis_equivalencies(export)
    assert again["confirmed"] == again["external_courses"] == again["schools"] == 0
    assert again["skipped_existing"] == 6
    assert Equivalency.query.count() == before


def test_lookup_after_import(app, client, export):
    load_sis_equivalencies(export)
    school = School.query.filter_by(name="Example Community College").one()
    r = client.post("/api/equivalencies/lookup", json={"school_id": school.id, "subject": "engl", "number": "1010"})
    body = r.get_json()
    assert body["status"] == "confirmed"
    assert body["equivalency"]["course"]["code"] == "EN 1113"


def test_csv_export_works_too(app, tmp_path):
    path = tmp_path / "export.csv"
    with open(path, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(HEADER)
        w.writerows(FAKE)
    assert load_sis_equivalencies(path)["confirmed"] == 6
