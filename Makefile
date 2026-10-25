.DEFAULT_GOAL := help
SHELL := /bin/bash
PYTHON ?= python3
VENV ?= .venv
DS ?= 2026-01-15
ROWS ?= 5000
TF := terraform -chdir=terraform

.PHONY: help setup lint test run-local tf-init tf-plan deploy upload-code env airflow-up airflow-down destroy

help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## ' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  %-14s %s\n", $$1, $$2}'

setup: ## Create a virtualenv and install dev dependencies
	$(PYTHON) -m venv $(VENV)
	$(VENV)/bin/pip install -r requirements-dev.txt

lint: ## Lint with ruff
	$(VENV)/bin/ruff check .

test: ## Run unit tests (Spark tests need Java 11 or 17)
	$(VENV)/bin/pytest -q

run-local: ## Generate synthetic data and run the Spark clean job locally (no GCP needed)
	$(VENV)/bin/python dags/include/synthetic_claims.py --ds $(DS) --rows $(ROWS) --out data/raw/claims/ds=$(DS)/claims.csv
	PYSPARK_PYTHON=$(abspath $(VENV)/bin/python) $(VENV)/bin/python spark/clean_claims.py --input data/raw/claims/ds=$(DS)/claims.csv --output data/curated/claims/ds=$(DS) --rejects data/rejects/ds=$(DS)

tf-init: ## terraform init
	$(TF) init

tf-plan: ## terraform plan
	$(TF) plan

deploy: ## Apply Terraform, upload the Spark job, write .env for Airflow
	$(TF) apply
	$(MAKE) upload-code env

upload-code: ## Upload the Spark job to the code bucket
	gcloud storage cp spark/clean_claims.py gs://$$($(TF) output -raw code_bucket)/spark/clean_claims.py

env: ## Write .env (Airflow settings) from Terraform outputs
	@{ \
	  echo "GCP_PROJECT_ID=$$($(TF) output -raw project_id)"; \
	  echo "GCP_REGION=$$($(TF) output -raw region)"; \
	  for k in raw_bucket curated_bucket code_bucket staging_bucket curated_dataset marts_dataset bq_location spark_service_account subnetwork_uri; do \
	    echo "$$(echo $$k | tr '[:lower:]' '[:upper:]')=$$($(TF) output -raw $$k)"; \
	  done; \
	  echo "AIRFLOW_UID=$$(id -u)"; \
	} > .env
	@echo "wrote .env"

airflow-up: ## Start Airflow locally in Docker (http://localhost:8080)
	docker compose up -d

airflow-down: ## Stop local Airflow
	docker compose down

destroy: ## Tear down all cloud resources (needs force_destroy = true for non-empty buckets)
	$(TF) destroy
