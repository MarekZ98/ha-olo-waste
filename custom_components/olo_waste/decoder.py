"""OLO pickup rows -> waste rules -> collection dates (pure, no Home Assistant imports)."""

from __future__ import annotations

import re
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import date, timedelta

from .api import PickupRow
from .const import WASTE_TYPES

_CYCLE_RE = re.compile(r"\[(.*)\]")
_WEEKDAYS_RE = re.compile(r"[1-7]+")
_SEASON_RE = re.compile(r"([0-9]{2})/([0-9]{2})\s*-\s*([0-9]{2})/([0-9]{2})")
_MONTH_DAY_RE = re.compile(r"(0[1-9]|1[0-2])-(0[1-9]|[12][0-9]|3[01])")


@dataclass(frozen=True)
class Season:
    """Yearly season "MM-DD" to "MM-DD" (inclusive); may wrap the new year."""

    from_md: str
    to_md: str


@dataclass(frozen=True)
class IsoWeekCycle:
    """The rule applies in ISO weeks where (week - 1) mod length == index."""

    length: int
    index: int


@dataclass(frozen=True)
class WasteRule:
    """One pickup rule: a weekday, repeated every `interval_weeks` weeks from `anchor_date`."""

    kind: str
    # ISO weekday, 1 = Monday ... 7 = Sunday (the weekday of `anchor_date`).
    weekday: int
    interval_weeks: int
    anchor_date: date
    season: Season | None = None
    iso_week_cycle: IsoWeekCycle | None = None
    # Last date (inclusive) the rule applies; OLO publishes schedules per calendar year.
    valid_until: date | None = None


@dataclass(frozen=True)
class DecodeResult:
    """Decoded rules plus the rows that were skipped."""

    rules: list[WasteRule]
    # wasteTypes without a mapping (skipped).
    unknown_types: list[str]
    # Rows whose frequency / season could not be read (skipped), as "wasteType: frequency".
    invalid: list[str]


@dataclass(frozen=True)
class Collection:
    """One pickup of `kind` on `date`."""

    kind: str
    date: date


# One week of a cycle: the ISO weekdays with a pickup ([] = "-").
type CycleWeek = list[int]


def iso_week_of(d: date) -> int:
    """ISO 8601 week number (1-53)."""
    return d.isocalendar().week


def parse_cycle(text: str) -> list[CycleWeek] | None:
    """ "[14,14]" -> [[1, 4], [1, 4]]; None when malformed."""
    match = _CYCLE_RE.fullmatch(text.strip())
    if not match or not match.group(1):
        return None
    weeks: list[CycleWeek] = []
    for raw in match.group(1).split(","):
        element = raw.strip()
        if element == "-":
            weeks.append([])
        elif _WEEKDAYS_RE.fullmatch(element):
            weeks.append(sorted({int(c) for c in element}))
        else:
            return None
    return weeks if 0 < len(weeks) <= 8 else None


def parse_season(text: str) -> Season | None:
    """ "01/04-31/10" -> Season("04-01", "10-31"); None when malformed."""
    match = _SEASON_RE.fullmatch(text.strip())
    if not match:
        return None
    from_day, from_month, to_day, to_month = match.groups()
    from_md = f"{from_month}-{from_day}"
    to_md = f"{to_month}-{to_day}"
    if _MONTH_DAY_RE.fullmatch(from_md) and _MONTH_DAY_RE.fullmatch(to_md):
        return Season(from_md, to_md)
    return None


def shortest_period(weeks: list[CycleWeek]) -> int:
    """The shortest period p (dividing the length) the cycle repeats with."""
    n = len(weeks)
    for p in range(1, n):
        if n % p != 0:
            continue
        if all(week == weeks[i % p] for i, week in enumerate(weeks)):
            return p
    return n


def anchor_for(reference: date, weekday: int, length: int, index: int) -> date:
    """The latest date <= `reference` on `weekday` in an ISO week with (week - 1) mod length == index."""
    day = reference - timedelta(days=(reference.isoweekday() - weekday + 7) % 7)
    for _ in range(9):
        if (iso_week_of(day) - 1) % length == index:
            return day
        day -= timedelta(weeks=1)
    return day


