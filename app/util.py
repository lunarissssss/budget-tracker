import os, re
from datetime import date, datetime
from zoneinfo import ZoneInfo

TZ = ZoneInfo(os.getenv("TZ", "Asia/Jakarta"))


def today() -> date:
    return datetime.now(TZ).date()


def parse_int(s, default=0) -> int:
    s = str(s or "").strip()
    d = re.sub(r"\D", "", s)
    if not d:
        return default
    return -int(d) if s.startswith("-") else int(d)


def parse_float(s):
    s = str(s or "").strip().replace(",", ".")
    try:
        return float(s) if s else None
    except ValueError:
        return None


def parse_date(s):
    try:
        return date.fromisoformat(s) if s else None
    except ValueError:
        return None


def rp(n, lang="id") -> str:
    if n is None:
        return "—"
    s = f"{abs(round(n)):,}"
    if lang == "id":
        s = s.replace(",", ".")
    return ("-" if n < 0 else "") + "Rp " + s
