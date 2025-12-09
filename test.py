import random
import math
from shapely.geometry import Polygon, Point, LineString
from shapely import affinity
from shapely.ops import unary_union
import matplotlib.pyplot as plt
import psycopg2
from psycopg2.extras import RealDictCursor
import json
import matplotlib.patheffects as PathEffects
from adjustText import adjust_text

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

def create_touching_pairs(polygons, indices_to_use, relationships_list):
    """
    Adjusts specified polygon pairs to share a single boundary point.
    """
    modified_polygons = polygons[:] # Work on a copy

    for i in range(0, len(indices_to_use), 2):
        # Get indices for the stationary polygon (A) and the mobile one (B)
        idx_a = indices_to_use[i]
        idx_b = indices_to_use[i+1]

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
        
        # Simple check to reduce severe overlap, though 'touches' can still mean overlap
        if not poly_a.overlaps(moved_poly_b):
            modified_polygons[idx_b] = moved_poly_b
        else:
            # If it overlaps, we'll just accept it for this demo
            modified_polygons[idx_b] = moved_poly_b
            
        # --- ADDED RELATIONSHIP ---
        relationships_list.append([["Polygon", f"P{idx_a}"], ["Polygon", f"P{idx_b}"], "touches"])
        # ---
    
    return modified_polygons

def get_random_point_in_polygon(poly):
    """
    Returns a random Point that is guaranteed to be inside the given polygon.
    Uses rejection sampling.
    """
    min_x, min_y, max_x, max_y = poly.bounds
    while True:
        p = Point(random.uniform(min_x, max_x), random.uniform(min_y, max_y))
        if poly.contains(p):
            return p

def create_aligned_edges(polygons, indices_to_use, relationships_list):
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
                # --- MODIFIED RELATIONSHIP ---
                relationships_list.append([["Polygon", f"P{idx_a}"], ["Polygon", f"P{idx_b}"], "borders"])
                # ---
                break
        
        if not pair_aligned:
            print(f"Warning: Could not align pair ({idx_a}, {idx_b}) without overlap.")

    return modified_polygons

def create_overlapping_pairs(polygons, indices_to_use, relationships_list):
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
        
        # --- ADDED RELATIONSHIP ---
        relationships_list.append([["Polygon", f"P{idx_a}"], ["Polygon", f"P{idx_b}"], "overlaps"])
        # ---
        
    return modified_polygons

def create_contained_pairs(polygons, indices_to_use, relationships_list):
    """
    Adjusts specified polygon pairs so one is STRICTLY contained within another.
    Uses an iterative shrink-to-fit method to prevent edges from sticking out.
    """
    modified_polygons = polygons[:]
    
    for i in range(0, len(indices_to_use), 2):
        idx_1 = indices_to_use[i]
        idx_2 = indices_to_use[i+1]
        
        # Determine which is larger to be the container
        if modified_polygons[idx_1].area > modified_polygons[idx_2].area:
            idx_a, idx_b = idx_1, idx_2 # A is container, B is contained
        else:
            idx_a, idx_b = idx_2, idx_1
            
        poly_a = modified_polygons[idx_a]
        poly_b = modified_polygons[idx_b]
        
        # 1. Initial Scale: aggressive scaling to start (make it clearly smaller)
        target_area_ratio = 0.4
        current_ratio = poly_b.area / poly_a.area
        scale_needed = math.sqrt(target_area_ratio / current_ratio) if current_ratio > 0 else 0.5
        
        poly_b = affinity.scale(poly_b, xfact=scale_needed, yfact=scale_needed, origin='center')

        # 2. Move B to a safe spot inside A
        # representative_point() is guaranteed to be inside A, unlike centroid.
        target_point = poly_a.representative_point()
        source_centroid = poly_b.centroid
        x_off = target_point.x - source_centroid.x
        y_off = target_point.y - source_centroid.y
        
        poly_b = affinity.translate(poly_b, xoff=x_off, yoff=y_off)
        
        # 3. Iterative Shrink-to-Fit
        # If B still sticks out (due to rotation/shape), shrink it until it fits.
        max_shrink_attempts = 20
        shrink_factor = 0.9
        
        for _ in range(max_shrink_attempts):
            if poly_a.contains(poly_b):
                break # It fits!
            
            # It doesn't fit, shrink it slightly and try again
            poly_b = affinity.scale(poly_b, xfact=shrink_factor, yfact=shrink_factor, origin='center')
            
            # Optional: If it gets ridiculously small, stop to prevent errors
            if poly_b.area < 0.5: 
                break

        modified_polygons[idx_b] = poly_b
        
        # Update relationship list
        relationships_list.append([["Polygon", f"P{idx_b}"], ["Polygon", f"P{idx_a}"], "within"])
        
    return modified_polygons

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

    # NEW LOGIC:
    target_point = get_random_point_in_polygon(container_poly)
    
    source_centroid = scaled_line.centroid
    x_off = target_point.x - source_centroid.x
    y_off = target_point.y - source_centroid.y
    
    final_line = affinity.translate(scaled_line, xoff=x_off, yoff=y_off)
    
    # Double check that the rotation/move kept it inside. 
    # If the random point was near the edge, the line might stick out.
    if not container_poly.contains(final_line):
        # Fallback: Try representative point if random placement failed to contain the whole line
        target_point = container_poly.representative_point()
        x_off = target_point.x - source_centroid.x
        y_off = target_point.y - source_centroid.y
        final_line = affinity.translate(scaled_line, xoff=x_off, yoff=y_off)

    return final_line

