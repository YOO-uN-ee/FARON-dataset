import random
import math
from shapely.geometry import Polygon, Point, box
from shapely import affinity
import matplotlib.pyplot as plt
import psycopg2

def generate_random_polygons(canvas_bounds, num_polygons, min_vertices, max_vertices, min_radius, max_radius,
                             regular_shapes=False):
    """
    Generates a list of random, non-overlapping vector polygons on a square plane.

    Args:
        canvas_bounds (tuple): A tuple (min_x, min_y, max_x, max_y) for the plane.
        num_polygons (int): The number of polygons to generate.
        min_vertices (int): The minimum number of vertices for a polygon.
        max_vertices (int): The maximum number of vertices for a polygon.
        min_radius (float): The minimum average radius of a polygon.
        max_radius (float): The maximum average radius of a polygon.

    Returns:
        list: A list of Shapely Polygon objects.
    """
    min_x, min_y, max_x, max_y = canvas_bounds
    polygons = []
    
    for _ in range(num_polygons):
        # Determine polygon properties
        num_vertices = random.randint(min_vertices, max_vertices)
        avg_radius = random.uniform(min_radius, max_radius)
        
        # Pick a random, valid center point for the polygon
        # The buffer ensures the entire polygon will fit on the canvas
        buffer = avg_radius * 1.5 # Use a slight buffer for irregular shapes
        center_x = random.uniform(min_x + buffer, max_x - buffer)
        center_y = random.uniform(min_y + buffer, max_y - buffer)
        
        # Generate vertices
        vertices = []
        
        if regular_shapes:
            # --- Generate a REGULAR polygon ---
            # Start with a random rotation angle for variety
            start_angle = random.uniform(0, 2 * math.pi)
            # Calculate the fixed angle step between vertices
            angle_step = 2 * math.pi / num_vertices
            
            for i in range(num_vertices):
                angle = start_angle + i * angle_step
                # Use the same average radius for all vertices to create a regular shape
                x = center_x + avg_radius * math.cos(angle)
                y = center_y + avg_radius * math.sin(angle)
                vertices.append((x, y))
        else:
            # --- Generate an IRREGULAR polygon (original logic) ---
            # Generate random angles and sort them to ensure a simple polygon
            angles = sorted([random.uniform(0, 2 * math.pi) for _ in range(num_vertices)])
            
            for angle in angles:
                # Vary the radius for each vertex to create an irregular shape
                radius = random.uniform(avg_radius * 0.8, avg_radius * 1.2)
                x = center_x + radius * math.cos(angle)
                y = center_y + radius * math.sin(angle)
                vertices.append((x, y))
        
        # Create the Shapely Polygon object
        polygon = Polygon(vertices)

        # Ensure the polygon is valid before adding it
        if polygon.is_valid:
            polygons.append(polygon)
            
    return polygons

def generate_random_lines():
    return 0

def generate_random_points():
    return 0

def create_touching_pairs(polygons, num_pairs):
    """
    Adjusts polygons so a specified number of pairs share a border.

    Args:
        polygons (list): The list of generated Shapely Polygons.
        num_pairs (int): The number of pairs to make touch.

    Returns:
        list: The modified list of polygons.
    """
    if num_pairs == 0:
        return polygons
        
    num_polygons = len(polygons)
    if num_pairs * 2 > num_polygons:
        print(f"Warning: Cannot create {num_pairs} pairs from {num_polygons} polygons. Reducing pairs.")
        num_pairs = num_polygons // 2

    # Create a list of indices and shuffle it to create random pairs
    indices = list(range(num_polygons))
    random.shuffle(indices)

    modified_polygons = polygons[:] # Work on a copy

    for i in range(num_pairs):
        # Get indices for the stationary polygon (A) and the mobile one (B)
        idx_a = indices[i*2]
        idx_b = indices[i*2 + 1]

        poly_a = modified_polygons[idx_a]
        poly_b = modified_polygons[idx_b]

        # Pick a random point on the boundary of polygon A
        dist_a = random.uniform(0, poly_a.exterior.length)
        touch_point_a = poly_a.exterior.interpolate(dist_a)

        # Pick a random point on the boundary of polygon B
        dist_b = random.uniform(0, poly_b.exterior.length)
        touch_point_b = poly_b.exterior.interpolate(dist_b)

        # Calculate the translation vector to move touch_point_b to touch_point_a
        x_off = touch_point_a.x - touch_point_b.x
        y_off = touch_point_a.y - touch_point_b.y

        # Move polygon B and update it in the list
        moved_poly_b = affinity.translate(poly_b, xoff=x_off, yoff=y_off)
        modified_polygons[idx_b] = moved_poly_b
    
    return modified_polygons

