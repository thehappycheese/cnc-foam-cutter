from __future__ import annotations
from dataclasses import dataclass, field, replace
from typing import Literal
from warnings import warn, deprecated

import numpy as np
from numpy.typing import ArrayLike

from scipy.interpolate import make_splprep
import matplotlib.pyplot as plt
from matplotlib.axes import Axes

from shapely import LineString, Polygon, is_ccw, Point, delaunay_triangles, intersection
from shapely import geometry
from shapely import difference, unary_union

import pyvista as pv

from .naca import naca, naca4, naca5
from .util.array_helpers import remove_sequential_duplicates
from .util.linestring_helpers import split_linestring_by_angle, ensure_closed, resample_linear_to_number_of_segments
from .util.pyvista_helpers import create_ruled_surface

@dataclass
class Decomposer:
    upcut_kerf            :float=0.01
    buffer                :float=0
    tolerance             :float=0.05
    split_angle_deg       :float=30
    segment_target_length :float=1.0
    _length_counts        :list[int]|None = None

    def decompose_many(self, airfoils:list[Airfoil]):
        result = []
        for airfoil in airfoils:
            result.append(self.decompose(airfoil))
        return result

    def decompose(self, airfoil:Airfoil):

        if any(hole.diameter_mm/2-self.buffer<self.buffer/2 for hole in airfoil.holes):
            warn(f"some holes will be buffered down to minimum size of the buffer/2={self.buffer/2}mm")

        shape_holes = [
            Point(hole.position)
            .buffer(max(self.buffer/4, hole.diameter_mm/2-self.buffer))
            for hole
            in airfoil.holes
        ]
        height=airfoil.bounding_size()[1]*10
        shape_upcuts = [
            geometry.box(
                *(hole.position+np.array([-self.upcut_kerf/2, 0])),
                *(hole.position+np.array([ self.upcut_kerf  ,height]))
            ) for hole in airfoil.holes
        ]

        shape_airfoil = airfoil.polygon().simplify(tolerance=self.tolerance)
        shape_hinges = [] if airfoil.hinge is None else [airfoil.hinge.to_polygon()]
        if self.buffer>0:
            shape_airfoil = shape_airfoil.buffer(self.buffer,quad_segs=1, join_style="mitre")
            shape_hinges = [hinge.buffer(-self.buffer,quad_segs=1,join_style="mitre") for hinge in shape_hinges]

        lsb = difference(
            airfoil.polygon().simplify(tolerance=self.tolerance).buffer(self.buffer),
            unary_union(shape_holes+shape_upcuts+shape_hinges)
        )
        lsb = np.array(lsb.boundary.coords)
        lsb = np.roll(lsb,-(lsb[:,0]+lsb[:,1]).argmax()-1, axis=0)[::-1]

        lsb = remove_sequential_duplicates(lsb)

        leading_edge_split = lsb[:,0].argmin()
        lsbc_upper = lsb[:leading_edge_split+1]
        lsbc_lower = lsb[leading_edge_split:]
        upper_chunks = split_linestring_by_angle(lsbc_upper,split_angle_deg=self.split_angle_deg)
        lower_chunks = split_linestring_by_angle(lsbc_lower,split_angle_deg=self.split_angle_deg)
        chunks = upper_chunks+lower_chunks

        if self._length_counts is None:
            result = []
            for chunk in chunks:
                new_segment_count = int(np.ceil(np.linalg.norm(np.diff(chunk,axis=0),axis=1).sum()/self.segment_target_length))
                if len(chunk)<=4:
                    #linear
                    result.append(resample_linear_to_number_of_segments(chunk, new_segment_count))
                else:
                    try:
                        bspline, u = make_splprep(chunk.transpose())
                        u_new = np.linspace(0, 1, new_segment_count)
                        interped = bspline(u_new).transpose()
                        assert self._is_valid_interpolation_result(interped)
                    except:
                        warn(f"Bspline failed with error for {airfoil} {chunk=} attempting linear resampling instead")
                        interped = resample_linear_to_number_of_segments(chunk, new_segment_count)
                    result.append(interped)
            self._length_counts = [len(chunk) for chunk in result]
        else:
            result = []
            for new_segment_count, chunk in zip(self._length_counts, chunks):
                if len(chunk)<=4:
                    #linear
                    result.append(resample_linear_to_number_of_segments(chunk, new_segment_count))
                else:
                    try:
                        bspline, u = make_splprep(chunk.transpose())
                        u_new = np.linspace(0, 1, new_segment_count)
                        interped = bspline(u_new).transpose()
                        assert self._is_valid_interpolation_result(interped)
                    except:
                        warn(f"Bspline failed with error for {airfoil} {chunk=} attempting linear resampling instead")
                        interped = resample_linear_to_number_of_segments(chunk, new_segment_count)
                    result.append(interped)
        return result

    def _is_valid_interpolation_result(self, result):
        """Check if interpolation result is valid"""
        
        # Check for NaN or infinite values
        if not np.isfinite(result).all():
            return False
        
        # Check if result has reasonable variance (not all points the same)
        if np.allclose(result, result[0], atol=1e-10):
            return False
        
        return True

