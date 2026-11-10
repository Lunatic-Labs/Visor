"""HTTP upload for the registrar's catalog/section CSVs (KAN-25).

Thin wrapper around seed.load(): saves whichever of terms/courses/prereqs/sections.csv were
actually uploaded into a temp directory under the names load() expects, imports just those,
and returns the same counts/errors load() produces. All the row validation, line-numbered
error reporting, and idempotent-upsert behavior lives in seed.py; this module only deals with
getting uploaded files onto disk in the shape load() already understands.
"""
from __future__ import annotations

import csv
import os
import tempfile
from pathlib import Path

from flask import Blueprint, jsonify, request

from .auth import write_guard
from .schedule_import import RemovalTooLarge, load_schedule
from .seed import load

bp = Blueprint("catalog_import", __name__, url_prefix="/api")
bp.before_request(write_guard)  # every route here writes (KAN-46)

FILES = ("terms", "courses", "prereqs", "sections")


@bp.post("/import/catalog")
def import_catalog():
    """multipart/form-data with any subset of file fields named terms, courses, prereqs,
    sections (each a .csv). ?dry_run=1 checks everything without saving."""
    uploaded = {name: request.files[name] for name in FILES
               if name in request.files and request.files[name].filename}
    if not uploaded:
        return jsonify({"error": "upload at least one of: " + ", ".join(f"{n}.csv" for n in FILES)}), 400

    dry_run = request.args.get("dry_run", "").lower() in ("1", "true", "yes")

    with tempfile.TemporaryDirectory() as tmp:
        d = Path(tmp)
        for name, file in uploaded.items():
            file.save(d / f"{name}.csv")
        result = load(d, dry_run=dry_run, only=[f"{name}.csv" for name in uploaded])

    return jsonify({"ok": result.ok, "dry_run": dry_run, "counts": result.counts, "errors": result.errors})


@bp.post("/import/schedule")
def import_schedule():
    """multipart/form-data with one file field, schedule: the CSV from the university's public
    class-schedule page (Export > CSV). ?dry_run=1 checks it without saving. ?remove_missing=1
    also removes sections the file no longer lists (409 if that looks like a partial export). A
    real run also records the time, which the Schedule screen shows as "last updated"."""
    file = request.files.get("schedule")
    if file is None or not file.filename:
        return jsonify({"error": "choose the class schedule CSV to upload"}), 400
    dry_run = request.args.get("dry_run", "").lower() in ("1", "true", "yes")
    remove_missing = request.args.get("remove_missing", "").lower() in ("1", "true", "yes")

    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "schedule.csv"
        file.save(path)
        try:
            result = load_schedule(path, dry_run=dry_run, filename=os.path.basename(file.filename),
                                   remove_missing=remove_missing)
        except RemovalTooLarge as e:
            return jsonify({"error": str(e)}), 409
        except (UnicodeDecodeError, csv.Error):
            return jsonify({"error": "that doesn't look like a CSV file Visor can read"}), 400
        except ValueError as e:
            return jsonify({"error": f"that isn't the class schedule export: {e}"}), 400

    if result.counts["sections_in_file"] == 0:
        return jsonify({"error": "no sections found in that file. Is it the class schedule (Export > CSV)?"}), 400
    return jsonify({"ok": not result.issues, "dry_run": dry_run, "remove_missing": remove_missing,
                    "counts": result.counts, "issues": result.issues})
