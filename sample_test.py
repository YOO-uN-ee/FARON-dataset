import random
import math
import numpy as np
from shapely.geometry import Polygon, Point, LineString, box
from shapely import affinity
from shapely.ops import unary_union
import matplotlib.pyplot as plt
import matplotlib.patheffects as PathEffects
from adjustText import adjust_text
import psycopg2
from psycopg2.extras import RealDictCursor
import json

# ==========================================
# 1. GEOMETRY GENERATORS (Local Coordinates)
# ==========================================

def smooth_coords(coords, iterations=3):
    """Applies Chaikin's Corner Cutting algorithm to smooth coordinates."""
    if len(coords) < 3: return coords
    for _ in range(iterations):
        new_coords = [coords[0]]
        for i in range(len(coords) - 1):
            p0, p1 = coords[i], coords[i+1]
            Q = (0.75 * p0[0] + 0.25 * p1[0], 0.75 * p0[1] + 0.25 * p1[1])
            R = (0.25 * p0[0] + 0.75 * p1[0], 0.25 * p0[1] + 0.75 * p1[1])
            new_coords.extend([Q, R])
        new_coords.append(coords[-1])
        coords = new_coords
    return coords

def make_random_polygon(radius=8, num_verts=5):
    """Creates a polygon centered at 0,0."""
    angles = sorted([random.uniform(0, 2 * math.pi) for _ in range(num_verts)])
    vertices = []
    for angle in angles:
        r = radius * random.uniform(0.5, 1.2)
        vertices.append((r * math.cos(angle), r * math.sin(angle)))
    return Polygon(vertices)

def make_contained_pair(outer_radius=30):
    """
    Returns [PolyOuter, PolyInner].
    Strictly enforces that Inner is FULLY inside Outer (not just touching).
    """
    outer = make_random_polygon(outer_radius, num_verts=7)
    
    # Start smaller
    inner_radius = outer_radius * 0.5
    inner = make_random_polygon(inner_radius, num_verts=5)
    
    # 1. Center Inner on Outer
    inner = affinity.translate(inner, 
                               outer.centroid.x - inner.centroid.x, 
                               outer.centroid.y - inner.centroid.y)
    
    # 2. Strict Fit Loop
    # If strictly contained, .contains is True. If touching border, it might be False or True depending on precision
    # We want a buffer.
    for _ in range(10):
        if outer.contains(inner) and outer.boundary.distance(inner) > 0.5:
            return [outer, inner]
        
        # Shrink if not fitting
        inner = affinity.scale(inner, 0.9, 0.9, origin='centroid')
        
    return [outer, inner]

def make_overlapping_pair(radius=20):
    """
    Returns [PolyA, PolyB].
    Strictly enforces PARTIAL overlap (Neither is fully inside the other).
    """
    p1 = make_random_polygon(radius)
    p2 = make_random_polygon(radius)
    
    # 1. Move p2 to the edge of p1 to guarantee intersection without containment
    # Move p2 to the right by roughly 1 radius (partial overlap zone)
    shift_dist = radius * 1.2
    p2 = affinity.translate(p2, shift_dist, 0)
    
    # 2. Correction Loop
    # We want Intersection > 0 AND Intersection < Area(p1) AND Intersection < Area(p2)
    for _ in range(20):
        inter = p1.intersection(p2)
        
        # Case A: Too far apart (No intersection) -> Move closer
        if inter.is_empty or inter.area < 1.0:
            p2 = affinity.translate(p2, -2, 0)
            continue
            
        # Case B: One swallowed the other (Containment) -> Move away
        if p1.contains(p2) or p2.contains(p1) or inter.area >= 0.95 * p2.area or inter.area >= 0.95 * p1.area:
            p2 = affinity.translate(p2, 5, 0)
            continue
            
        # Case C: Valid Partial Overlap
        return [p1, p2]
        
    return [p1, p2]

