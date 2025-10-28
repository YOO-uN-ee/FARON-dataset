import random
import math
from shapely.geometry import Polygon, Point, LineString
from shapely import affinity
from shapely.ops import unary_union
import matplotlib.pyplot as plt
import psycopg2
import json

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
    
    attempts = 0
    # Give up after 10x attempts per polygon
    MAX_GEN_ATTEMPTS = num_polygons * 10 

    while len(polygons) < num_polygons and attempts < MAX_GEN_ATTEMPTS:
        attempts += 1
        # 1. Determine polygon properties
        num_vertices = random.randint(min_vertices, max_vertices)
        avg_radius = random.uniform(min_radius, max_radius)
        
        # 2. Pick a random, valid center point for the polygon
        buffer = avg_radius * 1.1 
        center_x = random.uniform(min_x + buffer, max_x - buffer)
        center_y = random.uniform(min_y + buffer, max_y - buffer)
        
        # 3. Generate vertices based on the control variable
        vertices = []
        
        if regular_shapes:
            # --- Generate a REGULAR polygon ---
            start_angle = random.uniform(0, 2 * math.pi)
            angle_step = 2 * math.pi / num_vertices
            
            for i in range(num_vertices):
                angle = start_angle + i * angle_step
                x = center_x + avg_radius * math.cos(angle)
                y = center_y + avg_radius * math.sin(angle)
                vertices.append((x, y))
        else:
            # --- Generate an IRREGULAR polygon (original logic) ---
            angles = sorted([random.uniform(0, 2 * math.pi) for _ in range(num_vertices)])
            
            for angle in angles:
                radius = random.uniform(avg_radius * 0.8, avg_radius * 1.2)
                x = center_x + radius * math.cos(angle)
                y = center_y + radius * math.sin(angle)
                vertices.append((x, y))
        
        # 4. Create the Shapely Polygon object
        polygon = Polygon(vertices)
        if polygon.is_valid:
            polygons.append(polygon)
            
    if len(polygons) < num_polygons:
        print(f"Warning: Could only generate {len(polygons)} valid polygons out of {num_polygons} requested.")
            
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
    """Generates lists of straight and curly LineString objects."""
    straight_lines = []
    curly_lines = []
    
    for _ in range(num_lines):
        line = generate_one_line(canvas_bounds, straight_only, length_range, segment_range)
        if len(line.coords) == 2:
            straight_lines.append(line)
        else:
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
    """
    Adjusts polygons so pairs share a boundary line with no interior overlap.
    """
    modified_polygons = polygons[:]
    MAX_ATTEMPTS_PER_PAIR = 20

    for i in range(0, len(indices_to_use), 2):
        idx_a = indices_to_use[i]
        idx_b = indices_to_use[i+1]
        
        pair_aligned = False
        for _ in range(MAX_ATTEMPTS_PER_PAIR):
            poly_a = modified_polygons[idx_a]
            poly_b = modified_polygons[idx_b] # Get original for retry

            # 1. Pick a random edge from each polygon
            coords_a = list(poly_a.exterior.coords)
            edge_idx_a = random.randrange(len(coords_a) - 1)
            p_a1, p_a2 = Point(coords_a[edge_idx_a]), Point(coords_a[edge_idx_a + 1])
            edge_a = LineString([p_a1, p_a2])
            mid_a = edge_a.interpolate(0.5, normalized=True)

            coords_b = list(poly_b.exterior.coords)
            edge_idx_b = random.randrange(len(coords_b) - 1)
            p_b1, p_b2 = Point(coords_b[edge_idx_b]), Point(coords_b[edge_idx_b + 1])
            edge_b = LineString([p_b1, p_b2])

            # 2. Calculate the angles
            angle_a = math.atan2(p_a2.y - p_a1.y, p_a2.x - p_a1.x)
            angle_b = math.atan2(p_b2.y - p_b1.y, p_b2.x - p_b1.x)
            
            # 3. Force anti-parallel alignment to place interiors on opposite sides
            rotation_angle_rad = angle_a - angle_b + math.pi
            
            # 4. Rotate polygon B
            rotated_poly_b = affinity.rotate(poly_b, math.degrees(rotation_angle_rad), origin=poly_b.centroid)
            
            # 5. Find the new midpoint of B's rotated edge
            rotated_coords_b = list(rotated_poly_b.exterior.coords)
            r_p_b1 = Point(rotated_coords_b[edge_idx_b])
            r_p_b2 = Point(rotated_coords_b[edge_idx_b + 1])
            edge_b_rotated = LineString([r_p_b1, r_p_b2])
            mid_b_rotated = edge_b_rotated.interpolate(0.5, normalized=True)

            # 6. Translate B to align midpoints
            x_off = mid_a.x - mid_b_rotated.x
            y_off = mid_a.y - mid_b_rotated.y
            final_poly_b = affinity.translate(rotated_poly_b, xoff=x_off, yoff=y_off)
            
            # 7. VERIFY that the interiors do not overlap.
            if not poly_a.overlaps(final_poly_b):
                modified_polygons[idx_b] = final_poly_b
                pair_aligned = True
                break # Succeeded, move to the next pair
        
        if not pair_aligned:
            print(f"Warning: Could not align pair ({idx_a}, {idx_b}) without overlap after {MAX_ATTEMPTS_PER_PAIR} attempts.")

    return modified_polygons

