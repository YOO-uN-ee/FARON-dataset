import os
import re
import psycopg2
import shapely.wkb
from shapely.geometry import Polygon, Point, LineString
import matplotlib.pyplot as plt
import random

# --- 1. Configuration ---
# I've corrected the invalid SQL from your original text
# (e.g., "(((geom_type...)))" is now "(geom_type...)")
SQL_STEPS_TEXT = """
--- SQL Steps in Execution Order ---

-- Step 1 (L4: Index Scan) --
-- Output Table: temp_yiizphvh
CREATE TEMPORARY TABLE temp_yiizphvh AS (SELECT * FROM public.generated_geometries WHERE (id = 2) AND ((geom_type)::text = 'Polygon'::text));

-- Step 2 (L4: Seq Scan) --
-- Output Table: temp_rhjigwgv
CREATE TEMPORARY TABLE temp_rhjigwgv AS (SELECT * FROM public.generated_geometries WHERE ((geom_type)::text = 'Polygon'::text));

-- Step 3 (L3: Nested Loop) --
-- Output Table: temp_dhrxcykw
CREATE TEMPORARY TABLE temp_dhrxcykw AS (SELECT * FROM temp_yiizphvh AS t2 INNER JOIN temp_rhjigwgv AS t1 ON st_within(t1.geom, t2.geom));

-- Step 4 (L3: Seq Scan) --
-- Output Table: temp_gdirqspf
CREATE TEMPORARY TABLE temp_gdirqspf AS (SELECT * FROM public.generated_geometries WHERE ((geom_type)::text = 'POINT'::text));

-- Step 5 (L2: Nested Loop) --
-- Output Table: temp_rtfzqmvl
CREATE TEMPORARY TABLE temp_rtfzqmvl AS (SELECT * FROM temp_dhrxcykw AS t2 INNER JOIN temp_gdirqspf AS t_final ON st_within(t_final.geom, t2.geom));

-- Step 6 (L1: Sort) --
-- Output Table: temp_kgqgvbsh
CREATE TEMPORARY TABLE temp_kgqgvbsh AS (SELECT * FROM temp_rtfzqmvl ORDER BY t_final.id);

-- Step 7 (L0: Unique) --
-- Output Table: temp_vzgioibc
CREATE TEMPORARY TABLE temp_vzgioibc AS (SELECT * FROM (unknown_operation: Unique));

--- Final Query (Root Node) ---
The final result is in table: temp_vzgioibc
(Run 'SELECT * FROM temp_vzgioibc;' to see results)
"""

# Your database connection
DB_CONFIG = {
    "dbname": "postgres",
    "user": "postgres",
    "password": "jiYOON7162@",
    "host": "localhost", 
    "port": "5432"
}

# Directory to save the PNG files
OUTPUT_DIR = "intermediate_plots"


# --- 2. Helper Function for Plotting ---

def plot_geoms_to_file(geometries, title, save_path):
    """
    Plots a list of Shapely geometries and saves to a file.
    """
    fig, ax = plt.subplots(figsize=(10, 10))
    ax.set_aspect('equal', adjustable='box')
    
    if not geometries:
        ax.text(0.5, 0.5, "No geometries", 
                horizontalalignment='center', verticalalignment='center',
                transform=ax.transAxes)
    else:
        # Get bounds to set plot limits
        all_geoms_union = shapely.ops.unary_union(geometries)
        min_x, min_y, max_x, max_y = all_geoms_union.bounds
        buffer = max(max_x - min_x, max_y - min_y, 10) * 0.1 # 10% buffer, min 1 unit
        ax.set_xlim(min_x - buffer, max_x + buffer)
        ax.set_ylim(min_y - buffer, max_y + buffer)

    for geom in geometries:
        color = (random.random(), random.random(), random.random())
        if geom.geom_type == 'Polygon':
            x, y = geom.exterior.xy
            ax.fill(x, y, color=color, alpha=0.7, edgecolor='black')
        elif geom.geom_type == 'LineString':
            x, y = geom.xy
            ax.plot(x, y, color='blue', linewidth=1, alpha=0.8)
        elif geom.geom_type == 'Point':
            ax.scatter(geom.x, geom.y, c='black', s=10, zorder=5)
    
    ax.set_title(title, fontsize=12)
    ax.set_xticks([])
    ax.set_yticks([])
    
    plt.savefig(save_path, dpi=100, bbox_inches='tight')
    plt.close(fig) # Close the figure to save memory


# --- 3. Main Execution Script ---

