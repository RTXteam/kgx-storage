"""
Rules for deriving folder "modified" timestamps from S3 object keys.

S3 has no directory mtime. The UI uses the latest object LastModified under a
prefix. Ingest-side paths (source_data, transform_*) change on every sync and
make release folders look freshly updated even when graph artifacts under e.g.
1.0/ are older.
"""

from __future__ import annotations

# Segments that reflect pipeline churn rather than primary dataset age.
_MODIFIED_EXCLUDE_EXACT: frozenset[str] = frozenset({"source_data"})


def exclude_key_for_folder_modified_date(prefix: str, key: str) -> bool:
    """
    Return True if this object should not set the folder's displayed modified time.

    Always exclude the prefix placeholder object (key equals the folder prefix).
    """
    if not key.startswith(prefix):
        return True
    rel = key[len(prefix) :]
    if rel.endswith("/"):
        rel = rel[:-1]
    if not rel:
        return True
    for segment in rel.split("/"):
        if not segment:
            continue
        if segment in _MODIFIED_EXCLUDE_EXACT:
            return True
        if segment.startswith("transform_"):
            return True
    return False
