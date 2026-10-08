"""Database models.

Catalog/schedule tables from specs/02-design-data-model.md, plus the transfer-equivalency tables
from specs/03-design-equivalencies.md. Student and plan tables wait on scope (KAN-14).
"""
from __future__ import annotations

from datetime import datetime, timezone

from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import UniqueConstraint

db = SQLAlchemy()


class Term(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(10), unique=True, nullable=False)  # e.g. 2027SP
    name = db.Column(db.String(40), nullable=False)


class Course(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    subject = db.Column(db.String(8), nullable=False)
    number = db.Column(db.String(8), nullable=False)
    title = db.Column(db.String(120), nullable=False)
    credits = db.Column(db.Integer, nullable=False, default=3)
    __table_args__ = (UniqueConstraint("subject", "number"),)

    @property
    def code(self) -> str:
        return f"{self.subject} {self.number}"


class Section(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    course_id = db.Column(db.ForeignKey("course.id"), nullable=False)
    term_id = db.Column(db.ForeignKey("term.id"), nullable=False)
    section_no = db.Column(db.String(4), nullable=False)
    capacity = db.Column(db.Integer, nullable=False, default=30)
    enrolled_count = db.Column(db.Integer, nullable=False, default=0)
    course = db.relationship("Course")
    term = db.relationship("Term")
    meetings = db.relationship("MeetingTime", cascade="all, delete-orphan")
    __table_args__ = (UniqueConstraint("course_id", "term_id", "section_no"),)


class MeetingTime(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    section_id = db.Column(db.ForeignKey("section.id"), nullable=False)
    days = db.Column(db.String(7), nullable=False)  # e.g. MWF, TR
    start_time = db.Column(db.Time, nullable=False)
    end_time = db.Column(db.Time, nullable=False)


class PrereqGroup(db.Model):
    """A course's prereqs = AND of these groups; each group = OR of its items."""
    id = db.Column(db.Integer, primary_key=True)
    course_id = db.Column(db.ForeignKey("course.id"), nullable=False)
    items = db.relationship("PrereqItem", cascade="all, delete-orphan")


class PrereqItem(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    group_id = db.Column(db.ForeignKey("prereq_group.id"), nullable=False)
    required_course_id = db.Column(db.ForeignKey("course.id"), nullable=False)
    required_course = db.relationship("Course")


# --- Transfer equivalencies (specs/03-design-equivalencies.md, KAN-38) -------------------------

EQUIV_KINDS = ("direct", "elective", "none")
EQUIV_STATUSES = ("confirmed", "proposed", "rejected")
EQUIV_SOURCES = ("sis_import", "registrar", "professor", "rules")
REVIEW_DECISIONS = ("pending", "approved", "rejected")


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class School(db.Model):
    """A school students transfer from."""
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), unique=True, nullable=False)
    state = db.Column(db.String(2))
    kind = db.Column(db.String(20), nullable=False, default="community_college")
    catalog_url = db.Column(db.String(300))
    active = db.Column(db.Boolean, nullable=False, default=True)


class ExternalCourse(db.Model):
    """A course at another school, as it appears in that school's catalog."""
    id = db.Column(db.Integer, primary_key=True)
    school_id = db.Column(db.ForeignKey("school.id"), nullable=False)
    subject = db.Column(db.String(8), nullable=False)
    number = db.Column(db.String(8), nullable=False)
    title = db.Column(db.String(160), nullable=False)
    credits = db.Column(db.Integer)
    description = db.Column(db.Text)
    catalog_year = db.Column(db.String(4), nullable=False)
    source_url = db.Column(db.String(300))
    school = db.relationship("School")
    __table_args__ = (UniqueConstraint("school_id", "subject", "number", "catalog_year"),)

    @property
    def code(self) -> str:
        return f"{self.subject} {self.number}"


class Equivalency(db.Model):
    """What an external course counts as at Lipscomb.

    course_id is null for kind 'elective' (general elective credit) and 'none' (does not transfer).
    Only a person sets status 'confirmed'; rules may only propose.
    """
    id = db.Column(db.Integer, primary_key=True)
    external_course_id = db.Column(db.ForeignKey("external_course.id"), nullable=False)
    course_id = db.Column(db.ForeignKey("course.id"))
    kind = db.Column(db.String(10), nullable=False, default="direct")
    status = db.Column(db.String(10), nullable=False, default="proposed")
    source = db.Column(db.String(12), nullable=False, default="registrar")
    confidence = db.Column(db.Float)
    decided_by = db.Column(db.String(120))
    decided_at = db.Column(db.DateTime(timezone=True))
    notes = db.Column(db.Text, nullable=False, default="")
    updated_at = db.Column(db.DateTime(timezone=True), nullable=False, default=_utcnow, onupdate=_utcnow)
    external_course = db.relationship("ExternalCourse")
    course = db.relationship("Course")
    reviews = db.relationship("EquivalencyReview", cascade="all, delete-orphan",
                              order_by="EquivalencyReview.requested_at")


class EquivalencyReview(db.Model):
    """A request for a professor to weigh in on an equivalency."""
    id = db.Column(db.Integer, primary_key=True)
    equivalency_id = db.Column(db.ForeignKey("equivalency.id"), nullable=False)
    requested_by = db.Column(db.String(120), nullable=False)
    requested_at = db.Column(db.DateTime(timezone=True), nullable=False, default=_utcnow)
    reviewer = db.Column(db.String(120), nullable=False)
    decision = db.Column(db.String(10), nullable=False, default="pending")
    decided_at = db.Column(db.DateTime(timezone=True))
    notes = db.Column(db.Text, nullable=False, default="")
