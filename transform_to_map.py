# import geopandas as gpd
# import pandas as pd
# from shapely import wkb
# from shapely.geometry import Polygon, LineString, Point, box
# import matplotlib.pyplot as plt
# import matplotlib.patches as mpatches

# # --- 1. Load Data (Simulating your WKB input) ---
# # In your real code, you would load this from Postgres using:
# # df = pd.read_sql("SELECT id, geom_type, ST_AsBinary(geom) as wkb_geom FROM ...", conn)

# # Simulating the geometries from your image for demonstration
# data = [
#     {'id': 1, 'wkb': Point(20, 20).wkb, 'type': 'Point'},
#     {'id': 2, 'wkb': Point(30, 10).wkb, 'type': 'Point'},
#     {'id': 3, 'wkb': Point(80, 80).wkb, 'type': 'Point'},
#     {'id': 4, 'wkb': Polygon([(15, 50), (18, 55), (22, 52), (20, 48)]).wkb, 'type': 'Polygon'}, # Small poly
#     {'id': 5, 'wkb': Polygon([(15, 30), (18, 28), (25, 25), (30, 28), (28, 45)]).wkb, 'type': 'Polygon'}, # Med poly
#     {'id': 6, 'wkb': Polygon([(50, 50), (70, 70), (75, 65), (55, 45)]).wkb, 'type': 'Polygon'}, # Long poly
#     {'id': 7, 'wkb': LineString([(70, 90), (75, 88), (80, 90)]).wkb, 'type': 'LineString'}
# ]

# df = pd.DataFrame(data)
# # Convert WKB to Shapely objects
# df['geometry'] = df['wkb'].apply(lambda x: wkb.loads(bytes(x)))
# gdf = gpd.GeoDataFrame(df, geometry='geometry')

# # --- 2. Classification Logic ---
# # We define heuristics to decide what each random shape "is" in the real world.

# def classify_feature(row):
#     geom = row.geometry
    
#     if geom.geom_type == 'Point':
#         return 'tree'
    
#     elif geom.geom_type == 'LineString':
#         return 'path'
        
#     elif geom.geom_type == 'Polygon':
#         area = geom.area
#         # Heuristic: Small polygons are buildings, large are parks/lakes
#         if area < 20: 
#             return 'building'
#         elif area < 100:
#             return 'water' # Let's pretend medium shapes are ponds
#         else:
#             return 'park'
            
#     return 'unknown'

# gdf['feature_type'] = gdf.apply(classify_feature, axis=1)

# # --- 3. Morphology (Making them look the part) ---
# # Buildings should be square. Lakes should be smooth.

# def morph_geometry(row):
#     geom = row.geometry
#     f_type = row['feature_type']
    
#     if f_type == 'building':
#         # buildings in maps usually have hard, orthogonal edges.
#         # We replace the random blob with its "minimum rotated rectangle"
#         return geom.minimum_rotated_rectangle
    
#     elif f_type == 'water' or f_type == 'park':
#         # Natural features are usually smooth.
#         # We assume the random polygons are jagged, so we smooth them.
#         # Buffer(2) then Buffer(-2) is a cheap smoothing trick.
#         return geom.buffer(3, join_style=1).buffer(-3, join_style=1)
        
#     elif f_type == 'path':
#         # Lines in maps need thickness to be roads/paths
#         return geom.buffer(0.5)
        
#     return geom

# gdf['styled_geometry'] = gdf.apply(morph_geometry, axis=1)
# styled_gdf = gpd.GeoDataFrame(gdf, geometry='styled_geometry')

# # --- 4. Visualization (Map Styling) ---

# # Define a "Map" color palette (OpenStreetMap style)
# styles = {
#     'building': {'color': '#d9d0c9', 'edgecolor': '#c2c2c2', 'label': 'Building'}, # Light Grey
#     'water':    {'color': '#aad3df', 'edgecolor': '#88bbee', 'label': 'Water'},    # Blue
#     'park':     {'color': '#cdebb0', 'edgecolor': '#aace90', 'label': 'Park'},     # Green
#     'tree':     {'color': '#6e8c5d', 'markersize': 40, 'label': 'Tree'},           # Dark Green
#     'path':     {'color': '#f7f4ea', 'edgecolor': '#dedede', 'label': 'Path'}      # Off-white path
# }

# fig, ax = plt.subplots(figsize=(10, 10))
# ax.set_facecolor('#f2f2f2') # Background color (Standard Map Land color)

# for f_type, style_data in styles.items():
#     subset = styled_gdf[styled_gdf['feature_type'] == f_type]
#     if subset.empty: continue
    
#     if f_type == 'tree': # Points need scatter
#         subset.plot(ax=ax, color=style_data['color'], markersize=style_data['markersize'], zorder=5)
#     else: # Polygons
#         subset.plot(ax=ax, 
#                     color=style_data['color'], 
#                     edgecolor=style_data.get('edgecolor', 'none'), 
#                     linewidth=1,
#                     zorder=2 if f_type == 'water' else 3) # Water below buildings

# # Remove axis ticks to look like a map
# ax.set_xticks([])
# ax.set_yticks([])

# # Create a custom legend
# patches = [mpatches.Patch(color=d['color'], label=d['label']) for k, d in styles.items()]
# plt.legend(handles=patches, loc='upper right')

# plt.title("Generated Map Representation")
# plt.savefig('./map_shapes.png')
# plt.show()

import matplotlib.pyplot as plt
import geopandas as gpd

def save_segmentation_mask(gdf, output_path="controlnet_input.png"):
    """
    Converts vector data into a semantic segmentation mask for ControlNet.
    Specific colors help the model distinguish classes (ADE20k palette is common).
    """
    fig, ax = plt.subplots(figsize=(5.12, 5.12)) # 512x512 is standard for SD v1.5
    
    # 1. Background (Land/Ground) - usually distinct from features
    ax.set_facecolor('#000000') # Black background
    
    # 2. Assign standard 'semantic' colors
    # These colors don't need to look good; they need to be distinct for the AI.
    color_map = {
        'building': '#FF0000', # Red
        'water':    '#0000FF', # Blue
        'park':     '#00FF00', # Green
        'path':     '#FFFFFF', # White
        'tree':     '#FFFF00'  # Yellow
    }

    # Plot each category
    for feature_type, color in color_map.items():
        subset = gdf[gdf['feature_type'] == feature_type]
        if not subset.empty:
            if feature_type == 'tree':
                subset.plot(ax=ax, color=color, markersize=20)
            elif feature_type == 'path':
                subset.plot(ax=ax, color=color, linewidth=2)
            else:
                subset.plot(ax=ax, color=color, edgecolor='none')

    # 3. Clean up (Remove all axes, ticks, borders)
    ax.set_axis_off()
    plt.subplots_adjust(top=1, bottom=0, right=1, left=0, hspace=0, wspace=0)
    plt.margins(0,0)
    
    # Save exact raw pixels
    plt.savefig(output_path, dpi=100, pad_inches=0)
    plt.close()
    print(f"Mask saved to {output_path}")

# Run this on your existing GDF
# save_segmentation_mask(styled_gdf)