@dataclass
class Hole:
    diameter_mm:float
    position:np.ndarray
    def __post_init__(self):
        assert self.position.shape == (2,), "position must have shape `(2)`"

@dataclass
class Hinge:
    position: ArrayLike
    angle_deg: float = 60
    rotation_deg: float = -20
    height: float = 300.0
    
    def __post_init__(self):
        self.position = np.array(self.position)
        assert self.position.shape == (2,), "upper_point must have shape `(2)`"
        assert 0 < self.angle_deg <= 180, "angle_deg must be between 0 and 180 degrees"
    
    def to_polygon(self) -> Polygon:
        """Generate the equilateral triangle polygon based on parameters."""
        # Calculate the base width from the angle and height
        # For an equilateral triangle, if we know the angle at the top and height,
        # we can calculate the base width
        half_base = self.height * np.tan(np.deg2rad(self.angle_deg / 2))
        
        # Create triangle points relative to origin (upper point at origin, pointing down)
        triangle_points = np.array([
            [0, 0],  # upper point
            [-half_base, -self.height],  # bottom left
            [half_base, -self.height],   # bottom right
            [0, 0]   # close the triangle
        ])
        
        # Apply rotation
        if self.rotation_deg != 0:
            rotation_rad = np.deg2rad(self.rotation_deg)
            rotation_matrix = np.array([
                [np.cos(rotation_rad), -np.sin(rotation_rad)],
                [np.sin(rotation_rad),  np.cos(rotation_rad)]
            ])
            triangle_points = triangle_points @ rotation_matrix
        
        # Translate to the actual upper point position
        triangle_points = triangle_points + self.position.reshape(1, -1)
        
        return Polygon(triangle_points)

