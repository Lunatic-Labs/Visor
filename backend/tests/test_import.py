"""CSV import (KAN-25)."""
import shutil
from pathlib import Path

import pytest

from visor.models import Course, MeetingTime, PrereqGroup, Section, Term
from visor.seed import load

DATA = Path(__file__).resolve().parents[2] / "data" / "sample"


@pytest.fixture()
def data(tmp_path):
    """A writable copy of the sample data."""
    d = tmp_path / "data"
    shutil.copytree(DATA, d)
    return d


def append(path: Path, line: str) -> None:
    with open(path, "a", newline="") as f:
        f.write(line + "\n")


def snapshot():
    return (Term.query.count(), Course.query.count(), Section.query.count(), MeetingTime.query.count())


def test_new_rows_are_added(app, data):
    append(data / "courses.csv", "CS,4999,Capstone,3")
    append(data / "sections.csv", "2027SP,CS 4999,01,20,0,TR,16:00,17:15")
    result = load(data)
    assert result.ok
    assert result.counts["courses"] == 1 and result.counts["sections"] == 1 and result.counts["meetings"] == 1
    assert Course.query.filter_by(subject="CS", number="4999").one().title == "Capstone"


def test_reimport_updates_enrollment(app, data):
    text = (data / "sections.csv").read_text()
    (data / "sections.csv").write_text(text.replace("2027SP,CS 3213,01,30,30", "2027SP,CS 3213,01,35,31"))
    result = load(data)
    assert result.counts["updated"] == 1 and result.counts["sections"] == 0
    course = Course.query.filter_by(subject="CS", number="3213").one()
    sec = Section.query.filter_by(course_id=course.id, section_no="01").one()
    assert (sec.capacity, sec.enrolled_count) == (35, 31)


def test_reimport_is_idempotent(app, data):
    load(data)
    before = snapshot()
    result = load(data)
    assert result.ok
    assert sum(result.counts.values()) == 0
    assert snapshot() == before


def test_bad_row_is_skipped_but_good_rows_still_load(app, data):
    """The core KAN-25 acceptance criterion: one bad row doesn't block the rest of the file."""
    append(data / "courses.csv", "CS,4999,Capstone,three")  # bad: credits not a number
    append(data / "courses.csv", "CS,4998,Independent Study,3")  # good

    result = load(data)

    assert len(result.errors) == 1
    assert "courses.csv line" in result.errors[0]
    assert "credits 'three' is not a whole number" in result.errors[0]
    assert Course.query.filter_by(subject="CS", number="4999").first() is None
    assert Course.query.filter_by(subject="CS", number="4998").one().title == "Independent Study"


def test_every_bad_row_is_reported_with_its_line(app, data):
    append(data / "courses.csv", "CS,4999,Capstone,three")
    append(data / "sections.csv", "2027SP,CS 3213,03,30,0,MWF,11:00,10:00")
    append(data / "sections.csv", "2027SP,CS 3213,04,30,0,MXF,11:00,11:50")
    append(data / "sections.csv", "2027SP,CS 3213,05,30,0,MWF,9am,11:50")
    append(data / "sections.csv", "2099FA,CS 3213,06,30,0,MWF,11:00,11:50")
    append(data / "prereqs.csv", "CS 3213,CS 3213")

    result = load(data)

    errors = "\n".join(result.errors)
    assert "courses.csv line" in errors and "credits 'three' is not a whole number" in errors
    assert "end 10:00 is not after start 11:00" in errors
    assert "days 'MXF'" in errors
    assert "start '9am' is not a 24-hour HH:MM time" in errors
    assert "unknown term '2099FA'" in errors
    assert "can't be its own prerequisite" in errors
    assert len(result.errors) == 6
    # and the sections.csv rows that WERE valid still made it in
    assert Section.query.join(Course).filter(Course.subject == "CS", Course.number == "3213",
                                             Section.section_no.in_(("03", "04", "05", "06"))).count() == 0


def test_row_depending_on_a_rejected_row_fails_with_its_own_reason(app, data):
    """A section for a course that failed to import is reported as 'unknown course', not silently dropped."""
    append(data / "courses.csv", "CS,4999,Capstone,three")  # bad, so CS 4999 is never created
    append(data / "sections.csv", "2027SP,CS 4999,01,20,0,TR,16:00,17:15")  # depends on it

    result = load(data)

    assert any("unknown course 'CS 4999'" in e for e in result.errors)
    assert Course.query.filter_by(subject="CS", number="4999").first() is None


def test_error_gives_line_number(app, data):
    lines = (data / "sections.csv").read_text().splitlines()
    append(data / "sections.csv", "2027SP,NOPE 1000,01,30,0,MWF,11:00,11:50")
    result = load(data)
    assert result.errors == [f"sections.csv line {len(lines) + 1}: unknown course 'NOPE 1000'"]


def test_missing_file_and_column(app, data):
    (data / "terms.csv").unlink()
    (data / "courses.csv").write_text("subject,number,title\nCS,1113,Programming I\n")
    result = load(data)
    assert "terms.csv: file not found" in result.errors
    assert "courses.csv: missing column(s) credits" in result.errors


def test_excel_bom_and_whitespace(app, data):
    (data / "courses.csv").write_text("﻿subject,number,title,credits\n CS , 4999 , Capstone , 3 \n\n",
                                      encoding="utf-8")
    result = load(data)
    assert result.counts["courses"] == 1
    assert Course.query.filter_by(subject="CS", number="4999").one().credits == 3


def test_dry_run_saves_nothing(app, data):
    before = snapshot()
    append(data / "courses.csv", "CS,4999,Capstone,3")
    result = load(data, dry_run=True)
    assert result.counts["courses"] == 1
    assert snapshot() == before


def test_prereq_group_not_duplicated_on_reimport(app, data):
    load(data)
    before = PrereqGroup.query.count()
    result = load(data)
    assert result.counts["prereq_groups"] == 0
    assert PrereqGroup.query.count() == before


def test_cli_import_reports_errors_but_exits_nonzero(app, data):
    append(data / "courses.csv", "CS,4999,Capstone,three")
    append(data / "courses.csv", "CS,4998,Independent Study,3")
    result = app.test_cli_runner().invoke(args=["import-csv", str(data)])
    assert result.exit_code == 1
    assert "credits 'three' is not a whole number" in result.output
    assert "courses=1" in result.output  # the good row still landed
    assert Course.query.filter_by(subject="CS", number="4998").first() is not None


def test_cli_dry_run(app, data):
    result = app.test_cli_runner().invoke(args=["import-csv", str(data), "--dry-run"])
    assert result.exit_code == 0, result.output
    assert "Dry run, nothing saved" in result.output
