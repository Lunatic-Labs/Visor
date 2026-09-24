"""Database models. First slice of specs/02-design-data-model.md.

Only the catalog/schedule tables for now; student and plan tables wait on scope (KAN-14).
"""
from __future__ import annotations

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
