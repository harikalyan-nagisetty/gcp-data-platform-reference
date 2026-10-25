"""DAG integrity checks. Skipped automatically when Airflow is not installed."""

from pathlib import Path

import pytest

pytest.importorskip("airflow")
pytest.importorskip("airflow.providers.google")

DAGS_FOLDER = Path(__file__).resolve().parents[1] / "dags"
DAG_ID = "synthetic_claims_pipeline"


@pytest.fixture(scope="module")
def dagbag():
    from airflow.models import DagBag

    return DagBag(dag_folder=str(DAGS_FOLDER), include_examples=False)


@pytest.fixture(scope="module")
def dag(dagbag):
    # Read from the parsed bag directly; get_dag() would require an Airflow metadata DB.
    return dagbag.dags.get(DAG_ID)


def test_dags_import_without_errors(dagbag):
    assert dagbag.import_errors == {}


def test_dag_is_registered(dag):
    assert dag is not None


def test_task_order(dag):
    chain = [
        "extract_synthetic_claims",
        "spark_clean_claims",
        "load_curated_claims",
        "build_claims_daily_summary",
        "quality_checks",
    ]
    assert {t.task_id for t in dag.tasks} == set(chain)
    for upstream, downstream in zip(chain, chain[1:], strict=False):
        assert dag.get_task(upstream).downstream_task_ids == {downstream}


def test_safe_scheduling_defaults(dag):
    assert dag.catchup is False
    assert dag.max_active_runs == 1
    assert dag.default_args["retries"] >= 1


def test_every_task_has_a_timeout(dag):
    assert all(task.execution_timeout is not None for task in dag.tasks)
