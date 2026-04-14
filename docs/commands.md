# kilodial commands

Generated from the command tree. Do not edit by hand.
Rebuild with: python -m kilodial.tools.build_docs

Groups: adjust, bench, bill, book, complaint, device, due, estimate, group, import, meter, point, read, repair, report, run, standard, tamper, tech, work, xfmr

## `adjust period`

    kilodial adjust period POINT_CODE

The period an adjustment would cover, and what bounds it.

- `--on` the day to work the period out as at (required)
- `--pf` the load angle to judge at

## `adjust show`

    kilodial adjust show POINT_CODE

Work out an adjustment and print the month by month sheet.

- `--on` the day the adjustment is worked out (required)
- `--pf` the load angle to judge at

## `adjust tariff`

    kilodial adjust tariff

The rules adjustments are worked out under.

## `bench add`

    kilodial bench add CODE NAME

Put a bench on the book.

- `--positions` how many meters the bench holds (required)
- `--standard` the reference standard behind it (required)
- `--max-amps` the most current the bench can hold (required)
- `--max-volts` the most voltage the bench can hold (required)
- `--polyphase` the bench can hold polyphase meters
- `--installed` the day it went into service (required)

## `bench capacity`

    kilodial bench capacity

How many positions the shop has on a day, and why any are missing.

- `--on` the day to work this out as at (required)

## `bench day`

    kilodial bench day

Fill the benches for a day off the live test orders.

- `--on` the day to plan (required)
- `--bench` only this bench

## `bench list`

    kilodial bench list

List benches.

- `--on` only benches in service on this day

## `bench restandard`

    kilodial bench restandard CODE STANDARD_SERIAL

Put a different standard on a bench.

## `bench show`

    kilodial bench show CODE

One bench, and the standard behind it.

## `bill add`

    kilodial bill add POINT_CODE

Record one billing period.

- `--from` first day of the billing period (required)
- `--to` last day of the billing period (required)
- `--amount` what was charged (required)
- `--kwh` energy billed, if it is known

## `bill list`

    kilodial bill list POINT_CODE

List a point's billed history.

- `--from` start of the window
- `--to` end of the window

## `bill remove`

    kilodial bill remove POINT_CODE FIRST_DAY

Take one billing period back off the book.

- `--yes` Confirm the action without prompting.

## `book audit`

    kilodial book audit

Report every record that points at something that is not there.

## `book check`

    kilodial book check

Report anything structurally wrong with the book.

## `book export`

    kilodial book export

Write the whole book out as json.

- `--out` write to a file rather than to standard output

## `book history`

    kilodial book history

What has been done to the book, oldest first.

- `--subject` only lines about this subject
- `--action` only lines with this action
- `--by` only lines by this actor
- `--on` only lines from this day
- `--last` only the last so many lines

## `book restore`

    kilodial book restore PATH

Load a json dump into an empty book.

- `--yes` Confirm the action without prompting.

## `book summary`

    kilodial book summary

Count what is on the book.

## `complaint answer`

    kilodial complaint answer REFERENCE

Close a request with the referee run that answered it.

- `--run` the referee run (required)
- `--on` the day the request is closed (required)
- `--fee` override the standard fee
- `--pf` the load angle to judge at

## `complaint clock`

    kilodial complaint clock

How many days are left on each open request.

- `--on` the day to work this out as at (required)

## `complaint list`

    kilodial complaint list

List customer requests, open by default.

- `--all` closed ones too
- `--point` only this service point
- `--overdue` only ones past due on this day

## `complaint open`

    kilodial complaint open REFERENCE POINT_CODE

Log a customer request against a service point.

- `--on` the day the customer asked (required)
- `--by` who asked (required)
- `--reason` why the customer says the meter is wrong
- `--note` anything worth writing down

## `complaint reasons`

    kilodial complaint reasons

The reasons a request can be filed under.

## `complaint show`

    kilodial complaint show REFERENCE

One request and everything decided about it.