def create_aligned_edges(polygons, num_pairs):
    """
    Adjusts polygons so pairs share a boundary line by aligning edge midpoints.
    This ensures the shared boundary is a line, not just a point.
    """
    if num_pairs == 0:
        return polygons
        
    num_polygons = len(polygons)
    if num_pairs * 2 > num_polygons:
        print(f"Warning: Cannot create {num_pairs} pairs. Reducing to {num_polygons // 2}.")
        num_pairs = num_polygons // 2

    indices = list(range(num_polygons))
    random.shuffle(indices)
    modified_polygons = polygons[:]
    
    MAX_ATTEMPTS_PER_PAIR = 20

    for i in range(num_pairs):
        idx_a = indices[i*2]
        idx_b = indices[i*2 + 1]
        
        pair_aligned = False
        for _ in range(MAX_ATTEMPTS_PER_PAIR):
            poly_a = modified_polygons[idx_a]
            poly_b = modified_polygons[idx_b]

            # 1. Pick a random edge from each polygon
            coords_a = list(poly_a.exterior.coords)
            edge_idx_a = random.randrange(len(coords_a) - 1)
            p_a1, p_a2 = Point(coords_a[edge_idx_a]), Point(coords_a[edge_idx_a + 1])
            
            coords_b = list(poly_b.exterior.coords)
            edge_idx_b = random.randrange(len(coords_b) - 1)
            p_b1, p_b2 = Point(coords_b[edge_idx_b]), Point(coords_b[edge_idx_b + 1])

            # 2. Calculate edge angles for rotation
            angle_a = math.atan2(p_a2.y - p_a1.y, p_a2.x - p_a1.x)
            angle_b = math.atan2(p_b2.y - p_b1.y, p_b2.x - p_b1.x)
            
            # 3. Rotate polygon B to make its edge anti-parallel to A's edge
            rotation_angle_rad = angle_a - angle_b + math.pi
            rotated_poly_b = affinity.rotate(poly_b, math.degrees(rotation_angle_rad), origin='center')
            
            # 4. Find the new coordinates of B's edge and calculate its midpoint
            rotated_coords_b = list(rotated_poly_b.exterior.coords)
            p_b1_rot, p_b2_rot = Point(rotated_coords_b[edge_idx_b]), Point(rotated_coords_b[edge_idx_b + 1])
            mid_b_rot = Point((p_b1_rot.x + p_b2_rot.x) / 2, (p_b1_rot.y + p_b2_rot.y) / 2)
            
            # 5. Calculate the midpoint of A's edge
            mid_a = Point((p_a1.x + p_a2.x) / 2, (p_a1.y + p_a2.y) / 2)
            
            # 6. Translate the rotated polygon to align the midpoints
            x_off = mid_a.x - mid_b_rot.x
            y_off = mid_a.y - mid_b_rot.y
            final_poly_b = affinity.translate(rotated_poly_b, xoff=x_off, yoff=y_off)
            
            # 7. Verify no interior overlap exists
            if not poly_a.overlaps(final_poly_b):
                modified_polygons[idx_b] = final_poly_b
                pair_aligned = True
                break
        
        if not pair_aligned:
            print(f"Warning: Could not align pair ({idx_a}, {idx_b}) without overlap.")

    return modified_polygons

def plot_polygons(polygons, canvas_bounds, save_path):
    """
    Visualizes the generated polygons on a 2D plot.

    Args:
        polygons (list): A list of Shapely Polygon objects.
        canvas_bounds (tuple): The boundaries of the canvas for plotting.
    """
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
        ax.fill(x, y, color=color, alpha=0.7, edgecolor='black')

    # ax.set_title(f"{len(polygons)} Randomly Placed Polygons")
    # ax.set_xlabel("X Coordinate")
    # ax.set_ylabel("Y Coordinate")
    # plt.grid(True)
    # plt.show()
    ax.set_xticks([]) # Hides x-axis tick marks and labels
    ax.set_yticks([]) # Hides y-axis tick marks and labels
    plt.savefig(save_path)

