"""Pure slot arithmetic - no database, no clock, no HTTP. Easy to unit/property test."""

from collections.abc import Iterable
from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta, tzinfo


@dataclass(frozen=True, slots=True)
class Slot:
    start: datetime  # aware, UTC
    end: datetime  # aware, UTC


def generate_slots(
    blocks: Iterable[tuple[time, time]], day: date, tz: tzinfo, slot_minutes: int
) -> list[Slot]:
    """Cut a doctor's working-hour blocks (clinic-local wall-clock) into slots for `day`.

    Rules:
    * a slot must FULLY fit inside a block (09:00-10:15 yields 09:00 and 09:30, not 10:00)
    * slots sit on the clinic-wide grid (:00/:30 for 30-minute slots), so a block that starts
      at 08:15 yields its first slot at 08:30. This keeps generator and validator consistent.
    * overlapping/duplicate blocks never produce duplicate slots
    """
    step = timedelta(minutes=slot_minutes)
    starts: set[datetime] = set()
    for block_start, block_end in blocks:
        start_min = block_start.hour * 60 + block_start.minute
        end_min = block_end.hour * 60 + block_end.minute
        minute = -(-start_min // slot_minutes) * slot_minutes  # round UP to the grid
        while minute + slot_minutes <= end_min:
            local = datetime.combine(day, time(minute // 60, minute % 60), tzinfo=tz)
            starts.add(local.astimezone(UTC))
            minute += slot_minutes
    return [Slot(s, s + step) for s in sorted(starts)]


def bookable(
    slots: Iterable[Slot], taken_starts: set[datetime], now: datetime, min_lead: timedelta
) -> list[Slot]:
    """Slots a patient could actually book right now: not taken and not too soon/past."""
    earliest = now + min_lead
    return [s for s in slots if s.start not in taken_starts and s.start >= earliest]
