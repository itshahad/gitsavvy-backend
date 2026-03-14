from datetime import datetime, timedelta, timezone
import re


SHA1_RE = re.compile(r"^[0-9a-f]{40}$")


def validate_sha(v: str) -> str:
    if not SHA1_RE.match(v):
        raise ValueError("SHA1 must be a 40-char hex")
    return v


def is_stale(updated_at: datetime, stale_after: timedelta):
    return datetime.now(timezone.utc) - updated_at > stale_after
