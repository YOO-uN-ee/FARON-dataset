import random
import math
from shapely.geometry import Polygon, Point, LineString
from shapely import affinity
from shapely.ops import unary_union
import matplotlib.pyplot as plt
import psycopg2

# --- Polygon Generation ---

def generate_random_polygons(
    canvas_bounds, 
    num_polygons, 
    min_vertices, 
    max_vertices, 
    min_radius, 
    max_radius, 
    regular_shapes=False
):
    """Generates a list of random vector polygons on a square plane."""
    min_x, min_y, max_x, max_y = canvas_bounds
    polygons = []
    
    for _ in range(num_polygons):
        num_vertices = random.randint(min_vertices, max_vertices)
        avg_radius = random.uniform(min_radius, max_radius)
        buffer = avg_radius * 1.1 
        center_x = random.uniform(min_x + buffer, max_x - buffer)
        center_y = random.uniform(min_y + buffer, max_y - buffer)
        
        vertices = []
        if regular_shapes:
            start_angle = random.uniform(0, 2 * math.pi)
            angle_step = 2 * math.pi / num_vertices
            for i in range(num_vertices):
                angle = start_angle + i * angle_step
                x = center_x + avg_radius * math.cos(angle)
                y = center_y + avg_radius * math.sin(angle)
                vertices.append((x, y))
        else:
            angles = sorted([random.uniform(0, 2 * math.pi) for _ in range(num_vertices)])
            for angle in angles:
                radius = random.uniform(avg_radius * 0.8, avg_radius * 1.2)
                x = center_x + radius * math.cos(angle)
                y = center_y + radius * math.sin(angle)
                vertices.append((x, y))
        
        polygon = Polygon(vertices)
        if polygon.is_valid:
            polygons.append(polygon)
            
    return polygons

# --- Point Generation ---

def generate_random_points(canvas_bounds, num_points):
    """Generates a list of random Point objects."""
    min_x, min_y, max_x, max_y = canvas_bounds
    points = []
    for _ in range(num_points):
        x = random.uniform(min_x, max_x)
        y = random.uniform(min_y, max_y)
        points.append(Point(x, y))
    return points

def generate_one_point(canvas_bounds):
    """Generates a single random Point object."""
    min_x, min_y, max_x, max_y = canvas_bounds
    x = random.uniform(min_x, max_x)
    y = random.uniform(min_y, max_y)
    return Point(x, y)

# --- Line Generation ---

def generate_random_lines(
    canvas_bounds, 
    num_lines, 
    straight_only, 
    length_range, 
    segment_range
):
    """Generates lists of straight and/or curly LineString objects."""
    straight_lines = []
    curly_lines = []
    
    for _ in range(num_lines):
        is_straight = straight_only or (not straight_only and random.choice([True, False]))
        if is_straight:
            line = generate_one_line(canvas_bounds, True, length_range, segment_range)
            straight_lines.append(line)
        else:
            line = generate_one_line(canvas_bounds, False, length_range, segment_range)
            if line:
                curly_lines.append(line)

    return straight_lines, curly_lines

def generate_one_line(canvas_bounds, straight_only, length_range, segment_range):
    """Generates a single random LineString object."""
    min_x, min_y, max_x, max_y = canvas_bounds
    is_straight = straight_only or (not straight_only and random.choice([True, False]))
    
    if is_straight:
        x1 = random.uniform(min_x, max_x)
        y1 = random.uniform(min_y, max_y)
        x2 = random.uniform(min_x, max_x)
        y2 = random.uniform(min_y, max_y)
        return LineString([(x1, y1), (x2, y2)])
    else:
        num_segments = random.randint(segment_range[0], segment_range[1])
        seg_len = random.uniform(length_range[0], length_range[1]) / num_segments
        
        cx = random.uniform(min_x, max_x)
        cy = random.uniform(min_y, max_y)
        vertices = [(cx, cy)]
        angle = random.uniform(0, 2 * math.pi)
        
        for _ in range(num_segments - 1):
            angle += random.uniform(-math.pi / 2, math.pi / 2)
            nx = cx + seg_len * math.cos(angle)
            ny = cy + seg_len * math.sin(angle)
            nx = max(min_x, min(nx, max_x))
            ny = max(min_y, min(ny, max_y))
            vertices.append((nx, ny))
            cx, cy = nx, ny
        
        if len(vertices) > 1:
            return LineString(vertices)
        else:
            # Fallback to a simple line if random walk fails
            return generate_one_line(canvas_bounds, True, length_range, segment_range)

# --- Polygon Relationship Functions ---

