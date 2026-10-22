"""
generate_data.py
 
Generates realistic, imbalanced synthetic credit application data and
inserts it into the 3-table schema (applicants -> loan_applications).
 
Default risk is a deliberate function of applicant features (debt-to-income,
credit history length, existing credit lines), not random noise, so the
pattern is genuinely learnable by a model in Phase 2. Real-world noise is
layered on top: noisy feature distributions, a probabilistic (not
deterministic) default outcome, and a small amount of injected missingness
to mimic dirty real-world data.
"""
 
import numpy as np
import psycopg2
 
# ── Connection ────────────────────────────────────────────────────────────
 
conn = psycopg2.connect(
    host="localhost",
    port=5432,
    dbname="bank_db",
    user="postgres",
    password="devpass",
)
cur = conn.cursor()
 
 
# ── Applicant generation ─────────────────────────────────────────────────
 
def generate_applicant():
    """
    Generate one applicant's person-level data, with features that
    genuinely depend on each other the way a real person's profile
    would — not five independent random draws that happen to land in
    the same row.
 
    Dependency chain:
        age
         ├─> employment_length_months  (capped by adult years lived)
         │        │
         │        v
         └─────> income                (career growth w/ age, tenure bump)
                    │
                    v
         age ──> credit_history_months (capped by adult years, nudged by income)
         age, income ──> existing_credit_lines (more time + more income = more credit offered)
 
    Every step still keeps real noise on top of the structural
    relationship, so it's realistic, not deterministic.
    """
    # ── age: the root variable, nothing upstream of it ──
    age = int(np.clip(np.random.normal(38, 11), 18, 75))
    adult_years = age - 18  # years since legally able to work/borrow
 
    # ── employment_length_months: capped by how long they've been an
    # adult, can't exceed that no matter how noisy the draw gets ──
    max_possible_employment = max(adult_years * 12, 1)
    # most people are relatively new in their *current* job even late
    # in their career (job-hopping, promotions resetting tenure), so
    # skew toward the lower end of what's possible, with noise
    employment_length_months = int(
        np.clip(np.random.exponential(max_possible_employment * 0.25), 0, max_possible_employment)
    )
 
    # ── income: driven by age (career growth, plateauing after ~50)
    # and by employment_length_months (longer tenure -> raises/promotions),
    # plus its own independent noise (skill, industry, luck) ──
    age_factor = age if age <= 50 else 50 - (age - 50) * 0.3  # gentle plateau/decline post-50
    tenure_bonus = employment_length_months * 15  # longer tenure -> modestly higher income
    base_income = 950 * max(age_factor, 10) + tenure_bonus
    income = float(np.clip(base_income * np.random.lognormal(mean=0, sigma=0.4), 8000, 350000))
 
    # ── credit_history_months: capped by adult years like employment,
    # but independently nudged upward for higher earners (higher income
    # applicants tend to have opened credit products earlier/more) ──
    max_possible_history = max(adult_years * 12, 1)
    income_percentile_boost = np.clip(income / 120000, 0, 1)  # 0-1 scale, richer -> higher boost
    history_center = max_possible_history * (0.45 + 0.25 * income_percentile_boost)
    credit_history_months = int(
        np.clip(np.random.normal(history_center, max_possible_history * 0.15),
                0, max_possible_history)
    )
 
    # ── existing_credit_lines: more accumulated over time (age) and
    # more offered to higher earners (income), plus noise ──
    lines_center = 1.0 + (adult_years / 12) * 0.15 + (income / 100000) * 1.2
    existing_credit_lines = int(np.clip(np.random.poisson(max(lines_center, 0.1)), 0, 15))
 
    return {
        "age": age,
        "income": round(income, 2),
        "employment_length_months": employment_length_months,
        "credit_history_months": credit_history_months,
        "existing_credit_lines": existing_credit_lines,
    }
 

# ── Loan application generation ──────────────────────────────────────────