def move_point_into_poly(container_poly, point_to_move):
    """Moves a single point to a RANDOM location contained within a polygon."""
        
    # NEW LOGIC:
    target_point = get_random_point_in_polygon(container_poly)
    
    # Calculate offset to move the point from its current spot to the new random spot
    x_off = target_point.x - point_to_move.x
    y_off = target_point.y - point_to_move.y
    
    final_point = affinity.translate(point_to_move, xoff=x_off, yoff=y_off)
    return final_point

def plot_geometries(polygon_data, line_data, point_data, canvas_bounds, title_info="", save_path="./polygons.png"):
    """
    Visualizes the generated geometries.
    
    Arguments now expect lists of tuples: [(id, geometry), ...]
    This ensures labels match the logical IDs even if we sort the list for rendering order.
    """
    fig, ax = plt.subplots(figsize=(12, 12))
    min_x, min_y, max_x, max_y = canvas_bounds
    ax.set_xlim(min_x, max_x); ax.set_ylim(min_y, max_y)
    ax.set_aspect('equal', adjustable='box')
    
    texts_to_adjust = []
    points_to_avoid = [] 

    text_obj_to_id = {}

    # Extract just the geometries for calculation purposes
    all_polys = [p for _, p in polygon_data]

    # 1. Plot Polygons 
    # We iterate through the tuples to get the specific ID associated with that shape
    for real_id, poly in polygon_data:
        color = (random.random(), random.random(), random.random())
        x, y = poly.exterior.xy
        ax.fill(x, y, color=color, alpha=0.7, edgecolor='black', linewidth=0.5)
        
        # --- EXCLUSIVE REGION LOGIC ---
        label_region = poly
        for _, other_poly in polygon_data:
            if poly == other_poly: continue 
            if poly.intersects(other_poly):
                try:
                    diff = label_region.difference(other_poly)
                    if not diff.is_empty:
                        label_region = diff
                except Exception:
                    pass
        
        if label_region.is_empty or label_region.geom_type == 'GeometryCollection':
             c = poly.representative_point()
        else:
             c = label_region.representative_point()

        # Use 'real_id' for the label, not the loop index
        str_id = f"P{real_id}"
        ann = ax.annotate(str_id, 
                          xy=(c.x, c.y), 
                          xytext=(c.x, c.y),
                          fontsize=11, ha='center', va='center', color='white',
                          path_effects=[PathEffects.withStroke(linewidth=3, foreground="black")])
        texts_to_adjust.append(ann)
        text_obj_to_id[ann] = str_id

    # 2. Plot Lines
    for real_id, line in line_data:
        x, y = line.xy
        ax.plot(x, y, color='purple', linewidth=2, alpha=0.9, linestyle='--')
        
        mid_point = line.interpolate(0.5, normalized=True)
        
        # Use 'real_id'
        str_id = f"L{real_id}"
        ann = ax.annotate(str_id, 
                          xy=(mid_point.x, mid_point.y), 
                          xytext=(mid_point.x, mid_point.y),
                          fontsize=11, color='black', ha='center', va='center', 
                          path_effects=[PathEffects.withStroke(linewidth=3, foreground="white")])
        texts_to_adjust.append(ann)
        text_obj_to_id[ann] = str_id

    # 3. Plot Points
    for real_id, point in point_data:
        scatter_pt = ax.scatter(point.x, point.y, c='black', s=50, zorder=5)
        points_to_avoid.append(scatter_pt)

        # Use 'real_id'
        str_id = f"Pt{real_id}"
        ann = ax.annotate(str_id, 
                          xy=(point.x, point.y), 
                          xytext=(point.x + 0.5, point.y + 0.5), 
                          textcoords='data',
                          ha='left', va='bottom',
                          fontsize=11, color='black', 
                          path_effects=[PathEffects.withStroke(linewidth=2, foreground="white")])
        texts_to_adjust.append(ann)
        text_obj_to_id[ann] = str_id
    
    ax.set_xticks([]) 
    ax.set_yticks([]) 
    ax.set_title(title_info)

    print("Adjusting label positions to avoid overlaps...")
    
    adjust_text(texts_to_adjust, 
                ax=ax, 
                add_objects=points_to_avoid,
                force_text=(0.3, 0.5),   
                force_points=(0.1, 0.2), 
                expand_points=(1.1, 1.1)
                )

    plt.savefig(save_path)
    print(f"Plot saved to {save_path}")

    final_positions = {}
    for ann in texts_to_adjust:
        # Get the final position (x, y) after adjustment
        final_x, final_y = ann.get_position()
        label_id = text_obj_to_id[ann]
        final_positions[label_id] = (final_x, final_y)
        
    return final_positions

