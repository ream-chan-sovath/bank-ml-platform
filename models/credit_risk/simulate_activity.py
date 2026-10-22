"""
simulate_activity.py

Simulates a bank that never stops operating. Runs in an infinite loop,
every SLEEP_SECONDS it does a mix of:
  1. Adds one new applicant + one new loan application for them
  2. Resolves a random unresolved loan's `defaulted` outcome (NULL -> True/False)
  3. Inserts a new payment against a random still-active (non-defaulted) loan

Run this in a SEPARATE terminal from generate_data.py, and leave it running
in the background while you work through the rest of Phase 1. It reuses
generate_applicant()/generate_loan_application() from generate_data.py so
the same realistic, dependency-driven generation logic applies here too.

Stop with Ctrl+C.
"""

import time

import numpy as np
import psycopg2

from generate_data import generate_applicant, generate_loan_application

SLEEP_SECONDS = 2000

# ── Connection ────────────────────────────────────────────────────────────

conn = psycopg2.connect(
    host="localhost",
    port=5432,
    dbname="bank_db",
    user="postgres",
    password="devpass",
)
cur = conn.cursor()


# ── Insert helpers (same RETURNING pattern as generate_data.py) ─────────

def insert_applicant(applicant):
    cur.execute(
        """
        INSERT INTO applicants (age, income, employment_length_months,
                                 credit_history_months, existing_credit_lines)
        VALUES (%(age)s, %(income)s, %(employment_length_months)s,
                %(credit_history_months)s, %(existing_credit_lines)s)
        RETURNING applicant_id
        """,
        applicant,
    )
    return cur.fetchone()[0]


def insert_loan_application(applicant_id, loan):
    cur.execute(
        """
        INSERT INTO loan_applications (applicant_id, loan_amount_requested,
                                        debt, defaulted)
        VALUES (%s, %s, %s, %s)
        RETURNING loan_id
        """,
        (applicant_id, loan["loan_amount_requested"], loan["debt"], loan["defaulted"]),
    )
    return cur.fetchone()[0]


def insert_payment(loan_id, amount):
    cur.execute(
        """
        INSERT INTO payments (loan_id, amount)
        VALUES (%s, %s)
        RETURNING payment_id
        """,
        (loan_id, amount),
    )
    return cur.fetchone()[0]


# ── Activity 1: add a brand new applicant + loan application ────────────

def add_new_applicant():
    applicant = generate_applicant()
    applicant_id = insert_applicant(applicant)

    loan = generate_loan_application(applicant)
    loan_id = insert_loan_application(applicant_id, loan)

    conn.commit()
    print(f"  [new] applicant_id={applicant_id} loan_id={loan_id} defaulted={loan['defaulted']}")


# ── Activity 2: resolve a random unresolved loan's default outcome ──────

def resolve_random_loan():
    cur.execute(
        "SELECT loan_id FROM loan_applications WHERE defaulted IS NULL ORDER BY RANDOM() LIMIT 1"
    )
    row = cur.fetchone()
    if row is None:
        print("  [resolve] no unresolved loans found, skipping")
        return

    loan_id = row[0]
    # Resolve to True/False with roughly the same overall default rate
    # generate_data.py targets, so ongoing activity stays consistent
    # with the historical data's pattern.
    defaulted = bool(np.random.random() < 0.10)

    cur.execute(
        "UPDATE loan_applications SET defaulted = %s, last_updated = NOW() WHERE loan_id = %s",
        (defaulted, loan_id),
    )
    conn.commit()
    print(f"  [resolve] loan_id={loan_id} -> defaulted={defaulted}")


# ── Activity 3: insert a payment against a random active (non-defaulted) loan ──

def add_random_payment():
    # defaulted IS NOT TRUE catches both FALSE (confirmed not-defaulted)
    # and NULL (still-open) loans — a defaulted loan shouldn't keep
    # generating new payments.
    cur.execute(
        "SELECT loan_id, loan_amount_requested FROM loan_applications "
        "WHERE defaulted IS NOT TRUE ORDER BY RANDOM() LIMIT 1"
    )
    row = cur.fetchone()
    if row is None:
        print("  [payment] no active loans found, skipping")
        return

    loan_id, loan_amount_requested = row
    # A single payment is a small, noisy fraction of the total loan amount.
    amount = round(float(loan_amount_requested) * np.random.uniform(0.02, 0.08), 2)

    payment_id = insert_payment(loan_id, amount)
    conn.commit()
    print(f"  [payment] payment_id={payment_id} loan_id={loan_id} amount={amount}")


# ── Main loop ─────────────────────────────────────────────────────────────

if __name__ == "__main__":
    print(f"Simulating ongoing bank activity every {SLEEP_SECONDS}s.")

    try:
        while True:
            add_new_applicant()
            resolve_random_loan()
            add_random_payment()
            print("Simulated new activity\n")
            time.sleep(SLEEP_SECONDS)
    except KeyboardInterrupt:
        print("\nStopping simulation.")
    finally:
        cur.close()
        conn.close()