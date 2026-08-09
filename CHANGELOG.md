# Changelog

## 1.0.0

The book is complete enough to run a shop on, so this is 1.0. Nothing in it is
new since 0.2.0 in the sense of a feature nobody asked for; what changed is that
the parts that were sketched are finished and the repository now checks itself.

- Register readings, the rollover that is not always one, and consumption
  across a meter change.
- Tamper findings, and what confirming one does: a longer back bill window, and
  a refusal to price a bypass from a registration at all.
- Estimating a period nobody metered, on four bases the book supports and none
  it invents, with the choice and the person who made it written down.
- Repair records, the fault counts that decide a purchase order, and the rule
  about when a repair was not worth doing.
- The bench rota, the certification report, the fault report and the bench
  report.
- An append only event log, a book that can be written out as json and read
  back, and a doctor that asks every question at once.
- Seventeen gates the repository runs on itself, from the migration list to the
  readme, plus a command that runs all of them.

## 0.2.0

- Demand metering: demand registers, their intervals, and the timing error a
  demand meter can carry with a perfectly good measurement circuit.
- A technician certification register. A run signed by somebody who was not
  certified to sign it on the day is void.
- Work orders, and a planner that raises them off the periodic due list.
- Imports for bench exports and billing extracts.
- Shop, commission and adjustment register reports, in text, json or csv.

## 0.1.0

- The book: device types, meters, benches, certified reference standards, bench
  runs and the verdict a run earns.
- Instrument transformers, service points and the multiplier chain.
- Homogeneous groups, sample plans and the periodic test programme.
- Billing adjustment, and customer requested tests.
