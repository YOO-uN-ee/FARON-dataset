import psycopg2 # or import psycopg for psycopg3

# Replace with your actual database credentials
db_params = {
    "dbname": "postgres",
    "user": "postgres",
    "password": "jiYOON7162@",
    "host": "localhost", # e.g., "localhost" or an IP address
    "port": "5432" # Default PostgreSQL port
}

try:
    # Establish the connection
    conn = psycopg2.connect(**db_params) # or psycopg.connect(**db_params)

    # Create a cursor object
    cursor = conn.cursor()

    # Execute a simple query to test the connection
    cursor.execute("SELECT 1")

    # Fetch the result (optional, but good for confirmation)
    result = cursor.fetchone()
    print(f"Connection successful! Query result: {result}")

except psycopg2.OperationalError as e: # or psycopg.OperationalError for psycopg3
    print(f"Error: Unable to connect to the database. Details: {e}")
except Exception as e:
    print(f"An unexpected error occurred: {e}")
finally:
    # Close the cursor and connection in a finally block to ensure cleanup
    if 'cursor' in locals() and cursor:
        cursor.close()
    if 'conn' in locals() and conn:
        conn.close()
        print("Database connection closed.")