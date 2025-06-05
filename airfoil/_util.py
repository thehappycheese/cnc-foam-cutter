import numpy as np
import pyvista as pv

from shapely.geometry.base import BaseGeometry

from ._itertools import split_indexable, sliding_window
import numpy as np

def create_ruled_surface(curve_a, curve_b, face_data=None):
    n_points = curve_a.shape[0]
    # Points are ordered: [curve_a[0], curve_b[0], curve_a[1], curve_b[1], ...]
    points = np.empty((2 * n_points, 3))
    points[0::2] = curve_a  # Even indices: curve A
    points[1::2] = curve_b  # Odd indices: curve B

    faces = []
    for i in range(n_points - 1):
        # Quad Points: curve_a[i], curve_b[i], curve_b[i+1], curve_a[i+1]
        p1 = 2 * i
        p2 = 2 * i + 1
        p3 = 2 * i + 3
        p4 = 2 * i + 2
        faces.extend([4, p1, p2, p3, p4])
    
    mesh = pv.PolyData(points, faces)
    
    # Add face data if provided
    if face_data is not None:
        # Ensure face_data has the correct length (number of quads)
        n_faces = n_points - 1
        if isinstance(face_data, (int, float)):
            # Single value - apply to all faces
            mesh.cell_data['face_values'] = np.full(n_faces, face_data)
        elif len(face_data) == n_faces:
            # Array of values - one per face
            mesh.cell_data['face_values'] = np.array(face_data)
        else:
            raise ValueError(f"face_data must be a single value or array of length {n_faces}")
    
    return mesh

def shapely_to_svg(shape:BaseGeometry)->str:
    
    return f"""<svg version="1.1" xmlns="http://www.w3.org/2000/svg" xmlns:xlink= "http://www.w3.org/1999/xlink">
    {shape.svg()}
    </svg>
    """

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

def remove_sequential_duplicates(arr):
    last = arr[0]
    result = [last]
    for item in arr[1:]:
        if not np.allclose(item, last):
            result.append(item)
            last = item
    return np.array(result)

def ensure_closed(values:np.ndarray):
    if np.equal(values[0],values[1]).all():
        return values
    else:
        return np.concat([values,[values[0]]])

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