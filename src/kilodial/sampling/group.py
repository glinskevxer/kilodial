"""Homogeneous groups: the population a sample is allowed to speak for.

Periodic testing does not test every meter. It tests a sample of a group and
extends or shortens that whole group's interval on the strength of it, which is
only defensible if the group really is homogeneous. A group that quietly mixes
two manufacturers, or twenty year old meters with two year old ones, produces a
sample mean that describes nothing.

So a group is a set of criteria rather than a list of serials, and membership is
recomputed every time it is asked for. A list would go stale the first time a
meter was scrapped, and the denominator of a sample plan going stale is the one
error nobody notices until a regulator asks how the interval was arrived at.

Criteria left out are not criteria. A group with no class named takes every
class, which is usually wrong and is occasionally exactly what a small utility
wants for its handful of polyphase meters.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from kilodial.errors import BadInputError, RuleError
from kilodial.model.device import DeviceType
from kilodial.model.form import MeterClass, Technology, meter_class
from kilodial.model.meter import Meter, MeterState
from kilodial.units.span import DateSpan, parse_date
from kilodial.units.text import key, tidy

# A meter in one of these is not in service and does not belong in a population
# whose whole purpose is to describe what the utility has out on customers.
OUT_OF_POPULATION = frozenset({MeterState.SCRAP, MeterState.LOST})


@dataclass(frozen=True)
class Group:
    """A homogeneous population, defined by what is in it rather than by who."""

    code: str
    name: str
    device_keys: tuple[str, ...]
    meter_class: MeterClass | None
    technology: Technology | None
    form_codes: tuple[str, ...]
    acquired_from: date | None
    acquired_to: date | None

    @classmethod
    def build(
        cls,
        code: object,
        name: object,
        *,
        device_keys: list[str] | None = None,
        class_code: object = None,
        technology: Technology | None = None,
        form_codes: list[str] | None = None,
        acquired_from: object = None,
        acquired_to: object = None,
    ) -> Group:
        first = None if acquired_from is None else parse_date(acquired_from)
        last = None if acquired_to is None else parse_date(acquired_to)
        if first is not None and last is not None and last < first:
            raise RuleError("a group's acquisition window cannot end before it starts")
        if technology is not None and not isinstance(technology, Technology):
            raise BadInputError("the technology has to be a Technology")
        return cls(
            code=key(code, "group code", 16),
            name=tidy(name, "group name", 60),
            device_keys=tuple(sorted({k.strip() for k in device_keys or [] if k.strip()})),
            meter_class=None if class_code is None else meter_class(class_code),
            technology=technology,
            form_codes=tuple(sorted({f.strip().upper() for f in form_codes or [] if f.strip()})),
            acquired_from=first,
            acquired_to=last,
        )

    @property
    def window(self) -> DateSpan | None:
        """The acquisition window, or nothing when the group is open ended."""
        if self.acquired_from is None and self.acquired_to is None:
            return None
        start = self.acquired_from or date(1900, 1, 1)
        return DateSpan(start, self.acquired_to)

    @property
    def is_open(self) -> bool:
        """True when the group has no criteria at all and takes everything."""
        return not any(
            (
                self.device_keys,
                self.meter_class,
                self.technology,
                self.form_codes,
                self.acquired_from,
                self.acquired_to,
            )
        )

    def criteria(self) -> list[str]:
        """The criteria in words, for a report that has to justify a sample."""
        said: list[str] = []
        if self.device_keys:
            said.append("type " + " or ".join(self.device_keys))
        if self.meter_class is not None:
            said.append(f"class {self.meter_class}")
        if self.technology is not None:
            said.append(f"{self.technology}")
        if self.form_codes:
            said.append("form " + " or ".join(self.form_codes))
        window = self.window
        if window is not None:
            said.append(f"acquired {window}")
        return said or ["every meter"]

    def takes(self, meter: Meter, device: DeviceType | None = None) -> bool:
        """Whether a meter belongs in this population."""
        if meter.state in OUT_OF_POPULATION:
            return False
        if self.device_keys and meter.device_key not in self.device_keys:
            return False
        window = self.window
        if window is not None and not window.contains(meter.acquired):
            return False
        if self.meter_class is None and self.technology is None and not self.form_codes:
            return True
        if device is None:
            raise RuleError(
                f"group {self.code} judges on the device type and none was supplied "
                f"for meter {meter.serial}"
            )
        if self.meter_class is not None and device.meter_class is not self.meter_class:
            return False
        if self.technology is not None and device.technology is not self.technology:
            return False
        return not (self.form_codes and device.form.code not in self.form_codes)

    def needs_device(self) -> bool:
        """Whether membership can be decided from the meter record alone."""
        return bool(self.meter_class or self.technology or self.form_codes)

    def __str__(self) -> str:
        return f"{self.code} {self.name}"


__all__ = ["OUT_OF_POPULATION", "Group"]
