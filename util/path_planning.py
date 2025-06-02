from typing import Literal
import numpy as np
from shapely import Polygon
from warnings import deprecated


def split_and_roll(polygon:Polygon)->np.ndarray:
    lsb = np.array(polygon.boundary.coords)[:-1]
    lsb = np.roll(lsb,-(lsb[:,0]+lsb[:,1]).argmax()-1, axis=0)[::-1]
    return lsb


def intro_path(coords:np.ndarray, padding:float = 10) -> np.ndarray:
    coords = np.roll(coords,-(coords[:,0]+coords[:,1]).argmax()-1, axis=0)[::-1]
    start = coords[0]
    bottom_left = coords.min(axis=0)
    top_right = coords.max(axis=0)
    width, height = top_right-bottom_left
    
    coords = np.vstack([
        [
            bottom_left - np.array([padding,padding]),
            bottom_left+np.array([-padding,height+padding]),
            top_right + np.array([padding,padding]),
            start + np.array([padding,0])
        ],
        coords,
        [
            coords[-1]+np.array([padding,0])
        ]
    ])
    coords = coords - coords.min(axis=0)
    return coords

@deprecated("Please use project_line_to_plane instead")
def project_line_to_z_plane(p1:np.ndarray, p2:np.ndarray, z_plane:float):
    """
    Project a line defined by two 3D points onto a plane with constant x coordinate.
    
    Args:
        p1: First point as (3,) numpy array [x, y, z]
        p2: Second point as (3,) numpy array [x, y, z]
        z_plane: Z coordinate of the plane (e.g., -100)
    
    Returns:
        tuple: (y, z) coordinates where the line intersects the plane
               Returns None if line is parallel to the plane
    """
    # Direction vector of the line
    direction = p2 - p1
    
    # Check if line is parallel to the plane (dx = 0)
    if abs(direction[2]) < 1e-10:
        # Line is parallel to plane - use orthogonal projection of midpoint
        midpoint = (p1 + p2) / 2
        return midpoint[0], midpoint[1]
    
    # Parameter t where line intersects the plane: p1 + t * direction
    t = (z_plane - p1[2]) / direction[2]
    
    # Calculate intersection point
    intersection = p1 + t * direction
    
    # Return y, z coordinates on the plane
    return intersection[0],intersection[1]


def project_line_to_plane(
        p1: np.ndarray,
        p2: np.ndarray,
        plane: Literal[
            'xy',
            'yx',
            'xz',
            'zx',
            'yz',
            'zy',
        ],
        plane_position: float = 0.0
    ):
    """
    Project a line defined by two 3D points onto a coordinate plane.
    
    The plane order determines the normal direction using cross product convention:
    - 'xy': normal = x × y = +z direction, plane at z = +plane_position
    - 'yx': normal = y × x = -z direction, plane at z = -plane_position
    - 'xz': normal = x × z = -y direction, plane at y = -plane_position
    - 'zx': normal = z × x = +y direction, plane at y = +plane_position
    - 'yz': normal = y × z = +x direction, plane at x = +plane_position
    - 'zy': normal = z × y = -x direction, plane at x = -plane_position
    
    Args:
        p1: First point as (3,) numpy array [x, y, z]
        p2: Second point as (3,) numpy array [x, y, z]
        plane: Plane specification using cross product convention
        plane_position: Distance from origin along the normal direction (default: 0.0)
    
    Returns:
        np.ndarray: 3D coordinates where the line intersects the plane
                   Returns None if line is parallel to the plane
    
    Raises:
        ValueError: If plane is not a valid option
    """
    # Define basis vectors
    x_axis = np.array([1, 0, 0])
    y_axis = np.array([0, 1, 0])
    z_axis = np.array([0, 0, 1])
    
    # Map plane strings to their cross product normals and signed positions
    plane_configs = {
        'xy': (np.cross(x_axis, y_axis), +plane_position),  # +z normal
        'yx': (np.cross(y_axis, x_axis), -plane_position),  # -z normal
        'xz': (np.cross(x_axis, z_axis), -plane_position),  # -y normal
        'zx': (np.cross(z_axis, x_axis), +plane_position),  # +y normal
        'yz': (np.cross(y_axis, z_axis), +plane_position),  # +x normal
        'zy': (np.cross(z_axis, y_axis), -plane_position),  # -x normal
    }
    if plane not in plane_configs:
        valid_planes = list(plane_configs.keys())
        raise ValueError(f"Plane must be one of {valid_planes}. Got: {plane}")
    
    normal, signed_position = plane_configs[plane]
    
    # Direction vector of the line
    line_direction = p2 - p1
    
    # Check if line is parallel to the plane
    denominator = line_direction @ normal #np.dot(line_direction, normal)
    if (np.abs(denominator) < 1e-10).any():
        # Line is parallel to plane - no unique intersection
        raise ValueError("One of the line sections was parallel  to the plane")
    
    # Calculate parameter t where line intersects the plane
    # Plane equation: dot(point, normal) = signed_position
    # Line equation: p1 + t * line_direction
    # Solve: dot(p1 + t * line_direction, normal) = signed_position
    numerator = signed_position - (p1 @ normal)
    t = numerator / denominator
    
    # Calculate intersection point in 3D space
    intersection = p1 + t[...,np.newaxis] * line_direction

    
    return intersection

