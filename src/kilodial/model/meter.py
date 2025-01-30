"""The individual meter, and the states it is allowed to move between.

A meter is an asset with a serial number and a life. The reason the state
machine is spelled out rather than left to whoever is writing the command is
that two of the transitions carry money with them: a meter that goes to scrap
takes its history out of the sample population, and a meter that goes back to
stock without a passing as left test is a meter the shop cannot defend.
"""

from __future__ import annotations

import enum
import re
from dataclasses import dataclass, replace
from datetime import date

from kilodial.errors import BadInputError, StateError
from kilodial.units.span import parse_date

SERIAL_PATTERN = re.compile(r"^[A-Z0-9][A-Z0-9-]{2,19}$")


class MeterState(enum.Enum):
    """Where a meter is, in the only terms the shop cares about."""

    RECEIVED = "received"
    STOCK = "stock"
    SET = "set"
    PULLED = "pulled"
    REPAIR = "repair"
    SCRAP = "scrap"
    LOST = "lost"

    def __str__(self) -> str:
        return self.value


# Every move the shop allows, and nothing else. Scrap is terminal on purpose:
# a meter that comes back from the scrap bin is a records problem, not a
# transition, and it gets a new asset record.
TRANSITIONS: dict[MeterState, frozenset[MeterState]] = {
    MeterState.RECEIVED: frozenset({MeterState.STOCK, MeterState.REPAIR, MeterState.SCRAP}),
    MeterState.STOCK: frozenset({MeterState.SET, MeterState.REPAIR, MeterState.SCRAP}),
    MeterState.SET: frozenset({MeterState.PULLED, MeterState.LOST}),
    MeterState.PULLED: frozenset({MeterState.STOCK, MeterState.REPAIR, MeterState.SCRAP}),
    MeterState.REPAIR: frozenset({MeterState.STOCK, MeterState.SCRAP}),
    MeterState.LOST: frozenset({MeterState.PULLED, MeterState.SCRAP}),
    MeterState.SCRAP: frozenset(),
}

# States in which the meter is physically in the shop and can be put on a bench.
BENCHABLE = frozenset({MeterState.RECEIVED, MeterState.STOCK, MeterState.PULLED, MeterState.REPAIR})


def normalise_serial(value: object) -> str:
    """Serials are upper case, trimmed, and have to look like a serial."""
    if not isinstance(value, str):
        raise BadInputError(f"cannot read a serial from {type(value).__name__}")
    serial = value.strip().upper().replace(" ", "")
    if not SERIAL_PATTERN.match(serial):
        raise BadInputError(f"{value!r} is not a meter serial number")
    return serial


@dataclass(frozen=True)
class Meter:
    """One asset, tracked from receipt to scrap."""

    serial: str
    device_key: str
    state: MeterState
    acquired: date
    owner: str
    seal: str | None
    retired_on: date | None

    @classmethod
    def receive(
        cls,
        serial: object,
        device_key: str,
        *,
        acquired: object,
        owner: str = "utility",
        seal: object = None,
    ) -> Meter:
        """Book a meter in for the first time."""
        return cls(
            serial=normalise_serial(serial),
            device_key=device_key,
            state=MeterState.RECEIVED,
            acquired=parse_date(acquired),
            owner=_owner(owner),
            seal=_seal(seal),
            retired_on=None,
        )

    @property
    def is_in_shop(self) -> bool:
        return self.state in BENCHABLE

    @property
    def is_retired(self) -> bool:
        return self.state is MeterState.SCRAP

    def can_move_to(self, state: MeterState) -> bool:
        return state in TRANSITIONS[self.state]

    def moved_to(self, state: MeterState, *, on: object = None) -> Meter:
        """Return the meter in its new state, or refuse the move.

        Moving to scrap records the day it happened, because the retirement date
        is what takes the meter out of the sampling population and a group whose
        denominator drifts cannot be defended.
        """
        if not isinstance(state, MeterState):
            raise BadInputError("that is not a meter state")
        if state is self.state:
            raise StateError(f"meter {self.serial} is already {state}")
        if not self.can_move_to(state):
            raise StateError(f"meter {self.serial} cannot go from {self.state} to {state}")
        retired = self.retired_on
        if state is MeterState.SCRAP:
            if on is None:
                raise BadInputError("scrapping a meter needs the day it happened")
            retired = parse_date(on)
        return replace(self, state=state, retired_on=retired)

    def resealed(self, seal: object) -> Meter:
        """Put a new seal on, or cut the old one off with None."""
        return replace(self, seal=_seal(seal))

    def __str__(self) -> str:
        return f"{self.serial} ({self.device_key}, {self.state})"


def _owner(value: object) -> str:
    if not isinstance(value, str):
        raise BadInputError(f"cannot read an owner from {type(value).__name__}")
    owner = " ".join(value.split())
    if not owner:
        raise BadInputError("an owner cannot be blank")
    if len(owner) > 40:
        raise BadInputError("an owner runs to 40 characters at most")
    return owner


def _seal(value: object) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise BadInputError(f"cannot read a seal from {type(value).__name__}")
    seal = value.strip().upper()
    if not seal:
        return None
    if len(seal) > 16 or not seal.isalnum():
        raise BadInputError(f"{value!r} is not a seal number")
    return seal


__all__ = ["BENCHABLE", "SERIAL_PATTERN", "TRANSITIONS", "Meter", "MeterState", "normalise_serial"]