def create_overlapping_pairs(polygons, indices_to_use):
    """
    Adjusts polygons so pairs partially overlap.
    """
    modified_polygons = polygons[:]
    for i in range(0, len(indices_to_use), 2):
        idx_a = indices_to_use[i]
        idx_b = indices_to_use[i+1]

        poly_a = modified_polygons[idx_a]
        poly_b = modified_polygons[idx_b]

        # Move B so its centroid is on a random point on A's boundary
        target_point = poly_a.boundary.interpolate(random.uniform(0, poly_a.boundary.length))
        source_point = poly_b.centroid

        x_off = target_point.x - source_point.x
        y_off = target_point.y - source_point.y

        moved_poly_b = affinity.translate(poly_b, xoff=x_off, yoff=y_off)
        modified_polygons[idx_b] = moved_poly_b
        
    return modified_polygons

def create_contained_pairs(polygons, indices_to_use):
    """
    Adjusts polygons so one is contained within the other.
    """
    modified_polygons = polygons[:]
    for i in range(0, len(indices_to_use), 2):
        idx_a = indices_to_use[i]
        idx_b = indices_to_use[i+1]

        # Ensure A is the larger (container) and B is the smaller (contained)
        if modified_polygons[idx_a].area < modified_polygons[idx_b].area:
            idx_a, idx_b = idx_b, idx_a # Swap

        container_poly = modified_polygons[idx_a]
        poly_to_move = modified_polygons[idx_b]

        # 1. Scale down the smaller polygon to guarantee it fits
        minx, miny, maxx, maxy = container_poly.bounds
        c_width = maxx - minx
        c_height = maxy - miny
        
        minx, miny, maxx, maxy = poly_to_move.bounds
        m_width = maxx - minx if (maxx - minx) > 1e-6 else 1.0
        m_height = maxy - miny if (maxy - miny) > 1e-6 else 1.0
        
        # Scale to 25% of the container's dimension, whichever is smaller
        scale_factor = min((c_width / m_width) * 0.25, (c_height / m_height) * 0.25)
        
        scaled_poly = affinity.scale(
            poly_to_move, xfact=scale_factor, yfact=scale_factor, origin='center'
        )

        # 2. Move the scaled polygon to the container's 'representative_point'
        target_point = container_poly.representative_point()
        source_centroid = scaled_poly.centroid
        
        x_off = target_point.x - source_centroid.x
        y_off = target_point.y - source_centroid.y

        moved_poly = affinity.translate(scaled_poly, xoff=x_off, yoff=y_off)
        modified_polygons[idx_b] = moved_poly

    return modified_polygons

def create_touching_polygons(polygons, indices_to_use):
    """
    Adjusts polygons so pairs touch at a single vertex without overlapping.
    """
    modified_polygons = polygons[:]
    MAX_ATTEMPTS_PER_PAIR = 10

    for i in range(0, len(indices_to_use), 2):
        idx_a = indices_to_use[i]
        idx_b = indices_to_use[i+1]
        
        pair_touched = False
        for _ in range(MAX_ATTEMPTS_PER_PAIR):
            poly_a = modified_polygons[idx_a]
            poly_b = modified_polygons[idx_b] # Get original for retry

            # 1. Pick random vertex from each polygon's exterior coordinates
            coords_a = list(poly_a.exterior.coords)
            vertex_a = Point(random.choice(coords_a))
            
            coords_b = list(poly_b.exterior.coords)
            vertex_b = Point(random.choice(coords_b))

            # 2. Calculate translation vector
            x_off = vertex_a.x - vertex_b.x
            y_off = vertex_a.y - vertex_b.y
            
            # 3. Move poly_b
            moved_poly_b = affinity.translate(poly_b, xoff=x_off, yoff=y_off)
            
            # 4. Check for overlap
            if not poly_a.overlaps(moved_poly_b):
                modified_polygons[idx_b] = moved_poly_b
                pair_touched = True
                break # Success, move to next pair
        
        if not pair_touched:
            print(f"Warning: Could not create non-overlapping touch for pair ({idx_a}, {idx_b}).")
            
    return modified_polygons


# --- Geometry Relationship Functions ---