def generate_loan_application(applicant):
    """
    Generate a loan request for this applicant, with a default outcome
    that is a genuine (but noisy) function of their features.
    
    Design:
    - debt is generated as a noisy multiple of income, so debt to income varies realistically across applicants
    - loan_amount_requested is independently noisy, loosely scaled to income
    - risk_score combines debt-to-income (higher = riskier), credit_history_months (longer = safer), and eisting_credit_lines (more = riskier, proxy for over-leverage)
    - the score is squashed through a sigmoid into a proability, then an actual random draw decides the outcome - this deeps the label genuinely probabilistic (noisy), not a hard rule
    """

    income = applicant["income"]

    # Debt: noisy multiple of income, but also pushed up by how many
    # existing credit lines they already hold (more open lines -> more
    # accumulated balances in real life).
    lines_debt_multiplier = 1 + 0.12 * applicant["existing_credit_lines"]
    debt = float(
        np.clip(income * np.random.lognormal(mean=-1.1, sigma=0.7) * lines_debt_multiplier,
                0, income * 3)
    )

    # Loan amount requested: scales with income, but people who already
    # carry more debt tend to ask for relatively smaller *additional*
    # loans (less remaining borrowing appetite/capacity), captured as a
    # mild negative pull from current debt-to-income.
    debt_to_income_so_far = debt / income if income > 0 else 0
    request_fraction = np.clip(np.random.uniform(0.15, 0.7) - 0.1 * debt_to_income_so_far, 0.03, None)
    loan_amount_requested = float(
        np.clip(income * request_fraction + np.random.normal(0, 800), 500, None)
    )
 
    debt_to_income = debt / income if income > 0 else 0
 
    risk_score = (
        2.2 * debt_to_income
        - 0.35 * (applicant["credit_history_months"] / 12)
        + 0.18 * applicant["existing_credit_lines"]
        - 0.015 * (applicant["age"] - 38)          # slight protective effect of age/stability
        + np.random.normal(0, 0.4)                  # unexplainable noise — real defaults
                                                       # have causes a model can never see
                                                       # (job loss, medical bills, etc.)
    )
 
    probability_of_default = 1 / (1 + np.exp(-risk_score + 1.6))  # +1.6 shifts baseline down
                                                                     # so overall rate lands
                                                                     # in the realistic range
    defaulted = bool(np.random.random() < probability_of_default)
 
    return {
        "loan_amount_requested": round(loan_amount_requested, 2),
        "debt": round(debt, 2),
        "defaulted": defaulted,
    }



# ── Insert helpers (RETURNING pattern) ───────────────────────────────────
 
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

# ── Realistic dirtiness: inject a small amount of missing data ──────────
 
def maybe_null(value, probability=0.015):
    """With a small probability, return None instead of the value —
    mimics real-world missing/unreported fields (e.g., income not
    disclosed on some applications)."""
    return None if np.random.random() < probability else value

# ── Main generation loop ─────────────────────────────────────────────────
 
def generate_and_insert(n=5000):
    defaults = []
 
    for i in range(n):
        applicant = generate_applicant()
 
        # Inject light missingness into a couple of fields, the way real
        # intake forms sometimes have unreported values.
        applicant["income"] = maybe_null(applicant["income"])
        applicant["employment_length_months"] = maybe_null(applicant["employment_length_months"])
 
        # Can't compute a risk score off a missing income — fall back to
        # a neutral placeholder for the risk calculation only (the NULL
        # is still what gets stored in the DB for applicants.income).
        income_for_risk = applicant["income"] if applicant["income"] is not None else 30000
        applicant_for_risk = {**applicant, "income": income_for_risk}
 
        applicant_id = insert_applicant(applicant)
 
        loan = generate_loan_application(applicant_for_risk)
        insert_loan_application(applicant_id, loan)
 
        defaults.append(loan["defaulted"])
 
        if (i + 1) % 1000 == 0:
            conn.commit()
            print(f"  ...{i + 1}/{n} inserted")
 
    conn.commit()
    return defaults


if __name__ == "__main__":
    print("Generating synthetic applicants + loan applications...")
    defaults = generate_and_insert(n=5000)
 
    cur.close()
    conn.close()
 
    default_rate = np.mean(defaults)
    print(f"\nDone. Inserted {len(defaults)} applicants + loan applications.")
    print(f"Default rate: {default_rate:.2%}")
 
    if not (0.05 <= default_rate <= 0.15):
        print(
            "WARNING: default rate is outside the target 5-15% range. "
            "Adjust the +1.6 shift or the risk_score weights in "
            "generate_loan_application() and re-run."
        )