## `device add`

    kilodial device add MANUFACTURER MODEL_CODE

Put a meter model on the catalogue.

- `--form` ANSI form, such as 2S or 16S (required)
- `--class` meter class, such as CL200 (required)
- `--volts` nameplate voltage (required)
- `--kh` watthour constant per revolution or pulse (required)
- `--tech` induction or solid_state
- `--ratio` register ratio, required on an induction meter
- `--demand` the type registers demand as well as energy
- `--interval` demand window in minutes
- `--introduced` first day the shop bought this type (required)
- `--retired` last day the shop bought this type

## `device list`

    kilodial device list

List the catalogue.

- `--class` only this meter class
- `--tech` only this technology
- `--on` only types the shop bought on this day

## `device retire`

    kilodial device retire KEY

Close a catalogue entry off.

- `--on` last day the shop bought this type (required)

## `device show`

    kilodial device show KEY

Everything on one catalogue entry.

## `doctor`

    kilodial doctor

Ask every question the shop should be able to answer.

- `--on` the day to examine the book as at (required)
- `--quiet` leave the notes out

## `due counts`

    kilodial due counts

How many meters are current, due and overdue.

- `--on` the day to work this out as at (required)

## `due list`

    kilodial due list

Who is due, and how far past it.

- `--on` the day to judge against (required)
- `--group` only this sampling group
- `--overdue` only meters past their grace period
- `--grace` grace period in days

## `estimate bases`

    kilodial estimate bases

The bases an estimate can rest on, strongest first.

## `estimate gap`

    kilodial estimate gap POINT_CODE

The period confirmed interference covered, clipped to a meter set.

- `--on` the day to judge the findings as at (required)

## `estimate list`

    kilodial estimate list POINT_CODE

Every basis the book supports for a gap, strongest first.

- `--on` find the gap from the findings
- `--from` or give the period yourself
- `--to` end of the window
- `--note` anything worth writing down

## `estimate load`

    kilodial estimate load POINT_CODE

Estimate from nameplate load when there is no history to work from.

- `--from` start of the window (required)
- `--to` end of the window (required)
- `--kw` connected load in kilowatts (required)
- `--duty` share of the day the load ran (required)
- `--rate` energy rate (required)
- `--note` anything worth writing down

## `estimate settle`

    kilodial estimate settle REFERENCE POINT_CODE

Write down which estimate was used, and who chose it.

- `--basis` which basis was chosen (required)
- `--on` find the gap from the findings
- `--from` or give the period yourself
- `--to` end of the window
- `--settled-on` the day it was settled (required)
- `--by` who settled it (required)
- `--note` anything worth writing down

## `estimate settled`

    kilodial estimate settled POINT_CODE

Estimates already settled at a point.

## `group add`

    kilodial group add CODE NAME

Put a sampling group on the book.

- `--type` catalogue key, repeatable
- `--class` only this meter class
- `--tech` only this technology
- `--form` ANSI form, repeatable
- `--acquired-from` earliest delivery day in the group
- `--acquired-to` latest delivery day in the group
- `--grace` days past due before this group's meters are overdue

## `group delete`

    kilodial group delete CODE

Take a sampling group and its decisions off the book.

- `--yes` Confirm the action without prompting.

## `group list`

    kilodial group list

List groups with their population and interval.

## `group members`

    kilodial group members CODE

The meters in a group right now.

## `group sample`

    kilodial group sample CODE

Judge a season's bench work and set the group's next interval.

- `--from` start of the season (required)
- `--to` end of the season (required)
- `--on` the day the decision is taken (required)
- `--note` anything worth writing down

## `group show`

    kilodial group show CODE

One group, its criteria, and its decision history.

## `import bills`

    kilodial import bills PATH

Load a billing extract into the billed history.

## `import columns`

    kilodial import columns

The columns each import needs.

## `import runs`

    kilodial import runs PATH

Load a bench export into runs.

- `--dry-run` read and check without writing

## `init`

    kilodial init

Create the book, or bring an existing one up to date.