@dataclass
class Airfoil:
    points:np.ndarray = field()
    holes:list[Hole] = field(default_factory=list)
    hinge:Hinge|None = None

    def __repr__(self) -> str:
        size = np.max(self.points,axis=0) - np.min(self.points,axis=0)
        return f"<Airfoil p={len(self.points)} h={len(self.holes)} w={size[0]:.1f} h={size[1]:.1f} />"
    
    def __post_init__(self) -> None:
        assert self.points.shape[1]==2, "points must have shape (n, 2)" 
        assert self.points.shape[0]>4, f"need more points. only got {len(self.points)=}"
        assert (self.points[0]==self.points[-1]).all(), "first and last point must be the same"
        assert is_ccw(LineString(self.points)), "Points must be counterclockwise from trailing edge"
    @classmethod
    def from_upper_lower(
        cls,
        upper:np.ndarray,
        lower:np.ndarray,
    ):
        selig = np.vstack((upper[::-1], lower[1:]))
        average_terminator = (selig[0]+selig[-1])/2
        selig = np.concatenate([
            [average_terminator],
            selig,
            [average_terminator]
        ])
        return Airfoil(selig)
    @classmethod
    def from_naca4(
            cls,
            max_camber:float,
            max_camber_position:float,
            max_thickness:float,
            chord_length:float,
            points:int=100,
        ):
        upper, lower = naca4(
            max_thickness=max_thickness, 
            max_camber_position=max_camber_position, 
            max_camber=max_camber,
        )(n=points)
        return Airfoil.from_upper_lower(upper*chord_length,lower*chord_length)
    
    @classmethod
    def from_naca5(
        cls,
        type: Literal["standard","reflex"],
        design_lift_coefficient: float,
        max_camber_position: float,
        max_thickness: float,
        chord_length:float,
        points:int=100,
    ):
        upper, lower = naca5(
            type=type,
            design_lift_coefficient=design_lift_coefficient,
            max_camber_position=max_camber_position,
            max_thickness=max_thickness
        )(n=points)
        return Airfoil.from_upper_lower(upper*chord_length, lower*chord_length)
    
    @classmethod
    def from_naca_designation(cls, designation:str, chord_length:float, points:int=100):
        upper, lower = naca(designation, points)
        return Airfoil.from_upper_lower(upper*chord_length, lower*chord_length)

    def with_holes(self, holes:list[Hole]) -> Airfoil:
        return replace(self, holes=holes)
    
    def with_hinge(self, hinge:Hinge|None, upper_thickness:float|None=None) -> Airfoil:
        if upper_thickness is not None and hinge is not None:
            shape = intersection(
                self.polygon(),
                LineString([[hinge.position[0],-500],[hinge.position[0],500]])
            )
            hinge = replace(
                hinge,
                position=np.array([
                    hinge.position[0],
                    np.array(shape.coords)[:,1].max()-upper_thickness,
                ])
            )
        return replace(self, hinge=hinge)
    
    def with_translation(self, translation:ArrayLike)->Airfoil:
        translation = np.array(translation)
        assert translation.shape==(2,), "Translation must be an ndarray of shape (2,)"
        return replace(
            self,
            points = self.points+translation.reshape(1,-1),
            holes  = [replace(hole,position=hole.position+translation) for hole in self.holes],
            hinge  = None if self.hinge is None else replace(
                self.hinge, 
                position=self.hinge.position + translation
            ),
        )
    
    def with_rotation(self, rotation_deg:float)->Airfoil:
        rotation_rad = np.deg2rad(rotation_deg)
        rotation_matrix = np.array([
            [np.cos(rotation_rad), -np.sin(rotation_rad)],
            [np.sin(rotation_rad),  np.cos(rotation_rad)]
        ])
        return replace(
            self,
            points = self.points @ rotation_matrix,
            holes  = [replace(hole, position=hole.position@rotation_matrix) for hole in self.holes],
            hinge  = None if self.hinge is None else replace(
                self.hinge,
                upper_point  = self.hinge.position @ rotation_matrix,
                rotation_deg = self.hinge.rotation_deg + rotation_deg
            ),
        )

    def show(self):
        from IPython.display import display
        display(LineString(self.points))
    
    def linestring(self) -> LineString:
        return LineString(self.points)
    
    def polygon(self) -> Polygon:
        return Polygon(self.points)
    
    def plot(
            self,
            ax:Axes|None=None,
            decomposer:Decomposer|None=None):
        if ax is None:
            fig,ax = plt.subplots(figsize=(10,10))
        if decomposer is None:
            decomposer = Decomposer()
        decomposed = decomposer.decompose(self)
        for chunk in decomposed:
            ax.plot(*chunk.transpose(),"o-",markersize=2)
        ax.set_aspect("equal")
        return ax, [len(chunk) for chunk in decomposed]
    
    def plot_raw(self, ax:Axes|None=None, ):
        
        if ax is None:
            fig,ax = plt.subplots(figsize=(10,10))
        
        ax.plot(*self.points.transpose(),"o-",markersize=2)
        ax.set_aspect("equal")
        return ax
    
    def to_mesh(
            self,
            decomposer:Decomposer|None = None
        ):
        if decomposer is None:
            decomposer = Decomposer()
        chunks = decomposer.decompose(self)
        s =  ensure_closed(remove_sequential_duplicates(np.concat(chunks)))
        pol = Polygon(s)
        triangles = delaunay_triangles(pol)
        # Collect all vertices and faces
        all_vertices = []
        all_faces = []
        vertex_offset = 0
        for triangle in triangles.geoms:
            if pol.contains(triangle.centroid):
                # Extract triangle vertices
                coords = np.array(triangle.exterior.coords[:-1])  # Remove duplicate last point
                # Add to vertex list
                all_vertices.extend(coords)
                # Create face indices (triangle with 3 vertices)
                face = [3, vertex_offset, vertex_offset + 1, vertex_offset + 2]
                all_faces.extend(face)
                vertex_offset += 3
        vertices_array = np.array(all_vertices)
        faces_array = np.array(all_faces)
        points_3d = np.insert(vertices_array, 2, 0, axis=-1)
        mesh = pv.PolyData(points_3d, faces_array)
        mesh = mesh.clean(tolerance=1e-6)
        return mesh#, [len(item) for item in chunks]
    
    def bounding_size(self):
        return self.points.max(axis=1)-self.points.min(axis=1)
    
    def bounding_center(self):
        return self.points.min(axis=1)+self.bounding_size()/2
    
