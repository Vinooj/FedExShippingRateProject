# pip install psycopg2-binary

import csv
import psycopg2
import re

# --- Database Configuration ---
# Replace with your actual PostgreSQL connection details
DB_HOST = "localhost"
DB_NAME = "supportvectors_db"
DB_USER = "postgres"
DB_PASSWORD = "<your_password>"
DB_PORT = "5432"

# --- CSV and Table Configuration ---
CSV_FILE = './output/output.csv'
TABLE_NAME = 'shipping_rates'

def sanitize_column_name(name):
    """Sanitizes a string to be a valid SQL column name."""
    name = name.strip()
    name = re.sub(r'\s+', '_', name)
    name = re.sub(r'[^a-zA-Z0-9_]', '', name)
    name = name.lower()
    if name and name[0].isdigit():
        name = f"_{name}"
    return name

def create_and_insert_data():
    """Reads data from a CSV and inserts it into a new PostgreSQL table."""
    conn = None
    try:
        # --- 1. Connect to the PostgreSQL database ---
        conn = psycopg2.connect(
            host=DB_HOST,
            dbname=DB_NAME,
            user=DB_USER,
            password=DB_PASSWORD,
            port=DB_PORT
        )
        cur = conn.cursor()

        # --- 2. Read CSV and prepare for table creation ---
        with open(CSV_FILE, 'r', encoding='utf-8') as f:
            reader = csv.reader(f)
            header = next(reader)

            sanitized_columns = [sanitize_column_name(h) for h in header]

            # --- 3. Dynamically create the CREATE TABLE statement ---
            create_table_query = f"CREATE TABLE IF NOT EXISTS {TABLE_NAME} (\n"
            # First column is VARCHAR, the rest are NUMERIC
            create_table_query += f"    {sanitized_columns[0]} VARCHAR(255) PRIMARY KEY,\n"
            for col_name in sanitized_columns[1:]:
                create_table_query += f"    {col_name} NUMERIC(10, 2),\n"
            create_table_query = create_table_query.rstrip(',\n') + "\n);"

            print("--- Executing CREATE TABLE statement ---")
            print(create_table_query)
            cur.execute(create_table_query)
            print(f"Table '{TABLE_NAME}' created successfully (or already exists).")

            # --- 4. Prepare and execute INSERT statements ---
            insert_query = f"INSERT INTO {TABLE_NAME} ({', '.join(sanitized_columns)}) VALUES ({', '.join(['%s'] * len(sanitized_columns))})"

            print("\n--- Inserting data ---")
            row_count = 0
            for row in reader:
                # Ensure row has the correct number of columns
                if len(row) == len(sanitized_columns):
                    cur.execute(insert_query, row)
                    row_count += 1
                else:
                    print(f"Skipping malformed row: {row}")


            conn.commit()
            print(f"{row_count} rows inserted successfully.")

    except (Exception, psycopg2.DatabaseError) as error:
        print(f"--- Error ---")
        print(error)
        if conn:
            conn.rollback()
    finally:
        if conn:
            cur.close()
            conn.close()
            print("\nDatabase connection closed.")

if __name__ == '__main__':
    create_and_insert_data()