def save_geometries_to_postgis(polygon_data, point_data, line_data, label_positions, is_regular_polygon, db_config):
    """
    Connects to PostGIS and saves all geometry types with their alphanumeric IDs (e.g., 'Pt2').
    """
    conn = None
    try:
        print("\nConnecting to the PostGIS database...")
        conn = psycopg2.connect(**db_config)
        cur = conn.cursor()

        # 1. Drop old table to ensure schema update (int -> varchar)
        cur.execute("DROP TABLE IF EXISTS generated_geometries;")

        # 2. Create table with id as VARCHAR
        create_table_sql = """
        CREATE TABLE generated_geometries (
            id VARCHAR(20) PRIMARY KEY, 
            geom GEOMETRY(GEOMETRY, 0),
            geom_type VARCHAR(20), 
            style VARCHAR(20),
            vertices INTEGER, 
            area DOUBLE PRECISION,
            label_x DOUBLE PRECISION,
            label_y DOUBLE PRECISION,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );"""
        cur.execute(create_table_sql)
        
        polygon_style = "regular" if is_regular_polygon else "irregular"

        # 3. Insert Polygons (P0, P1...)
        # We iterate over the tuple list: (real_id, geometry)
        for real_id, poly in polygon_data:
            str_id = f"P{real_id}"

            raw_lx, raw_ly = label_positions.get(str_id, (0, 0))
            lx = float(raw_lx)
            ly = float(raw_ly)

            cur.execute(
                """INSERT INTO generated_geometries (id, geom, geom_type, style, vertices, area, label_x, label_y)
                   VALUES (%s, ST_GeomFromText(%s, 0), 'Polygon', %s, %s, %s, %s, %s);""",
                (str_id, poly.wkt, polygon_style, len(poly.exterior.coords) - 1, poly.area, lx, ly)
            )
        
        # 4. Insert Points (Pt0, Pt1...)
        for real_id, point in point_data:
            str_id = f"Pt{real_id}"

            raw_lx, raw_ly = label_positions.get(str_id, (0, 0))
            lx = float(raw_lx)
            ly = float(raw_ly)

            cur.execute(
                """INSERT INTO generated_geometries (id, geom, geom_type, style, vertices, area, label_x, label_y)
                   VALUES (%s, ST_GeomFromText(%s, 0), 'Point', 'point', 1, 0, %s, %s);""",
                (str_id, point.wkt, lx, ly)
            )

        # 5. Insert Lines (L0, L1...)
        for real_id, line in line_data:
            str_id = f"L{real_id}"

            raw_lx, raw_ly = label_positions.get(str_id, (0, 0))
            lx = float(raw_lx)
            ly = float(raw_ly)

            cur.execute(
                """INSERT INTO generated_geometries (id, geom, geom_type, style, vertices, area, label_x, label_y)
                   VALUES (%s, ST_GeomFromText(%s, 0), 'Line', 'straight', %s, 0, %s, %s);""",
                (str_id, line.wkt, len(line.coords), lx, ly)
            )

        conn.commit()
        print("Successfully saved all geometries to the database.")
    except (Exception, psycopg2.DatabaseError) as error:
        print(f"Database error: {error}")
    finally:
        if conn is not None:
            conn.close()
            print("Database connection closed.")

