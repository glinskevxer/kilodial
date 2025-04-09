"""Service points and the meter sets that sit on them.

A service point is a place where the utility sells electricity. A meter set is
one meter, and possibly a pair of instrument transformers, standing at that
point between two dates. The distinction matters because a meter moves and a
service point does not, and every adjustment question is asked about a point
over a period rather than about a meter.

The multiplier is the part people get wrong. What the customer is billed is the
register reading times a multiplier, and that multiplier is a product: the
current transformer ratio, the voltage transformer ratio, and the register
multiplier stamped on the meter. It gets programmed into the billing system by
hand, and a set whose programmed multiplier does not match the product of its
parts is a billing error of a completely different kind from a meter that drifted
half a percent. One is arithmetic and gets corrected in full; the other is
measurement and gets corrected within a tolerance.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from kilodial.errors import BadInputError, RuleError
from kilodial.model.form import Service
from kilodial.units.electrical import Volts
from kilodial.units.span import DateSpan, parse_date

MAX_MULTIPLIER = Decimal("100000")


@dataclass(frozen=True)
class ServicePoint:
    """Somewhere the utility sells electricity."""

    code: str
    account: str
    address: str
    service: Service
    voltage: Volts
    rate_code: str
    energised: date
    disconnected: date | None

    @classmethod
    def build(
        cls,
        code: object,
        *,
        account: object,
        address: object,
        service: Service,
        voltage: object,
        rate_code: object,
        energised: object,
        disconnected: object = None,
    ) -> ServicePoint:
        if not isinstance(service, Service):
            raise BadInputError("the service has to be one of the Service values")
        first = parse_date(energised)
        last = None if disconnected is None else parse_date(disconnected)
        if last is not None and last < first:
            raise RuleError("a service point cannot be disconnected before it was energised")
        return cls(
            code=_text(code, "service point code", 16).upper(),
            account=_text(account, "account number", 24).upper(),
            address=_text(address, "address", 80),
            service=service,
            voltage=Volts(voltage),
            rate_code=_text(rate_code, "rate code", 12).upper(),
            energised=first,
            disconnected=last,
        )

    @property
    def live(self) -> DateSpan:
        return DateSpan(self.energised, self.disconnected)

    def was_live_on(self, day: object) -> bool:
        return self.live.contains(day)

    def __str__(self) -> str:
        return f"{self.code} {self.address} ({self.rate_code})"


@dataclass(frozen=True)
class MeterSet:
    """One meter standing at one service point over one period."""

    point_code: str
    meter_serial: str
    ct_serial: str | None
    vt_serial: str | None
    register_multiplier: Decimal
    programmed_multiplier: Decimal
    set_on: date
    removed_on: date | None

    @classmethod
    def build(
        cls,
        point_code: object,
        meter_serial: object,
        *,
        ct_serial: object = None,
        vt_serial: object = None,
        register_multiplier: object = 1,
        programmed_multiplier: object,
        set_on: object,
        removed_on: object = None,
    ) -> MeterSet:
        first = parse_date(set_on)
        last = None if removed_on is None else parse_date(removed_on)
        if last is not None and last < first:
            raise RuleError("a meter cannot be pulled before it was set")
        return cls(
            point_code=_text(point_code, "service point code", 16).upper(),
            meter_serial=_text(meter_serial, "meter serial", 24).upper(),
            ct_serial=None if ct_serial is None else _text(ct_serial, "CT serial", 24).upper(),
            vt_serial=None if vt_serial is None else _text(vt_serial, "VT serial", 24).upper(),
            register_multiplier=_multiplier(register_multiplier, "register multiplier"),
            programmed_multiplier=_multiplier(programmed_multiplier, "programmed multiplier"),
            set_on=first,
            removed_on=last,
        )

    @property
    def span(self) -> DateSpan:
        return DateSpan(self.set_on, self.removed_on)

    @property
    def is_transformer_rated(self) -> bool:
        return self.ct_serial is not None or self.vt_serial is not None

    @property
    def is_current(self) -> bool:
        return self.removed_on is None

    def was_set_on(self, day: object) -> bool:
        return self.span.contains(day)

    def pulled_on(self, day: object) -> MeterSet:
        """Close the set off, refusing to close one that is already closed."""
        if self.removed_on is not None:
            raise RuleError(
                f"{self.meter_serial} was already pulled off {self.point_code} "
                f"on {self.removed_on.isoformat()}"
            )
        when = parse_date(day)
        if when < self.set_on:
            raise RuleError("a meter cannot be pulled before it was set")
        return MeterSet(
            point_code=self.point_code,
            meter_serial=self.meter_serial,
            ct_serial=self.ct_serial,
            vt_serial=self.vt_serial,
            register_multiplier=self.register_multiplier,
            programmed_multiplier=self.programmed_multiplier,
            set_on=self.set_on,
            removed_on=when,
        )

    def __str__(self) -> str:
        return (
            f"{self.meter_serial} at {self.point_code} from {self.set_on.isoformat()} "
            f"x{self.programmed_multiplier.normalize():f}"
        )


def _multiplier(value: object, what: str) -> Decimal:
    try:
        number = Decimal(str(value).strip())
    except Exception:
        raise BadInputError(f"{value!r} is not a {what}") from None
    if number <= 0:
        raise BadInputError(f"a {what} has to be above zero")
    if number > MAX_MULTIPLIER:
        raise BadInputError(f"a {what} of {number} is not a real installation")
    return number


def _text(value: object, what: str, limit: int) -> str:
    if not isinstance(value, str):
        raise BadInputError(f"cannot read a {what} from {type(value).__name__}")
    text = " ".join(value.split())
    if not text:
        raise BadInputError(f"a {what} cannot be blank")
    if len(text) > limit:
        raise BadInputError(f"a {what} runs to {limit} characters at most")
    return text


__all__ = ["MAX_MULTIPLIER", "MeterSet", "ServicePoint"]
