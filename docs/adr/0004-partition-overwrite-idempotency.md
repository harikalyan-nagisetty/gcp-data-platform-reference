# ADR-0004: Idempotent loads by overwriting a single day partition

- **Status:** Accepted
- **Date:** 2026-10-23
- **Tags:** correctness, backfills, cost

## Context

Pipelines get retried and backfilled. A load that appends will double count the day it runs twice. We need reruns of any date to be safe without special handling.

## Decision

Each run owns exactly one day. The BigQuery load and the mart build write to a single partition using the `$YYYYMMDD` decorator with `WRITE_TRUNCATE`, so the partition is replaced, never appended to. Upstream steps write to date-scoped paths with overwrite.

## Options considered

### Option A: Partition overwrite (chosen)
- Pros: trivial to reason about, no scan of existing data, cheap, backfill is just rerunning dates
- Cons: every row in a run must belong to that run's partition, otherwise the load fails. Late-arriving data needs a different approach.

### Option B: `MERGE` into the table
- Pros: handles late and out-of-order data, upserts
- Cons: scans more data, needs a stable business key and update semantics, more cost and complexity

### Option C: Append, then de-duplicate on read
- Pros: simplest write path
- Cons: every consumer must de-duplicate, easy to get wrong, grows storage

## Consequences

**Positive**
- Retries and backfills are safe by construction. The quality checks assert uniqueness of `claim_id` within the partition.

**Negative / costs**
- The generator keeps `service_date` equal to the run date for valid rows. A real source with late claims would need Option B or routing by date.

**Risks and mitigations**
- A bad deploy that writes the wrong partition: the partition decorator and the date in the SQL both come from `ds`, and the quality checks read the same partition they just wrote.

## Validation

Revisit if late-arriving data exceeds a small percentage of volume. That is the trigger to move to a staging table and `MERGE`.