def geometric_curvature(path:np.ndarray):
    p1, p2, p3 = path[:-2], path[1:-1], path[2:]
    
    # Vectors from p1 to p2 and p2 to p3
    v1 = p2 - p1
    v2 = p3 - p2
    
    # Cross product magnitude (2D: determinant)
    cross = v1[:, 0] * v2[:, 1] - v1[:, 1] * v2[:, 0]
    
    # Segment lengths
    len1 = np.linalg.norm(v1, axis=1)
    len2 = np.linalg.norm(v2, axis=1)
    
    # Curvature = |cross product| / (|v1| * |v2|)
    curvature = np.abs(cross) / (len1 * len2 + 1e-10)  # small epsilon to avoid division by zero
    
    # Pad to match original path length by repeating the last value
    padded_curvature = np.pad(curvature, (1, 1), mode='edge')
    
    return padded_curvature

def blur1d(values, count=31, std=6):
    from scipy import ndimage
    from scipy.signal.windows import gaussian
    blur_kernel = gaussian(31,6)
    blur_kernel /= blur_kernel.sum()
    return ndimage.convolve1d(values,blur_kernel)

def map_to_range(values:np.ndarray, min:float, max:float):
    target_range = max-min
    current_range = values.max()-values.min()
    return (values-values.min())/current_range*target_range+min

def remove_sequential_duplicates(values:np.ndarray):
    """values is assumed to be 2d"""
    return values[np.concatenate(([True],np.all(values[:-1]!= values[1:], axis=1)))]

def ensure_closed(values:np.ndarray):
    if np.equal(values[0],values[1]).all():
        return values
    else:
        return np.concat([values,[values[0]]])

def geometric_curvature2(path: np.ndarray):
    """
    Most robust n-dimensional curvature using sine of angle approach.
    This gives results most similar to the original 2D function.
    
    Args:
        path: numpy array of shape (n_points, n_dimensions)
    
    Returns:
        numpy array of curvature values with same length as input path
    """
    if path.shape[0] < 3:
        return np.zeros(path.shape[0])
    
    p1, p2, p3 = path[:-2], path[1:-1], path[2:]
    
    # Vectors from p1 to p2 and p2 to p3
    v1 = p2 - p1
    v2 = p3 - p2
    
    # Segment lengths
    len1 = np.linalg.norm(v1, axis=1)
    len2 = np.linalg.norm(v2, axis=1)
    
    # Dot product for cosine of angle
    dot_product = np.sum(v1 * v2, axis=1)
    
    # cos(theta) = dot_product / (len1 * len2)
    cos_theta = dot_product / (len1 * len2 + 1e-10)
    cos_theta = np.clip(cos_theta, -1.0, 1.0)
    
    # sin(theta) = sqrt(1 - cos²(theta))
    sin_theta = np.sqrt(1 - cos_theta**2)
    
    # Curvature = sin(theta) / average_segment_length
    # This is equivalent to |cross_product| / (|v1| * |v2|) for any dimension
    curvature = sin_theta
    
    # Pad to match original path length
    padded_curvature = np.pad(curvature, (1, 1), mode='edge')
    
    return padded_curvature