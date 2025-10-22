from typing import List, Union, Tuple, Dict
from shapely import affinity
from shapely.geometry import Point, Line, Polygon

def topo_pairs(polygons: List[Union[Point, Line, Polygon]],
               relation:str,
               grp_details:int) -> List[Union[Point, Line, Polygon]]:
    
    if relation == 'touch':
        return 0
    
    elif relation == 'border':
        return 0

    elif relation == 'overlap':
        return 0
    
    elif relation == 'within':
        return 0
    return 0

def create_touching_pairs(polygons, num_pairs):
    """
    Args:
        polygons (list): 
        num_pairs (int):
    """

    return 0

def create_bordering_pairs(polygons: List[tuple]):
    """
    Move & rotate polygons so that polgyons share a boundary line.
    Shared region is always a line

    Args:
        polygons (list): 

    Return:
        polygons (list):
    """
    if not polygons:
        return polygons

    MAX_ATTEMPTS_PER_PAIR = 20

    for t in polygons:
        pair_bordering = False

        for _ in range(MAX_ATTEMPTS_PER_PAIR):
            poly_a = t[0]
            poly_b = t[1]
            
        return 0

    return 0

def create_overlapping_pairs(polygons, num_pairs):
    """
    Args:
        polygons (list): 
        num_pairs (int):
    """

    return 0

def create_within_pairs(polygons, num_pairs):
    """
    Args:
        polygons (list): 
        num_pairs (int):
    """

    return 0

def create_crossing_pairs(polygons, num_pairs):
    """
    Args:
        polygons (list): 
        num_pairs (int):
    """

    return 0