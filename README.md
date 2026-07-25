# kilodial

Meter shop register for an electric distribution utility.

kilodial is the book a meter shop runs on. It holds the meters, the benches and
the certified reference standards behind them, records what came off the bench,
decides whether a result can be relied on, and works out the money when a meter
turns out to have been wrong.

## What it does

**The fleet.** Device types, meters, their state from delivery to scrap, and the
seals on them.

**The bench.** Runs, their load points, and the verdict each run earns. A run is
judged against the standard it names, the bench it was on, the sequence its
device type calls for, and the person who signed it. A run against a lapsed
certificate is void, not failed, and the difference matters.

**Installations.** Service points, meter sets, and instrument transformers.
A transformer rated installation's error is the meter's error composed with the
ratio and phase angle corrections of its transformers, and a phase angle error
is exactly zero at unity power factor and real on a motor load.

**The periodic programme.** Homogeneous groups, ANSI style sample plans, and the
interval ladder a group's sample moves it along. The sample decides the interval,
the interval decides who is due, and who gets tested decides the next sample.

**Money.** Billing adjustment, with the tariff's asymmetric lookback: five years
back on a refund and one on a back bill. A multiplier typed in wrong is not a
meter error and is corrected in full whichever way it points.

**Customers.** Requested tests, the thirty day clock, and the fee, which is
waived when the meter turns out to be bad, when the shop was late, or when it is
the customer's free test.

## A worked example

Stand a shop up, bench a meter, and find out what the customer is owed.

    pip install kilodial
    export KILODIAL_BOOK=shop.sqlite3

    kilodial init
    kilodial device add Halvern R4S --form 2S --class 200 --volts 240 \
        --kh 7.2 --ratio 100 --introduced 2004-05-01
    kilodial meter receive 84-119302 --type Halvern/R4S --acquired 2015-01-01
    kilodial standard add RS-5511 --maker Radian --model RD-23 \
        --certificate NVLAP-88214 --certified 2015-01-01 --due 2035-01-01 \
        --uncertainty 0.02
    kilodial bench add B2 "north wall" --positions 8 --standard RS-5511 \
        --max-amps 100 --max-volts 480 --installed 2010-01-01
    kilodial point add SP-1042 --account 44-9021 --address "18 Fenwick Row" \
        --service 1P3W --volts 240 --rate R1 --energised 2011-06-14
    kilodial point set SP-1042 84-119302 --multiplier 1 --on 2019-05-02

The meter comes off the service and goes on the bench. It is three percent fast,
so it fails, and the shop can say why.

    kilodial run record TR-1 --meter 84-119302 --bench B2 --on 2025-06-30 \
        --by "R Ellis" --fl 103.20 --ll 102.40
    kilodial run show TR-1

Load what the customer was billed, and the adjustment falls out of it.

    kilodial bill add SP-1042 --from 2025-01-01 --to 2025-01-31 --amount 104.22
    kilodial adjust show SP-1042 --on 2025-07-15

Then the questions somebody asks on a Monday.

    kilodial doctor --on 2026-01-01
    kilodial report shop --on 2026-01-01
    kilodial about

## Using it

Every command lives under a group and the full reference is in
[docs/commands.md](docs/commands.md), which is generated from the command tree.
The schema is in [docs/schema.sql](docs/schema.sql), the vocabulary is in
[docs/glossary.md](docs/glossary.md), and the layering is in
[docs/layers.md](docs/layers.md). All four are generated from the code.

## The book

One sqlite file. Numbered migrations, applied forward, each inside the
transaction that records it. Every number is stored as text, because a
registration read back as 99.86999999999999 is not something to argue a bill
over.

## Working on it

    pip install -e ".[dev]" -c constraints.txt
    pytest -q
    ruff check . && ruff format --check . && mypy
    python -m kilodial.tools.gates

Every dependency is pinned exactly, and `constraints.txt` is the closure of
those pins including everything they pull in, so a build in six months installs
what a build today installs.

CI runs those on 3.12 and 3.13, plus a set of gates the repository runs on
itself: the migrations build the tables the code expects, every module declares
its exports, nothing public is unexplained, the schema dump and the command
reference are current, coverage holds its floors, and the workflow actually runs
all of it.
