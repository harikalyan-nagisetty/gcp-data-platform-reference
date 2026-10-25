# ADR-0001: Run Spark on Dataproc Serverless

- **Status:** Accepted
- **Date:** 2026-10-23
- **Tags:** compute, cost, operations

## Context

The cleaning step needs Spark semantics (explicit types, windowed duplicate detection, Parquet output) and must scale beyond what a single machine handles. The platform is run by a small team, so cluster operations (sizing, patching, autoscaling, idle cost) should be avoided where possible.

## Decision

We will run the cleaning job as a Dataproc Serverless batch, submitted by Airflow, with a dedicated service account in a subnet with Private Google Access.

## Options considered

### Option A: Dataproc Serverless batches (chosen)
- Pros: no cluster lifecycle, no idle cost, per-job isolation and identity
- Cons: startup overhead on every batch, less control over the runtime, runtime versions are deprecated on a schedule

### Option B: Ephemeral Dataproc cluster per run
- Pros: full control of machine types and init actions
- Cons: cluster create and delete tasks to manage and fail, slower for small jobs

### Option C: BigQuery SQL only
- Pros: simplest, no second engine
- Cons: no Spark portfolio signal and less control over file formats. A valid choice for this data volume, noted here honestly.

## Consequences

**Positive**
- One less thing to operate. The job is a plain Python file that also runs locally for tests.

**Negative / costs**
- Per-batch startup time. The runtime version must be reviewed regularly (`DATAPROC_RUNTIME_VERSION`).

**Risks and mitigations**
- Runtime drift between local PySpark and the cloud runtime: `requirements-dev.txt` pins PySpark to the same minor version as the chosen runtime (3.5 at the time of writing; confirm against the runtime's release notes when you change it), and the code uses `try_cast`/`try_to_timestamp` so behavior matches under ANSI and non-ANSI modes.

## Validation

Revisit if daily volume stays small enough that BigQuery SQL alone would do, or if batch startup dominates run time.

## References

- Dataproc Serverless for Spark documentation
