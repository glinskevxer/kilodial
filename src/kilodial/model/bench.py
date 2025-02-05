"""Test benches and the reference standards that make their results mean anything.

A bench result is only as good as the standard sitting behind it, and a standard
is only good between the day it was certified and the day its certificate runs
out. That window is the single most common reason a run gets voided months
later, usually when somebody is looking for something else, so the window lives
on the record rather than in a procedure.

The other thing a bench carries is what it can actually do. A single phase bench
cannot hold a load for a three element meter no matter how carefully the
technician sets it up, and a run that claims otherwise is a transcription error.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from kilodial.errors import BadInputError, RuleError
from kilodial.model.device import DeviceType
from kilodial.model.form import Service
from kilodial.units.electrical import Amperes, Volts
from kilodial.units.span import DateSpan, parse_date

# A shop standard is an order of magnitude better than the meters it judges.
# Anything looser than this is a working meter, not a standard.
WORST_UNCERTAINTY = Decimal("0.1")

POLYPHASE_SERVICES = frozenset(
    {
        Service.THREE_PHASE_3W_DELTA,
        Service.THREE_PHASE_4W_WYE,
        Service.THREE_PHASE_4W_DELTA,
    }
)


@dataclass(frozen=True)
class ReferenceStandard:
    """A certified standard, and the window its certificate covers."""

    serial: str
    maker: str
    model_code: str
    certificate: str
    certified_on: date
    certificate_due: date
    uncertainty: Decimal
    traceable_to: str

    @classmethod
    def build(
        cls,
        serial: object,
        *,
        maker: object,
        model_code: object,
        certificate: object,
        certified_on: object,
        certificate_due: object,
        uncertainty: object,
        traceable_to: object = "NIST",
    ) -> ReferenceStandard:
        first = parse_date(certified_on)
        last = parse_date(certificate_due)
        if last <= first:
            raise RuleError("a certificate has to run out after it was issued, not before")
        band = _uncertainty(uncertainty)
        return cls(
            serial=_text(serial, "standard serial", 24).upper(),
            maker=_text(maker, "maker name", 40),
            model_code=_text(model_code, "model code", 24),
            certificate=_text(certificate, "certificate number", 32).upper(),
            certified_on=first,
            certificate_due=last,
            uncertainty=band,
            traceable_to=_text(traceable_to, "traceability", 40),
        )

    @property
    def window(self) -> DateSpan:
        return DateSpan(self.certified_on, self.certificate_due)

    def is_valid_on(self, day: object) -> bool:
        """Whether a run on that day is backed by a live certificate."""
        return self.window.contains(day)

    def days_left_on(self, day: object) -> int:
        """Days of certificate remaining, negative once it has run out."""
        return (self.certificate_due - parse_date(day)).days

    def __str__(self) -> str:
        return f"{self.serial} cert {self.certificate} to {self.certificate_due.isoformat()}"


@dataclass(frozen=True)
class Bench:
    """A test position or bank of them, and what it can hold."""

    code: str
    name: str
    positions: int
    standard_serial: str
    max_amperes: Amperes
    max_volts: Volts
    polyphase: bool
    installed: date
    removed: date | None

    @classmethod
    def build(
        cls,
        code: object,
        name: object,
        *,
        positions: object,
        standard_serial: object,
        max_amperes: object,
        max_volts: object,
        polyphase: bool = False,
        installed: object,
        removed: object = None,
    ) -> Bench:
        count = _positions(positions)
        first = parse_date(installed)
        last = None if removed is None else parse_date(removed)
        if last is not None and last < first:
            raise RuleError("a bench cannot come out before it went in")
        return cls(
            code=_text(code, "bench code", 12).upper(),
            name=_text(name, "bench name", 60),
            positions=count,
            standard_serial=_text(standard_serial, "standard serial", 24).upper(),
            max_amperes=Amperes(max_amperes),
            max_volts=Volts(max_volts),
            polyphase=bool(polyphase),
            installed=first,
            removed=last,
        )

    @property
    def service_life(self) -> DateSpan:
        return DateSpan(self.installed, self.removed)

    def is_available_on(self, day: object) -> bool:
        return self.service_life.contains(day)

    def can_hold(self, device: DeviceType) -> bool:
        """Whether this bench can run that device type's sequence at all."""
        if device.form.service in POLYPHASE_SERVICES and not self.polyphase:
            return False
        if device.test_amperes.value > self.max_amperes.value:
            return False
        return device.voltage.value <= self.max_volts.value

    def refuse_unless_it_can_hold(self, device: DeviceType) -> None:
        """The same question, raising with a reason a technician can act on."""
        if device.form.service in POLYPHASE_SERVICES and not self.polyphase:
            raise RuleError(f"bench {self.code} is single phase and {device.key} is polyphase")
        if device.test_amperes.value > self.max_amperes.value:
            raise RuleError(
                f"bench {self.code} tops out at {self.max_amperes} and {device.key} "
                f"needs {device.test_amperes}"
            )
        if device.voltage.value > self.max_volts.value:
            raise RuleError(
                f"bench {self.code} tops out at {self.max_volts} and {device.key} "
                f"needs {device.voltage}"
            )

    def __str__(self) -> str:
        return f"{self.code} {self.name} ({self.positions} positions)"


def _text(value: object, what: str, limit: int) -> str:
    if not isinstance(value, str):
        raise BadInputError(f"cannot read a {what} from {type(value).__name__}")
    text = " ".join(value.split())
    if not text:
        raise BadInputError(f"a {what} cannot be blank")
    if len(text) > limit:
        raise BadInputError(f"a {what} runs to {limit} characters at most")
    return text


def _positions(value: object) -> int:
    if not isinstance(value, int) or isinstance(value, bool):
        raise BadInputError("a bench position count has to be a whole number")
    if value < 1 or value > 64:
        raise BadInputError("a bench has between 1 and 64 positions")
    return value


def _uncertainty(value: object) -> Decimal:
    try:
        band = Decimal(str(value).strip())
    except Exception:
        raise BadInputError(f"{value!r} is not an uncertainty") from None
    if band <= 0:
        raise BadInputError("an uncertainty has to be above zero")
    if band > WORST_UNCERTAINTY:
        raise RuleError(
            f"an uncertainty of {band} percent is looser than the {WORST_UNCERTAINTY} "
            "percent a shop standard has to hold"
        )
    return band


__all__ = ["POLYPHASE_SERVICES", "WORST_UNCERTAINTY", "Bench", "ReferenceStandard"]
