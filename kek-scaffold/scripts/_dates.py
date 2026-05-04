"""Dynamic week-of-month and period-label helpers.

Replaces hardcoded W1_DATES..W5_DATES blocks. Convention matches the
existing dashboard:
  - Mon-Sun weeks
  - W1 = Mon-Sun week containing the 1st of the month (may start in
    the prior month)
  - W2..W5 follow consecutively (some months end in W4, but we always
    return 5 keys for UI stability)

Month resolution priority:
  1. KEK_REPORT_MONTH=YYYY-MM env var (manual pin)
  2. Latest date in the data (so the dashboard tracks the latest month
     that actually has data, not "today's month" which may be empty)
  3. Today's month (fallback)
"""
from datetime import date, timedelta
from os import environ


def _resolve_year_month(latest_date_iso=None):
    """Pin via env, else from latest_date_iso, else today's month."""
    override = environ.get('KEK_REPORT_MONTH')
    if override:
        y, m = override.split('-')
        return int(y), int(m)
    if latest_date_iso:
        y, m = latest_date_iso.split('-')[:2]
        return int(y), int(m)
    today = date.today()
    return today.year, today.month


def month_weeks(year=None, month=None, latest_date_iso=None):
    """Return {'w1': [iso, ...7 dates], 'w2': [...], ..., 'w5': [...]}."""
    if year is None or month is None:
        year, month = _resolve_year_month(latest_date_iso)
    first = date(year, month, 1)
    monday = first - timedelta(days=first.weekday())
    out = {}
    for i in range(5):
        start = monday + timedelta(days=7 * i)
        out[f'w{i+1}'] = [(start + timedelta(days=j)).isoformat() for j in range(7)]
    return out


def period_label(latest_date_iso, year=None, month=None):
    """e.g. 'April 2026 MTD (through 30 Apr)'."""
    if year is None or month is None:
        year, month = _resolve_year_month(latest_date_iso)
    first = date(year, month, 1)
    return f"{first.strftime('%B')} {year} MTD (through {latest_date_iso[-2:]} {first.strftime('%b')})"

