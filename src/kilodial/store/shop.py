"""One handle on the whole book.

The repositories are deliberately narrow and none of them knows about another
except where a reference has to be checked. The Shop is where they are put
together, and it is the only place in the package that is allowed to reach
across two of them to answer a question.

``judge`` is the one worth reading. Judging a run needs the device type behind
the meter, the standard the run names and the bench it names, and every one of
those is a lookup that a caller would otherwise have to remember to do. Getting
one of them wrong is how a run ends up judged against the standard that is on
the bench today rather than the one that was on it in March.
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from types import TracebackType

from kilodial.errors import NotFoundError, RuleError
from kilodial.install.multiplier import InstalledAccuracy, accuracy_of
from kilodial.install.point import MeterSet
from kilodial.model.device import DeviceType
from kilodial.model.run import BenchRun, RunKind
from kilodial.store.benches import BenchRepository, StandardRepository
from kilodial.store.billing import BillingRepository
from kilodial.store.book import Book, open_migrated
from kilodial.store.complaints import ComplaintRepository
from kilodial.store.devices import DeviceRepository
from kilodial.store.groups import GroupRepository, PlanRepository
from kilodial.store.installs import InstallRepository, ServicePointRepository
from kilodial.store.meters import MeterRepository
from kilodial.store.orders import OrderRepository
from kilodial.store.runs import RunRepository
from kilodial.store.tamper import TamperRepository
from kilodial.store.technicians import TechnicianRepository
from kilodial.store.transformers import TransformerRepository
from kilodial.testing.demand import DemandVerdict, judge_demand
from kilodial.testing.verdict import Outcome, Verdict, judge
from kilodial.units.electrical import PowerFactor
from kilodial.units.registration import Registration

IN_SERVICE = frozenset({RunKind.AS_FOUND, RunKind.REFEREE})


class Shop:
    """Every repository on one book, plus the questions that span them."""

    def __init__(self, book: Book) -> None:
        self.book = book
        conn = book.connection
        self.devices = DeviceRepository(conn)
        self.meters = MeterRepository(conn)
        self.standards = StandardRepository(conn)
        self.benches = BenchRepository(conn)
        self.runs = RunRepository(conn)
        self.transformers = TransformerRepository(conn)
        self.points = ServicePointRepository(conn)
        self.installs = InstallRepository(conn)
        self.groups = GroupRepository(conn)
        self.plans = PlanRepository(conn)
        self.billing = BillingRepository(conn)
        self.complaints = ComplaintRepository(conn)
        self.orders = OrderRepository(conn)
        self.technicians = TechnicianRepository(conn)
        self.tamper = TamperRepository(conn)

    @property
    def path(self) -> Path:
        return self.book.path

    def close(self) -> None:
        self.book.close()

    def __enter__(self) -> Shop:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        self.close()

    @contextmanager
    def transaction(self) -> Iterator[Shop]:
        with self.book.transaction():
            yield self

    def device_for(self, serial: str) -> DeviceType:
        """The device type behind a meter, by serial."""
        return self.devices.get(self.meters.get(serial).device_key)

    def judge(self, reference: str) -> Verdict:
        """Judge a stored run against everything it names."""
        return self.judge_run(self.runs.get(reference))

    def judge_run(self, run: BenchRun) -> Verdict:
        """Judge a run in hand, resolving what it names off this book."""
        device = self.device_for(run.meter_serial)
        standard = self.standards.get(run.standard_serial)
        bench = self.benches.get(run.bench_code)
        return judge(
            run,
            device,
            standard=standard,
            bench=bench,
            signer=self.technicians.find(run.badge),
        )

    def judge_demand(self, reference: str) -> DemandVerdict:
        """Judge a stored run's demand half against the type it was run on."""
        return self.judge_demand_run(self.runs.get(reference))

    def judge_demand_run(self, run: BenchRun) -> DemandVerdict:
        """The same question about a run in hand."""
        device = self.device_for(run.meter_serial)
        return judge_demand(
            run,
            device,
            interval=device.demand_interval,
            measured_seconds=run.demand_seconds,
        )

    def history(self, serial: str) -> list[tuple[BenchRun, Verdict]]:
        """Every run on a meter with the verdict each one earns today."""
        return [(r, self.judge_run(r)) for r in self.runs.for_meter(serial)]

    def installed_accuracy(
        self,
        point_code: str,
        *,
        on: object = None,
        power_factor: PowerFactor | None = None,
    ) -> InstalledAccuracy:
        """What the installation at a point registers, transformers included.

        The meter's share comes from its most recent usable as found run, which
        is the only run kind that says anything about a meter as the customer
        had it. A meter with no such run has no installed accuracy, and that is
        an answer rather than a zero.
        """
        meter_set = (
            self.installs.current(point_code)
            if on is None
            else self.installs.on_day(point_code, on)
        )
        if meter_set is None:
            raise RuleError(f"nothing was set at {point_code.strip().upper()}")
        return self.accuracy_of_set(meter_set, power_factor=power_factor)

    def accuracy_of_set(
        self,
        meter_set: MeterSet,
        *,
        reading: Registration | None = None,
        power_factor: PowerFactor | None = None,
    ) -> InstalledAccuracy:
        """The same question about a set already in hand.

        ``reading`` names the meter's own registration when the caller already
        has the run it wants used. A customer requested test has to be answered
        on the run the customer asked for, not on whichever run happens to be
        latest, so that path passes its reading in rather than letting this
        method go looking.
        """
        if reading is None:
            reading = self.in_service_registration(meter_set.meter_serial)
        return accuracy_of(
            meter_set,
            reading,
            current=self.transformers.find(meter_set.ct_serial),
            voltage=self.transformers.find(meter_set.vt_serial),
            power_factor=power_factor,
        )

    def in_service_registration(self, serial: str) -> Registration:
        """The meter's own registration, from its latest usable in service run.

        In service means as found or referee: both measure the meter as the
        customer had it. An as left run is the shop's own certification and an
        acceptance run happened before the meter went out, so neither says
        anything about what the customer was billed.
        """
        for run in reversed(self.runs.for_meter(serial)):
            if run.kind not in IN_SERVICE:
                continue
            verdict = self.judge_run(run)
            if verdict.outcome.is_usable and verdict.registration is not None:
                return verdict.registration
        raise RuleError(f"meter {serial.strip().upper()} has no usable as found run")

    def unusable_runs(self) -> list[tuple[BenchRun, Verdict]]:
        """Every run the shop cannot rely on, with the reason it cannot."""
        found = []
        for run in self.runs.all():
            try:
                verdict = self.judge_run(run)
            except NotFoundError:
                continue
            if verdict.outcome in (Outcome.VOID, Outcome.SUSPECT):
                found.append((run, verdict))
        return found

    def summary(self) -> dict[str, int]:
        """Row counts, for the doctor and for a smoke test."""
        return {
            "device types": self.devices.count(),
            "meters": self.meters.count(),
            "standards": self.standards.count(),
            "benches": self.benches.count(),
            "runs": self.runs.count(),
            "transformers": self.transformers.count(),
            "service points": self.points.count(),
            "meter sets": self.installs.count(),
            "groups": self.groups.count(),
            "sample decisions": self.plans.count(),
            "billed months": self.billing.count(),
            "complaints": self.complaints.count(),
            "work orders": self.orders.count(),
            "technicians": self.technicians.count(),
            "tamper findings": self.tamper.count(),
        }

    def audit(self) -> list[str]:
        """Everything inconsistent about the book, in one pass."""
        faults = list(self.book.check())
        for meter in self.meters.all():
            if not self.devices.exists(meter.device_key):
                faults.append(
                    f"meter {meter.serial} names device type {meter.device_key}, "
                    "which is not on the book"
                )
        for bench in self.benches.all():
            if not self.standards.exists(bench.standard_serial):
                faults.append(
                    f"bench {bench.code} names standard {bench.standard_serial}, "
                    "which is not on the book"
                )
        for meter_set in self._all_sets():
            for kind, key in (
                ("current transformer", meter_set.ct_serial),
                ("voltage transformer", meter_set.vt_serial),
            ):
                if key is not None and not self.transformers.exists(key):
                    faults.append(
                        f"set at {meter_set.point_code} names {kind} {key}, "
                        "which is not on the book"
                    )
            if not self.meters.exists(meter_set.meter_serial):
                faults.append(
                    f"set at {meter_set.point_code} names meter {meter_set.meter_serial}, "
                    "which is not on the book"
                )
        for run in self.runs.all():
            for kind, key, exists in (
                ("meter", run.meter_serial, self.meters.exists(run.meter_serial)),
                ("bench", run.bench_code, self.benches.exists(run.bench_code)),
                (
                    "standard",
                    run.standard_serial,
                    self.standards.exists(run.standard_serial),
                ),
            ):
                if not exists:
                    faults.append(
                        f"run {run.reference} names {kind} {key}, which is not on the book"
                    )
        return faults

    def _all_sets(self) -> list[MeterSet]:
        sets: list[MeterSet] = []
        for point in self.points.all():
            sets.extend(self.installs.history(point.code))
        return sets

    def __str__(self) -> str:
        return f"shop book at {self.path}"


def open_shop(path: str | Path, *, create: bool = False) -> Shop:
    """Open a book, migrate it, and wrap it in a Shop."""
    return Shop(open_migrated(path, create=create))


def require(value: object, kind: str, key: str) -> None:
    """Raise the standard not found error when a lookup came back empty."""
    if value is None:
        raise NotFoundError(kind, key)


__all__ = ["IN_SERVICE", "Shop", "open_shop", "require"]