def move_line_into_poly(container_poly, line_to_move):
    """Scales and moves a line to be inside a polygon."""
    p_minx, p_miny, p_maxx, p_maxy = container_poly.bounds
    l_minx, l_miny, l_maxx, l_maxy = line_to_move.bounds
    
    poly_width = p_maxx - p_minx
    poly_height = p_maxy - p_miny
    line_width = l_maxx - l_minx if (l_maxx - l_minx) > 1e-6 else 1.0
    line_height = l_maxy - l_miny if (l_maxy - l_miny) > 1e-6 else 1.0

    scale_factor = min((poly_width / line_width) * 0.5, (poly_height / line_height) * 0.5)
    scaled_line = affinity.scale(line_to_move, xfact=scale_factor, yfact=scale_factor, origin='center')

    target_point = container_poly.representative_point()
    source_centroid = scaled_line.centroid
    x_off = target_point.x - source_centroid.x
    y_off = target_point.y - source_centroid.y
    
    return affinity.translate(scaled_line, xoff=x_off, yoff=y_off)

def move_point_into_poly(container_poly, point_to_move):
    """Moves a point to be inside a polygon."""
    target_point = container_poly.representative_point()
    x_off = target_point.x - point_to_move.x
    y_off = target_point.y - point_to_move.y
    return affinity.translate(point_to_move, xoff=x_off, yoff=y_off)

def create_line_on_poly_border(container_poly):
    """Creates a new line that lies on the polygon's border."""
    boundary = container_poly.boundary
    start_dist = random.uniform(0, boundary.length * 0.8)
    end_dist = random.uniform(start_dist + (boundary.length * 0.1), boundary.length)
    
    start_point = boundary.interpolate(start_dist)
    end_point = boundary.interpolate(end_dist)
    
    # Extract coordinates from the boundary between the two points
    coords = [start_point.coords[0]]
    all_coords = list(boundary.coords)
    # This is a simplified way to get points on the segment
    # A more robust way would trace the boundary coords
    for _ in range(3): # Add a few intermediate points
        dist = random.uniform(start_dist, end_dist)
        coords.append(boundary.interpolate(dist).coords[0])
    coords.append(end_point.coords[0])
    
    return LineString(sorted(coords)) # Sort to ensure simple line

def move_point_onto_line(container_line, point_to_move):
    """Moves a point to lie on a line."""
    dist = random.uniform(0, container_line.length)
    target_point = container_line.interpolate(dist)
    
    x_off = target_point.x - point_to_move.x
    y_off = target_point.y - point_to_move.y
    return affinity.translate(point_to_move, xoff=x_off, yoff=y_off)
    
def move_point_onto_poly_border(container_poly, point_to_move):
    """Moves a point to lie on a polygon's border."""
    dist = random.uniform(0, container_poly.boundary.length)
    target_point = container_poly.boundary.interpolate(dist)
    
    x_off = target_point.x - point_to_move.x
    y_off = target_point.y - point_to_move.y
    return affinity.translate(point_to_move, xoff=x_off, yoff=y_off)
    
def create_line_through_poly(container_poly):
    """Creates a new line that crosses through a polygon."""
    boundary = container_poly.boundary
    
    # Pick two random points on the boundary
    p1 = boundary.interpolate(random.uniform(0, boundary.length))
    p2 = boundary.interpolate(random.uniform(0, boundary.length))
    
    # To ensure it's a 'through' line, extend it past the boundary
    # Calculate vector from p1 to p2 and extend it
    dx = p2.x - p1.x
    dy = p2.y - p1.y
    
    # Create start point by going "backwards" from p1
    start_x = p1.x - dx * 0.5
    start_y = p1.y - dy * 0.5
    
    # Create end point by going "forwards" from p2
    end_x = p2.x + dx * 0.5
    end_y = p2.y + dy * 0.5
    
    return LineString([(start_x, start_y), (end_x, end_y)])

def create_crossing_lines(line_a, line_b):
    """Takes two lines and moves/rotates B to cross A."""
    # 1. Pick a target point on line A (not an endpoint)
    target_point = line_a.interpolate(random.uniform(0.2, 0.8))
    
    # 2. Pick a source point on line B (its midpoint)
    source_point = line_b.centroid
    
    # 3. Translate line B so its midpoint is on line A
    x_off = target_point.x - source_point.x
    y_off = target_point.y - source_point.y
    translated_line_b = affinity.translate(line_b, xoff=x_off, yoff=y_off)
    
    # 4. Rotate line B by a random significant angle
    rotation_angle = random.uniform(30, 150)
    final_line_b = affinity.rotate(translated_line_b, rotation_angle, origin=target_point)
    
    return line_a, final_line_b

# --- Relationship Finding Function ---

