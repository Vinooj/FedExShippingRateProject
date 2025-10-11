import os
import psycopg2
from fastmcp import FastMCP

mcp = FastMCP(name="Shpping-rate-lookup-server")

# --- Database Configuration ---
DB_HOST = "localhost"
DB_NAME = "supportvectors_db"
DB_USER = "postgres"
DB_PORT = "5432"
TABLE_NAME = 'shipping_rates'


@mcp.tool()
def shipping_rate_lookup(weight: float, destination_zip: str) -> dict:
    """
    Calculate shipping rate for a package.
    
    Only call this tool after you have confirmed BOTH parameters with the user.
    
    Args:
        weight: Package weight in pounds (must be a positive number)
        destination_zip: 5-digit US ZIP code (as a string)
        
    Returns:
        Dictionary with rate information including price, currency, weight, and destination
    """
    print(f"------Inside shipping_rate_lookup. weight: {weight} lbs to zip: {destination_zip}---")
    
    DB_PASSWORD = os.getenv("DB_PASSWORD")

    try:
        # The database stores weight as an integer string in the primary key.
        lookup_weight = str(round(float(weight)))
    except (ValueError, TypeError):
        return {"error": "Invalid weight provided"}

    conn = None
    try:
        conn = psycopg2.connect(
            host=DB_HOST,
            dbname=DB_NAME,
            user=DB_USER,
            password=DB_PASSWORD,
            port=DB_PORT
        )
        cur = conn.cursor()

        # Assumes the table has a 'service_lbs' column for the weight.
        query = f"SELECT * FROM {TABLE_NAME} WHERE service_lbs = %s"
        cur.execute(query, (lookup_weight,))
        result = cur.fetchone()

        if result:
            colnames = [desc[0] for desc in cur.description]
            rate_data = dict(zip(colnames, result))
            rate_data['destination_zip'] = destination_zip # Add destination_zip to the result
            print(f"Found rate data: {rate_data}")
            return rate_data
        else:
            print(f"No shipping rate data found: {rate_data}")
            return {"error": f"No shipping rate found for weight {lookup_weight} lbs."}

    except (Exception, psycopg2.DatabaseError) as error:
        print(f"Database error: {error}")
        return {"error": f"Database error: {error}"}
    finally:
        if conn:
            cur.close()
            conn.close()

if __name__ == "__main__":
    mcp.run(transport="http", host="127.0.0.1", port=9000)