@dataclass
class WingSegment:
    left:Airfoil
    right:Airfoil
    length:float

    def __repr__(self) -> str:
        return f"<AirfoilPair length={self.length:.1f} left={self.left} right={self.right} />"

    def with_translation(self, translation:ArrayLike) -> WingSegment:
        return replace(
            self,
            left  = self.left .with_translation(translation),
            right = self.right.with_translation(translation),
        )
    
    def bounding_size(self):
        allpoints = np.concat([self.left.points, self.right.points])
        size = allpoints.max(axis=0)-allpoints.min(axis=0)
        return np.array([*size, self.length])
    
    def bounding_center(self):
        allpoints = np.concat([self.left.points, self.right.points])
        return np.array([0, *(allpoints.min(axis=0)+(allpoints.max(axis=0)-allpoints.min(axis=0))/2)])

    def decompose(
        self,
        decomposer:Decomposer|None=None
    ):
        if decomposer is None:
            decomposer = Decomposer()
        ad, bd = decomposer.decompose_many([self.left, self.right])
        return ad, bd

    def to_mesh(
        self,
        decomposer:Decomposer|None=None
    ):
        if decomposer is None:
            decomposer = Decomposer()
        
        ad, bd = self.decompose(decomposer)

        a_3d = np.insert(
            ensure_closed(remove_sequential_duplicates(np.concat(ad))),
            0,
            -self.length/2,
            axis=1
        )
        b_3d = np.insert(
            ensure_closed(remove_sequential_duplicates(np.concat(bd))),
            0,
            self.length/2,
            axis=1
        )

        lengths = [len(item) for item in ad]
        mesha = self.left.to_mesh(decomposer).rotate_x(90).rotate_z(90).translate((-self.length/2,0,0))
        meshb = self.right.to_mesh(decomposer).rotate_x(90).rotate_z(90).translate(( self.length/2,0,0))

        meshc = create_ruled_surface(a_3d,b_3d)
        mesh_target = (mesha + meshb + meshc).clean().fill_holes(hole_size=20)
        mesh_target = mesh_target.compute_normals(auto_orient_normals=True)
        #assert mesh_target.is_manifold
        return mesh_target