def find_all_relationships(all_named_geoms):
    """Finds all spatial relationships between all generated geometries."""
    relationships = []
    geom_items = list(all_named_geoms.items())
    
    for i in range(len(geom_items)):
        for j in range(i + 1, len(geom_items)):
            name_a, geom_a = geom_items[i]
            name_b, geom_b = geom_items[j]
            
            type_a = geom_a.geom_type
            type_b = geom_b.geom_type

            # Use a flag to track if any positive relationship was found
            found_relationship = False

            # Check for equals first, as it's the simplest
            if geom_a.equals(geom_b):
                # relationships.append((name_a, name_b, "equals"))
                found_relationship = True
                continue # Don't check other relationships if they are equal

            # --- WITHIN / CONTAINS ---
            # (A within B) is same as (B contains A)
            # We only check valid type combinations
            
            # Check A within B
            if (type_a == 'Point' and type_b == 'Polygon') or \
               (type_a == 'LineString' and type_b == 'Polygon') or \
               (type_a == 'Polygon' and type_b == 'Polygon'):
                if geom_a.within(geom_b):
                    relationships.append((name_a, name_b, "within"))
                    relationships.append((name_b, name_a, "contains"))
                    found_relationship = True

            # Check B within A (if not already found)
            elif (type_b == 'Point' and type_a == 'Polygon') or \
                 (type_b == 'LineString' and type_a == 'Polygon'):
                if geom_b.within(geom_a):
                    relationships.append((name_b, name_a, "within"))
                    relationships.append((name_a, name_b, "contains"))
                    found_relationship = True

            # --- OVERLAPS ---
            # Must be same-dimension and > 0 dimension
            if type_a == type_b and (type_a == 'LineString' or type_a == 'Polygon'):
                if geom_a.overlaps(geom_b):
                    relationships.append((name_a, name_b, "overlaps"))
                    found_relationship = True

            # --- CROSSES ---
            # Must be mixed-dimension (Line/Poly) or Line/Line
            if (type_a == 'LineString' and type_b == 'LineString') or \
               (type_a == 'LineString' and type_b == 'Polygon') or \
               (type_a == 'Polygon' and type_b == 'LineString'):
                if geom_a.crosses(geom_b):
                    relationships.append((name_b, name_a, "cross"))
                    found_relationship = True
            
            # --- TOUCHES ---
            # Cannot be Point/Point
            if not (type_a == 'Point' and type_b == 'Point'):
                # Get the full relate matrix once
                relate_matrix = geom_a.relate(geom_b)
                
                # Check for interior intersection
                interiors_intersect = relate_matrix[0] == 'T'
                
                if not interiors_intersect:
                    # Interiors do not intersect, now check boundary/interior intersections
                    # B(a) intersects B(b)
                    b_int_b = relate_matrix[4] in ('T', '0', '1', '2') 
                    
                    # I(a) intersects B(b) (relate matrix [0][1])
                    i_int_b = relate_matrix[1] in ('T', '0', '1', '2')
                    
                    # B(a) intersects I(b) (relate matrix [1][0])
                    b_int_i = relate_matrix[3] in ('T', '0', '1', '2')
                    
                    if b_int_b or i_int_b or b_int_i:
                        relationships.append((name_a, name_b, "touches"))
                        found_relationship = True

            # If no positive relationship was found, label it as disjoint
            if not found_relationship:
                if random.random() < 0.05:
                    relationships.append((name_a, name_b, "disjoint"))
                
    return {"relationships": relationships}

# --- Plotting Function ---

def plot_geometries(all_geom_wrappers, canvas_bounds, title_info="", save_path="./polygons.png"):
    """Visualizes all generated geometries on a 2D plot."""
    fig, ax = plt.subplots(figsize=(10, 10))
    min_x, min_y, max_x, max_y = canvas_bounds
    
    ax.set_xlim(min_x, max_x)
    ax.set_ylim(min_y, max_y)
    ax.set_aspect('equal', adjustable='box')
    
    # Sort for rendering (largest polygons first)
    all_geom_wrappers.sort(key=lambda g: g["geom"].area, reverse=True)
    
    for geom_wrapper in all_geom_wrappers:
        geom = geom_wrapper["geom"]
        style = geom_wrapper["style"]
        geom_type = geom_wrapper["type"]

        if geom_type == 'Polygon':
            color = (random.random(), random.random(), random.random())
            x, y = geom.exterior.xy
            ax.fill(x, y, color=color, alpha=0.6, edgecolor='black', zorder=1)
        
        elif geom_type == 'LineString':
            x, y = geom.xy
            if style == 'on_poly_border':
                ax.plot(x, y, color='red', linewidth=3, alpha=1.0, zorder=3)
            elif style == 'through_poly':
                ax.plot(x, y, color='cyan', linewidth=2, alpha=0.8, zorder=3)
            elif style == 'crossing_line':
                ax.plot(x, y, color='orange', linewidth=2, alpha=0.8, zorder=2)
            elif style == 'straight':
                ax.plot(x, y, color='blue', linewidth=2, alpha=0.8, zorder=2)
            elif style == 'in_poly': # Make contained lines dashed purple
                ax.plot(x, y, color='purple', linestyle='--', linewidth=2, alpha=0.8, zorder=2)
            else: # curly
                ax.plot(x, y, color='purple', linewidth=2, alpha=0.8, zorder=2)
        
        elif geom_type == 'Point':
            x, y = geom.xy
            if style == 'on_border_or_line':
                ax.scatter(x, y, color='red', s=50, edgecolor='black', zorder=4)
            elif style == 'in_poly':
                ax.scatter(x, y, color='green', s=30, edgecolor='black', zorder=4)
            else: # 'point'
                ax.scatter(x, y, color='black', s=20, zorder=4)

    ax.set_xticks([]) # Hides x-axis tick marks and labels
    ax.set_yticks([]) # Hides y-axis tick marks and labels
    plt.savefig(save_path)
    # ax.set_xlabel("X Coordinate")
    # ax.set_ylabel("Y Coordinate")
    # plt.grid(True)
    # plt.show()


