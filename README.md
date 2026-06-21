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

## Using it

    pip install kilodial
    kilodial --book shop.sqlite3 init
    kilodial --book shop.sqlite3 doctor --on 2026-01-01

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
