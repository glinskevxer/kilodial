# kilodial glossary

Generated from the classes that define these things.
Rebuild with: python -m kilodial.tools.build_glossary

## adjust

### Adjustment

The whole adjustment, ready to be argued about.

Defined in `kilodial.adjust.compute`.

### BilledMonth

What the customer was actually billed over one period.

Defined in `kilodial.adjust.compute`.

### Boundary

What stopped the period reaching further back.

Values: `the tariff lookback`, `the day the meter was set`, `the last test inside tolerance`

Defined in `kilodial.adjust.period`.

### Direction

Which way the money moves.

Values: `refund`, `back bill`, `none`

Defined in `kilodial.adjust.rules`.

### Line

One billing month of an adjustment.

Defined in `kilodial.adjust.compute`.

### Period

The window an adjustment covers, and why it starts where it does.

Defined in `kilodial.adjust.period`.

### Refusal

Why no adjustment was raised, in words a clerk can pass on.

Defined in `kilodial.adjust.service`.

### Tariff

One jurisdiction's adjustment rules.

Defined in `kilodial.adjust.rules`.

## complaint

### Answer

What answering a request decided, with the reading behind it.

Defined in `kilodial.complaint.service`.

### Charge

What the customer ends up owing for the test.

Values: `charged`, `waived, meter outside tolerance`, `waived, tested past the deadline`, `waived, first test in the free window`

Defined in `kilodial.complaint.request`.

### Reason

Why the customer says the meter is wrong.

Values: `high bill`, `low bill`, `no usage`, `suspected tamper`, `other`

Defined in `kilodial.complaint.request`.

### Request

One customer request, from the day it was made.

Defined in `kilodial.complaint.request`.

## estimate

### Basis

How an estimate was arrived at.

Values: `same period last year`, `neighbouring periods`, `metered either side`, `connected load`, `declared by the customer`

Defined in `kilodial.estimate.basis`.

### Estimate

A figure, the period it covers, and how it was arrived at.

Defined in `kilodial.estimate.basis`.

### Options

Every estimate the book can support for one gap, strongest first.

Defined in `kilodial.estimate.service`.

## install

### InstalledAccuracy

Everything wrong with one installation, kept apart by kind.

Defined in `kilodial.install.multiplier`.

### MeterSet

One meter standing at one service point over one period.

Defined in `kilodial.install.point`.

### ServicePoint

Somewhere the utility sells electricity.

Defined in `kilodial.install.point`.

## model

### Bench

A test position or bank of them, and what it can hold.

Defined in `kilodial.model.bench`.

### BenchPoint

One load held, and what the meter did at it.

Defined in `kilodial.model.run`.

### BenchRun

One meter, one bench, one day.

Defined in `kilodial.model.run`.

### Consumption

What two readings say passed, and whether the register rolled.

Defined in `kilodial.model.reading`.

### DemandKind

How the peak is picked out of the intervals.

Values: `block`, `rolling`

Defined in `kilodial.model.demand`.

### DemandRegister

How a meter is programmed to measure demand, and what it is holding.

Defined in `kilodial.model.demand`.

### DeviceType

One make and model of meter, as the shop stocks it.

Defined in `kilodial.model.device`.

### Fault

What was found wrong, from the shop's fixed list.

Values: `bearing`, `magnet`, `register`, `disc`, `potential link`, `coil`, `board`, `battery`, `firmware`, `cover`, `terminal`, `none found`

Defined in `kilodial.model.repair`.

### Form

One row of the form table.

Defined in `kilodial.model.form`.

### Grade

What a certification lets somebody sign, in ascending order.

Values: `bench`, `polyphase`, `supervisor`

Defined in `kilodial.model.technician`.

### Interval

The window demand is averaged over.

Values: `5 minute`, `15 minute`, `30 minute`, `60 minute`

Defined in `kilodial.model.demand`.

### Meter

One asset, tracked from receipt to scrap.

Defined in `kilodial.model.meter`.

### MeterClass

Continuous current rating, and with it the bench test current.

Values: `CL10`, `CL20`, `CL100`, `CL200`, `CL320`, `CL480`

Defined in `kilodial.model.form`.

### MeterState

Where a meter is, in the only terms the shop cares about.

Values: `received`, `stock`, `set`, `pulled`, `repair`, `scrap`, `lost`

Defined in `kilodial.model.meter`.

### Mounting

How the meter is held: in a socket, or bolted to a base.

Values: `socket`, `bottom`

Defined in `kilodial.model.form`.

### PointKind

The loads a shop sequence is made of.

Values: `FL`, `LL`, `PF`, `HL`, `CR`, `RG`, `DM`

Defined in `kilodial.model.run`.

### Reading

One reading off one register.

Defined in `kilodial.model.reading`.

### ReadingKind

Where the number came from.

Values: `actual`, `estimated`, `customer`, `final`, `initial`

Defined in `kilodial.model.reading`.

### ReferenceStandard

A certified standard, and the window its certificate covers.

Defined in `kilodial.model.bench`.

### Repair

One repair: what was wrong, what it took, and what it cost.

Defined in `kilodial.model.repair`.