def save_to_postgis(polygons, db_config, is_regular):
    """Connects to a PostGIS database and saves the polygons."""
    conn = None
    try:
        # Establish connection
        print("\nConnecting to the PostGIS database...")
        conn = psycopg2.connect(**db_config)
        cur = conn.cursor()

        # 1. Create table if it doesn't exist
        # SRID 0 is used for a generic 2D Cartesian plane.
        create_table_sql = """
        CREATE TABLE IF NOT EXISTS generated_polygons (
            id SERIAL PRIMARY KEY,
            geom GEOMETRY(Polygon, 0),
            shape_type VARCHAR(50),
            vertices INTEGER,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        """
        cur.execute(create_table_sql)
        
        # 2. Clear existing data from the table for a fresh start
        print("Clearing old data from the table...")
        cur.execute("DELETE FROM generated_polygons;")

        # 3. Prepare and execute INSERT statements for each polygon
        print(f"Inserting {len(polygons)} new polygons...")
        shape_type_str = "regular" if is_regular else "irregular"
        
        for poly in polygons:
            # Convert Shapely polygon to Well-Known Text (WKT) format
            wkt_polygon = poly.wkt
            num_vertices = len(poly.exterior.coords) - 1
            
            insert_sql = """
            INSERT INTO generated_polygons (geom, shape_type, vertices)
            VALUES (ST_GeomFromText(%s, 0), %s, %s);
            """
            cur.execute(insert_sql, (wkt_polygon, shape_type_str, num_vertices))

        # Commit the transaction to save changes
        conn.commit()
        print("Successfully saved polygons to the database.")

    except (Exception, psycopg2.DatabaseError) as error:
        print(f"Database error: {error}")
    finally:
        if conn is not None:
            conn.close()
            print("Database connection closed.")

if __name__ == '__main__':
    # --- Configuration ---
    CANVAS_BOUNDS = (0, 0, 100, 100) # (min_x, min_y, max_x, max_y)
    NUM_POLYGONS = 3                 # How many polygons to create
    VERTEX_RANGE = (3, 8)             # Min and max vertices (e.g., 3=triangle, 8=octagon)
    RADIUS_RANGE = (5, 25)            # Min and max average radius for polygons

    # --- Control Variables ---
    CREATE_REGULAR_SHAPES = False
    NUM_TOUCHING_PAIRS = 1

    SAVE_TO_DB = True # Set to True to save results to PostGIS

    # --- PostGIS Database Configuration ---
    # IMPORTANT: Replace these with your actual database credentials.
    # For better security, use environment variables or a secrets manager in production.
    DB_CONFIG = {
        "host": "localhost",
        "database": "spatial_db",
        "user": "postgres",
        "password": "mysecretpassword" 
    }

    # --- Execution ---
    print("Generating polygons...")
    random_polygons = generate_random_polygons(
        canvas_bounds=CANVAS_BOUNDS,
        num_polygons=NUM_POLYGONS,
        min_vertices=VERTEX_RANGE[0],
        max_vertices=VERTEX_RANGE[1],
        min_radius=RADIUS_RANGE[0],
        max_radius=RADIUS_RANGE[1],
        regular_shapes=CREATE_REGULAR_SHAPES
    )

    print(f"Adjusting {NUM_TOUCHING_PAIRS} pairs to make them border...")
    # final_polygons = create_touching_pairs(random_polygons, NUM_TOUCHING_PAIRS)
    final_polygons = create_aligned_edges(random_polygons, NUM_TOUCHING_PAIRS)
    
    print(f"Successfully generated {len(random_polygons)} polygons.")
    print("Displaying results...")
    plot_polygons(final_polygons, CANVAS_BOUNDS, "./polygons.png")

    # # --- Database Saving ---
    # if SAVE_TO_DB:
    #     save_to_postgis(final_polygons, DB_CONFIG, CREATE_REGULAR_SHAPES)