- `--force` migrate a book that is already there

## `meter counts`

    kilodial meter counts

How many meters are in each state.

## `meter list`

    kilodial meter list

List meters.

- `--state` only meters in this state
- `--type` only meters of this type
- `--in-shop` only meters a bench could take today

## `meter move`

    kilodial meter move SERIAL STATE

Move a meter to another state.

- `--on` the day it happened, needed for scrap

## `meter receive`

    kilodial meter receive SERIAL

Book a meter in for the first time.

- `--type` catalogue key, maker/model (required)
- `--acquired` the day the shop took delivery (required)
- `--owner` who owns the asset
- `--seal` seal number if one is on it
- `--uncatalogued` take delivery of a type that is not on the catalogue yet

## `meter seal`

    kilodial meter seal SERIAL SEAL

Put a seal on a meter, or cut the old one off by leaving it out.

## `meter show`

    kilodial meter show SERIAL

Everything on one meter, including its run history.

## `point accuracy`

    kilodial point accuracy CODE

What the installation at a point registers, and why.

- `--on` the day the set was standing
- `--pf` the load angle to judge at

## `point add`

    kilodial point add CODE

Put a service point on the book.

- `--account` the customer account number (required)
- `--address` where the service point is (required)
- `--service` 1P2W, 1P3W, 3P3W, 3P4WY, 3P4WD or NET3W (required)
- `--volts` the service voltage (required)
- `--rate` the rate code the point is billed on (required)
- `--energised` the day the service was energised (required)

## `point disconnect`

    kilodial point disconnect CODE

Close a service point off.

- `--on` the day to work this out as at (required)

## `point history`

    kilodial point history CODE

Every meter that has ever stood at a service point.

## `point list`

    kilodial point list

List service points.

- `--account` the customer account number
- `--on` only points live on this day

## `point pull`

    kilodial point pull CODE

Pull whatever meter is standing at a service point.

- `--on` the day to work this out as at (required)

## `point set`

    kilodial point set CODE METER_SERIAL

Set a meter at a service point.

- `--ct` the current transformer serial
- `--vt` the voltage transformer serial
- `--register-multiplier` the multiplier stamped on the register
- `--multiplier` as programmed (required)
- `--on` the day to work this out as at (required)

## `read consumption`

    kilodial read consumption POINT_CODE

What passed at a point between two readings.

- `--from` start of the window (required)
- `--to` end of the window (required)
- `--multiplier` override the set's multiplier

## `read kinds`

    kilodial read kinds

The kinds of reading the shop records.

## `read list`

    kilodial read list POINT_CODE

A point's readings, oldest first.

- `--from` start of the window
- `--to` end of the window

## `read take`

    kilodial read take POINT_CODE METER_SERIAL VALUE

Write a register reading down.

- `--on` the day it was read (required)
- `--dials` how many dials the register has (required)
- `--kind` which kind this is
- `--note` anything worth writing down

## `repair faults`

    kilodial repair faults

Count what went wrong, which is the question a purchase order asks.

- `--type` only this device type

## `repair list`

    kilodial repair list

List repairs.

- `--meter` only this meter
- `--fault` only this fault code
- `--from` start of the window
- `--to` end of the window
- `--wasteful` only ones that cost more than a meter

## `repair record`

    kilodial repair record REFERENCE METER_SERIAL FAULT

Write a repair down.

- `--on` the day it was repaired (required)
- `--by` who did it (required)
- `--hours` time on the bench (required)
- `--parts` what the parts cost
- `--replacement` what a new meter would cost (required)
- `--note` anything worth writing down

## `repair show`

    kilodial repair show REFERENCE

One repair and what it came to.

## `repair spend`

    kilodial repair spend

What the shop spent on repairs over a window.

- `--from` start of the window (required)
- `--to` end of the window (required)

## `report bench`

    kilodial report bench

Who benched what, and what came of it.

- `--from` start of the window (required)
- `--to` end of the window (required)
- `--format` the shape to write it in
- `--out` write to a file rather than to standard output

