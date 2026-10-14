# app/utils/date_utils.py
"""Helpers de périodes (dates UTC naïves, comme les colonnes DateTime du projet)."""

from datetime import datetime, timedelta, timezone

MONTH_NAMES = ['Janvier', 'Février', 'Mars', 'Avril', 'Mai', 'Juin', 'Juillet',
               'Août', 'Septembre', 'Octobre', 'Novembre', 'Décembre']


def _now():
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _day_bounds(day):
    start = datetime(day.year, day.month, day.day)
    return start, start + timedelta(days=1) - timedelta(microseconds=1)


def get_last_days(days):
    """Les `days` derniers jours (aujourd'hui inclus), du plus ancien au plus récent."""
    today = _now().date()
    result = []
    for offset in range(max(days, 0) - 1, -1, -1):
        day = today - timedelta(days=offset)
        start, end = _day_bounds(day)
        result.append({'date': day.isoformat(), 'start': start, 'end': end})
    return result


def get_last_months(months):
    """Les `months` derniers mois (mois courant inclus), du plus ancien au plus récent."""
    now = _now()
    result = []
    for offset in range(max(months, 0) - 1, -1, -1):
        year, month0 = divmod(now.year * 12 + (now.month - 1) - offset, 12)
        month = month0 + 1
        start = datetime(year, month, 1)
        next_start = datetime(year + (month == 12), month % 12 + 1, 1)
        result.append({
            'name': f'{MONTH_NAMES[month0]} {year}',
            'start': start,
            'end': next_start - timedelta(microseconds=1),
        })
    return result


def get_date_range(period):
    """(début, fin) de la période courante : day, week (lundi), month ou year."""
    now = _now()
    today_start, today_end = _day_bounds(now.date())
    if period == 'day':
        return today_start, today_end
    if period == 'week':
        return today_start - timedelta(days=now.weekday()), today_end
    if period == 'year':
        return datetime(now.year, 1, 1), today_end
    return datetime(now.year, now.month, 1), today_end  # month (défaut)