def make_bordering_pair(radius=8):
    """
    Returns [PolyA, PolyB] that share a boundary LINE (Edge).
    Strictly aligns an edge from B to an edge from A.
    """
    p1 = make_random_polygon(radius)
    p2 = make_random_polygon(radius)
    
    # Try multiple times to find a compatible edge pair that doesn't cause overlap
    for _ in range(20):
        # 1. Pick random edges
        coords1 = list(p1.exterior.coords)
        idx1 = random.randrange(len(coords1) - 1)
        u1, v1 = Point(coords1[idx1]), Point(coords1[idx1 + 1])
        
        coords2 = list(p2.exterior.coords)
        idx2 = random.randrange(len(coords2) - 1)
        u2, v2 = Point(coords2[idx2]), Point(coords2[idx2 + 1])
        
        # 2. Calculate angles
        angle1 = math.atan2(v1.y - u1.y, v1.x - u1.x)
        angle2 = math.atan2(v2.y - u2.y, v2.x - u2.x)
        
        # 3. Rotate p2 so its edge is parallel and opposite to p1's edge
        # We want angle2 to become (angle1 + 180 degrees)
        rotation = angle1 - angle2 + math.pi
        p2_rotated = affinity.rotate(p2, rotation, origin='centroid', use_radians=True)
        
        # 4. Snap the midpoints of the edges together
        # We need to re-calculate the edge midpoint of the rotated polygon
        coords2_rot = list(p2_rotated.exterior.coords)
        # Note: Index doesn't change after rotation
        rot_u2 = Point(coords2_rot[idx2])
        rot_v2 = Point(coords2_rot[idx2 + 1])
        
        mid1 = Point((u1.x + v1.x)/2, (u1.y + v1.y)/2)
        mid2 = Point((rot_u2.x + rot_v2.x)/2, (rot_u2.y + rot_v2.y)/2)
        
        x_off = mid1.x - mid2.x
        y_off = mid1.y - mid2.y
        
        p2_final = affinity.translate(p2_rotated, x_off, y_off)
        
        # 5. Check validity
        # We expect them to touch (intersect) but not overlap (area of intersection should be ~0)
        # However, floating point precision usually results in a tiny intersection.
        # Valid if intersection area is negligible relative to polygon size.
        inter_area = p1.intersection(p2_final).area
        
        if inter_area < 0.1: # Almost zero overlap
            return [p1, p2_final]
            
    # Fallback: Just return non-touching if alignment failed (prevents crash)
    return [p1, affinity.translate(p2, radius*3, 0)]

def make_random_line_geom(length=25, num_segments=5):
    """
    Creates a line centered at (0,0).
    Randomly chooses between 'straight', 'jagged', or 'curvy'.
    """
    # 1. Randomly select style
    line_style = random.choice(['straight', 'jagged', 'curvy'])
    
    start_x = -length / 2
    end_x = length / 2
    
    # CASE A: Straight
    if line_style == 'straight':
        return LineString([(start_x, 0), (end_x, 0)])

    # Generate Control Points (Used for both Jagged and Curvy)
    points = [(start_x, 0)]
    step = length / num_segments
    current_x = start_x
    
    for _ in range(num_segments - 1):
        current_x += step
        # Add random Y jitter
        jitter_y = random.uniform(-length * 0.2, length * 0.2)
        points.append((current_x, jitter_y))
        
    points.append((end_x, 0))

    # CASE B: Curvy (Smooth the control points)
    if line_style == 'curvy':
        points = smooth_coords(points, iterations=4)
        return LineString(points)

    # CASE C: Jagged (Return control points directly)
    return LineString(points)