## `report certificates`

    kilodial report certificates

Standards, technicians and transformers on one clock.

- `--on` the day to report as at (required)
- `--warning` days ahead to warn on
- `--format` the shape to write it in
- `--out` write to a file rather than to standard output

## `report commission`

    kilodial report commission

The annual filing for the commission.

- `--from` start of the reporting period (required)
- `--to` end of the reporting period (required)
- `--format` the shape to write it in
- `--out` write to a file rather than to standard output

## `report faults`

    kilodial report faults

What breaks, on which types, and what it costs to keep fixing.

- `--from` start of the window (required)
- `--to` end of the window (required)
- `--format` the shape to write it in
- `--out` write to a file rather than to standard output

## `report formats`

    kilodial report formats

The shapes a report can be written in.

## `report register`

    kilodial report register

Every point that owes money or is owed it.

- `--on` the day to price the register at (required)
- `--format` the shape to write it in
- `--out` write to a file rather than to standard output

## `report shop`

    kilodial report shop

What the shop looks like on a day.

- `--on` the day to report as at (required)
- `--format` the shape to write it in
- `--out` write to a file rather than to standard output

## `run delete`

    kilodial run delete REFERENCE

Remove a run that should not have been entered.

- `--yes` Confirm the action without prompting.

## `run demand`

    kilodial run demand REFERENCE

Judge the demand half of a run on its own.

## `run judge`

    kilodial run judge REFERENCE

Judge one run and say why.

## `run list`

    kilodial run list

List runs.

- `--meter` only this meter
- `--bench` only this bench
- `--kind` which kind this is
- `--from` start of the window
- `--to` end of the window

## `run record`

    kilodial run record REFERENCE

Write a bench run down.

- `--meter` only this meter (required)
- `--bench` only this bench (required)
- `--standard` override the bench standard
- `--kind` which kind this is
- `--on` the day it was run (required)
- `--by` who did it (required)
- `--badge` the signing technician's badge
- `--fl` full load registration
- `--ll` light load registration
- `--pf` lagging power factor registration
- `--hl` heavy load registration
- `--register` register or dial test registration
- `--demand` demand registration
- `--creep` held or crept
- `--volts` service voltage if not the nameplate
- `--interval-seconds` measured demand window
- `--note` anything worth writing down

## `run show`

    kilodial run show REFERENCE

One run, its points and the verdict it earns today.

## `standard add`

    kilodial standard add SERIAL

Put a reference standard on the book.

- `--maker` who made it (required)
- `--model` the model code (required)
- `--certificate` the certificate number (required)
- `--certified` the day the certificate was issued (required)
- `--due` the day the certificate runs out (required)
- `--uncertainty` stated uncertainty in percent (required)
- `--traceable` what the certificate traces to

## `standard expired`

    kilodial standard expired

List standards whose certificate had run out on a day.

- `--on` the day to judge against (required)

## `standard list`

    kilodial standard list

List reference standards.

- `--on` only standards valid on this day
- `--due-within` days ahead to look

## `standard recertify`

    kilodial standard recertify SERIAL

Record a new certificate against a standard already on the book.

- `--certificate` the new certificate number (required)
- `--certified` the day it was issued (required)
- `--due` the day it runs out (required)
- `--uncertainty` stated uncertainty, if it changed

## `tamper clear`

    kilodial tamper clear REFERENCE

Close a suspicion without confirming it.

- `--on` the day to work this out as at (required)
- `--why` clearing needs a reason (required)

## `tamper confirm`

    kilodial tamper confirm REFERENCE

Confirm a suspicion, which changes what the customer can be billed.

- `--on` the day it was confirmed (required)
- `--since` the day the interference started (required)
- `--evidence` what was seen (required)

## `tamper kinds`

    kilodial tamper kinds

The findings the shop records, and which stop the meter measuring.

## `tamper list`

    kilodial tamper list

List tamper findings, open suspicions by default.

- `--all` settled ones too
- `--point` only this service point
- `--from` start of the window
- `--to` end of the window

