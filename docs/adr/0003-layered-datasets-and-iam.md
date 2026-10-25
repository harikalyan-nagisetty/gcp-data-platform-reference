# ADR-0003: Layered datasets, two service accounts, dataset-level IAM

- **Status:** Accepted
- **Date:** 2026-10-23
- **Tags:** security, governance

## Context

Healthcare-style data needs a clear boundary between data that only pipelines should touch and data that people query. A single dataset with project-wide editor access is simple, but it makes accidental exposure and accidental writes easy.

## Decision

We will separate `curated` (pipeline-only) from `marts` (analyst-facing) datasets, use two service accounts (one for Spark, one for Airflow), and grant roles at the narrowest scope GCP allows: bucket-level for storage, dataset-level for BigQuery. Only roles that cannot be scoped (BigQuery job user, Dataproc roles) are project-wide.

## Options considered

### Option A: Layered datasets with scoped grants (chosen)
- Pros: analysts can be given marts only, a compromised job identity has a small blast radius
- Cons: more Terraform to read

### Option B: One dataset, project-level `bigquery.dataEditor`
- Pros: least configuration
- Cons: everyone and everything can read and write everything

### Option C: Authorized views over a single dataset
- Pros: fine-grained sharing
- Cons: more moving parts than this scale needs, and a good next step rather than a first one

## Consequences

**Positive**
- Access is explainable in a table (see `docs/architecture.md`).

**Negative / costs**
- Adding a new consumer means an explicit grant, which is intended.

**Risks and mitigations**
- Project-level `dataproc.editor` for Airflow is broader than ideal. Mitigation: it can only run workloads as the Spark service account, which has narrow storage access.

## Validation

Review the grants quarterly and prefer column-level policy tags once real sensitive columns exist.
