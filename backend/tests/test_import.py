"""CSV import (KAN-25)."""
import shutil
from pathlib import Path

import pytest

from visor.models import Course, MeetingTime, Section, Term
from visor.seed import CsvImportError, load

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
    counts = load(data)
    assert counts["courses"] == 1 and counts["sections"] == 1 and counts["meetings"] == 1
    assert Course.query.filter_by(subject="CS", number="4999").one().title == "Capstone"


def test_reimport_updates_enrollment(app, data):
    text = (data / "sections.csv").read_text()
    (data / "sections.csv").write_text(text.replace("2027SP,CS 3213,01,30,30", "2027SP,CS 3213,01,35,31"))
    counts = load(data)
    assert counts["updated"] == 1 and counts["sections"] == 0
    course = Course.query.filter_by(subject="CS", number="3213").one()
    sec = Section.query.filter_by(course_id=course.id, section_no="01").one()
    assert (sec.capacity, sec.enrolled_count) == (35, 31)


def test_bad_rows_are_all_reported_and_nothing_is_saved(app, data):
    before = snapshot()
    append(data / "courses.csv", "CS,4999,Capstone,three")
    append(data / "sections.csv", "2027SP,CS 3213,03,30,0,MWF,11:00,10:00")
    append(data / "sections.csv", "2027SP,CS 3213,04,30,0,MXF,11:00,11:50")
    append(data / "sections.csv", "2027SP,CS 3213,05,30,0,MWF,9am,11:50")
    append(data / "sections.csv", "2099FA,CS 3213,06,30,0,MWF,11:00,11:50")
    append(data / "prereqs.csv", "CS 3213,CS 3213")

    with pytest.raises(CsvImportError) as exc:
        load(data)

    errors = "\n".join(exc.value.errors)
    assert "courses.csv line" in errors and "credits 'three' is not a whole number" in errors
    assert "end 10:00 is not after start 11:00" in errors
    assert "days 'MXF'" in errors
    assert "start '9am' is not a 24-hour HH:MM time" in errors
    assert "unknown term '2099FA'" in errors
    assert "can't be its own prerequisite" in errors
    assert len(exc.value.errors) == 6
    assert snapshot() == before


def test_error_gives_line_number(app, data):
    lines = (data / "sections.csv").read_text().splitlines()
    append(data / "sections.csv", "2027SP,NOPE 1000,01,30,0,MWF,11:00,11:50")
    with pytest.raises(CsvImportError) as exc:
        load(data)
    assert exc.value.errors == [f"sections.csv line {len(lines) + 1}: unknown course 'NOPE 1000'"]


def test_missing_file_and_column(app, data):
    (data / "terms.csv").unlink()
    (data / "courses.csv").write_text("subject,number,title\nCS,1113,Programming I\n")
    with pytest.raises(CsvImportError) as exc:
        load(data)
    assert "terms.csv: file not found" in exc.value.errors
    assert "courses.csv: missing column(s) credits" in exc.value.errors


def test_excel_bom_and_whitespace(app, data):
    (data / "courses.csv").write_text("﻿subject,number,title,credits\n CS , 4999 , Capstone , 3 \n\n",
                                      encoding="utf-8")
    counts = load(data)
    assert counts["courses"] == 1
    assert Course.query.filter_by(subject="CS", number="4999").one().credits == 3


def test_dry_run_saves_nothing(app, data):
    before = snapshot()
    append(data / "courses.csv", "CS,4999,Capstone,3")
    assert load(data, dry_run=True)["courses"] == 1
    assert snapshot() == before


def test_cli_import_reports_errors(app, data):
    append(data / "courses.csv", "CS,4999,Capstone,three")
    result = app.test_cli_runner().invoke(args=["import-csv", str(data)])
    assert result.exit_code == 1
    assert "credits 'three' is not a whole number" in result.output
    assert "nothing was imported" in result.output


def test_cli_dry_run(app, data):
    result = app.test_cli_runner().invoke(args=["import-csv", str(data), "--dry-run"])
    assert result.exit_code == 0, result.output
    assert "Dry run, nothing saved" in result.output