def create_aligned_edges(polygons, indices_to_use):
    """Adjusts specified polygon pairs to share a boundary line."""
    modified_polygons = polygons[:]
    MAX_ATTEMPTS_PER_PAIR = 20

    for i in range(0, len(indices_to_use), 2):
        idx_a = indices_to_use[i]
        idx_b = indices_to_use[i+1]
        
        pair_aligned = False
        for _ in range(MAX_ATTEMPTS_PER_PAIR):
            poly_a = modified_polygons[idx_a]
            poly_b = modified_polygons[idx_b]

            coords_a = list(poly_a.exterior.coords)
            edge_idx_a = random.randrange(len(coords_a) - 1)
            p_a1, p_a2 = Point(coords_a[edge_idx_a]), Point(coords_a[edge_idx_a + 1])
            
            coords_b = list(poly_b.exterior.coords)
            edge_idx_b = random.randrange(len(coords_b) - 1)
            p_b1, p_b2 = Point(coords_b[edge_idx_b]), Point(coords_b[edge_idx_b + 1])

            angle_a = math.atan2(p_a2.y - p_a1.y, p_a2.x - p_a1.x)
            angle_b = math.atan2(p_b2.y - p_b1.y, p_b2.x - p_b1.x)
            
            rotation_angle_rad = angle_a - angle_b + math.pi
            rotated_poly_b = affinity.rotate(poly_b, math.degrees(rotation_angle_rad), origin='center')
            
            rotated_coords_b = list(rotated_poly_b.exterior.coords)
            p_b1_rot, p_b2_rot = Point(rotated_coords_b[edge_idx_b]), Point(rotated_coords_b[edge_idx_b + 1])
            mid_b_rot = Point((p_b1_rot.x + p_b2_rot.x) / 2, (p_b1_rot.y + p_b2_rot.y) / 2)
            
            mid_a = Point((p_a1.x + p_a2.x) / 2, (p_a1.y + p_a2.y) / 2)
            
            x_off = mid_a.x - mid_b_rot.x
            y_off = mid_a.y - mid_b_rot.y
            final_poly_b = affinity.translate(rotated_poly_b, xoff=x_off, yoff=y_off)
            
            if not poly_a.overlaps(final_poly_b):
                modified_polygons[idx_b] = final_poly_b
                pair_aligned = True
                break
        
        if not pair_aligned:
            print(f"Warning: Could not align pair ({idx_a}, {idx_b}) without overlap.")

    return modified_polygons

def create_overlapping_pairs(polygons, indices_to_use):
    """Adjusts specified polygon pairs to partially overlap."""
    modified_polygons = polygons[:]
    for i in range(0, len(indices_to_use), 2):
        idx_a = indices_to_use[i]
        idx_b = indices_to_use[i+1]

        poly_a = modified_polygons[idx_a]
        poly_b = modified_polygons[idx_b]

        target_point = poly_a.centroid
        dist_b = random.uniform(0, poly_b.exterior.length)
        source_point = poly_b.exterior.interpolate(dist_b)
        
        x_off = target_point.x - source_point.x
        y_off = target_point.y - source_point.y
        
        moved_poly_b = affinity.translate(poly_b, xoff=x_off, yoff=y_off)
        modified_polygons[idx_b] = moved_poly_b
        
    return modified_polygons

def create_contained_pairs(polygons, indices_to_use):
    """Adjusts specified polygon pairs so one is contained within another."""
    modified_polygons = polygons[:]
    for i in range(0, len(indices_to_use), 2):
        idx_1 = indices_to_use[i]
        idx_2 = indices_to_use[i+1]
        
        if modified_polygons[idx_1].area > modified_polygons[idx_2].area:
            idx_a, idx_b = idx_1, idx_2 # A is container, B is contained
        else:
            idx_a, idx_b = idx_2, idx_1
            
        poly_a = modified_polygons[idx_a]
        poly_b = modified_polygons[idx_b]
        
        scale_factor = min(0.5, math.sqrt(poly_a.area / poly_b.area) * 0.5)
        scaled_poly_b = affinity.scale(poly_b, xfact=scale_factor, yfact=scale_factor, origin='center')

        target_point = poly_a.representative_point()
        source_centroid = scaled_poly_b.centroid
        x_off = target_point.x - source_centroid.x
        y_off = target_point.y - source_centroid.y
        
        final_poly_b = affinity.translate(scaled_poly_b, xoff=x_off, yoff=y_off)
        modified_polygons[idx_b] = final_poly_b
        
    return modified_polygons

# --- (NEW) Geometry Relationship Functions ---

