import psycopg2

conn = psycopg2.connect(host="localhost", port=5432, dbname="bank_db", user="postgres", password="devpass")
cur = conn.cursor()

cur.execute("""
    CREATE TABLE applicants (
        applicant_id SERIAL PRIMARY KEY,
        age INT,
        income NUMERIC,
        employment_length_months INT,
        credit_history_months INT,
        existing_credit_lines INT
    )
""")

cur.execute("""
    CREATE TABLE loan_applications (
        loan_id SERIAL PRIMARY KEY,
        applicant_id INT REFERENCES applicants(applicant_id),
        loan_amount_requested NUMERIC,
        debt NUMERIC,
        defaulted BOOLEAN,
        application_date DATE DEFAULT CURRENT_DATE,
        last_updated TIMESTAMP DEFAULT NOW()
    )
""")

cur.execute("""
    CREATE TABLE payments (
        payment_id SERIAL PRIMARY KEY,
        loan_id INT REFERENCES loan_applications(loan_id),
        amount NUMERIC,
        payment_date DATE DEFAULT CURRENT_DATE
    )
""")

conn.commit()
cur.close()
conn.close()