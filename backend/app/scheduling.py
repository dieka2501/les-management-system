from __future__ import annotations

from dataclasses import dataclass


DAY_NAMES = ["Senin", "Selasa", "Rabu", "Kamis", "Jumat", "Sabtu", "Minggu"]


@dataclass(frozen=True)
class TimeRange:
    start: str
    end: str


def parse_time(value: str) -> int:
    try:
        hour_text, minute_text = value.split(":", 1)
        hour = int(hour_text)
        minute = int(minute_text)
    except (AttributeError, ValueError) as exc:
        raise ValueError(f"Format jam tidak valid: {value!r}. Gunakan HH:MM.") from exc

    if not (0 <= hour <= 23 and 0 <= minute <= 59):
        raise ValueError(f"Jam di luar rentang: {value!r}.")
    return hour * 60 + minute


def format_time(minutes: int) -> str:
    hour, minute = divmod(minutes, 60)
    return f"{hour:02d}:{minute:02d}"


def ranges_overlap(start_a: str, end_a: str, start_b: str, end_b: str) -> bool:
    start_a_minutes = parse_time(start_a)
    end_a_minutes = parse_time(end_a)
    start_b_minutes = parse_time(start_b)
    end_b_minutes = parse_time(end_b)
    return start_a_minutes < end_b_minutes and end_a_minutes > start_b_minutes


def contains_range(outer_start: str, outer_end: str, inner_start: str, inner_end: str) -> bool:
    return parse_time(outer_start) <= parse_time(inner_start) and parse_time(inner_end) <= parse_time(outer_end)


def validate_time_range(start: str, end: str) -> None:
    if parse_time(start) >= parse_time(end):
        raise ValueError("Jam selesai harus lebih besar dari jam mulai.")


def normalize_day(value: int | str) -> int:
    day = int(value)
    if not 0 <= day <= 6:
        raise ValueError("Hari harus bernilai 0 sampai 6.")
    return day
