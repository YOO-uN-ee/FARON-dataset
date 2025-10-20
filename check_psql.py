import os
import psycopg2
from dotenv import load_dotenv

load_dotenv()  # take environment variables

psql_string = os.getenv('PSQL_CONN_STRING')

try:
    conn = psycopg2.connect(
        psql_string
    )

    cur = conn.cursor()
    cur.execute("SELECT version();")
    print(cur.fetchone())

    cur.close()
    conn.close()
except:
    print("I am unable to connect to the database")