if __name__ == "__main__":
    
    if not os.path.exists(OUTPUT_DIR):
        os.makedirs(OUTPUT_DIR)
        print(f"Created output directory: {OUTPUT_DIR}")

    # --- Pass 1: Parse All Steps ---
    print("Parsing all SQL steps...")
    parsed_steps = []
    
    step_blocks = re.split(r'-- Step ', SQL_STEPS_TEXT)[1:]
    step_pattern = re.compile(r'(\d+ \([^)]+\))')
    table_pattern = re.compile(r'-- Output Table: (temp_\w+)')
    # Regex to find the full CREATE TABLE...; statement
    sql_pattern = re.compile(r'(CREATE TEMPORARY TABLE .*?;)', re.DOTALL | re.IGNORECASE)

    for block in step_blocks:
        step_match = step_pattern.search(block)
        table_match = table_pattern.search(block)
        sql_match = sql_pattern.search(block)

        if step_match and table_match and sql_match:
            step_info = step_match.group(1).replace(':', '_').replace('/', '_')
            output_table = table_match.group(1)
            sql_query = sql_match.group(1).strip()
            
            parsed_steps.append({
                "info": step_info,
                "table": output_table,
                "sql": sql_query
            })
    
    print(f"Found {len(parsed_steps)} steps to execute.")

    # --- Pass 2: Correct, Execute, Fetch, and Plot ---
    try:
        # Set the search_path in the connection 'options'
        print(f"Connecting to database '{DB_CONFIG['dbname']}'...")
        conn_options = f"-c search_path=public,\"{DB_CONFIG['user']}\""
        with psycopg2.connect(**DB_CONFIG, options=conn_options) as conn:
            with conn.cursor() as cur:
                
                # We still need to ensure PostGIS is enabled
                print("Enabling PostGIS extension (CREATE EXTENSION IF NOT EXISTS postgis)...")
                cur.execute("CREATE EXTENSION IF NOT EXISTS postgis;")
                print("PostGIS enabled. Session search_path is set.")
                
                print("Executing steps...")
                
                for i, step in enumerate(parsed_steps):
                    
                    step_info = step["info"]
                    output_table = step["table"]
                    sql_command = step["sql"]
                    
                    print(f"\n--- Executing: {step_info} ---")

                    # --- DYNAMIC SQL CORRECTION ---
                    
                    # 1. Fix "Unique" operation
                    if "unknown_operation: Unique" in sql_command:
                        if i == 0:
                            print("  !!! ERROR: 'Unique' operation on first step. Cannot fix.")
                            break
                        previous_table = parsed_steps[i-1]["table"]
                        sql_command = sql_command.replace(
                            "(SELECT * FROM (unknown_operation: Unique))",
                            f"(SELECT DISTINCT * FROM {previous_table})"
                        )
                        print(f"  > Corrected 'Unique' to use: {previous_table}")

                    # 2. Fix "JOIN" ambiguity
                    if "INNER JOIN" in sql_command.upper() and "SELECT *" in sql_command.upper():
                        join_match = re.search(r'INNER\s+JOIN\s+\S+\s+AS\s+(\w+)', sql_command, re.IGNORECASE)
                        if join_match:
                            second_alias = join_match.group(1)
                            sql_command = sql_command.replace("SELECT *", f"SELECT {second_alias}.*", 1)
                            print(f"  > Corrected 'SELECT *' to 'SELECT {second_alias}.*'")
                        else:
                            print("  > WARNING: Could not correct JOIN, aliases not found.")

                    # --- EXECUTION ---
                    
                    # 1. Execute the (now corrected) SQL
                    try:
                        cur.execute(sql_command)
                        print(f"  Created temporary table: {output_table}")
                    except Exception as e:
                        print(f"  !!! ERROR executing step: {e}")
                        print(f"  Failed SQL: {sql_command}")
                        break 
                    
                    # 2. Fetch all 'geom' columns from the new table
                    geometries = []
                    try:
                        # --- THIS IS THE FIX ---
                        # Explicitly state the schema: public.ST_AsWKB
                        cur.execute(f"SELECT public.ST_AsWKB(geom::geometry) FROM {output_table};")
                        # ---
                        
                        results = cur.fetchall()
                        
                        for (wkb_geom,) in results:
                            if wkb_geom:
                                geometries.append(shapely.wkb.loads(wkb_geom))
                        print(f"  Fetched {len(geometries)} geometries from {output_table}.")
                        
                    except Exception as e:
                        print(f"  !!! ERROR fetching geometries: {e}")
                        print(f"Example error: {e}")
                        print(f"  (Did the table '{output_table}' have a 'geom' column?)")
                        break # Stop the loop on error

                    # 3. Plot the geometries to a PNG file
                    save_path = os.path.join(OUTPUT_DIR, f"{step_info.replace(' ', '_')}.png")
                    title = f"{step_info}\n{output_table} ({len(geometries)} geometries)"
                    
                    try:
                        plot_geoms_to_file(geometries, title, save_path)
                        print(f"  Successfully saved plot to: {save_path}")
                    except Exception as e:
                        print(f"  !!! ERROR plotting geometries: {e}")

            print("\n--- All steps complete. ---")

    except (Exception, psycopg2.DatabaseError) as error:
        print(f"\nDatabase connection error: {error}")