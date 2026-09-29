"""Pure scheduling rules. No Flask or database imports allowed in this package."""
from .conflicts import Meeting, Section, meetings_overlap, find_conflicts, missing_prereqs  # noqa: F401
