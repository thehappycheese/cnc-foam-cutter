from typing import Literal
import numpy as np



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

def compensate_feedrate(dx, dy, dz, da):
    """GRBL control systems will (should?) interpret 4-axis feed-rate in 4D space.
    This makes our two toolheads move unexpectedly slowly.

    This function takes a planned relative movement of the toolhead and returns a compensation factor.

    ```python
    desired_feedrate = 500
    compensated_feedrate = desired_feedrate * compensate_feedrate(100,0,100,0)
    cnc.feed(compensated_feedrate, 100,0,100,0)
    ```

    This function returns the ratio between the maximum magnitude of XY and ZA toolheads and the magnitude of the vector
    XYZA.
    This roughly aims to move both toolheads at a speed as high as possible without either exceeding the specified feedrate."""
    xy_magnitude = np.sqrt(dx**2 + dy**2)
    za_magnitude = np.sqrt(dz**2 + da**2)
    total_4d_magnitude = np.sqrt(dx**2 + dy**2 + dz**2 + da**2)
    max_independent_magnitude = np.max([xy_magnitude,za_magnitude], axis=0)
    compensation_factor = total_4d_magnitude / max_independent_magnitude
    return compensation_factor