def make_crossing_pair(poly_radius=20, line_len=60):
    """Returns [Poly, Line] where line crosses poly."""
    poly = make_random_polygon(poly_radius)
    
    # Generate line (Force it to be long enough to cross)
    # We allow it to be curly, but we treat it as a 'trend' from left to right
    line = make_random_line_geom(length=line_len, num_segments=6)
    
    # Rotate line randomly around 0,0 so it doesn't just cross horizontally
    line = affinity.rotate(line, random.uniform(0, 360), origin=(0,0))
    
    return [poly, line]

def make_touching_pair(radius=20):
    """Returns [PolyA, PolyB] touching at a point."""
    p1 = make_random_polygon(radius)
    p2 = make_random_polygon(radius)
    # Move p2 to right
    p2 = affinity.translate(p2, radius*2, 0)
    
    # Touch logic: Find rightmost of p1 and leftmost of p2
    # Simplified: just move p2 until distance is 0
    dist = p1.distance(p2)
    p2 = affinity.translate(p2, -dist, 0)
    
    # Check if they overlap too much, if so, back off
    if p1.intersects(p2) and not p1.touches(p2):
        p2 = affinity.translate(p2, 5, 0) # naive backoff
    return [p1, p2]

def make_border_point_pair(radius=20):
    """Returns [Poly, Point] where Point is on border."""
    poly = make_random_polygon(radius)
    pt = poly.exterior.interpolate(random.uniform(0, poly.exterior.length))
    return [poly, pt]

# ==========================================
# 2. PLACEMENT MANAGER
# ==========================================

class PlacementManager:
    def __init__(self, bounds):
        self.min_x, self.min_y, self.max_x, self.max_y = bounds
        self.occupied_geom = None # Shapely geometry of occupied space
        self.items = [] # List of {'type': 'Polygon', 'id': 'P0', 'geom': geom}
        self.counters = {'Polygon': 0, 'Line': 0, 'Point': 0}

    def place_object(self, geoms, types, relations=None, max_attempts=200):
        """
        Attempts to place a list of geometries (a cluster) such that they don't 
        overlap existing items.
        
        geoms: list of Shapely geometries (e.g. [Poly, Line]) already related locally
        types: list of types strings (e.g. ['Polygon', 'Line'])
        """
        # Calculate local bounding box of the cluster
        cluster_grp = unary_union(geoms)
        minx, miny, maxx, maxy = cluster_grp.bounds
        w, h = maxx - minx, maxy - miny
        
        for _ in range(max_attempts):
            # 1. Generate random shift
            rand_x = random.uniform(self.min_x + w/2, self.max_x - w/2)
            rand_y = random.uniform(self.min_y + h/2, self.max_y - h/2)
            
            # 2. Translate all items in cluster
            # First center them to 0, then move to rand
            # (Assuming input geoms are roughly near 0,0)
            shift_x = rand_x - (minx + w/2)
            shift_y = rand_y - (miny + h/2)
            
            candidates = [affinity.translate(g, shift_x, shift_y) for g in geoms]
            candidate_union = unary_union(candidates)
            
            # 3. Check Collision
            # We buffer occupied zone slightly to ensure visual separation
            is_collision = False
            if self.occupied_geom is not None:
                # Check intersection
                if self.occupied_geom.intersects(candidate_union):
                    is_collision = True
            
            if not is_collision:
                # 4. Success! Commit.
                ids = []
                for i, g in enumerate(candidates):
                    t = types[i]
                    cid = self.counters[t]
                    if t == 'Polygon': label = f"P{cid}"
                    elif t == 'Line': label = f"L{cid}"
                    elif t == 'Point': label = f"Pt{cid}"
                    
                    self.items.append({'type': t, 'id': label, 'geom': g})
                    ids.append([t, label])
                    self.counters[t] += 1
                
                # Update Occupied Zone
                if self.occupied_geom is None:
                    self.occupied_geom = candidate_union
                else:
                    self.occupied_geom = unary_union([self.occupied_geom, candidate_union])
                
                return ids # Return the IDs generated for this cluster
        
        print("Warning: Could not place object after max attempts.")
        return None

    def add_contained_item(self, container_id, item_type):
        """
        Adds a point/line STRICTLY inside an existing polygon.
        Ensures it does not touch the border.
        """
        container = next((x for x in self.items if x['id'] == container_id), None)
        if not container: return None
        poly = container['geom']
        
        minx, miny, maxx, maxy = poly.bounds
        
        # Buffer distance to ensure we aren't on the edge
        # 0.2 units is usually safe for visual distinction in a 100x100 canvas
        BORDER_BUFFER = 1
        
        for _ in range(50):
            if item_type == 'Point':
                p = Point(random.uniform(minx, maxx), random.uniform(miny, maxy))
                
                # STRICT CHECK:
                # 1. Must be contained (mathematically inside)
                # 2. Distance to boundary must be > buffer
                if poly.contains(p) and poly.boundary.distance(p) > BORDER_BUFFER:
                    cid = self.counters['Point']
                    lbl = f"Pt{cid}"
                    self.items.append({'type': 'Point', 'id': lbl, 'geom': p})
                    self.counters['Point'] += 1
                    return [['Point', lbl], ['Polygon', container_id], 'within']
            
            elif item_type == 'Line':
                # Generate a smaller curly line for inside
                l_len = random.uniform(3, 8) # Keep lines small relative to poly size (radius ~8)
                l = make_random_line_geom(length=l_len, num_segments=4)
                l = affinity.rotate(l, random.uniform(0, 360), origin=(0,0))
                
                rand_x = random.uniform(minx, maxx)
                rand_y = random.uniform(miny, maxy)
                l = affinity.translate(l, rand_x, rand_y)
                
                # STRICT CHECK for Line:
                # 1. Must be contained
                # 2. Distance from line to polygon boundary must be > buffer
                if poly.contains(l) and poly.boundary.distance(l) > BORDER_BUFFER:
                    cid = self.counters['Line']
                    lbl = f"L{cid}"
                    self.items.append({'type': 'Line', 'id': lbl, 'geom': l})
                    self.counters['Line'] += 1
                    return [['Line', lbl], ['Polygon', container_id], 'within']
                    
        return None

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

