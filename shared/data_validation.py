"""
data_validation.py

Reusable data validation checklist, meant to live in shared/ because it's
genuinely applicable to any future use case (churn, etc.), not specific to
credit risk. Run directly, it pulls a joined applicants + loan_applications
view from Postgres and validates it.

Checks:
  - Missing values per column
  - Duplicate rows
  - Duplicate loan_id (the meaningful uniqueness check now that one
    applicant can legitimately have multiple loan rows)
  - Out-of-range values (negative income, implausible age, negative debt)
  - Class balance of `defaulted` (excluding unresolved/NULL rows)
"""

import pandas as pd


def validate_data(df):
    """
    Run the full validation checklist against a joined
    applicants + loan_applications DataFrame and print a report.

    Expects at least these columns: age, income, debt, loan_id, defaulted.
    """
    print("=" * 60)
    print("DATA VALIDATION REPORT")
    print("=" * 60)
    print(f"Total rows: {len(df)}")

    # ── Missing values ───────────────────────────────────────────────
    print("\n--- Missing values per column ---")
    missing = df.isnull().sum()
    missing_pct = (missing / len(df) * 100).round(2)
    missing_report = pd.DataFrame({"missing_count": missing, "missing_pct": missing_pct})
    missing_report = missing_report[missing_report["missing_count"] > 0]
    if missing_report.empty:
        print("No missing values found.")
    else:
        print(missing_report.to_string())

    # ── Duplicate rows ───────────────────────────────────────────────
    print("\n--- Duplicate rows ---")
    dup_rows = df.duplicated().sum()
    print(f"Fully duplicated rows: {dup_rows}")

    # ── Duplicate loan_id ─────────────────────────────────────────────
    # loan_id is the meaningful uniqueness check here, not applicant_id,
    # since one applicant can legitimately have multiple loan applications.
    print("\n--- Duplicate loan_id ---")
    if "loan_id" in df.columns:
        dup_loan_ids = df["loan_id"].duplicated().sum()
        print(f"Duplicate loan_id values: {dup_loan_ids}")
        if dup_loan_ids > 0:
            print("WARNING: loan_id should be unique. Investigate the join or insert logic.")
    else:
        print("Column 'loan_id' not found, skipping.")

    # ── Out-of-range values ──────────────────────────────────────────
    print("\n--- Out-of-range values ---")

    if "age" in df.columns:
        bad_age = ((df["age"] < 18) | (df["age"] > 100)).sum()
        print(f"Ages outside [18, 100]: {bad_age}")

    if "income" in df.columns:
        bad_income = (df["income"] < 0).sum()
        print(f"Negative income values: {bad_income}")

    if "debt" in df.columns:
        bad_debt = (df["debt"] < 0).sum()
        print(f"Negative debt values: {bad_debt}")

    if "loan_amount_requested" in df.columns:
        bad_loan_amount = (df["loan_amount_requested"] <= 0).sum()
        print(f"Non-positive loan_amount_requested values: {bad_loan_amount}")

    if "existing_credit_lines" in df.columns:
        bad_lines = (df["existing_credit_lines"] < 0).sum()
        print(f"Negative existing_credit_lines values: {bad_lines}")

    # ── Class balance ─────────────────────────────────────────────────
    print("\n--- Class balance of 'defaulted' (excluding NULL/unresolved) ---")
    if "defaulted" in df.columns:
        resolved = df["defaulted"].dropna()
        unresolved_count = df["defaulted"].isnull().sum()
        print(f"Unresolved (still NULL): {unresolved_count} ({unresolved_count / len(df):.1%} of total)")
        if len(resolved) > 0:
            balance = resolved.value_counts(normalize=True)
            print(balance.to_string())
        else:
            print("No resolved loans to compute class balance from.")
    else:
        print("Column 'defaulted' not found, skipping.")

    print("\n" + "=" * 60)
    print("END OF REPORT")
    print("=" * 60)


if __name__ == "__main__":
    import psycopg2

    conn = psycopg2.connect(
        host="localhost",
        port=5432,
        dbname="bank_db",
        user="postgres",
        password="devpass",
    )

    df = pd.read_sql(
        """
        SELECT a.*, l.loan_id, l.loan_amount_requested, l.debt, l.defaulted
        FROM applicants a
        JOIN loan_applications l ON a.applicant_id = l.applicant_id
        """,
        conn,
    )
    conn.close()

    validate_data(df)