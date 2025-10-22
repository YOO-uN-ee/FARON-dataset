import os
from Typing import List, Dict, Tuple, Union

import random
from shapely.geometry import Point, Line, Polygon
import matplotlib.pyplot as plt

import psycopg2
from dotenv import load_dotenv

load_dotenv()  # take environment variables
psql_string = os.getenv('PSQL_CONN_STRING')

def create_dataset_dir(save_path:str='./data') -> None:
    """
    Create dataset directory if it doesn't exist

    Args:
        save_path (str): path to save the augmented dataset (default: 'FARON/data')
    """
    if os.path.exists(save_path):
        os.makedirs(save_path)
        print("[INFO] Save path created")

    else:
        print("[INFO] Path already exists")

def plot_polygons(polygons:List[Union[Point, Line, Polygon]],
                  canvas_bounds:Tuple[int],
                  save_path:str) -> None:
    """
    Visualize the generated polygons on a 2D plot.

    Args:
        polgyons (list): As list of Shapely Point, Line, or Polygon object
        canvas_bounds (tuple): The boundaries of the canvas for plotting
        save_path (str): Path to store the visualized polygons
    """
    # Initialize the 2d plot plane
    fig, ax = plt.subplots(figsize=(15, 15))
    min_x, min_y, max_x, max_y = canvas_bounds

    # Set plot limits and aspect ratio
    ax.set_xlim(min_x, max_x)
    ax.set_ylim(min_y, max_y)
    ax.set_aspect('equal', adjustable='box')
    
    # Draw each polygon
    for poly in polygons:
        # Generate a random color for each polygon
        color = (random.random(), random.random(), random.random())
        x, y = poly.exterior.xy
        ax.fill(x, y, color=color, alpha=0.7, edgecolor='black')    # TODO: maybe remove the edgecolor

    ax.set_xticks([]) # Hides x-axis tick marks and labels
    ax.set_yticks([]) # Hides y-axis tick marks and labels
    
    plt.savefig(save_path)

def save_to_postgis(polygons: Union[Point, Line, Polygon], 
                    db_config:Dict[str, str], 
                    is_regular:bool) -> int:
    """
    Connect to PostGIS database and save polygons

    Args:
        polygons (Union):
        db_config (Dict): 
        is_regular (bool):
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