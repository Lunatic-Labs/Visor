"""Class-schedule import (KAN-25). Every row here is invented; the real export stays in data/private/."""
from datetime import time

import pytest

from visor.models import Course, MeetingTime, Section, Term
from visor.schedule_import import (SECTION_NO_MAX, DatedMeetings, load_schedule, parse_days, parse_meetings,
                                   parse_schedule, parse_term, parse_time)

HEADER = ("Course Code,Section Code,Course Name,Term,Start Date,End Date,Instructor,Start Time,End Time,"
          "Meeting Days,Total Seats,Seats Filled,Seats Available,Credit Hours,Course Level,Delivery Method,"
          "Location,Course Notes")


def row(code="DEMO1013", sec="01", name="Demo Course", term="2027 Spring Full Term", start="01:00 PM",
        end="01:50 PM", days="MonWedFri", seats="24", filled="0", credits="3.0"):
    return (f'"{code}","{sec}","{name}","{term}","2027-01-06","2027-04-29","Staff, Staff","{start}","{end}",'
            f'"{days}","{seats}","{filled}","{int(seats) - int(filled)}","{credits}","Undergraduate",'
            f'"On Ground","Demo 1 (24)",""')


JUNK = '"","","","All2027 Spring Full Term2027 Spring Term I","","","","","","","","","","","","","",""'


def write(tmp_path, *rows, name="schedule.csv"):
    p = tmp_path / name
    p.write_text("\n".join([HEADER, *rows]) + "\n", encoding="utf-8")
    return p


# --- pure helpers ----------------------------------------------------------------------------

def test_parse_time():
    assert parse_time("01:00 PM") == time(13, 0)
    assert parse_time("11:55 AM") == time(11, 55)
    assert parse_time("12:00 PM") == time(12, 0)
    assert parse_time("12:00 AM") == time(0, 0)
    assert parse_time("17:30") == time(17, 30)
    for bad in ("", "noon", "13:00 PM", "9:75 AM", "25:00"):
        with pytest.raises(ValueError):
            parse_time(bad)


def test_parse_days():
    assert parse_days("MonWedFri") == "MWF"
    assert parse_days("TuesThurs") == "TR"
    assert parse_days("Thurs") == "R"
    assert parse_days("ThursFriSat") == "RFS"
    assert parse_days("MonTuesWedThursFri") == "MTWRF"
    for bad in ("", "Someday", "MonXWed"):
        with pytest.raises(ValueError):
            parse_days(bad)


def test_parse_meetings_single_pair_and_none():
    assert parse_meetings("MonWed", "11:00 AM", "12:15 PM") == [("MW", time(11, 0), time(12, 15))]
    assert parse_meetings("", "", "") == []


def test_parse_meetings_two_patterns_are_paired_up():
    assert parse_meetings("MonWed/TuesThurs", "09:00 AM/09:25 AM", "09:50 AM/10:40 AM") == [
        ("MW", time(9, 0), time(9, 50)), ("TR", time(9, 25), time(10, 40))]
    assert parse_meetings("Mon/Wed", "01:00 PM/01:00 PM", "01:50 PM/02:45 PM")[1] == ("W", time(13, 0), time(14, 45))


def test_parse_meetings_problems():
    with pytest.raises(DatedMeetings):
        parse_meetings("01/30, 01/31", "09:00", "15:00")
    with pytest.raises(ValueError, match="not after start"):
        parse_meetings("Thurs", "11:55 AM", "02:35 AM")
    with pytest.raises(ValueError, match="line up"):
        parse_meetings("Mon/Wed", "01:00 PM", "01:50 PM/02:45 PM")


def test_parse_term_sub_terms_share_one_term():
    assert parse_term("2027 Spring Full Term") == ("2027SP", "Spring 2027")
    assert parse_term("2027 Spring Term II") == ("2027SP", "Spring 2027")
    assert parse_term("2026 Fall Term I") == ("2026FA", "Fall 2026")
    with pytest.raises(ValueError):
        parse_term("Sometime in 2027")


# --- parse_schedule --------------------------------------------------------------------------

def records(*rows):
    import csv
    import io
    return list(csv.DictReader(io.StringIO("\n".join([HEADER, *rows]))))


def test_junk_row_is_skipped_silently():
    plan = parse_schedule(records(row(), JUNK))
    assert len(plan.sections) == 1 and plan.issues == []