def get_relative_location(db_config, table_name='generated_geometries'):
    MAX_RADIUS = 100000 

    sql_query = f"""
    WITH RECURSIVE 
    Directions (dir_name, start_rad, mid_rad, end_rad) AS (
        VALUES 
            ('North',      5.89,  0.0,   0.39),
            ('North East', 0.39,  0.78,  1.17),
            ('East',       1.17,  1.57,  1.96),
            ('South East', 1.96,  2.35,  2.74),
            ('South',      2.74,  3.14,  3.53),
            ('South West', 3.53,  3.92,  4.31),
            ('West',       4.31,  4.71,  5.10),
            ('North West', 5.10,  5.49,  5.89)
    ),
    
    Geoms AS (
        SELECT id, geom, ST_Centroid(geom) as center, ST_GeometryType(geom) as gtype
        FROM {table_name}
    ),

    Cones AS (
        SELECT 
            s.id as source_id,
            d.dir_name,
            ST_MakePolygon(ST_MakeLine(ARRAY[
                s.center,
                ST_MakePoint(ST_X(s.center) + {MAX_RADIUS} * sin(d.start_rad), ST_Y(s.center) + {MAX_RADIUS} * cos(d.start_rad)),
                ST_MakePoint(ST_X(s.center) + {MAX_RADIUS} * sin(d.mid_rad),   ST_Y(s.center) + {MAX_RADIUS} * cos(d.mid_rad)),
                ST_MakePoint(ST_X(s.center) + {MAX_RADIUS} * sin(d.end_rad),   ST_Y(s.center) + {MAX_RADIUS} * cos(d.end_rad)),
                s.center
            ])) as cone_geom
        FROM Geoms s
        CROSS JOIN Directions d
    )

    SELECT 
        t.id as target_name,
        t.gtype as target_type,
        c.dir_name as direction,
        s.id as source_name,
        s.gtype as source_type,
        
        CASE 
            WHEN t.gtype ILIKE '%Polygon%' THEN 
                ST_Area(ST_Intersection(t.geom, c.cone_geom)) / NULLIF(ST_Area(t.geom), 0)
            
            WHEN t.gtype ILIKE '%Line%' THEN 
                ST_Length(ST_Intersection(t.geom, c.cone_geom)) / NULLIF(ST_Length(t.geom), 0)
            
            ELSE 
                CASE WHEN ST_Intersects(t.geom, c.cone_geom) THEN 1.0 ELSE 0.0 END
        END as overlap_ratio

    FROM Geoms t
    JOIN Geoms s ON t.id != s.id
    JOIN Cones c ON c.source_id = s.id
    
    WHERE 
        CASE 
            WHEN t.gtype ILIKE '%Polygon%' THEN 
                (ST_Area(ST_Intersection(t.geom, c.cone_geom)) / NULLIF(ST_Area(t.geom), 0)) > 0.7
            WHEN t.gtype ILIKE '%Line%' THEN 
                (ST_Length(ST_Intersection(t.geom, c.cone_geom)) / NULLIF(ST_Length(t.geom), 0)) > 0.7
            ELSE 
                ST_Intersects(t.geom, c.cone_geom)
        END;
    """

    try:
        conn = psycopg2.connect(**db_config)
        cur = conn.cursor(cursor_factory=RealDictCursor)
        cur.execute(sql_query)
        rows = cur.fetchall()

        results_list = []
        for row in rows:
            item = [
                [row['target_type'].replace('ST_', ''), row['target_name']], 
                [row['source_type'].replace('ST_', ''), row['source_name']],
                row['direction']
            ]
            results_list.append(item)

        conn.close()
        return results_list

    except Exception as e:
        print(f"Error: {e}")
        return []
    
def merge_relationships(existing_data, new_sql_data):
    existing_pairs = set()
    
    for item in existing_data:
        obj1 = tuple(item[0])
        obj2 = tuple(item[1])
        existing_pairs.add((obj1, obj2))

    final_list = list(existing_data)

    for item in new_sql_data:
        obj1 = tuple(item[0])
        obj2 = tuple(item[1])
        
        if ((obj1, obj2) not in existing_pairs) and ((obj2, obj1) not in existing_pairs):
            final_list.append(item)
            
    return final_list

