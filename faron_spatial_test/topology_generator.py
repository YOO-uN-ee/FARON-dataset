import matplotlib.pyplot as plt
from matplotlib.patches import PathPatch, Rectangle
from matplotlib.path import Path
from shapely.geometry import box
from shapely import affinity
import numpy as np
import random
import io
from PIL import Image

class TopologicalExperiment:
    def __init__(self):
        # Colors for the shapes (R, G, B, Alpha)
        self.color_a = (1, 0, 0, 0.6) # Red
        self.color_b = (0, 0, 1, 0.6) # Blue

    def shapely_to_patch(self, geom, color, label):
        """Converts a Shapely geometry to a Matplotlib patch."""
        path = Path.make_compound_path(
            Path(np.asarray(geom.exterior.coords)[:, :2]),
            *[Path(np.asarray(ring.coords)[:, :2]) for ring in geom.interiors])
        return PathPatch(path, facecolor=color, edgecolor='black', linewidth=1, label=label)

    def get_relationship_label(self, shape_a, shape_b):
        """Determines the RCC-8 topological relationship."""
        intersection = shape_a.intersection(shape_b)
        
        if shape_a.equals(shape_b): return "EQ"
        if intersection.is_empty:
            if shape_a.distance(shape_b) > 1e-9: return "DC"
            else: return "EC"
        
        if shape_a.contains(shape_b):
            if shape_a.boundary.intersects(shape_b.boundary): return "TPP-i"
            return "NTPP-i"
            
        if shape_b.contains(shape_a):
            if shape_b.boundary.intersects(shape_a.boundary): return "TPP"
            return "NTPP"

        if intersection.area > 0 and not shape_a.contains(shape_b) and not shape_b.contains(shape_a):
            return "PO"
            
        if shape_a.touches(shape_b): return "EC"

        return "Unknown"

    def generate_sample(self, relation_type):
        """Generates a pair of shapes (A and B) satisfying the relationship."""
        base_size = random.uniform(2, 4)
        shape_a = box(0, 0, base_size, base_size)
        shape_b = None
        
        if relation_type == "DC":
            offset = base_size + random.uniform(1, 3)
            shape_b = affinity.translate(shape_a, xoff=offset, yoff=offset)
        elif relation_type == "EC":
            b_width = random.uniform(1, 3)
            shape_b = box(base_size, 0, base_size + b_width, base_size)
            shape_b = affinity.translate(shape_b, yoff=random.uniform(-0.5, 0.5))
        elif relation_type == "PO":
            offset = base_size * 0.5
            shape_b = affinity.translate(shape_a, xoff=offset, yoff=offset)
            shape_b = affinity.scale(shape_b, xfact=0.8, yfact=0.8)
        elif relation_type == "NTPP": # A inside B
            shape_b = affinity.scale(shape_a, xfact=2.5, yfact=2.5, origin='center')
        elif relation_type == "TPP": # A inside B touching
             shape_b = box(0, 0, base_size * 2, base_size * 2)
        elif relation_type == "EQ":
            shape_b = shape_a

        # Random rotation (skip for delicate touch relations to preserve precision)
        if relation_type not in ["EC", "TPP", "TPP-i"]: 
            angle = random.uniform(0, 360)
            shape_a = affinity.rotate(shape_a, angle, origin='center')
            shape_b = affinity.rotate(shape_b, angle, origin='center')

        return shape_a, shape_b

    def render_to_pil(self, shape_a, shape_b, visual_cues=False):
        """
        Renders the shapes to a PIL Image.
        visual_cues=True enables Condition C (Bounding Boxes/Overlays).
        """
        fig, ax = plt.subplots(figsize=(5, 5))
        
        # Plot Shapes
        ax.add_patch(self.shapely_to_patch(shape_a, self.color_a, "Object A"))
        ax.add_patch(self.shapely_to_patch(shape_b, self.color_b, "Object B"))
        
        # Condition C: Visual Cues (Dashed Bounding Boxes)
        if visual_cues:
            # Draw Box for A
            minx, miny, maxx, maxy = shape_a.bounds
            rect_a = Rectangle((minx, miny), maxx-minx, maxy-miny, 
                             linewidth=2, edgecolor='red', facecolor='none', linestyle='--')
            ax.add_patch(rect_a)
            
            # Draw Box for B
            minx, miny, maxx, maxy = shape_b.bounds
            rect_b = Rectangle((minx, miny), maxx-minx, maxy-miny, 
                             linewidth=2, edgecolor='blue', facecolor='none', linestyle='--')
            ax.add_patch(rect_b)

        # Set Limits
        total_bounds = shape_a.union(shape_b).bounds
        margin = 2
        ax.set_xlim(total_bounds[0] - margin, total_bounds[2] + margin)
        ax.set_ylim(total_bounds[1] - margin, total_bounds[3] + margin)
        ax.set_aspect('equal')
        ax.axis('off') # Hide axes for the AI to focus on shapes

        # Convert to PIL
        buf = io.BytesIO()
        plt.savefig(buf, format='png', bbox_inches='tight', pad_inches=0)
        plt.close(fig)
        buf.seek(0)
        return Image.open(buf).convert("RGB")