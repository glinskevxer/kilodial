"""Device types: the nameplate, shared by every meter of that make and model.

A meter's serial number is unique and almost nothing hangs off it. Everything
the bench needs to know comes from the type: the form, the class, the watthour
constant, whether it is an induction disc or a solid state register. Grouping
meters by type is also what makes periodic sample testing possible, because a
sample is only meaningful across a population that is genuinely alike.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from kilodial.errors import BadInputError, RuleError
from kilodial.model.demand import Interval, interval_of
from kilodial.model.form import Form, MeterClass, Technology, form, meter_class
from kilodial.units.electrical import Amperes, Volts
from kilodial.units.span import DateSpan, parse_date
from kilodial.units.text import number, positive, tidy

# A watthour constant outside this range means somebody read the nameplate
# wrong. Real ones run from about 0.03 on a solid state pulse output to 14.4 on
# an old polyphase disc.
MIN_KH = Decimal("0.005")
MAX_KH = Decimal("100")


@dataclass(frozen=True)
class DeviceType:
    """One make and model of meter, as the shop stocks it."""

    manufacturer: str
    model_code: str
    form: Form
    meter_class: MeterClass
    voltage: Volts
    kh: Decimal
    technology: Technology
    register_ratio: Decimal | None
    demand_capable: bool
    demand_interval: Interval | None
    introduced: date
    retired: date | None

    @classmethod
    def build(
        cls,
        manufacturer: object,
        model_code: object,
        *,
        form_code: object,
        class_code: object,
        voltage: object,
        kh: object,
        technology: Technology,
        register_ratio: object = None,
        demand_capable: bool = False,
        demand_interval: object = None,
        introduced: object,
        retired: object = None,
    ) -> DeviceType:
        """Build a type, refusing a nameplate that cannot exist.

        The two checks worth naming: a class 10 or class 20 meter has to sit on
        a transformer rated form, because that class of meter has no winding
        heavy enough to carry a service; and an induction meter has to have a
        register ratio, because without one nobody can read its dials.
        """
        maker = tidy(manufacturer, "manufacturer name")
        model = tidy(model_code, "model code", 24)
        the_form = form(form_code)
        the_class = meter_class(class_code)
        constant = _kh(kh)
        if not isinstance(technology, Technology):
            raise BadInputError("the technology has to be one of the Technology values")
        if the_class.is_transformer_class and not the_form.transformer_rated:
            raise RuleError(
                f"class {the_class} is a transformer rated class and form "
                f"{the_form} is self contained"
            )
        ratio = _ratio(register_ratio, technology)
        window = _demand_interval(demand_interval, bool(demand_capable))
        first = parse_date(introduced)
        last = None if retired is None else parse_date(retired)
        if last is not None and last < first:
            raise RuleError(f"{maker} {model} cannot retire before it was introduced")
        return cls(
            manufacturer=maker,
            model_code=model,
            form=the_form,
            meter_class=the_class,
            voltage=Volts(voltage),
            kh=constant,
            technology=technology,
            register_ratio=ratio,
            demand_capable=bool(demand_capable),
            demand_interval=window,
            introduced=first,
            retired=last,
        )

    @property
    def key(self) -> str:
        """How a type is named on the command line and in a report."""
        return f"{self.manufacturer}/{self.model_code}"

    @property
    def elements(self) -> Decimal:
        return self.form.elements

    @property
    def test_amperes(self) -> Amperes:
        """The current a full load point is run at."""
        return Amperes(self.meter_class.test_amperes)

    @property
    def light_load_amperes(self) -> Amperes:
        """Ten percent of test amperes, where a worn bearing shows up first."""
        return Amperes(self.meter_class.test_amperes / 10)

    @property
    def power_factor_amperes(self) -> Amperes:
        """Half of test amperes, which is where the lagging point is run."""
        return Amperes(self.meter_class.test_amperes / 2)

    @property
    def is_transformer_rated(self) -> bool:
        return self.form.transformer_rated or self.meter_class.is_transformer_class

    @property
    def registers_demand(self) -> bool:
        """Whether a run on this type is expected to carry a demand point."""
        return self.demand_capable and self.demand_interval is not None

    @property
    def is_disc(self) -> bool:
        return self.technology is Technology.INDUCTION

    @property
    def service_life(self) -> DateSpan:
        return DateSpan(self.introduced, self.retired)

    def was_current_on(self, day: object) -> bool:
        """Whether the shop was still buying this type on a given day."""
        return self.service_life.contains(day)

    def __str__(self) -> str:
        return f"{self.key} form {self.form} {self.meter_class}"


def _kh(value: object) -> Decimal:
    constant = number(value, "watthour constant")
    if constant < MIN_KH or constant > MAX_KH:
        raise BadInputError(f"a watthour constant of {constant} is outside anything real")
    return constant


def _demand_interval(value: object, demand_capable: bool) -> Interval | None:
    """A demand meter has to say what window it is programmed for.

    The nameplate does not carry it, because the same meter is programmed for
    fifteen minutes on one service and thirty on the next. It is a property of
    how the shop stocks the type, which is why it sits here rather than on the
    installation.
    """
    if value is None:
        if demand_capable:
            raise RuleError("a demand meter has to say which interval it registers over")
        return None
    if not demand_capable:
        raise RuleError("a type that does not register demand has no demand interval")
    return interval_of(value)


def _ratio(value: object, technology: Technology) -> Decimal | None:
    if value is None:
        if technology is Technology.INDUCTION:
            raise RuleError("an induction meter has to carry a register ratio")
        return None
    return positive(value, "register ratio")


__all__ = ["MAX_KH", "MIN_KH", "DeviceType"]