if __name__ == '__main__':
    # --- Configuration ---
    CANVAS_BOUNDS = (0, 0, 100, 100)
    SAVE_TO_DB = True
    DB_CONFIG = {
        "dbname": "postgres",
        "user": "postgres",
        "password": "jiYOON7162@",
        "host": "localhost",
        "port": "5432"
    }

    # --- Polygon Stuff ---
    NUM_POLYGONS = 4
    VERTEX_RANGE = (3, 6)
    RADIUS_RANGE = (10, 35)
    CREATE_REGULAR_SHAPES = False

    # --- Polygon Relationship Controls ---
    NUM_TOUCHING_PAIRS = 0
    NUM_ALIGNED_PAIRS = 0
    NUM_OVERLAPPING_PAIRS = 0
    NUM_CONTAINED_PAIRS = 1

    # --- Line Stuff ---
    NUM_LINES = 1
    STRAIGHT_LINES_ONLY = False
    LINE_LENGTH_RANGE = (10, 30)
    LINE_SEGMENT_RANGE = (3, 8)
    LINE_CONTAINMENT_PROBABILITY = 0.3

    # --- Point Stuff ---
    NUM_POINTS = 10
    POINT_CONTAINMENT_PROBABILITY = 0.3

    MIN_POINT_DISTANCE = 8.0

    # --- Disjoint Placement Controls ---
    MAX_ATTEMPTS_PER_PLACEMENT = 100 # Attempts to find a disjoint spot

    all_relationships = []


    # --- Generation ---
    total_polygons_needed = (NUM_ALIGNED_PAIRS + NUM_OVERLAPPING_PAIRS + NUM_CONTAINED_PAIRS + NUM_TOUCHING_PAIRS) * 2

    if total_polygons_needed > NUM_POLYGONS:
        raise ValueError(f"Not enough polygons ({NUM_POLYGONS}) to create all requested pairs ({total_polygons_needed} needed).")


    print(f"Generating {NUM_POLYGONS} random polygons...")
    initial_polygons = generate_random_polygons(
        canvas_bounds=CANVAS_BOUNDS,
        num_polygons=NUM_POLYGONS,
        min_vertices=VERTEX_RANGE[0],
        max_vertices=VERTEX_RANGE[1],
        min_radius=RADIUS_RANGE[0],
        max_radius=RADIUS_RANGE[1],
        regular_shapes=CREATE_REGULAR_SHAPES
    )

    # --- Polygon Relationship Processing ---
    indices = list(range(NUM_POLYGONS))
    random.shuffle(indices)

    aligned_indices = indices[:NUM_ALIGNED_PAIRS*2]
    off_1 = NUM_ALIGNED_PAIRS*2
    overlapping_indices = indices[off_1 : off_1 + NUM_OVERLAPPING_PAIRS*2]
    off_2 = off_1 + NUM_OVERLAPPING_PAIRS*2
    contained_indices = indices[off_2 : off_2 + NUM_CONTAINED_PAIRS*2]

    modified_polygons = create_aligned_edges(initial_polygons, aligned_indices, all_relationships)
    modified_polygons = create_overlapping_pairs(modified_polygons, overlapping_indices, all_relationships)
    modified_polygons = create_contained_pairs(modified_polygons, contained_indices, all_relationships)

    # --- Repositioning to satisfy disjoint condition ---
    print("Repositioning free polygons to ensure they are disjoint...")
    involved_indices_set = set(aligned_indices) | set(overlapping_indices) | set(contained_indices)
    free_indices = [i for i in range(NUM_POLYGONS) if i not in involved_indices_set]
    
    involved_polygons_list = [modified_polygons[i] for i in involved_indices_set]
    involved_footprint = unary_union(involved_polygons_list)
    
    placed_free_polygons_so_far = []
    
    for free_idx in free_indices:
        poly_to_check = modified_polygons[free_idx]
        attempt = 0
        is_placed = False
        
        while attempt < MAX_ATTEMPTS_PER_PLACEMENT:
            # Check against the "no-go" zone of involved polygons
            overlaps_involved = poly_to_check.intersects(involved_footprint)
            
            # Check against other "free" polygons already placed
            overlaps_other_free = False
            for placed_poly in placed_free_polygons_so_far:
                if poly_to_check.intersects(placed_poly):
                    overlaps_other_free = True
                    break
            
            # If it's in a clear spot, place it and move on
            if not overlaps_involved and not overlaps_other_free:
                modified_polygons[free_idx] = poly_to_check
                placed_free_polygons_so_far.append(poly_to_check)
                is_placed = True
                break
            
            # If it failed, generate a new polygon at a new random spot
            poly_to_check = generate_random_polygons(
                canvas_bounds=CANVAS_BOUNDS, num_polygons=1,
                min_vertices=VERTEX_RANGE[0], max_vertices=VERTEX_RANGE[1],
                min_radius=RADIUS_RANGE[0], max_radius=RADIUS_RANGE[1],
                regular_shapes=CREATE_REGULAR_SHAPES
            )[0]
            attempt += 1
            
        if not is_placed:
            print(f"Warning: Could not find a disjoint spot for polygon {free_idx} after {MAX_ATTEMPTS_PER_PLACEMENT} attempts. Placing it anyway.")
            modified_polygons[free_idx] = poly_to_check # Add its last position
            placed_free_polygons_so_far.append(poly_to_check)
            
    all_poly_footprint = unary_union(modified_polygons)
    placed_free_geometries = [] # Keep track of free lines/points
    
    modified_lines = []
    modified_points = []
    num_contained_lines = 0
    num_contained_points = 0

    print(f"Generating and placing {NUM_LINES} lines...")
    for _ in range(NUM_LINES):
        if random.random() < LINE_CONTAINMENT_PROBABILITY:
            container_idx = random.choice(range(len(modified_polygons)))
            container_poly = modified_polygons[container_idx]
            line_to_place = generate_one_line(
                CANVAS_BOUNDS, STRAIGHT_LINES_ONLY, 
                LINE_LENGTH_RANGE, LINE_SEGMENT_RANGE
            )
            final_line = move_line_into_poly(container_poly, line_to_place)
            modified_lines.append(final_line)

            line_idx = len(modified_lines) - 1
            all_relationships.append([["Line", f"L{line_idx}"], ["Polygon", f"P{container_idx}"], "within"])

            num_contained_lines += 1
        
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
        
        point_successfully_placed = False
        attempt = 0
        
        # We try multiple times to find a point that is valid AND far enough from others
        while not point_successfully_placed and attempt < MAX_ATTEMPTS_PER_PLACEMENT:
            attempt += 1
            
            # 1. Generate Candidate Point (Contained or Free)
            is_contained = (random.random() < POINT_CONTAINMENT_PROBABILITY and len(modified_polygons) > 0)
            candidate_point = None
            
            if is_contained:
                container_idx = random.choice(range(len(modified_polygons)))
                container_poly = modified_polygons[container_idx]
                raw_point = generate_one_point(CANVAS_BOUNDS)
                # Uses our random placement helper
                candidate_point = move_point_into_poly(container_poly, raw_point)
            else:
                candidate_point = generate_one_point(CANVAS_BOUNDS)
                # If free, must not be inside a polygon
                if candidate_point.intersects(all_poly_footprint):
                    continue 

            # 2. Check Distance against ALL existing points
            too_close = False
            for existing_point in modified_points:
                if candidate_point.distance(existing_point) < MIN_POINT_DISTANCE:
                    too_close = True
                    break
            
            if too_close:
                # Discard and try again ("replace them")
                continue

            # 3. Accept the Point
            modified_points.append(candidate_point)
            point_idx = len(modified_points) - 1
            
            if is_contained:
                # all_relationships.append([["Point", point_idx], ["Polygon", container_idx], "within"])
                all_relationships.append([["Point", f"Pt{point_idx}"], ["Polygon", f"P{container_idx}"], "within"])
            else:
                placed_free_geometries.append(candidate_point)
            
            point_successfully_placed = True

        if not point_successfully_placed:
            print("Warning: Could not place a point satisfying distance constraints.")

    # --- Sorting for Plotting ---
    all_geometries = modified_polygons + modified_lines + modified_points

    polygon_data = list(enumerate(modified_polygons))
    line_data = list(enumerate(modified_lines))
    point_data = list(enumerate(modified_points))

    polygon_data.sort(key=lambda p: p[1].area, reverse=True)
    
    # --- Plotting ---
    print(f"Generated {len(all_geometries)} total geometries.")
    final_label_coords = plot_geometries(polygon_data, line_data, point_data, CANVAS_BOUNDS)
# 
    # --- Database Saving ---
    if SAVE_TO_DB:
        save_geometries_to_postgis(
            polygon_data, point_data, line_data, 
            final_label_coords,
            CREATE_REGULAR_SHAPES, DB_CONFIG
        )

    # Add location information:
    location_list = get_relative_location(DB_CONFIG)
    all_relationships = merge_relationships(all_relationships, location_list)

    relationship_data = {"relationships": all_relationships}
    file_path = f"relationship.json"
    with open(file_path, "w") as f:
        json.dump(relationship_data, f, indent=4)

    print('Relationship saved to relationship.json')