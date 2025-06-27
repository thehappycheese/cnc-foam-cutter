from typing import Callable
import numpy as np
from scipy.interpolate import make_splprep

from airfoil.util.array_helpers import (
    remove_sequential_duplicates,
    sliding_window,
    split_indexable
)

def is_ccw(points:np.ndarray)->bool:
    """same as shapely's function but works on numpy coordinates in shape (n,2)
    
    This assumes the same kind of coordinate system as shapely, where positive x points to the right, and y points up.
    """
    x,y=points.transpose()
    return np.array(np.dot(x, np.roll(y, 1)) - np.dot(y, np.roll(x, 1))) < 0

def ensure_closed(values:np.ndarray):
    if np.equal(values[0],values[-1]).all():
        return values
    else:
        return np.concat([values,[values[0]]])



def split_linestring_by_angle(arr:np.ndarray, split_angle_deg:float=70)->list[np.ndarray]:
    arr_length, arr_dimentions = arr.shape
    assert arr_length>1
    assert arr_dimentions ==2

    return split_indexable(
        arr,
        np.where(
            deflection_angle(arr)>np.deg2rad(split_angle_deg)
        )[0]+1
    )

    # angles = []
    # lengths = []
    # for [a,b,c] in sliding_window(arr, 3):
    #     ba = (a-b)/np.linalg.norm(a-b)
    #     cb = (b-c)/np.linalg.norm(b-c)
    #     lengths.append(np.linalg.norm(a-b))
    #     angles.append(np.acos(np.dot(ba, cb)))

    # chunks = split_indexable(
    #     arr,
    #     np.where(abs(np.array(angles))>np.deg2rad(split_angle_deg))[0]+1
    # )
    # return chunks

def resample_long_segments(arr: np.ndarray, desired_length: float) -> np.ndarray:
    """
    Subdivide segments longer than max_length threshold.
    Original Points are undisturrbed so this keeps the exact original shape.
    """
    n, d = arr.shape
    assert n > 1, "Need at least 2 points"
    
    result = [arr[0]]
    
    for i in range(1, n):
        seg_vec = arr[i] - arr[i-1]
        seg_len = np.linalg.norm(seg_vec)
        
        if seg_len > desired_length:
            n_divs = int(np.ceil(seg_len / desired_length))
            for j in range(1, n_divs):
                t = j / n_divs
                result.append(arr[i-1] + t * seg_vec)
        
        result.append(arr[i])
    
    return np.array(result)

def resample_spline_fallback_linear(
        chunk:np.ndarray,
        number_of_points_from_total_distance:Callable[[float], int],
    ) -> np.ndarray:
    
    
    if len(chunk)<=4:
        return resample_linear(chunk, number_of_points_from_total_distance)
    else:
        total_length = np.linalg.norm(np.diff(chunk,axis=0),axis=1).sum()
        new_segment_count = int(number_of_points_from_total_distance(total_length))
        try:
            bspline, u = make_splprep(np.asarray(chunk).transpose())
            u_new = np.linspace(0, 1, new_segment_count)
            return bspline(u_new).transpose()
        except Exception as e:
            print(f"Bspline failed with error for {chunk=} attempting linear resampling instead")
            print(e)
            return resample_linear(chunk, lambda _: new_segment_count)

def resample_linear(
        line:np.ndarray,
        number_of_points_from_total_distance:Callable[[float], int]
    ) -> np.ndarray:
    """line is a numpy array of shape (n,d) where n is the number of points and d is the number of dimentions. d must be >=2
    points_from_total_distance is a function that takes the total length of the line and returns the number of points to resample the linestring into.
    """
    line = np.asarray(line)
    assert line.shape[1]>=2, "line must be of dimention 2 or greater"

    # Calculate cumulative distances along the chunk
    segment_lengths = np.linalg.norm(line[1:] - line[:-1], axis=-1)
    distances = np.concatenate([[0], segment_lengths.cumsum()])

    total_distance = distances[-1]

    # Create new points at evenly spaced distances
    target_distances = np.linspace(0, total_distance, int(number_of_points_from_total_distance(total_distance)))
    interpolated_points = []

    base_index    = 0
    for target_distance in target_distances:
        while base_index<len(line)-1:
            next_distance = distances[base_index+1]
            if target_distance <= next_distance:
                base_distance = distances[base_index]
                t = (target_distance-base_distance)/(next_distance-base_distance)
                interpolated_points.append(line[base_index]+t*(line[base_index+1]-line[base_index]))
                break
            else:
                base_index+=1
        if base_index==len(line)-1:
            interpolated_points.append(line[-1])
            break
    return np.array(interpolated_points)

def resample_linear_to_number_of_segments(line:np.ndarray, desired_segments:int):
    return resample_linear(line, lambda _:desired_segments)

def resample_linear_to_segment_length(line:np.ndarray, desired_segment_length:float):
    return resample_linear(line, lambda total_distance:int(np.ceil(total_distance/desired_segment_length)))

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

def split_and_roll(
    linear_ring:np.ndarray,
    at_index:int,
) -> np.ndarray:
    return remove_sequential_duplicates(ensure_closed(
        np.roll(
            linear_ring,
            -at_index-1,
            axis=0
        )[::-1]
    ))