# ==========================================
# 3. MAIN EXECUTION
# ==========================================

if __name__ == '__main__':
    # CONFIGURATION
    CANVAS_BOUNDS = (0, 0, 100, 100)
    
    # ---------------- USER INPUTS ---------------- 
    # Polygonal mainly
    NUM_CONTAINED_PAIRS = 0     # Uses 2 polys
    NUM_OVERLAPPING_PAIRS = 0   # Uses 2 polys
    NUM_BORDERING_PAIRS = 1     # Uses 2 polys
    NUM_TOUCHING_PAIRS = 1      # Uses 2 polys
    NUM_LINES_CROSSING = 0      # Uses 1 poly
    NUM_POINTS_ON_BORDER = 1    # Uses 1 poly
    
    # Point line within
    NUM_POINTS_CONTAINED = 4
    NUM_LINES_CONTAINED = 1
    
    # Free Objects (Disjoint)
    NUM_LINES_FREE = 1
    NUM_POINTS_FREE = 3

    # Calculated from relationship
    NUM_POLYGONS_TOTAL = (2*(NUM_CONTAINED_PAIRS + NUM_OVERLAPPING_PAIRS + NUM_TOUCHING_PAIRS + NUM_BORDERING_PAIRS)) + (NUM_LINES_CROSSING + NUM_POINTS_ON_BORDER)
    # ---------------------------------------------

    # Initialize Manager
    pm = PlacementManager(CANVAS_BOUNDS)
    all_relationships = []

    # --- PHASE 1: Place Mandatory Polygon Clusters ---
    
    # 1. Contained Pairs (Polygon inside Polygon)
    for _ in range(NUM_CONTAINED_PAIRS):
        geoms = make_contained_pair()
        ids = pm.place_object(geoms, ['Polygon', 'Polygon'])
        if ids:
            # ids[0] is Outer, ids[1] is Inner
            all_relationships.append([ids[1], ids[0], 'within'])

    # 2. Overlapping Pairs (Strictly Partial)
    for _ in range(NUM_OVERLAPPING_PAIRS):
        geoms = make_overlapping_pair()
        ids = pm.place_object(geoms, ['Polygon', 'Polygon'])
        if ids:
            all_relationships.append([ids[0], ids[1], 'overlaps'])
            all_relationships.append([ids[1], ids[0], 'overlaps']) # Symmetry

    for _ in range(NUM_BORDERING_PAIRS):
        geoms = make_bordering_pair()
        ids = pm.place_object(geoms, ['Polygon', 'Polygon'])
        if ids:
            all_relationships.append([ids[0], ids[1], 'borders'])
            all_relationships.append([ids[1], ids[0], 'borders'])

    for _ in range(NUM_TOUCHING_PAIRS):
        geoms = make_touching_pair()
        ids = pm.place_object(geoms, ['Polygon', 'Polygon'])
        if ids:
            all_relationships.append([ids[0], ids[1], 'borders'])
            all_relationships.append([ids[1], ids[0], 'borders'])

    # 2. Line Crossing Polygon
    for _ in range(NUM_LINES_CROSSING):
        geoms = make_crossing_pair() # [Poly, Line]
        ids = pm.place_object(geoms, ['Polygon', 'Line'])
        if ids:
            all_relationships.append([ids[1], ids[0], 'crosses'])

    # 3. Point on Border
    for _ in range(NUM_POINTS_ON_BORDER):
        geoms = make_border_point_pair() # [Poly, Point]
        ids = pm.place_object(geoms, ['Polygon', 'Point'])
        if ids:
            all_relationships.append([ids[1], ids[0], 'touches'])

    # 4. Touching Polygons
    for _ in range(NUM_TOUCHING_PAIRS):
        geoms = make_touching_pair()
        ids = pm.place_object(geoms, ['Polygon', 'Polygon'])
        if ids:
            all_relationships.append([ids[0], ids[1], 'touches'])

    # --- PHASE 2: Fill Remaining Polygons (Disjoint) ---
    
    current_poly_count = pm.counters['Polygon']
    needed = NUM_POLYGONS_TOTAL - current_poly_count
    
    if needed < 0:
        print(f"Warning: Configuration required {current_poly_count} polygons, but total set to {NUM_POLYGONS_TOTAL}. Some may be missing.")
    
    for _ in range(needed):
        p = make_random_polygon()
        pm.place_object([p], ['Polygon'])
        # No relationship added (implicitly disjoint)

    # --- PHASE 3: Dependent Objects (Points/Lines INSIDE existing) ---
    
    # Get all placed polygon IDs
    poly_ids = [x['id'] for x in pm.items if x['type'] == 'Polygon']
    
    if poly_ids:
        # Points Inside
        for _ in range(NUM_POINTS_CONTAINED):
            target = random.choice(poly_ids)
            rel = pm.add_contained_item(target, 'Point')
            if rel: all_relationships.append(rel)
            
        # Lines Inside
        for _ in range(NUM_LINES_CONTAINED):
            target = random.choice(poly_ids)
            rel = pm.add_contained_item(target, 'Line')
            if rel: all_relationships.append(rel)
            
    # --- PHASE 4: Free Objects (Strictly Disjoint) ---
    
    # Free Lines
    for _ in range(NUM_LINES_FREE):
        l = LineString([(0,0), (random.uniform(10,30), random.uniform(5,15))]) # random jagged line
        ids = pm.place_object([l], ['Line'])
        # No relationship
        
    # Free Points
    for _ in range(NUM_POINTS_FREE):
        p = Point(0,0)
        ids = pm.place_object([p], ['Point'])
        # No relationship

    # ==========================================
    # 4. OUTPUT & SAVING
    # ==========================================
    
    print(f"Generated {len(pm.items)} objects.")
    
    # Plotting
    fig, ax = plt.subplots(figsize=(10, 10))
    ax.set_xlim(*CANVAS_BOUNDS[0::2])
    ax.set_ylim(*CANVAS_BOUNDS[1::2])
    
    texts = []
    obstacles = []
    
    # Sort for consistent rendering order
    pm.items.sort(key=lambda x: (x['type'], x['id']))
    
    for item in pm.items:
        g = item['geom']
        tid = item['id']
        t = item['type']
        
        if t == 'Polygon':
            x, y = g.exterior.xy
            ax.fill(x, y, alpha=0.5, fc=np.random.rand(3,), ec='black')
            # Label
            cx, cy = g.centroid.x, g.centroid.y
            txt = ax.text(cx, cy, tid, color='white', ha='center', va='center', fontweight='bold')
            txt.set_path_effects([PathEffects.withStroke(linewidth=2, foreground='black')])
            texts.append(txt)
            
        elif t == 'Line':
            x, y = g.xy
            ax.plot(x, y, color='blue', linestyle='--', linewidth=2)
            # Label
            mx, my = g.interpolate(0.5, normalized=True).xy
            txt = ax.text(mx[0], my[0], tid, color='blue', fontweight='bold')
            txt.set_path_effects([PathEffects.withStroke(linewidth=2, foreground='white')])
            texts.append(txt)
            
        elif t == 'Point':
            ax.scatter([g.x], [g.y], color='black', zorder=10)
            obstacles.append(ax.collections[-1])
            txt = ax.text(g.x, g.y, tid, color='black', fontsize=9, ha='right')
            txt.set_path_effects([PathEffects.withStroke(linewidth=2, foreground='white')])
            texts.append(txt)

    adjust_text(texts, ax=ax, add_objects=obstacles)
    plt.savefig('disjoint_layout.png')
    print("Saved plot to disjoint_layout.png")
    
    # DB Save (Reuse your previous connection logic)
    # DB_CONFIG = { "dbname": "postgres", "user": "postgres", "password": "your_password", "host": "localhost", "port": "5432" }
    DB_CONFIG = {
        "dbname": "postgres",
        "user": "postgres",
        "password": "jiYOON7162@",
        "host": "localhost",
        "port": "5432"
    }

    def save_to_db():
        try:
            conn = psycopg2.connect(**DB_CONFIG)
            cur = conn.cursor()
            cur.execute("DROP TABLE IF EXISTS generated_geometries;")
            cur.execute("""
                CREATE TABLE generated_geometries (
                    id VARCHAR(20) PRIMARY KEY, 
                    geom GEOMETRY(GEOMETRY, 0),
                    geom_type VARCHAR(20), 
                    label_x DOUBLE PRECISION,
                    label_y DOUBLE PRECISION
                );
            """)
            
            # Map text positions
            pos_map = {t.get_text(): t.get_position() for t in texts}
            
            for item in pm.items:
                tid = item['id']
                lx, ly = pos_map.get(tid, (0,0))
                # Explicit float cast for safety
                lx, ly = float(lx), float(ly)
                
                cur.execute(
                    "INSERT INTO generated_geometries (id, geom, geom_type, label_x, label_y) VALUES (%s, ST_GeomFromText(%s, 0), %s, %s, %s)",
                    (tid, item['geom'].wkt, item['type'], lx, ly)
                )
            conn.commit()
            conn.close()
            print("Saved to DB.")
        except Exception as e:
            print(f"DB Error: {e}")

    save_to_db()

    location_list = get_relative_location(DB_CONFIG)
    all_relationships = merge_relationships(all_relationships, location_list)
    
    # Save JSON
    with open('relationship.json', 'w') as f:
        json.dump({"relationships": all_relationships}, f, indent=4)