# ADR-0002: Run Airflow locally in Docker; keep the DAG Composer-compatible

- **Status:** Accepted
- **Date:** 2026-10-23
- **Tags:** orchestration, cost

## Context

The reference needs an orchestrator that demonstrates real patterns (retries, timeouts, backfills, templating). Cloud Composer is the managed option on GCP but has an always-on cost, which is a poor fit for a personal reference that people will deploy and forget.

## Decision

We will provide a Docker Compose setup for local Airflow (official image) that talks to real GCP resources using Application Default Credentials. The DAG uses only standard Google provider operators and environment-based configuration, so it can be copied into a Composer environment unchanged.

## Options considered

### Option A: Local Airflow in Docker (chosen)
- Pros: no standing cost, easy to inspect, same operators as production
- Cons: not a deployment model, local credentials instead of a managed identity

### Option B: Provision Cloud Composer with Terraform
- Pros: closest to a production setup
- Cons: continuous cost and a long provisioning time

### Option C: Cloud Workflows or Cloud Scheduler
- Pros: serverless, cheap
- Cons: does not demonstrate Airflow patterns, weaker backfill story

## Consequences

**Positive**
- Anyone can run it for the cost of the resources the DAG touches.

**Negative / costs**
- Local runs use the developer's credentials. The `airflow` service account in Terraform documents the intended production identity but is not wired into the Docker setup.

**Risks and mitigations**
- The official Docker image bundles the OpenLineage provider, which the Google provider's Dataproc operators need to import. A bare `pip install` does not, so CI installs it explicitly.

## Validation

Revisit when this needs to run on a schedule unattended. At that point provision Composer and use the `airflow` service account.
