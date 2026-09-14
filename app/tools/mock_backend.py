"""Mock clinic backend. Three tools the state machine calls at transitions.

Availability is a weekly pattern from fixtures, expanded to concrete dates for
the next HORIZON_DAYS starting today. Slots that already started are dropped.
now() is a module attribute so tests can pin it. Booked slots leave the pool for the life of the process; reset()
clears bookings.
"""

from datetime import date, datetime, timedelta
from itertools import count

from app.tools import fixtures

WEEKDAYS = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]
HORIZON_DAYS = 14
SLOT_MINUTES = 30
# time_pref buckets, by hour of day: [start, end)
TIME_PREF_HOURS = {"morning": (0, 12), "afternoon": (12, 17), "evening": (17, 24)}

_bookings: list[dict] = []
_booked_slot_ids: set[str] = set()
_ids = count(1)


def now() -> datetime:
    return datetime.now()


def today() -> date:
    return now().date()


def reset() -> None:
    _bookings.clear()
    _booked_slot_ids.clear()


def fetch_patient(phone: str) -> dict | None:
    return next((p for p in fixtures.patients() if p["phone"] == phone), None)


def _expand_slots(doctor_id: str) -> list[dict]:
    """Concrete open slots for one doctor over the horizon, from the weekly pattern."""
    current = now()
    start = current.date()
    by_weekday: dict[str, list[str]] = {}
    for p in fixtures.slot_patterns():
        if p["doctor_id"] == doctor_id:
            by_weekday.setdefault(p["weekday"], []).extend(p["times"])
    out = []
    for offset in range(HORIZON_DAYS):
        d = start + timedelta(days=offset)
        for t in by_weekday.get(WEEKDAYS[d.weekday()], []):
            h, m = map(int, t.split(":"))
            s = datetime(d.year, d.month, d.day, h, m)
            if s <= current:
                continue  # already started today
            slot_id = f"{doctor_id}_{s.strftime('%Y%m%dT%H%M')}"
            if slot_id in _booked_slot_ids:
                continue
            out.append({
                "id": slot_id,
                "doctor_id": doctor_id,
                "start": s.isoformat(timespec="minutes"),
                "minutes": SLOT_MINUTES,
                "weekday": WEEKDAYS[d.weekday()],
            })
    return sorted(out, key=lambda s: s["start"])


def fetch_availability(doctor_id: str, days: list[date], time_pref: str | None = None) -> list[dict]:
    """Open slots for the doctor on the given dates. Empty `days` means any day in the horizon.
    `time_pref` (morning/afternoon/evening) narrows by hour; unknown values are ignored."""
    wanted = set(days)
    hours = TIME_PREF_HOURS.get(time_pref or "")
    out = []
    for s in _expand_slots(doctor_id):
        start = datetime.fromisoformat(s["start"])
        if wanted and start.date() not in wanted:
            continue
        if hours and not (hours[0] <= start.hour < hours[1]):
            continue
        out.append(s)
    return out


def create_booking(*, doctor_id: str, slot: dict, phone: str | None, session_type: str, patient_type: str) -> dict:
    if slot["id"] in _booked_slot_ids:
        raise ValueError(f"slot {slot['id']} already booked")
    _booked_slot_ids.add(slot["id"])
    doctor = fixtures.doctor_by_id(doctor_id)
    booking = {
        "booking_id": f"b{next(_ids):04d}",
        "doctor_id": doctor_id,
        "doctor_name": doctor["name"] if doctor else doctor_id,
        "slot_id": slot["id"],
        "start": slot["start"],
        "minutes": slot["minutes"],
        "phone": phone,
        "session_type": session_type,
        "patient_type": patient_type,
    }
    _bookings.append(booking)
    return booking


def bookings() -> list[dict]:
    return list(_bookings)
