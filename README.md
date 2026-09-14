# bank-ml-platform

A full MLOps system for bank credit risk prediction, built as a learning project, from synthetic data through a monitored, deployed model.

## Structure

- `infrastrcuture/` - Terraform, platform-level Helm charts (Airflow, MLflow, monitoring). Changes rarely, reviewed carefully.
- `models/' - training pipelines, DAGS, serving APIs. Changes frequently. One subfolder per use case (credit_risk, churn, etc.)
- `docs/` - decisions log and project documentation