import os
import psycopg2
from dotenv import load_dotenv

load_dotenv()  # take environment variables
psql_string = os.getenv('PSQL_CONN_STRING')

def create_dataset_dir(save_path:str='./data') -> None:
    """
    Create dataset directory if it doesn't exist

    Args:
    : save_path: path to save the augmented dataset (default: 'FARON/data')
    """
    if os.path.exists(save_path):
        os.makedirs(save_path)
        print("[INFO] Save path created")

    else:
        print("[INFO] Path already exists")

def save_to_postgis(polygons, db_config, is_regular) -> int:
    """
    Connect to PostGIS database and save polygons

    Args:
    : polygons: 
    : db_config: 
    : is_regular:
    """

    # Initiate connection

    try:
        conn = psycopg2.connect(psql_string)
        cur = conn.cursor()

    except:
        print("[ERROR] Cannot connect to the database")

        # End saving
        return -1
    
    # Close connection
    cur.close()
    conn.close()

    return 0

def save_to_gdb() -> None:
    return 0