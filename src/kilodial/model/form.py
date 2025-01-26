"""Meter forms and classes, and what they say about how a meter is wired.

The form number on a nameplate is the single most load bearing fact about a
meter. It fixes how many measuring elements the meter has, how many wires the
service has, whether the meter sits straight in the line or behind instrument
transformers, and which test sequence the bench has to run. Nearly every rule
downstream reads one of those four things rather than the form itself.

Numbers here follow the ANSI C12.10 form designations as they are used in the
field. A trailing S is a socket meter and a trailing A is bottom connected.
"""

from __future__ import annotations

import enum
from dataclasses import dataclass
from decimal import Decimal

from kilodial.errors import BadInputError


class Service(enum.Enum):
    """The service a form is built for, written the way a crew says it."""

    SINGLE_PHASE_2W = "1P2W"
    SINGLE_PHASE_3W = "1P3W"
    NETWORK_3W = "NET3W"
    THREE_PHASE_3W_DELTA = "3P3W"
    THREE_PHASE_4W_WYE = "3P4WY"
    THREE_PHASE_4W_DELTA = "3P4WD"

    def __str__(self) -> str:
        return self.value


class Mounting(enum.Enum):
    """How the meter is held: in a socket, or bolted to a base."""

    SOCKET = "socket"
    BOTTOM = "bottom"

    def __str__(self) -> str:
        return self.value


class Technology(enum.Enum):
    """What is doing the measuring inside."""

    INDUCTION = "induction"
    SOLID_STATE = "solid state"
    HYBRID = "hybrid"

    def __str__(self) -> str:
        return self.value


@dataclass(frozen=True)
class Form:
    """One row of the form table."""

    code: str
    elements: Decimal
    service: Service
    transformer_rated: bool
    mounting: Mounting

    @property
    def is_polyphase(self) -> bool:
        return self.service not in (Service.SINGLE_PHASE_2W, Service.SINGLE_PHASE_3W)

    @property
    def is_self_contained(self) -> bool:
        return not self.transformer_rated

    def __str__(self) -> str:
        return self.code


def _form(
    code: str,
    elements: str,
    service: Service,
    transformer_rated: bool,
    mounting: Mounting = Mounting.SOCKET,
) -> Form:
    return Form(code, Decimal(elements), service, transformer_rated, mounting)


# The forms this utility actually stocks. A form outside the table is not a
# typo to be guessed at: it is a meter nobody in the shop knows how to test.
FORMS: dict[str, Form] = {
    f.code: f
    for f in (
        _form("1S", "1", Service.SINGLE_PHASE_2W, False),
        _form("2S", "1", Service.SINGLE_PHASE_3W, False),
        _form("3S", "1", Service.SINGLE_PHASE_3W, True),
        _form("4S", "1", Service.SINGLE_PHASE_3W, True),
        _form("5S", "2", Service.THREE_PHASE_3W_DELTA, True),
        _form("6S", "2", Service.THREE_PHASE_3W_DELTA, False),
        _form("9S", "3", Service.THREE_PHASE_4W_WYE, True),
        _form("12S", "2", Service.NETWORK_3W, False),
        _form("16S", "3", Service.THREE_PHASE_4W_WYE, False),
        _form("25S", "2", Service.THREE_PHASE_4W_DELTA, False),
        _form("36S", "2.5", Service.THREE_PHASE_4W_WYE, True),
        _form("45S", "2", Service.THREE_PHASE_4W_WYE, False),
        _form("48S", "3", Service.THREE_PHASE_4W_WYE, True),
        _form("10A", "1", Service.SINGLE_PHASE_3W, False, Mounting.BOTTOM),
        _form("29A", "2", Service.THREE_PHASE_3W_DELTA, True, Mounting.BOTTOM),
    )
}


def form(code: object) -> Form:
    """Look a form up by its code, case and whitespace insensitive."""
    if not isinstance(code, str):
        raise BadInputError(f"cannot read a meter form from {type(code).__name__}")
    key = code.strip().upper()
    if key not in FORMS:
        raise BadInputError(f"{code!r} is not a meter form this shop stocks")
    return FORMS[key]


class MeterClass(enum.Enum):
    """Continuous current rating, and with it the bench test current.

    The class is the meter's maximum continuous amperes. The test ampere rating
    is a much smaller number that the sequence is run at, and the pairing is
    fixed by the class rather than chosen by the shop.
    """

    CL10 = ("CL10", "10", "2.5")
    CL20 = ("CL20", "20", "2.5")
    CL100 = ("CL100", "100", "15")
    CL200 = ("CL200", "200", "30")
    CL320 = ("CL320", "320", "30")
    CL480 = ("CL480", "480", "50")

    def __init__(self, code: str, continuous: str, test_amperes: str) -> None:
        self.code = code
        self.continuous = Decimal(continuous)
        self.test_amperes = Decimal(test_amperes)

    @property
    def is_transformer_class(self) -> bool:
        """CL10 and CL20 meters only ever sit behind current transformers."""
        return self in (MeterClass.CL10, MeterClass.CL20)

    def __str__(self) -> str:
        return self.code


def meter_class(code: object) -> MeterClass:
    """Look a class up by code, tolerating the bare number crews write."""
    if isinstance(code, MeterClass):
        return code
    if not isinstance(code, str):
        raise BadInputError(f"cannot read a meter class from {type(code).__name__}")
    key = code.strip().upper()
    if not key.startswith("CL"):
        key = f"CL{key}"
    for member in MeterClass:
        if member.code == key:
            return member
    raise BadInputError(f"{code!r} is not a meter class this shop stocks")


__all__ = [
    "FORMS",
    "Form",
    "MeterClass",
    "Mounting",
    "Service",
    "Technology",
    "form",
    "meter_class",
]
