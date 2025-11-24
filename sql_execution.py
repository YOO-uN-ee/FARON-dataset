import geopandas as gpd
import sqlalchemy
from sqlalchemy import URL
import matplotlib.pyplot as plt
import os
import re

class StatefulSqlVisualizer:
    """
    Manages the execution and visualization of decomposed SQL query stages
    by using a single, persistent database connection to support
    temporary tables and automatically inferring dependencies.
    """
    
    def __init__(self, db_url):
        """
        Initializes the visualizer and opens a persistent database connection.

        Args:
            db_url (str): The SQLAlchemy database connection string.
                          Example: "postgresql://user:pass@host:port/dbname"
        """
        self.stages = []
        self.results_gdf = {}
        self.temp_table_to_stage_name = {}
        
        try:
            self.engine = sqlalchemy.create_engine(db_url)
            # Open a single, persistent connection
            self.connection = self.engine.connect()
            print("Database connection successful.")
            
            print("Enabling PostGIS extension...")
            self.connection.execute(sqlalchemy.text("CREATE EXTENSION IF NOT EXISTS postgis;"))
            print("PostGIS enabled.")
            
        except Exception as e:
            print(f"Error connecting to database: {e}")
            self.engine = None
            self.connection = None

    def add_stages_from_text(self, sql_steps_text):
        """
        Parses a block of SQL steps, infers dependencies, and adds them.
        
        Args:
            sql_steps_text (str): The multi-line string of SQL steps.
        """
        print("Parsing SQL steps and building dependency graph...")
        
        step_blocks = re.split(r'-- Step ', sql_steps_text)[1:]
        
        for i, block in enumerate(step_blocks):
            try:
                step_info = re.search(r'(\d+ \([^)]+\))', block).group(1)
                output_table = re.search(r'-- Output Table: (temp_\w+)', block).group(1)
                sql_command = re.search(r'(CREATE TEMPORARY TABLE .*?;)', block, re.DOTALL | re.IGNORECASE).group(1)
                
                all_temp_tables = re.findall(r'(temp_\w+)', sql_command)
                
                input_tables = sorted(list(set(
                    [tbl for tbl in all_temp_tables if tbl != output_table]
                )))
                
                trace_stage_names = [
                    self.temp_table_to_stage_name[tbl] for tbl in input_tables
                    if tbl in self.temp_table_to_stage_name
                ]
                
                stage_name = f"{step_info.replace(' ', '_').replace(':', '_').replace('/', '_')}"
                
                self.stages.append({
                    "name": stage_name,
                    "sql_create": sql_command,
                    "output_table": output_table,
                    "traces": trace_stage_names
                })
                
                self.temp_table_to_stage_name[output_table] = stage_name
                
            except Exception as e:
                print(f"Error parsing step {i+1}: {e}\nBlock: {block[:100]}...")
                
        print(f"Added {len(self.stages)} stages automatically.")

    def _correct_sql(self, sql, stage_index):
        
        if "unknown_operation: Unique" in sql:
            if stage_index == 0:
                raise ValueError("Cannot run 'Unique' on the first step")
            previous_table = self.stages[stage_index - 1]["output_table"]
            sql = sql.replace(
                "(SELECT * FROM (unknown_operation: Unique))",
                f"(SELECT DISTINCT * FROM {previous_table})"
            )
            print(f"  > Corrected 'Unique' to use: {previous_table}")

        if "INNER JOIN" in sql.upper() and "SELECT *" in sql.upper():
            join_match = re.search(r'INNER\s+JOIN\s+\S+\s+AS\s+(\w+)', sql, re.IGNORECASE)
            if join_match:
                second_alias = join_match.group(1)
                sql = sql.replace("SELECT *", f"SELECT {second_alias}.*", 1)
                print(f"  > Corrected 'SELECT *' to 'SELECT {second_alias}.*'")

        return sql

    def run_and_plot_stages(self, output_dir=".", geom_col="geom", total_bounds=None):
        """
        Executes all added stages in order on one connection and saves plots.
        """
        if not self.connection:
            print("Cannot run stages: No database connection.")
            return

        os.makedirs(output_dir, exist_ok=True)
        
        for i, stage in enumerate(self.stages):
            name = stage["name"]
            sql_create_command = stage["sql_create"]
            output_table = stage["output_table"]
            trace_names = stage["traces"]
            
            print(f"\n--- Executing Stage: {name} ---")

            try:
                fig, ax = plt.subplots(figsize=(10, 10))
                
                if trace_names:
                    print(f"  > Plotting traces from: {trace_names}")
                    for trace_name in trace_names:
                        trace_gdf = self.results_gdf.get(trace_name)
                        
                        if trace_gdf is not None and not trace_gdf.empty:
                            trace_color = '#999999' if trace_gdf.geom_type.iloc[0] == 'Point' else 'gray'
                            trace_gdf.plot(
                                ax=ax, facecolor=trace_color, edgecolor='none',
                                alpha=0.3, zorder=1
                            )
                
                sql_to_run = self._correct_sql(sql_create_command, i)
                self.connection.execute(sqlalchemy.text(sql_to_run))
                print(f"  > Created temp table: {output_table}")

                gdf = gpd.read_postgis(
                    f"SELECT * FROM {output_table}", 
                    self.connection, 
                    geom_col=geom_col
                )
                print(f"  > Query successful. Found {len(gdf)} features.")
                
                if not gdf.empty:
                    plot_color = 'red' if gdf.geom_type.iloc[0] == 'Point' else 'lightblue'
                    gdf.plot(
                        ax=ax, edgecolor='black', facecolor=plot_color,
                        alpha=0.8, zorder=5
                    )
                else:
                    print("  > Current stage is empty.")
                
                if total_bounds:
                    ax.set_xlim(total_bounds[0], total_bounds[2])
                    ax.set_ylim(total_bounds[1], total_bounds[3])
                
                ax.set_title(name)
                output_filename = os.path.join(output_dir, f"{name}.png")
                fig.savefig(output_filename)
                
                print(f"Saved plot to {output_filename}")
                plt.close(fig) 

                self.results_gdf[name] = gdf

            except Exception as e:
                print(f"  !!! Error executing stage {name}: {e}")
                self.results_gdf[name] = None
                # Stop the whole process if one step fails
                break

        print("\nAll stages complete.")

    def close(self):
        if self.connection:
            self.connection.close()
            print("Database connection closed.")