### RunKind

Why the run happened, which decides what its result is allowed to do.

Values: `acceptance`, `as found`, `as left`, `referee`

Defined in `kilodial.model.run`.

### Service

The service a form is built for, written the way a crew says it.

Values: `1P2W`, `1P3W`, `NET3W`, `3P3W`, `3P4WY`, `3P4WD`

Defined in `kilodial.model.form`.

### Technician

One person, and the window their certification covers.

Defined in `kilodial.model.technician`.

### Technology

What is doing the measuring inside.

Values: `induction`, `solid state`, `hybrid`

Defined in `kilodial.model.form`.

## orders

### Disposition

What became of a meter that went through repair.

Values: `returned to stock`, `scrapped`, `unrepairable, held`

Defined in `kilodial.orders.order`.

### OrderKind

What the order is asking somebody to do.

Values: `receive`, `test`, `repair`, `set`, `pull`, `scrap`

Defined in `kilodial.orders.order`.

### OrderState

Where the order is.

Values: `open`, `assigned`, `done`, `cancelled`

Defined in `kilodial.orders.order`.

### Plan

What a planning run would raise, before it raises anything.

Defined in `kilodial.orders.planner`.

### Priority

How long the shop has before the order is late.

Values: `urgent`, `high`, `normal`, `low`

Defined in `kilodial.orders.order`.

### WorkOrder

One job, from the day it was raised to the day it was closed.

Defined in `kilodial.orders.order`.

## programme

### Day

A day's bench plan.

Defined in `kilodial.programme.rota`.

### DueMeter

One line of the due list.

Defined in `kilodial.programme.schedule`.

### DueState

Where a meter sits against its own due date.

Values: `current`, `due`, `overdue`

Defined in `kilodial.programme.schedule`.

### Roster

Every meter in the programme, with where it sits today.

Defined in `kilodial.programme.roster`.

### Season

What a window of bench work turned up for one group.

Defined in `kilodial.programme.season`.

### Slot

One meter on one bench position for a day.

Defined in `kilodial.programme.rota`.

## sampling

### Decision

What a group's sample did to its interval.

Defined in `kilodial.sampling.decision`.

### Group

A homogeneous population, defined by what is in it rather than by who.

Defined in `kilodial.sampling.group`.

### SampleOutcome

What a group's sample decided, and the working behind it.

Defined in `kilodial.sampling.plan`.

## tamper

### Finding

One tamper finding at one service point.

Defined in `kilodial.tamper.event`.

### Standing

Where a finding has got to.

Values: `suspected`, `confirmed`, `cleared`

Defined in `kilodial.tamper.event`.

### TamperKind

What was found, and whether it stops the meter measuring.

Values: `seal cut`, `seal missing`, `bypass`, `reversed`, `dials turned`, `meter missing`

Defined in `kilodial.tamper.event`.

## testing

### Band

A symmetric tolerance, in percentage points either side of nominal.

Defined in `kilodial.testing.tolerance`.

### Condition

The load a point is supposed to be run at.

Defined in `kilodial.testing.sequence`.

### DemandOutcome

What a demand test decided.

Values: `passed`, `failed on registration`, `failed on the interval clock`, `failed on registration and on the interval clock`, `not tested`

Defined in `kilodial.testing.demand`.

### DemandVerdict

The demand half of a run, with both errors kept apart.

Defined in `kilodial.testing.demand`.

### Outcome

What the shop decided about a run.

Values: `passed`, `failed`, `suspect`, `void`

Defined in `kilodial.testing.verdict`.

### Readings

What came off the bench, in the order the shop sheet lists it.

Defined in `kilodial.testing.record`.

### Verdict

The decision, with the working and the reasons kept.

Defined in `kilodial.testing.verdict`.

### WeightedAverage

The averaged figure, with the working kept.

Defined in `kilodial.testing.weighted`.

## units

### Amperes

Test current, held to a milliamp.

Defined in `kilodial.units.electrical`.

### DateSpan

A closed range of days, with an optional open end.

Defined in `kilodial.units.span`.

### Money

A signed amount in whole cents.

Defined in `kilodial.units.money`.

### PowerFactor

A power factor and the sense it was applied in.

Defined in `kilodial.units.electrical`.

### Registration

Percent registration, quantised to four places.

Defined in `kilodial.units.registration`.

### Sense

Which way the current sits against the voltage.

Values: `unity`, `lagging`, `leading`

Defined in `kilodial.units.electrical`.

### Volts

Test voltage, held to a centivolt.

Defined in `kilodial.units.electrical`.

### WattHours

Energy, held to a milliwatthour because light load runs are small.

Defined in `kilodial.units.electrical`.

## xfmr

### AccuracyClass

How far the transformer correction factor may sit from one.

Values: `0.3`, `0.6`, `1.2`

Defined in `kilodial.xfmr.transformer`.

### InstrumentTransformer

One current or voltage transformer, as tested.

Defined in `kilodial.xfmr.transformer`.

### TransformerKind

Which quantity the transformer steps down.

Values: `current`, `voltage`

Defined in `kilodial.xfmr.transformer`.