def move_line_into_poly(container_poly, line_to_move):
    """Moves and scales a single line to be contained within a polygon."""
    # Scale down the line to ensure it fits
    p_minx, p_miny, p_maxx, p_maxy = container_poly.bounds
    l_minx, l_miny, l_maxx, l_maxy = line_to_move.bounds
    
    poly_width = p_maxx - p_minx
    poly_height = p_maxy - p_miny
    line_width = l_maxx - l_minx if (l_maxx - l_minx) > 1e-6 else 1.0
    line_height = l_maxy - l_miny if (l_maxy - l_miny) > 1e-6 else 1.0

    scale_factor = min((poly_width / line_width) * 0.5, (poly_height / line_height) * 0.5)
    scaled_line = affinity.scale(line_to_move, xfact=scale_factor, yfact=scale_factor, origin='center')

    # Move to representative_point, which is guaranteed to be inside the polygon
    target_point = container_poly.representative_point()
    source_centroid = scaled_line.centroid
    x_off = target_point.x - source_centroid.x
    y_off = target_point.y - source_centroid.y
    
    final_line = affinity.translate(scaled_line, xoff=x_off, yoff=y_off)
    return final_line

def move_point_into_poly(container_poly, point_to_move):
    """Moves a single point to be contained within a polygon."""
    # Move to representative_point
    target_point = container_poly.representative_point()
    x_off = target_point.x - point_to_move.x
    y_off = target_point.y - point_to_move.y
    
    final_point = affinity.translate(point_to_move, xoff=x_off, yoff=y_off)
    return final_point

# --- Plotting Function ---

def plot_geometries(all_geometries, canvas_bounds, title_info=""):
    """Visualizes all generated geometries on a 2D plot."""
    fig, ax = plt.subplots(figsize=(10, 10))
    min_x, min_y, max_x, max_y = canvas_bounds
    ax.set_xlim(min_x, max_x); ax.set_ylim(min_y, max_y)
    ax.set_aspect('equal', adjustable='box')
    
    for geom in all_geometries:
        if geom.geom_type == 'Polygon':
            color = (random.random(), random.random(), random.random())
            x, y = geom.exterior.xy
            ax.fill(x, y, color=color, alpha=0.7, edgecolor='black')
        
        elif geom.geom_type == 'LineString':
            x, y = geom.xy
            if len(x) == 2: # Straight line
                ax.plot(x, y, color='blue', linewidth=2, alpha=0.8)
            else: # Curly line
                ax.plot(x, y, color='purple', linewidth=2, alpha=0.8, linestyle='--')

        elif geom.geom_type == 'Point':
            ax.scatter(geom.x, geom.y, c='black', s=10, zorder=5)
    
    ax.set_title(f"Generated Geometries ({title_info})")
    ax.set_xlabel("X Coordinate"); ax.set_ylabel("Y Coordinate")
    plt.grid(True); plt.show()

# --- Database Function ---

def save_geometries_to_postgis(
    polygons, points, straight_lines, curly_lines, 
    is_regular_polygon, db_config
):
    """Connects to PostGIS and saves all geometry types."""
    conn = None
    try:
        print("\nConnecting to the PostGIS database...")
        conn = psycopg2.connect(**db_config)
        cur = conn.cursor()
        create_table_sql = """
        CREATE TABLE IF NOT EXISTS generated_geometries (
            id SERIAL PRIMARY KEY, geom GEOMETRY(GEOMETRY, 0),
            geom_type VARCHAR(20), style VARCHAR(20),
            vertices INTEGER, area DOUBLE PRECISION,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );"""
        cur.execute(create_table_sql)
        print("Clearing old data from the table...")
        cur.execute("DELETE FROM generated_geometries;")
        
        print(f"Inserting {len(polygons)} polygons...")
        polygon_style = "regular" if is_regular_polygon else "irregular"
        for poly in polygons:
            cur.execute(
                """INSERT INTO generated_geometries (geom, geom_type, style, vertices, area)
                   VALUES (ST_GeomFromText(%s, 0), 'Polygon', %s, %s, %s);""",
                (poly.wkt, polygon_style, len(poly.exterior.coords) - 1, poly.area)
            )
        
        print(f"Inserting {len(points)} points...")
        for point in points:
            cur.execute(
                """INSERT INTO generated_geometries (geom, geom_type, style, vertices, area)
                   VALUES (ST_GeomFromText(%s, 0), 'Point', 'point', 1, 0);""",
                (point.wkt,)
            )

        print(f"Inserting {len(straight_lines)} straight lines...")
        for line in straight_lines:
            cur.execute(
                """INSERT INTO generated_geometries (geom, geom_type, style, vertices, area)
                   VALUES (ST_GeomFromText(%s, 0), 'LineString', 'straight', %s, 0);""",
                (line.wkt, len(line.coords))
            )
        
        print(f"Inserting {len(curly_lines)} curly lines...")
        for line in curly_lines:
            cur.execute(
                """INSERT INTO generated_geometries (geom, geom_type, style, vertices, area)
                   VALUES (ST_GeomFromText(%s, 0), 'LineString', 'curly', %s, 0);""",
                (line.wkt, len(line.coords))
            )

        conn.commit()
        print("Successfully saved all geometries to the database.")
    except (Exception, psycopg2.DatabaseError) as error:
        print(f"Database error: {error}")
    finally:
        if conn is not None:
            conn.close()
            print("Database connection closed.")


