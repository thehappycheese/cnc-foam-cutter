import numpy as np

def array_to_dxf_string(points, closed=True):
    """
    Convert numpy (n,2) array to DXF file string.
    Creates a polyline connecting all points.
    
    Args:
        points: numpy array of shape (n,2)
        closed: if True, creates closed polyline (polygon)
    """
    # Handle polygon termination for closed polygons
    if closed and len(points) > 2:
        # Check if first and last points are the same
        first_point = points[0]
        last_point = points[-1]
        
        # Use numpy's allclose for floating point comparison
        if np.allclose(first_point, last_point, rtol=1e-10, atol=1e-10):
            # Remove the duplicate last point since DXF closed flag handles closure
            points = points[:-1]
    
    # DXF header
    dxf_content = [
        "0", "SECTION",
        "2", "HEADER",
        "0", "ENDSEC",
        "0", "SECTION", 
        "2", "ENTITIES"
    ]
    
    # Add polyline entity
    dxf_content.extend([
        "0", "POLYLINE",
        "8", "0",  # Layer
        "70", "1" if closed else "0"  # 1 = closed, 0 = open
    ])
    
    # Add vertices
    for point in points:
        x, y = point[0], point[1]
        dxf_content.extend([
            "0", "VERTEX",
            "8", "0",
            "10", str(float(x)),  # X coordinate
            "20", str(float(y)),  # Y coordinate
            "30", "0.0"           # Z coordinate
        ])
    
    # Close polyline and file
    dxf_content.extend([
        "0", "SEQEND",
        "0", "ENDSEC",
        "0", "EOF"
    ])
    
    return "\n".join(dxf_content)