def test_long_and_blank_section_codes_skip_that_section_but_keep_the_course():
    plan = parse_schedule(records(row(sec="LO1.1"), row(code="DEMO2013", sec=""), row(code="DEMO3013", sec="02")))
    assert [s.section_no for s in plan.sections] == ["02"]
    assert plan.skipped_sections == 2
    assert {"DEMO1013", "DEMO2013", "DEMO3013"} == {f"{s}{n}" for s, n in plan.courses}
    assert any(f"longer than {SECTION_NO_MAX}" in i for i in plan.issues) and any("no section code" in i for i in plan.issues)


def test_bad_and_dated_meetings_keep_the_section_without_meetings():
    plan = parse_schedule(records(
        row(sec="01", days="Thurs", start="11:55 AM", end="02:35 AM"),
        row(sec="02", days="01/30, 03/06", start="09:00", end="15:00"),
        row(sec="03", days="", start="", end="")))
    assert [s.meetings for s in plan.sections] == [[], [], []]
    assert (plan.bad_meeting_sections, plan.dated_meeting_sections) == (1, 1)
    assert len(plan.issues) == 2 and plan.skipped_sections == 0


def test_course_gets_most_common_title_and_highest_credits():
    plan = parse_schedule(records(
        row(sec="01", name="Internship", credits="0.0"), row(sec="02", name="Internship", credits="3.0"),
        row(sec="03", name="Internship: Marketing", credits="6.0")))
    assert plan.courses[("DEMO", "1013")] == ("Internship", 6)


def test_missing_column_is_an_error():
    with pytest.raises(ValueError, match="missing columns"):
        parse_schedule([{"Course Code": "X1"}])


def test_fractional_credits_are_reported_not_guessed():
    plan = parse_schedule(records(row(credits="1.5")))
    assert plan.sections == [] and "whole number" in plan.issues[0]


# --- load_schedule ---------------------------------------------------------------------------

def test_load_adds_terms_courses_sections_and_meetings(app, tmp_path):
    path = write(tmp_path, row(code="DEMO1013", sec="01"), row(code="DEMO1013", sec="02", days="TuesThurs"),
                 row(code="DEMO2013", sec="01", days="", start="", end=""),
                 row(code="DEMO3013", sec="01", term="2030 Fall Term I"), JUNK)
    result = load_schedule(path)
    c = result.counts
    assert (c["courses_added"], c["sections_added"], c["meetings_added"], c["terms_added"]) == (3, 4, 3, 1)
    assert c["sections_without_meetings"] == 1
    assert Term.query.filter_by(code="2030FA").one().name == "Fall 2030"
    sec = (Section.query.join(Course).filter(Course.number == "1013", Section.section_no == "02").one())
    assert [(m.days, m.start_time) for m in sec.meetings] == [("TR", time(13, 0))]


def test_reimport_is_idempotent(app, tmp_path):
    path = write(tmp_path, row(sec="01"), row(sec="02"), row(code="DEMO2013", days="MonWed/TuesThurs",
                                                              start="09:00 AM/09:25 AM", end="09:50 AM/10:40 AM"))
    load_schedule(path)
    before = (Course.query.count(), Section.query.count(), MeetingTime.query.count())
    c = load_schedule(path).counts
    assert (c["courses_added"], c["sections_added"], c["sections_updated"], c["meetings_added"]) == (0, 0, 0, 0)
    assert (Course.query.count(), Section.query.count(), MeetingTime.query.count()) == before


def test_reimport_updates_seats(app, tmp_path):
    load_schedule(write(tmp_path, row(seats="24", filled="0")))
    c = load_schedule(write(tmp_path, row(seats="30", filled="12"))).counts
    assert c["sections_updated"] == 1 and c["sections_added"] == 0
    sec = Section.query.join(Course).filter(Course.number == "1013").one()
    assert (sec.capacity, sec.enrolled_count) == (30, 12)


def test_existing_courses_are_never_overwritten(app, tmp_path):
    before = Course.query.filter_by(subject="CS", number="1113").one()
    title, credits = before.title, before.credits
    result = load_schedule(write(tmp_path, row(code="CS1113", name="A Different Title", credits="4.0")))
    assert result.counts["courses_already_there"] == 1 and result.counts["existing_courses_differ"] == 1
    assert result.counts["courses_added"] == 0
    after = Course.query.filter_by(subject="CS", number="1113").one()
    assert (after.title, after.credits) == (title, credits)


def test_dry_run_saves_nothing(app, tmp_path):
    before = (Term.query.count(), Course.query.count(), Section.query.count())
    result = load_schedule(write(tmp_path, row(), row(term="2031 Fall Full Term")), dry_run=True)
    assert result.counts["sections_added"] == 2 and result.counts["terms_added"] == 1
    assert (Term.query.count(), Course.query.count(), Section.query.count()) == before


