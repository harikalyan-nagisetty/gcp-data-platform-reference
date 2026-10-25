-- Daily claims summary for one service_date (one partition of the mart).
-- Rendered by Airflow: the logical date (ds) and params come from the DAG.
-- The partition filter keeps the scan to a single day of the curated table.
SELECT
  service_date,
  diagnosis_code,
  claim_status,
  COUNT(*) AS claim_count,
  COUNT(DISTINCT member_id) AS member_count,
  SUM(billed_amount) AS total_billed,
  SUM(paid_amount) AS total_paid,
  SAFE_DIVIDE(SUM(paid_amount), SUM(billed_amount)) AS paid_ratio
FROM `{{ params.project_id }}.{{ params.curated_dataset }}.claims`
WHERE service_date = DATE '{{ ds }}'
GROUP BY service_date, diagnosis_code, claim_status
