"""Session state and an in-memory session store (v1)."""

from dataclasses import dataclass, field


@dataclass
class Session:
    session_id: str
    state: str = "GREET"
    turn: int = 0
    patient_type: str | None = None  # "new" | "returning"
    problem: str | None = None
    category: str | None = None
    doctor_id: str | None = None
    phone: str | None = None
    session_type: str | None = None  # "first_consultation" (new, set by code) | "therapy" | "followup"
    days: list[str] = field(default_factory=list)
    offered_slots: list[dict] = field(default_factory=list)
    chosen_slot: dict | None = None
    booking: dict | None = None
    # Re-ask counts per state, the ASK_DAYS no-slots loop, and corrections taken. Reset rules live in state_machine.py.
    loop_counts: dict = field(default_factory=lambda: {"reask": {}, "no_slots": 0, "corrections": 0})


class SessionStore:
    def __init__(self) -> None:
        self._sessions: dict[str, Session] = {}

    def get_or_create(self, session_id: str) -> Session:
        if session_id not in self._sessions:
            self._sessions[session_id] = Session(session_id=session_id)
        return self._sessions[session_id]

    def reset(self, session_id: str) -> Session:
        self._sessions[session_id] = Session(session_id=session_id)
        return self._sessions[session_id]