# --- Main Execution ---

if __name__ == '__main__':
    # --- Configuration ---
    CANVAS_BOUNDS = (0, 0, 100, 100) 
    SAVE_TO_DB = True
    DB_CONFIG = {
        "host": "localhost", "database": "spatial_db",
        "user": "postgres", "password": "mysecretpassword" 
    }
    
    # --- Polygon Controls ---
    NUM_POLYGONS = 15                 
    VERTEX_RANGE = (3, 6)             
    RADIUS_RANGE = (5, 12)            
    CREATE_REGULAR_SHAPES = True
    
    # --- Polygon Relationship Controls ---
    NUM_ALIGNED_PAIRS = 2
    NUM_OVERLAPPING_PAIRS = 2
    NUM_CONTAINED_PAIRS = 2
    
    # --- (NEW) Geometry Relationship Controls ---
    LINE_CONTAINMENT_PROBABILITY = 0.3 # e.g., 30% chance for a line to be in a poly
    POINT_CONTAINMENT_PROBABILITY = 0.3 # e.g., 30% chance for a point to be in a poly
    
    # --- Point Controls ---
    NUM_POINTS = 50
    
    # --- Line Controls ---
    NUM_LINES = 10
    STRAIGHT_LINES_ONLY = False
    LINE_LENGTH_RANGE = (10, 30)
    LINE_SEGMENT_RANGE = (3, 8)
    
    # --- Disjoint Placement Controls ---
    MAX_ATTEMPTS_PER_PLACEMENT = 100 # Attempts to find a disjoint spot

    # --- Generation ---
    # 1. Validate counts
    total_polygons_needed = (NUM_ALIGNED_PAIRS + NUM_OVERLAPPING_PAIRS + NUM_CONTAINED_PAIRS) * 2

    if total_polygons_needed > NUM_POLYGONS:
        raise ValueError(f"Not enough polygons ({NUM_POLYGONS}) to create all requested pairs ({total_polygons_needed} needed).")

    # 2. Generate initial polygons
    print("Generating initial random polygons...")
    initial_polygons = generate_random_polygons(
        canvas_bounds=CANVAS_BOUNDS, num_polygons=NUM_POLYGONS,
        min_vertices=VERTEX_RANGE[0], max_vertices=VERTEX_RANGE[1],
        min_radius=RADIUS_RANGE[0], max_radius=RADIUS_RANGE[1],
        regular_shapes=CREATE_REGULAR_SHAPES
    )
    
    # 3. Polygon Relationship Processing
    poly_indices = list(range(NUM_POLYGONS))
    random.shuffle(poly_indices)

    poly_idx_offset = 0
    aligned_indices = poly_indices[poly_idx_offset : poly_idx_offset + NUM_ALIGNED_PAIRS*2]
    poly_idx_offset += NUM_ALIGNED_PAIRS*2
    overlapping_indices = poly_indices[poly_idx_offset : poly_idx_offset + NUM_OVERLAPPING_PAIRS*2]
    poly_idx_offset += NUM_OVERLAPPING_PAIRS*2
    poly_contained_indices = poly_indices[poly_idx_offset : poly_idx_offset + NUM_CONTAINED_PAIRS*2]

    # Run relationship functions
    modified_polygons = create_aligned_edges(initial_polygons, aligned_indices)
    modified_polygons = create_overlapping_pairs(modified_polygons, overlapping_indices)
    modified_polygons = create_contained_pairs(modified_polygons, poly_contained_indices)

    
    # --- Disjoint Check and Repositioning (Polygons Only) ---
    print("Repositioning free polygons to ensure they are disjoint...")
    
    involved_poly_indices = set(aligned_indices) | set(overlapping_indices) | set(poly_contained_indices)
    involved_polygons_list = [modified_polygons[i] for i in involved_poly_indices]
    involved_footprint = unary_union(involved_polygons_list)
    
    placed_free_polygons = [] # Footprint of free geoms placed so far
    
    free_poly_indices = [i for i in range(NUM_POLYGONS) if i not in involved_poly_indices]
    for free_idx in free_poly_indices:
        poly_to_check = modified_polygons[free_idx]
        attempt = 0
        is_placed = False
        
        while attempt < MAX_ATTEMPTS_PER_PLACEMENT:
            overlaps_involved = poly_to_check.intersects(involved_footprint)
            overlaps_other_free = any(poly_to_check.intersects(g) for g in placed_free_polygons)
            
            if not overlaps_involved and not overlaps_other_free:
                modified_polygons[free_idx] = poly_to_check
                placed_free_polygons.append(poly_to_check)
                is_placed = True
                break
            
            poly_to_check = generate_random_polygons(
                canvas_bounds=CANVAS_BOUNDS, num_polygons=1,
                min_vertices=VERTEX_RANGE[0], max_vertices=VERTEX_RANGE[1],
                min_radius=RADIUS_RANGE[0], max_radius=RADIUS_RANGE[1],
                regular_shapes=CREATE_REGULAR_SHAPES
            )[0]
            attempt += 1
            
        if not is_placed:
            print(f"Warning: Could not find disjoint spot for polygon {free_idx}. Placing anyway.")
            modified_polygons[free_idx] = poly_to_check
            placed_free_polygons.append(poly_to_check)

    # --- (NEW) Generate, Classify, and Place Lines and Points ---
    
    # All polygons are now in their final place. Create a new "no-go" zone
    # that includes ALL polygons for free lines/points.
    all_poly_footprint = unary_union(modified_polygons)
    placed_free_geometries = [] # Keep track of free lines/points
    
    modified_lines = []
    modified_points = []
    num_contained_lines = 0
    num_contained_points = 0

    print(f"Generating and placing {NUM_LINES} lines...")
    for _ in range(NUM_LINES):
        # 1. Decide if it will be a "contained" line
        if random.random() < LINE_CONTAINMENT_PROBABILITY:
            container_poly = random.choice(modified_polygons)
            line_to_place = generate_one_line(
                CANVAS_BOUNDS, STRAIGHT_LINES_ONLY, 
                LINE_LENGTH_RANGE, LINE_SEGMENT_RANGE
            )
            final_line = move_line_into_poly(container_poly, line_to_place)
            modified_lines.append(final_line)
            num_contained_lines += 1
        
        # 2. Else, it's a "free" line that must be disjoint
        else:
            attempt = 0
            is_placed = False
            while attempt < MAX_ATTEMPTS_PER_PLACEMENT:
                line_to_check = generate_one_line(
                    CANVAS_BOUNDS, STRAIGHT_LINES_ONLY, 
                    LINE_LENGTH_RANGE, LINE_SEGMENT_RANGE
                )
                overlaps_polygons = line_to_check.intersects(all_poly_footprint)
                overlaps_other_free = any(line_to_check.intersects(g) for g in placed_free_geometries)
                
                if not overlaps_polygons and not overlaps_other_free:
                    modified_lines.append(line_to_check)
                    placed_free_geometries.append(line_to_check)
                    is_placed = True
                    break
                attempt += 1
            
            if not is_placed:
                 print(f"Warning: Could not find disjoint spot for a free line. Skipping.")
    
    print(f"Generating and placing {NUM_POINTS} points...")
    for _ in range(NUM_POINTS):
        # 1. Decide if it will be a "contained" point
        if random.random() < POINT_CONTAINMENT_PROBABILITY:
            container_poly = random.choice(modified_polygons)
            point_to_place = generate_one_point(CANVAS_BOUNDS)
            final_point = move_point_into_poly(container_poly, point_to_place)
            modified_points.append(final_point)
            num_contained_points += 1
        
        # 2. Else, it's a "free" point that must be disjoint
        else:
            attempt = 0
            is_placed = False
            while attempt < MAX_ATTEMPTS_PER_PLACEMENT:
                point_to_check = generate_one_point(CANVAS_BOUNDS)
                
                overlaps_polygons = point_to_check.intersects(all_poly_footprint)
                overlaps_other_free = any(point_to_check.intersects(g) for g in placed_free_geometries)

                if not overlaps_polygons and not overlaps_other_free:
                    modified_points.append(point_to_check)
                    placed_free_geometries.append(point_to_check)
                    is_placed = True
                    break
                attempt += 1
            
            if not is_placed:
                print(f"Warning: Could not find disjoint spot for a free point. Skipping.")

