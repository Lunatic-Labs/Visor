"""Vercel entry point: exposes the Flask app as a single serverless function.

Every /api/* request is rewritten here (see vercel.json). The real app lives in
backend/visor; this file only puts it on sys.path and builds it.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

from visor import create_app  # noqa: E402

app = create_app()
