import numpy as np
from shapely import Polygon

from airfoil.util.array_helpers import remove_sequential_duplicates, sliding_window, split_indexable


def ensure_closed(values:np.ndarray):
    if np.equal(values[0],values[1]).all():
        return values
    else:
        return np.concat([values,[values[0]]])
    
def split_linestring_by_angle(arr:np.ndarray, split_angle_deg:float=70)->list[np.ndarray]:
    arr_length, arr_dimentions = arr.shape
    assert arr_length>1
    assert arr_dimentions ==2
    angles = []
    lengths = []
    for [a,b,c] in sliding_window(arr, 3):
        ba = (a-b)/np.linalg.norm(a-b)
        cb = (b-c)/np.linalg.norm(b-c)
        lengths.append(np.linalg.norm(a-b))
        angles.append(np.acos(np.dot(ba, cb)))

    chunks = split_indexable(
        arr,
        np.where(abs(np.array(angles))>np.deg2rad(split_angle_deg))[0]+1
    )
    return chunks

def subdivide_by_length(arr: np.ndarray, max_length: float) -> np.ndarray:
    """Subdivide line segments longer than max_length threshold."""
    n, d = arr.shape
    assert n > 1, "Need at least 2 points"
    
    result = [arr[0]]
    
    for i in range(1, n):
        seg_vec = arr[i] - arr[i-1]
        seg_len = np.linalg.norm(seg_vec)
        
        if seg_len > max_length:
            n_divs = int(np.ceil(seg_len / max_length))
            for j in range(1, n_divs):
                t = j / n_divs
                result.append(arr[i-1] + t * seg_vec)
        
        result.append(arr[i])
    
    return np.array(result)


def linear_interpolation(chunk:np.ndarray, desired_segments:int):
    # Calculate cumulative distances along the chunk
    segment_lengths = np.linalg.norm(chunk[1:] - chunk[:-1], axis=-1)
    distances = np.concatenate([[0], segment_lengths.cumsum()])

    total_distance = distances[-1]

    # Create new points at evenly spaced distances
    target_distances = np.linspace(0, total_distance, desired_segments)
    interpolated_points = []

    base_index    = 0
    for target_distance in target_distances:
        while base_index<len(chunk)-1:
            next_distance = distances[base_index+1]
            if target_distance <= next_distance:
                base_distance = distances[base_index]
                t = (target_distance-base_distance)/(next_distance-base_distance)
                interpolated_points.append(chunk[base_index]+t*(chunk[base_index+1]-chunk[base_index]))
                break
            else:
                base_index+=1
        if base_index==len(chunk)-1:
                interpolated_points.append(chunk[-1])
                break
    return np.array(interpolated_points)


def linear_resampling_to_length(chunk:np.ndarray, desired_segment_length:float):

    segment_lengths = np.linalg.norm(chunk[1:] - chunk[:-1], axis=-1)
    distances = np.concatenate([[0], segment_lengths.cumsum()])

    total_distance = distances[-1]

    # Create new points at evenly spaced distances
    target_distances = np.linspace(0, total_distance, int(np.ceil(total_distance/desired_segment_length)))
    interpolated_points = []

    base_index    = 0
    for target_distance in target_distances:
        while base_index<len(chunk)-1:
            next_distance = distances[base_index+1]
            if target_distance <= next_distance:
                base_distance = distances[base_index]
                t = (target_distance-base_distance)/(next_distance-base_distance)
                interpolated_points.append(chunk[base_index]+t*(chunk[base_index+1]-chunk[base_index]))
                break
            else:
                base_index+=1
        if base_index==len(chunk)-1:
                interpolated_points.append(chunk[-1])
                break
    return np.array(interpolated_points)


def deflection_angle(path:np.ndarray):
    path = np.array(path)
    a, b, c = path[:-2], path[1:-1], path[2:]
    ab = b-a
    bc = c-b
    abdotbc = ab[:,0]*bc[:,0]+ab[:,1]*bc[:,1]
    items = abdotbc / (
        np.linalg.norm(ab, axis=-1)
        * np.linalg.norm(bc, axis=-1)
    )
    return np.acos(np.clip(items,-1,1))


def deflection_angle_padded(path:np.ndarray):
    return np.pad(
        deflection_angle(path),
        pad_width=(1, 1),
        mode='edge'
    )

# TODO: the at_index version of this function belongs to the array helpers.
def split_and_roll_at_top_right(
        polygon:Polygon,
        at_index:int|None=None,
        ensure_is_closed:bool=True
    ) -> np.ndarray:
    
    if at_index is None:
        lsb = np.array(polygon.boundary.coords)[:-1]
        top_right_point_index = (lsb[:,0]+lsb[:,1]).argmax()
    else:
        top_right_point_index = at_index
    lsb = np.roll(lsb,-top_right_point_index-1, axis=0)[::-1]
    if ensure_is_closed:
        lsb=ensure_closed(lsb)
    return remove_sequential_duplicates(lsb)
