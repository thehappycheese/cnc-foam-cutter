import numpy as np
import pyvista as pv
import shapely as sh

def create_ruled_surface(curve_a, curve_b):
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

    return mesh

def mesh_from_polygon(polygon:sh.Polygon):
    pol = sh.Polygon(polygon)
    triangles = sh.constrained_delaunay_triangles(pol)
    return pv.merge([
        pv.PolyData(
            np.insert(coords:=geom.exterior.coords[:-1],0, 0,-1),
            faces=[[len(coords), *range(len(coords))]]
        )
        for geom in triangles.geoms
    ])
