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

def mesh_from_polygon(polygon:sh.Polygon|np.ndarray):
    """Uses shapely's superior constrained_delaunay_triangles instead of pyvista's delaunay.
    Therefore the input has to be a shapely polygon or a (n,2) numpy array of xy points.
    The output will be a pyvista mesh."""
    pol = sh.Polygon(polygon)
    triangles = sh.constrained_delaunay_triangles(pol)
    return pv.merge([
        pv.PolyData(
            np.insert(coords:=geom.exterior.coords[:-1],0, 0,-1),
            faces=[[len(coords), *range(len(coords))]]
        )
        for geom in triangles.geoms
    ])

def make_mesh_from_side_surfaces(a:np.ndarray, b:np.ndarray, width:float=150):
    """uses related function `create_rules_surface` and `mesh_from_polygon`
    to create manifold lofted mesh from two 2D profiles that will be placed at ±width/2 from the yz plane.
    a and b should be line strings as nympy (n,2) arrays"""
    shapea3d = np.insert(a, 0, -width/2, axis=-1)
    shapeb3d = np.insert(b, 0,  width/2, axis=-1)

    aa = mesh_from_polygon(sh.Polygon(a)).translate((-width/2,0,0))
    bb = mesh_from_polygon(sh.Polygon(b)).translate(( width/2,0,0))
    aabb = create_ruled_surface(shapea3d, shapeb3d)

    result =  pv.merge([aa,bb,aabb])
    assert result.is_manifold
    return result