def split_and_roll_at_top_right(
        linear_ring:np.ndarray
    ) -> np.ndarray:
    linear_ring = np.asarray(linear_ring)
    return remove_sequential_duplicates(
        ensure_closed(
            split_and_roll(
                linear_ring,
                at_index=(linear_ring[:,0]+  linear_ring[:,1]).argmax() # top right
            )
        )
    )


def _make_segment_resampler_to_length(max_segment_length:float, core_resampler:Callable[[np.ndarray, Callable[[float],int]],np.ndarray]=resample_spline_fallback_linear) -> Callable[[list[np.ndarray]], list[np.ndarray]]:
    """set core_resampler=resample_linear to skip trying spline interpolation"""
    return lambda segments: [
        core_resampler(
            segment,
            lambda total_lenght: int(np.ceil(total_lenght/max_segment_length))
        )
        for segment
        in segments
    ]

def _make_segment_resampler_to_counts(counts:list[int], core_resampler:Callable[[np.ndarray, Callable[[float],int]],np.ndarray]=resample_spline_fallback_linear) -> Callable[[list[np.ndarray]], list[np.ndarray]]:
    """set core_resampler=resample_linear to skip trying spline interpolation"""
    return lambda segments: [
        core_resampler(
            segment,
            lambda _: count
        )
        for segment,count
        in zip(segments,counts)
    ]

def _first_point_index_selector_top_right(points:np.ndarray) -> int:
    return int(np.argmax(points[:,0]+points[:,1]))

def _resample_shape(
    shape:np.ndarray,
    segment_resampler:Callable[[list[np.ndarray]], list[np.ndarray]] = _make_segment_resampler_to_length(1.0),
    first_point_selector:Callable[[np.ndarray], int]                 = _first_point_index_selector_top_right,
    deflection_angle_split_deg:float=30,
):
    """
    use resample_shapes instead
    Resegments a shape
    `segment_resampler=make_segment_resampler_to_counts([len(seg) for seg in seg])` to make it so that the resulting shape has segment lengths matching some existing shape"""

    if not is_ccw(shape):
        shape = shape[::-1] # reversed

    # reset the starting position of the linestring
    shape = split_and_roll(shape, at_index=first_point_selector(shape))

    split_at_corners = split_indexable(
        shape,
        np.where(deflection_angle(shape)>np.deg2rad(deflection_angle_split_deg))[0]+1
    )

    resampled = segment_resampler(split_at_corners)

    result = remove_sequential_duplicates(ensure_closed(np.concat(resampled)))
    

    return result, [len(segment) for segment in resampled]

def resample_shapes(
    shapes:list[np.ndarray],
    target_length:float=1.0,
    first_point_selector:Callable[[np.ndarray], int]                        = _first_point_index_selector_top_right,
    deflection_angle_split_deg:float                                        = 30,
    core_resampler:Callable[[np.ndarray, Callable[[float],int]],np.ndarray] = resample_spline_fallback_linear,
):
    """
    Re-sample multiple shapes to have consistent segmentation on each 'side' of the shape.

    1. Initially splits up shapes into linestrings at 'corners' where the linestring turns by more than `deflection_angle_split_deg`
    1. LineStrings for the first `shapes` are resampled to meet the desired `target_length` segmentation
    1. LineStrings for all subsequent `shapes` are then resampled to match the count of the first shapes segmentation.
    1. Finally LineStrings for each `shapes` are stitched back together again and a list of the resegmented shapes are returned in the same order as the input shapes.

    ### Parameters
    
    - `shapes` List of closed 2D shapes as (N, 2) arrays, e.g. [airfoil1, airfoil2]
    - `target_length` Max segment length for first shape, e.g. 1.0
    - `first_point_selector` function that accepts a shape and returns an index to use as the new starting point for the shape outlines. The default fucntion chooses the upper-rightmost point.
    - `deflection_angle_split_deg` Corner split threshold in degrees, e.g. 30
    - `core_resampler` Interpolation method. The default is `resample_spline_fallback_linear` but you may wish to replace this with `resample_linear` if the default misbehaves and causes unexplected spliney shapes.

    ### Returns
    
    Resampled shapes with matching segment counts

    ### Examples
    
    ```python
    a=np.array([
        [0,0],
        [5,0],
        [5,10],
        [0,10]
    ])

    b=np.array([
        [0,0],
        [5,0],
        [10,10],
        [3,5]
    ])
    shape_a, shape_b = resample_shapes(
        [a,b],
        deflection_angle_split_deg=20
    )
    ```

    > note that in the example above `deflection_angle_split_deg` is adjusted from its default value
    > as there is a shallow angle in `b`
    """
    shape0, counts = _resample_shape(
        shapes[0],
        segment_resampler          = _make_segment_resampler_to_length(target_length, core_resampler=core_resampler),
        first_point_selector       = first_point_selector,
        deflection_angle_split_deg = deflection_angle_split_deg,
    )
    resampler = _make_segment_resampler_to_counts(counts, core_resampler=core_resampler)
    results = [shape0]
    for shape in shapes[1:]:
        result, each_counts = _resample_shape(
            shape,
            segment_resampler=resampler,
            deflection_angle_split_deg=deflection_angle_split_deg
        )
        assert all(a==b for a,b in zip(counts,each_counts)), "resampler failed to match counts of first shape??"
        results.append(result)
    return results