def test_cli_import_schedule(app, tmp_path):
    path = write(tmp_path, row(), row(sec="LO1.1"))
    runner = app.test_cli_runner()
    dry = runner.invoke(args=["import-schedule", str(path), "--dry-run"])
    assert dry.exit_code == 0 and "Dry run, nothing saved" in dry.output and "sections_added=1" in dry.output
    assert Course.query.filter_by(subject="DEMO").count() == 0
    real = runner.invoke(args=["import-schedule", str(path)])
    assert real.exit_code == 0 and "longer than 4 characters" in real.output
    assert Course.query.filter_by(subject="DEMO").count() == 1


# --- upload endpoint and "last updated" ------------------------------------------------------

def upload(client, path, query="", name=None):
    import io
    return client.post(f"/api/import/schedule{query}",
                       data={"schedule": (io.BytesIO(path.read_bytes()), name or path.name)},
                       content_type="multipart/form-data")


def term(client, code="2027SP"):
    return next(t for t in client.get("/api/terms").json if t["code"] == code)


def test_terms_have_no_update_time_until_a_schedule_is_loaded(client):
    assert term(client)["schedule_updated_at"] is None and term(client)["schedule_file"] is None


def test_upload_loads_the_schedule_and_stamps_the_time(app, client, tmp_path):
    path = write(tmp_path, row(sec="01"), row(sec="02", days="TuesThurs"), JUNK, name="Spring 2027.csv")
    r = upload(client, path)
    assert r.status_code == 200 and r.json["ok"] is True and r.json["dry_run"] is False
    assert r.json["counts"]["sections_in_file"] == 2 and r.json["counts"]["sections_added"] == 2
    t = term(client)
    assert t["schedule_file"] == "Spring 2027.csv"
    assert t["schedule_updated_at"].endswith("Z")


def test_reupload_refreshes_seats_and_moves_the_time_forward(app, client, tmp_path):
    from visor.models import ScheduleImport
    upload(client, write(tmp_path, row(seats="24", filled="0"), name="first.csv"))
    first = term(client)["schedule_updated_at"]
    r = upload(client, write(tmp_path, row(seats="24", filled="9"), name="second.csv"))
    assert r.json["counts"]["sections_updated"] == 1 and r.json["counts"]["sections_added"] == 0
    sec = Section.query.join(Course).filter(Course.number == "1013").one()
    assert sec.enrolled_count == 9
    assert term(client)["schedule_file"] == "second.csv" and term(client)["schedule_updated_at"] >= first
    assert ScheduleImport.query.count() == 2


def test_a_reupload_with_no_changes_still_counts_as_updated(app, client, tmp_path):
    from visor.models import ScheduleImport
    path = write(tmp_path, row())
    upload(client, path)
    r = upload(client, path)
    assert r.json["counts"]["sections_updated"] == 0 and ScheduleImport.query.count() == 2


def test_dry_run_upload_saves_nothing_and_does_not_stamp(app, client, tmp_path):
    r = upload(client, write(tmp_path, row(), row(term="2031 Fall Full Term")), "?dry_run=1")
    assert r.status_code == 200 and r.json["dry_run"] is True and r.json["counts"]["sections_added"] == 2
    assert Course.query.filter_by(subject="DEMO").count() == 0
    assert term(client)["schedule_updated_at"] is None


def test_upload_reports_problem_rows(app, client, tmp_path):
    r = upload(client, write(tmp_path, row(), row(sec="LO1.1")))
    assert r.status_code == 200 and r.json["ok"] is False
    assert r.json["counts"]["sections_skipped"] == 1 and "longer than 4" in r.json["issues"][0]


def test_upload_rejects_the_wrong_file_without_changing_anything(app, client, tmp_path):
    from visor.models import ScheduleImport
    wrong = tmp_path / "courses.csv"
    wrong.write_text("subject,number,title,credits\nCS,4999,Capstone,3\n")
    r = upload(client, wrong)
    assert r.status_code == 400 and "isn't the class schedule" in r.json["error"]
    assert upload(client, write(tmp_path, JUNK, name="empty.csv")).status_code == 400
    binary = tmp_path / "x.csv"
    binary.write_bytes(b"\xff\xfe\x00\x00 not text")
    assert upload(client, binary).status_code == 400
    assert client.post("/api/import/schedule", data={}, content_type="multipart/form-data").status_code == 400
    assert ScheduleImport.query.count() == 0


def test_cli_import_also_stamps_the_time(app, client, tmp_path):
    app.test_cli_runner().invoke(args=["import-schedule", str(write(tmp_path, row(), name="cli.csv"))])
    assert term(client)["schedule_file"] == "cli.csv"