# --- Database Function ---

def save_geometries_to_postgis(
    named_polygons, named_points_with_style, named_lines_with_style, 
    is_regular, db_config
):
    """
    Connects to PostGIS, creates a table, and inserts all geometries.
    """
    conn = None
    try:
        # print(f"Connecting to database '{db_config['database']}'...")
        # conn = psycopg2.connect(**db_config)
        # cur = conn.cursor()

        # # 1. Create table with geometry column
        # cur.execute("""
        #     CREATE TABLE IF NOT EXISTS generated_geometries (
        #         id SERIAL PRIMARY KEY,
        #         name VARCHAR(50) UNIQUE,
        #         geom_type VARCHAR(20),
        #         style VARCHAR(30),
        #         vertices INTEGER,
        #         geom GEOMETRY(GEOMETRY, 0)
        #     );
        # """)

        print("-- Table Creation: ")
        print("""
            CREATE TABLE IF NOT EXISTS generated_geometries (
                id SERIAL PRIMARY KEY,
                name VARCHAR(50) UNIQUE,
                geom_type VARCHAR(20),
                style VARCHAR(30),
                vertices INTEGER,
                geom GEOMETRY(GEOMETRY, 0)
            );
        """)
        
        # Clear existing data for this run
        # cur.execute("TRUNCATE TABLE generated_geometries RESTART IDENTITY;")
        # print("Table 'generated_geometries' created/cleared.")

        # 2. Insert Polygons
        poly_style = "regular" if is_regular else "irregular"
        for name, poly in named_polygons.items():
            num_vertices = len(poly.exterior.coords) - 1
            # cur.execute(
            #     """
            #     INSERT INTO generated_geometries (name, geom_type, style, vertices, geom)
            #     VALUES (%s, %s, %s, %s, ST_GeomFromText(%s))
            #     """,
            #     (name, 'Polygon', poly_style, num_vertices, poly.wkt)
            # )

            # print("-- Insert Polygons: ")
            print("""
                INSERT INTO generated_geometries (name, geom_type, style, vertices, geom)
                VALUES ('%s', '%s', '%s', %s, ST_GeomFromText('%s'))
                """
                % (name, 'Polygon', poly_style, num_vertices, poly.wkt))
            
        # 3. Insert Points
        for name, point_dict in named_points_with_style.items():
            point = point_dict["geom"]
            style = point_dict["style"]
            # print("-- Insert Points: ")
            print("""
                INSERT INTO generated_geometries (name, geom_type, style, vertices, geom)
                VALUES ('%s', '%s', '%s', %s, ST_GeomFromText('%s'))
                """
                % (name, 'Point', style, 1, point.wkt))
            # cur.execute(
            #     """
            #     INSERT INTO generated_geometries (name, geom_type, style, vertices, geom)
            #     VALUES (%s, %s, %s, %s, ST_GeomFromText(%s))
            #     """,
            #     (name, 'Point', style, 1, point.wkt)
            # )

        # 4. Insert Lines
        for name, line_dict in named_lines_with_style.items():
            line = line_dict["geom"]
            style = line_dict["style"]
            num_vertices = len(line.coords)
            # print("-- Insert Lines: ")
            print("""
                INSERT INTO generated_geometries (name, geom_type, style, vertices, geom)
                VALUES ('%s', '%s', '%s', %s, ST_GeomFromText('%s'))
                """
                % (name, 'LineString', style, num_vertices, line.wkt))
            # cur.execute(
            #     """
            #     INSERT INTO generated_geometries (name, geom_type, style, vertices, geom)
            #     VALUES (%s, %s, %s, %s, ST_GeomFromText(%s))
            #     """,
            #     (name, 'LineString', style, num_vertices, line.wkt)
            # )

        # conn.commit()
        print("Successfully saved all geometries to PostGIS.")

    # except (Exception, psycopg2.DatabaseError) as error:
    #     print(f"Database Error: {error}")
    #     if conn:
    #         conn.rollback()
    finally:
        pass
        # if conn:
        #     cur.close()
        #     conn.close()
        #     print("Database connection closed.")