def decode_rows(rows: Iterable[PickupRow], reference: date, valid_until: date | None = None) -> DecodeResult:
    """OLO pickup rows -> waste rules.

    `frequency` lists one cycle per season (";"); season i is the i-th range of
    `frequency_season` (none = all year). A cycle [a,b,...] of length n applies
    element (ISO week - 1) mod n; an element lists ISO weekdays as digits,
    "-" = no pickup. One rule per weekday per cycle position, the cycle reduced
    to its shortest period ([14,14] = weekly).
    """
    rules: dict[tuple[object, ...], WasteRule] = {}
    unknown_types: dict[str, None] = {}
    invalid: list[str] = []
    seen: set[tuple[str, str, str]] = set()
    for row in rows:
        row_key = (row.waste_type, row.frequency, row.frequency_season or "")
        if row_key in seen:
            continue
        seen.add(row_key)
        kind = WASTE_TYPES.get(row.waste_type.strip())
        if kind is None:
            unknown_types[row.waste_type] = None
            continue
        cycles = [parse_cycle(part) for part in row.frequency.split(";")]
        season_texts = row.frequency_season.split(",") if row.frequency_season and row.frequency_season.strip() else []
        seasons = [parse_season(part) for part in season_texts]
        seasons_ok = len(cycles) == 1 if not seasons else len(seasons) == len(cycles)
        if any(c is None for c in cycles) or any(s is None for s in seasons) or not seasons_ok:
            invalid.append(f"{row.waste_type}: {row.frequency}")
            continue
        for i, cycle in enumerate(cycles):
            if cycle is None:
                continue
            season = seasons[i] if i < len(seasons) else None
            length = shortest_period(cycle)
            for index in range(length):
                for weekday in cycle[index]:
                    rule = WasteRule(
                        kind=kind,
                        weekday=weekday,
                        interval_weeks=length,
                        anchor_date=anchor_for(reference, weekday, length, index),
                        season=season,
                        iso_week_cycle=IsoWeekCycle(length, index) if length > 1 else None,
                        valid_until=valid_until,
                    )
                    key = (
                        kind,
                        weekday,
                        length,
                        index,
                        season.from_md if season else "",
                        season.to_md if season else "",
                    )
                    rules[key] = rule

    def order(r: WasteRule) -> tuple[str, str, int, int]:
        return (
            r.kind,
            r.season.from_md if r.season else "",
            r.iso_week_cycle.index if r.iso_week_cycle else 0,
            r.weekday,
        )

    return DecodeResult(rules=sorted(rules.values(), key=order), unknown_types=list(unknown_types), invalid=invalid)


def in_season(d: date, season: Season) -> bool:
    """Is `d` inside the yearly season (inclusive, may wrap the new year)?"""
    md = f"{d.month:02d}-{d.day:02d}"
    if season.from_md <= season.to_md:
        return season.from_md <= md <= season.to_md
    return md >= season.from_md or md <= season.to_md


def rule_applies(rule: WasteRule, d: date) -> bool:
    """Does `rule` produce a collection on `d` (already on the rule's weekday / interval)?"""
    if rule.valid_until is not None and d > rule.valid_until:
        return False
    if rule.season is not None and not in_season(d, rule.season):
        return False
    if rule.iso_week_cycle is not None:
        length = max(1, rule.iso_week_cycle.length)
        return (iso_week_of(d) - 1) % length == rule.iso_week_cycle.index
    return True


def collections(rules: Iterable[WasteRule], start: date, end: date) -> list[Collection]:
    """Collections in [start, end] (inclusive), sorted by date then kind."""
    found: set[tuple[date, str]] = set()
    for rule in rules:
        # An ISO week cycle is checked per week: step one week, `rule_applies` filters.
        step_days = (1 if rule.iso_week_cycle is not None else max(1, round(rule.interval_weeks))) * 7
        offset = (start - rule.anchor_date).days
        # ceil(offset / step_days) * step_days
        d = rule.anchor_date + timedelta(days=-(-offset // step_days) * step_days)
        while d <= end:
            if rule_applies(rule, d):
                found.add((d, rule.kind))
            d += timedelta(days=step_days)
    return [Collection(kind=kind, date=d) for d, kind in sorted(found) if start <= d <= end]