if __name__ == "__main__":
    DB_URL = URL.create(
        "postgresql+psycopg2",
        username="postgres",
        password="jiYOON7162@", # plain text
        host="localhost",
        port=5432,
        database="postgres",
    )

    CANVAS_BOUNDS = (0, 0, 100, 100)

    SQL_STEPS_TEXT = """
    --- SQL Steps in Execution Order ---

    -- Step 1 (L4: Index Scan) --
    -- Output Table: temp_znjughrk
    CREATE TEMPORARY TABLE temp_znjughrk AS (SELECT * FROM public.generated_geometries WHERE (id = 1) AND ((geom_type)::text = 'Polygon'::text));

    -- Step 2 (L4: Seq Scan) --
    -- Output Table: temp_rtvtbklp
    CREATE TEMPORARY TABLE temp_rtvtbklp AS (SELECT * FROM public.generated_geometries WHERE ((geom_type)::text = 'Polygon'::text));

    -- Step 3 (L3: Nested Loop) --
    -- Output Table: temp_yimcnlzg
    CREATE TEMPORARY TABLE temp_yimcnlzg AS (SELECT * FROM temp_znjughrk AS t2 INNER JOIN temp_rtvtbklp AS t1 ON st_within(t1.geom, t2.geom));

    -- Step 4 (L3: Seq Scan) --
    -- Output Table: temp_xvamoeuc
    CREATE TEMPORARY TABLE temp_xvamoeuc AS (SELECT * FROM public.generated_geometries WHERE ((geom_type)::text = 'Point'::text));

    -- Step 5 (L2: Nested Loop) --
    -- Output Table: temp_jiqrgprf
    CREATE TEMPORARY TABLE temp_jiqrgprf AS (SELECT * FROM temp_yimcnlzg AS t2 INNER JOIN temp_xvamoeuc AS t_final ON st_within(t_final.geom, t2.geom));

    -- Step 6 (L1: Sort) --
    -- Output Table: temp_jxjtjuwd
    CREATE TEMPORARY TABLE temp_jxjtjuwd AS (SELECT * FROM temp_jiqrgprf AS t_final ORDER BY t_final.id);

    -- Step 7 (L0: Unique) --
    -- Output Table: temp_uxdbsfqx
    CREATE TEMPORARY TABLE temp_uxdbsfqx AS (SELECT * FROM (unknown_operation: Unique));

    --- Final Query (Root Node) ---
    The final result: temp_vzgioibc
    """

    visualizer = StatefulSqlVisualizer(DB_URL)
    visualizer.add_stages_from_text(SQL_STEPS_TEXT)

    visualizer.run_and_plot_stages(
        output_dir="my_query_plots_fully_auto",
        total_bounds=CANVAS_BOUNDS,
        geom_col="geom"
    )

    visualizer.close()