# --- Main Execution ---

if __name__ == '__main__':
    # --- Basic ---
    CANVAS_BOUNDS = (0, 0, 100, 100) 

    # --- Polygon Control ---
    NUM_POLYGONS = 5          
    VERTEX_RANGE = (3, 6)             
    RADIUS_RANGE = (5, 25)         
    CREATE_REGULAR_SHAPES = False
    
    # --- Polygon Relationship Control ---
    NUM_ALIGNED_PAIRS = 0
    NUM_OVERLAPPING_PAIRS = 0
    NUM_CONTAINED_PAIRS = 1
    NUM_TOUCHING_PAIRS = 0
    
    # --- Geometry Relationship Control ---
    LINE_CONTAINMENT_PROBABILITY = 0.1
    POINT_CONTAINMENT_PROBABILITY = 0.1
    LINE_ON_POLYGON_PROBABILITY = 0.1
    POINT_ON_LINE_PROBABILITY = 0.1
    POINT_ON_POLYGON_BORDER_PROBABILITY = 0.1
    LINE_THROUGH_POLYGON_PROBABILITY = 0.1
    LINE_CROSSES_LINE_PROBABILITY = 0.1
    
    # --- Point Control ---
    NUM_POINTS = 10
    
    # --- Line Control ---
    NUM_LINES = 3
    STRAIGHT_LINES_ONLY = False
    LINE_LENGTH_RANGE = (10, 30)
    LINE_SEGMENT_RANGE = (3, 8)
    
    # --- Disjoint Placement Control ---
    MAX_ATTEMPTS_PER_PLACEMENT = 100 # Attempts to find a disjoint spot
    
    # --- Database Control ---
    SAVE_TO_DB = True
    DB_CONFIG = {
        'host': 'localhost',
        'database': 'spatial_db',
        'user': 'postgres',
        'password': 'jiYOON7162@'
    }

    # --- Generation ---
    print("Generating initial random polygons...")
    initial_polygons = generate_random_polygons(
        canvas_bounds=CANVAS_BOUNDS,
        num_polygons=NUM_POLYGONS,
        min_vertices=VERTEX_RANGE[0],
        max_vertices=VERTEX_RANGE[1],
        min_radius=RADIUS_RANGE[0],
        max_radius=RADIUS_RANGE[1],
        regular_shapes=CREATE_REGULAR_SHAPES
    )
    
    # 2. Validate counts *after* generation, based on *actual* number generated
    num_generated_polygons = len(initial_polygons)
    total_polygons_needed = (
        (NUM_ALIGNED_PAIRS + NUM_OVERLAPPING_PAIRS + NUM_CONTAINED_PAIRS + NUM_TOUCHING_PAIRS) * 2
    )
    if total_polygons_needed > num_generated_polygons:
        raise ValueError(f"Not enough valid polygons generated ({num_generated_polygons}) to create all requested pairs ({total_polygons_needed} needed).")
    if NUM_LINES == 0 and (POINT_ON_LINE_PROBABILITY > 0 or LINE_CROSSES_LINE_PROBABILITY > 0):
        print("Warning: Cannot place points on lines or cross lines as NUM_LINES is 0.")
    
    # 3. Polygon Relationship Processing (now safe)
    poly_indices = list(range(num_generated_polygons))
    random.shuffle(poly_indices)

    poly_idx_offset = 0
    aligned_indices = poly_indices[poly_idx_offset : poly_idx_offset + NUM_ALIGNED_PAIRS*2]
    poly_idx_offset += NUM_ALIGNED_PAIRS*2
    overlapping_indices = poly_indices[poly_idx_offset : poly_idx_offset + NUM_OVERLAPPING_PAIRS*2]
    poly_idx_offset += NUM_OVERLAPPING_PAIRS*2
    poly_contained_indices = poly_indices[poly_idx_offset : poly_idx_offset + NUM_CONTAINED_PAIRS*2]
    poly_idx_offset += NUM_CONTAINED_PAIRS*2
    touching_indices = poly_indices[poly_idx_offset : poly_idx_offset + NUM_TOUCHING_PAIRS*2]
    poly_idx_offset += NUM_TOUCHING_PAIRS*2

    modified_polygons = create_aligned_edges(initial_polygons, aligned_indices)
    modified_polygons = create_overlapping_pairs(modified_polygons, overlapping_indices)
    modified_polygons = create_contained_pairs(modified_polygons, poly_contained_indices)
    modified_polygons = create_touching_polygons(modified_polygons, touching_indices)

    # 4. Disjoint Check for "Free" Polygons
    print("Repositioning free polygons to ensure they are disjoint...")
    
    involved_poly_indices = set(
        aligned_indices + overlapping_indices + poly_contained_indices + touching_indices
    )
    
    involved_footprint = unary_union([modified_polygons[i] for i in involved_poly_indices])
    
    placed_free_polygons = [] # Footprint of free polygons placed so far
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
            
            # Regenerate a new polygon in a new random spot
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

    # --- Generate, Classify, and Place Lines and Points ---
    
    # All polygons are now in their final place.
    # This list will track ALL placed geoms for disjoint checks
    placed_geometries = [g for g in modified_polygons] 
    
    modified_lines = []
    modified_points = []
    num_contained_lines, num_on_poly_lines, num_through_poly_lines, num_crossing_lines = 0, 0, 0, 0
    num_contained_points, num_on_poly_border_points, num_on_line_points = 0, 0, 0

    print(f"Generating and placing {NUM_LINES} lines...")
    
    # --- 1. Create Crossing Line Pairs ---
    num_crossing_pairs = int((NUM_LINES * LINE_CROSSES_LINE_PROBABILITY) / 2)
    num_lines_processed = 0
    
    for _ in range(num_crossing_pairs):
        if num_lines_processed + 2 > NUM_LINES:
            break
            
        line_a = generate_one_line(CANVAS_BOUNDS, True, LINE_LENGTH_RANGE, LINE_SEGMENT_RANGE)
        line_b = generate_one_line(CANVAS_BOUNDS, True, LINE_LENGTH_RANGE, LINE_SEGMENT_RANGE)
        line_a, line_b = create_crossing_lines(line_a, line_b)
        
        # Now find a disjoint spot for this pair
        pair_geom = unary_union([line_a, line_b])
        attempt = 0
        is_placed = False
        while attempt < MAX_ATTEMPTS_PER_PLACEMENT:
            overlaps_any = any(pair_geom.intersects(g) for g in placed_geometries)
            
            if not overlaps_any:
                modified_lines.append({"geom": line_a, "style": "crossing_line"})
                modified_lines.append({"geom": line_b, "style": "crossing_line"})
                placed_geometries.extend([line_a, line_b])
                num_crossing_lines += 2
                num_lines_processed += 2
                is_placed = True
                break
                
            # Regenerate and move the pair
            new_center = generate_one_point(CANVAS_BOUNDS)
            x_off = new_center.x - pair_geom.centroid.x
            y_off = new_center.y - pair_geom.centroid.y
            pair_geom = affinity.translate(pair_geom, xoff=x_off, yoff=y_off)
            line_a = affinity.translate(line_a, xoff=x_off, yoff=y_off)
            line_b = affinity.translate(line_b, xoff=x_off, yoff=y_off)
            attempt += 1

        if not is_placed:
            print(f"Warning: Could not find disjoint spot for a crossing line pair. Skipping.")

    # --- 2. Process Remaining Single Lines ---
    num_remaining_lines = NUM_LINES - num_lines_processed
    for _ in range(num_remaining_lines):
        line_to_place = generate_one_line(
            CANVAS_BOUNDS, STRAIGHT_LINES_ONLY, 
            LINE_LENGTH_RANGE, LINE_SEGMENT_RANGE
        )
        
        # --- Line Relationship Logic ---
        # Priority: Contained > On Border > Through > Free
        
        if random.random() < LINE_CONTAINMENT_PROBABILITY:
            container_poly = random.choice(modified_polygons)
            final_line = move_line_into_poly(container_poly, line_to_place)
            modified_lines.append({"geom": final_line, "style": "in_poly"})
            placed_geometries.append(final_line)
            num_contained_lines += 1
        
        elif random.random() < LINE_ON_POLYGON_PROBABILITY:
            container_poly = random.choice(modified_polygons)
            final_line = create_line_on_poly_border(container_poly)
            modified_lines.append({"geom": final_line, "style": "on_poly_border"})
            placed_geometries.append(final_line)
            num_on_poly_lines += 1

        elif random.random() < LINE_THROUGH_POLYGON_PROBABILITY:
            container_poly = random.choice(modified_polygons)
            final_line = create_line_through_poly(container_poly)
            modified_lines.append({"geom": final_line, "style": "through_poly"})
            placed_geometries.append(final_line)
            num_through_poly_lines += 1

        else: # "Free" line, must be disjoint
            attempt = 0
            is_placed = False
            while attempt < MAX_ATTEMPTS_PER_PLACEMENT:
                overlaps_any = any(line_to_place.intersects(g) for g in placed_geometries)
                
                if not overlaps_any:
                    style = 'straight' if len(line_to_place.coords) == 2 else 'curly'
                    modified_lines.append({"geom": line_to_place, "style": style})
                    placed_geometries.append(line_to_place)
                    is_placed = True
                    break
                
                line_to_place = generate_one_line(
                    CANVAS_BOUNDS, STRAIGHT_LINES_ONLY, 
                    LINE_LENGTH_RANGE, LINE_SEGMENT_RANGE
                )
                attempt += 1
            
            if not is_placed:
                 print(f"Warning: Could not find disjoint spot for a free line. Skipping.")
    
    # --- 3. Process All Points ---
    print(f"Generating and placing {NUM_POINTS} points...")
    for _ in range(NUM_POINTS):
        point_to_place = generate_one_point(CANVAS_BOUNDS)

        # --- Point Relationship Logic ---
        # Priority: Contained > On Poly Border > On Line > Free
        
        if random.random() < POINT_CONTAINMENT_PROBABILITY:
            container_poly = random.choice(modified_polygons)
            final_point = move_point_into_poly(container_poly, point_to_place)
            modified_points.append({"geom": final_point, "style": "in_poly"})
            placed_geometries.append(final_point)
            num_contained_points += 1
        
        elif random.random() < POINT_ON_POLYGON_BORDER_PROBABILITY:
            container_poly = random.choice(modified_polygons)
            final_point = move_point_onto_poly_border(container_poly, point_to_place)
            modified_points.append({"geom": final_point, "style": "on_border_or_line"})
            placed_geometries.append(final_point)
            num_on_poly_border_points += 1

        elif random.random() < POINT_ON_LINE_PROBABILITY and modified_lines:
            # Need to pick from the geom, not the dict
            container_line = random.choice(modified_lines)["geom"]
            final_point = move_point_onto_line(container_line, point_to_place)
            modified_points.append({"geom": final_point, "style": "on_border_or_line"})
            placed_geometries.append(final_point)
            num_on_line_points += 1

        else: # "Free" point, must be disjoint
            attempt = 0
            is_placed = False
            while attempt < MAX_ATTEMPTS_PER_PLACEMENT:
                overlaps_any = any(point_to_place.intersects(g) for g in placed_geometries)

                if not overlaps_any:
                    modified_points.append({"geom": point_to_place, "style": "point"})
                    placed_geometries.append(point_to_place)
                    is_placed = True
                    break
                
                point_to_place = generate_one_point(CANVAS_BOUNDS)
                attempt += 1
            
            if not is_placed:
                print(f"Warning: Could not find disjoint spot for a free point. Skipping.")

    
    # --- 4. Naming and Relationship Finding ---
    print("Assigning names and finding all relationships...")
    
    named_polygons = {f"POLYGON_{i+1}": poly for i, poly in enumerate(modified_polygons)}
    named_lines_with_style = {f"LINE_{i+1}": {"geom": d["geom"], "style": d["style"]} for i, d in enumerate(modified_lines)}
    named_points_with_style = {f"POINT_{i+1}": {"geom": d["geom"], "style": d["style"]} for i, d in enumerate(modified_points)}

    all_named_geoms = {
        **named_polygons,
        **{name: d["geom"] for name, d in named_lines_with_style.items()},
        **{name: d["geom"] for name, d in named_points_with_style.items()}
    }
    
    relationships_dict = find_all_relationships(all_named_geoms)

    with open("./relationship.json", "w") as outfile:
        json.dump(relationships_dict, outfile, indent=4)

    # --- 5. Plotting ---
    all_geom_wrappers = []
    poly_style = "regular" if CREATE_REGULAR_SHAPES else "irregular"
    all_geom_wrappers.extend([{"geom": g, "style": poly_style, "type": "Polygon"} for g in modified_polygons])
    all_geom_wrappers.extend([{"geom": d["geom"], "style": d["style"], "type": "LineString"} for d in modified_lines])
    all_geom_wrappers.extend([{"geom": d["geom"], "style": d["style"], "type": "Point"} for d in modified_points])

    print(f"Successfully generated {len(all_geom_wrappers)} total geometries.")
    title = (
        f"Polys: {len(modified_polygons)} ({NUM_ALIGNED_PAIRS} Aligned, {NUM_OVERLAPPING_PAIRS} Overlap, {NUM_CONTAINED_PAIRS} Poly-in-Poly, {NUM_TOUCHING_PAIRS} Touch) | "
        f"Lines: {len(modified_lines)} ({num_contained_lines} In, {num_on_poly_lines} On, {num_through_poly_lines} Through, {num_crossing_lines} Crossing) | "
        f"Points: {len(modified_points)} ({num_contained_points} In, {num_on_poly_border_points} On Poly, {num_on_line_points} On Line)"
    )
    plot_geometries(all_geom_wrappers, CANVAS_BOUNDS, title_info=title)

    # --- 6. Database Saving ---
    if SAVE_TO_DB:
        save_geometries_to_postgis(
            named_polygons, named_points_with_style, named_lines_with_style, 
            CREATE_REGULAR_SHAPES, DB_CONFIG
        )