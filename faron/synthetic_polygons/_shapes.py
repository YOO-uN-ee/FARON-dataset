from Typing import List, Dict, Tuple

from shapely.geometry import Point, Line, Polygon, box

def generate_random_polygons(canvas_bounds:Tuple[int],
                             num_polygons:int,
                             min_vertices:int, max_vertices:int,
                             min_radius:int, max_radius:int,
                             is_regular:bool=False) -> List[Polygon]:
    """
    Args:
        canvas_bounds (tuple):
        is_regular (bool):

    Returns:
        list: A list of Shapely Polygon objects
    """
    return 0

def generate_random_lines(canvas_bounds:Tuple[int],
                          num_lines:int,
                          min_length:int, max_length:int,
                          is_regular:bool=False) -> List[Line]:
    """
    Args:
        canvas_bounds (tuple):
        is_regular (bool):

    Returns:
        list: A list of Shapely Line objects
    """
    return 0

def generate_random_points(canvas_bounds:Tuple[int],
                           num_points:int,
                           min_radius:int, max_radius:int,) -> List[Point]:
    """
    Args:
        canvas_bounds (tuple):
        is_regular (bool):

    Returns:
        list: A list of Shapely Point objects
    """
    return 0