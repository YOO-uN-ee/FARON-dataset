import geopandas as gpd
import sqlalchemy
import matplotlib.pyplot as plt
import os

class SqlStageVisualizer:
    """
    Manages the execution and visualization of decomposed SQL query stages.

    This class connects to a PostGIS database, runs a series of SQL queries
    in a defined order, saves a plot of the resulting geometry for each stage,
    and stores the GeoDataFrames for later access.
    """
    
    def __init__(self, db_url):
        """
        Initializes the visualizer with a database connection.

        Args:
            db_url (str): The SQLAlchemy database connection string.
                          Example: "postgresql://user:pass@host:port/dbname"
        """
        try:
            self.engine = sqlalchemy.create_engine(db_url)
            print("Database connection successful.")
        except Exception as e:
            print(f"Error connecting to database: {e}")
            self.engine = None
        
        self.stages = []
        self.results = {}

    def add_stage(self, name, sql_query):
        """
        Adds a query stage to the execution queue.

        The stages will be executed in the order they are added.

        Args:
            name (str): A unique name for this stage (e.g., "01_filtered_parks").
            sql_query (str): The SQL query for this stage.
        """
        self.stages.append({"name": name, "sql": sql_query})
        print(f"Stage '{name}' added.")

    def run_and_plot_stages(self, output_dir=".", geom_col="geom"):
        """
        Executes all added stages in order and saves plots.

        Args:
            output_dir (str): The directory to save the output PNG files.
            geom_col (str): The name of the geometry column in your queries.
        """
        if not self.engine:
            print("Cannot run stages: No database connection.")
            return

        # Ensure the output directory exists
        os.makedirs(output_dir, exist_ok=True)

        for stage in self.stages:
            name = stage["name"]
            sql = stage["sql"]
            print(f"\n--- Executing Stage: {name} ---")

            try:
                # Run the query and load data into GeoDataFrame
                gdf = gpd.read_postgis(sql, self.engine, geom_col=geom_col)
                
                # Store the result
                self.results[name] = gdf
                print(f"Query successful. Found {len(gdf)} features.")

                if gdf.empty:
                    print("GeoDataFrame is empty. No plot will be generated.")
                    continue

                # --- Plotting ---
                ax = gdf.plot(
                    figsize=(10, 10), 
                    edgecolor='black', 
                    facecolor='lightblue',
                    alpha=0.7
                )
                ax.set_title(name)
                
                # Save the figure
                fig = ax.get_figure()
                output_filename = os.path.join(output_dir, f"{name}.png")
                fig.savefig(output_filename)
                
                print(f"Saved plot to {output_filename}")
                plt.close(fig) # Close the plot to free up memory

            except Exception as e:
                print(f"Error executing stage {name}: {e}")
                self.results[name] = None # Store None on failure

        print("\nAll stages complete.")

    def get_geodataframe(self, name):
        """
        Retrieves the stored GeoDataFrame for a completed stage.

        Args:
            name (str): The name of the stage you want to retrieve.

        Returns:
            geopandas.GeoDataFrame: The results of the query, or None if
                                    the stage was not found or failed.
        """
        return self.results.get(name)