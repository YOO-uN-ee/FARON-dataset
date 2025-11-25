import matplotlib.pyplot as plt
from matplotlib.patches import PathPatch, Rectangle
from matplotlib.path import Path
from shapely.geometry import box, Polygon
from shapely import affinity
import numpy as np
import random
import io
from PIL import Image

class TopologicalExperiment:
    def __init__(self):
        self.color_a = (1, 0, 0, 0.6) # Red
        self.color_b = (0, 0, 1, 0.6) # Blue
        self.color_c = (1, 1, 0, 0.6) # Yellow 

    def shapely_to_patch(self, geom, color, label):
        path = Path.make_compound_path(
            Path(np.asarray(geom.exterior.coords)[:, :2]),
            *[Path(np.asarray(ring.coords)[:, :2]) for ring in geom.interiors])
        return PathPatch(path, facecolor=color, edgecolor='black', linewidth=1, label=label)

    def get_relationship_label(self, shape_a, shape_b):
        intersection = shape_a.intersection(shape_b)
        
        if shape_a.equals(shape_b): return "EQ"
        if intersection.is_empty:
            if shape_a.distance(shape_b) > 1e-9: return "DC"
            else: return "EC"
        
        if shape_a.contains(shape_b):
            if shape_a.boundary.intersects(shape_b.boundary): return "TPPi"
            return "nTPPi"
            
        if shape_b.contains(shape_a):
            if shape_b.boundary.intersects(shape_a.boundary): return "TPP"
            return "nTPP"

        if intersection.area > 0 and not shape_a.contains(shape_b) and not shape_b.contains(shape_a):
            return "PO"
            
        if shape_a.touches(shape_b): return "EC"

        return "Unknown"

    def generate_random_polygon(self, center=(0,0), scale=1.0):
        num_vertices = random.randint(3, 8)
        angles = sorted([random.uniform(0, 2 * np.pi) for _ in range(num_vertices)])
        
        points = []
        for angle in angles:
            r = scale * random.uniform(0.8, 1.2)
            x = center[0] + r * np.cos(angle)
            y = center[1] + r * np.sin(angle)
            points.append((x, y))
            
        return Polygon(points)

    def generate_confounder(self, shape_a, shape_b):
        minx, miny, maxx, maxy = shape_a.bounds
        base_size = (maxx - minx)
        shape_c = self.generate_random_polygon(scale=base_size)

        total_bounds = shape_a.union(shape_b).bounds
        center_x = (total_bounds[0] + total_bounds[2]) / 2
        center_y = (total_bounds[1] + total_bounds[3]) / 2
        
        max_attempts = 50
        for _ in range(max_attempts):
            angle = random.uniform(0, 2 * np.pi)
            distance = random.uniform(base_size * 1.5, base_size * 4.0)
            
            dx = center_x + distance * np.cos(angle)
            dy = center_y + distance * np.sin(angle)
            
            candidate = affinity.translate(shape_c, xoff=dx, yoff=dy)
            
            if not candidate.intersects(shape_a) and not candidate.intersects(shape_b):
                return candidate
                
        return affinity.translate(shape_c, xoff=base_size*10, yoff=base_size*10)


    def generate_sample(self, relation_type):
        base_scale = random.uniform(1.5, 2.5)
        shape_a = self.generate_random_polygon(center=(0,0), scale=base_scale)
        shape_b = None
        
        if relation_type == "DC":
            shape_b = self.generate_random_polygon(scale=base_scale)
            offset = base_scale * 3.5
            shape_b = affinity.translate(shape_b, xoff=offset, yoff=offset)
            
        elif relation_type == "EC":
            coords = list(shape_a.exterior.coords)
            rightmost_pt = max(coords, key=lambda p: p[0])         
            shape_b = affinity.scale(shape_a, xfact=-1, origin=rightmost_pt)        
            shape_b = affinity.scale(shape_b, xfact=random.uniform(0.8, 1.2), yfact=random.uniform(0.8, 1.2), origin=rightmost_pt)

        elif relation_type == "PO":
            shape_b = self.generate_random_polygon(scale=base_scale)
            shift = base_scale * 0.8
            shape_b = affinity.translate(shape_b, xoff=shift, yoff=shift)
            
        elif relation_type == "nTPP": 
            shape_b = affinity.scale(shape_a, xfact=3.0, yfact=3.0, origin='center')
            candidate_b = affinity.rotate(shape_b, random.uniform(0, 360), origin='center')

            if candidate_b.contains(shape_a) and not candidate_b.touches(shape_a):
                shape_b = candidate_b
            else:
                shape_b = affinity.scale(shape_a, xfact=3.2, yfact=2.8, origin='center')

            
        elif relation_type == "TPP": 
            shape_b = affinity.scale(shape_a, xfact=2.0, yfact=2.0, origin='center')
            
            pt_a = shape_a.exterior.coords[0]
            pt_b = shape_b.exterior.coords[0]
            
            dx = pt_a[0] - pt_b[0]
            dy = pt_a[1] - pt_b[1]
            shape_b = affinity.translate(shape_b, xoff=dx, yoff=dy)
            
        elif relation_type == "EQ":
            shape_b = shape_a

        if relation_type not in ["EC", "TPP", "TPPi, nTTP"]: 
            angle = random.uniform(0, 360)
            shape_a = affinity.rotate(shape_a, angle, origin='center')
            shape_b = affinity.rotate(shape_b, angle, origin='center')

        return shape_a, shape_b

    def render_to_pil(self, shape_a, shape_b, shape_c=None, visual_cues=False, figure_name='output_figure.png'):
        fig, ax = plt.subplots(figsize=(5, 5))
        
        ax.add_patch(self.shapely_to_patch(shape_a, self.color_a, "Object A"))
        ax.add_patch(self.shapely_to_patch(shape_b, self.color_b, "Object B"))

        if shape_c:
            ax.add_patch(self.shapely_to_patch(shape_c, self.color_c, "Object C"))
        
        if visual_cues:
            minx, miny, maxx, maxy = shape_a.bounds
            rect_a = Rectangle((minx, miny), maxx-minx, maxy-miny, 
                             linewidth=2, edgecolor='red', facecolor='none', linestyle='--')
            ax.add_patch(rect_a)
            
            minx, miny, maxx, maxy = shape_b.bounds
            rect_b = Rectangle((minx, miny), maxx-minx, maxy-miny, 
                             linewidth=2, edgecolor='blue', facecolor='none', linestyle='--')
            ax.add_patch(rect_b)

        combined_obj = shape_a.union(shape_b)

        if shape_c:
            combined_obj = combined_obj.union(shape_c)

        total_bounds = combined_obj.bounds   
        margin = 2
        ax.set_xlim(total_bounds[0] - margin, total_bounds[2] + margin)
        ax.set_ylim(total_bounds[1] - margin, total_bounds[3] + margin)
        ax.set_aspect('equal')
        ax.axis('off')

        buf = io.BytesIO()
        plt.savefig(buf, format='png', bbox_inches='tight', pad_inches=0)
        plt.close(fig)
        buf.seek(0)

        img = Image.open(buf).convert("RGB")
        img.save(figure_name)

        return figure_name