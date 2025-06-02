import numpy as np
import pyvista as pv

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