## `tamper log`

    kilodial tamper log REFERENCE POINT_CODE KIND

Log a suspicion against a service point.

- `--on` the day it was found (required)
- `--by` who found it (required)
- `--evidence` what was seen

## `tamper show`

    kilodial tamper show REFERENCE

One finding and everything decided about it.

## `tech add`

    kilodial tech add BADGE NAME

Put a technician on the register.

- `--grade` bench, polyphase or supervisor (required)
- `--certified` the day the certification was issued (required)
- `--due` the day it runs out (required)
- `--note` anything worth writing down

## `tech grades`

    kilodial tech grades

The grades and what each one signs.

## `tech lapsed`

    kilodial tech lapsed

Certifications that had run out on a day.

- `--on` the day to work this out as at (required)

## `tech list`

    kilodial tech list

List the register.

- `--on` only those certified on this day
- `--grade` the certification grade
- `--due-within` days ahead to look

## `tech may`

    kilodial tech may BADGE METER_SERIAL

Say whether somebody may sign that run on that day, before it is run.

- `--kind` which kind this is
- `--on` the day to work this out as at (required)

## `tech recertify`

    kilodial tech recertify BADGE

Record a new certification against somebody already on the register.

- `--certified` the day the certificate was issued (required)
- `--due` the day the certificate runs out (required)
- `--grade` promote at the same time

## `work assign`

    kilodial work assign REFERENCE TECHNICIAN

Put a technician's name on an order.

## `work cancel`

    kilodial work cancel REFERENCE

Close an order without doing it.

- `--on` the day to work this out as at (required)
- `--why` cancelling needs a reason (required)

## `work counts`

    kilodial work counts

How many orders are in each state.

## `work done`

    kilodial work done REFERENCE

Close an order with whatever evidence its kind wants.

- `--on` the day to work this out as at (required)
- `--run` for a test order
- `--disposition` for a repair order
- `--repair` the repair record

## `work kinds`

    kilodial work kinds

The kinds of order the shop raises, and what closes each.

## `work list`

    kilodial work list

List work orders, live ones by default.

- `--all` closed ones too
- `--meter` only this meter
- `--kind` which kind this is
- `--to` assigned to this technician
- `--late` only ones late on this day

## `work plan`

    kilodial work plan

Work out the test orders the due list calls for.

- `--on` the day to plan from (required)
- `--limit` cap the number raised
- `--raise` actually put them on the book

## `work raise`

    kilodial work raise REFERENCE KIND METER_SERIAL

Open one work order by hand.

- `--on` the day it was raised (required)
- `--priority` how urgent it is
- `--point` only this service point
- `--note` anything worth writing down

## `work show`

    kilodial work show REFERENCE

One order and everything on it.

## `xfmr add`

    kilodial xfmr add SERIAL

Put an instrument transformer on the book.

- `--kind` current or voltage (required)
- `--maker` who made it (required)
- `--ratio` marked ratio as a number (required)
- `--accuracy` 0.3, 0.6 or 1.2 (required)
- `--rcf` ratio correction factor (required)
- `--minutes` phase angle in minutes
- `--burden` the burden it was tested at
- `--tested` the day it was last tested (required)

## `xfmr check`

    kilodial xfmr check SERIAL

Say whether a transformer holds its class at a given load.

- `--pf` the load angle

## `xfmr list`

    kilodial xfmr list

List instrument transformers.

- `--kind` current or voltage
- `--accuracy` 0.3, 0.6 or 1.2
- `--tested-before` only ones older than this day

## `xfmr retest`

    kilodial xfmr retest SERIAL

Record a new test against a transformer already on the book.

- `--rcf` ratio correction factor (required)
- `--minutes` phase angle in minutes (required)
- `--tested` the day it was tested (required)
- `--burden` the burden it was tested at

## `xfmr where`

    kilodial xfmr where SERIAL

Which service points a transformer has been installed at.

Generated for kilodial 0.2.0.
