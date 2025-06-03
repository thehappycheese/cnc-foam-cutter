from __future__ import annotations
from dataclasses import dataclass, field, replace
from typing import Literal
from warnings import deprecated

import numpy as np
from numpy.typing import ArrayLike

from scipy.interpolate import make_splprep
import matplotlib.pyplot as plt
from matplotlib.axes import Axes

from ._naca4 import naca4
from ._naca5 import naca5
from ._naca_parse import naca

from shapely import LineString, Polygon, is_ccw, Point, delaunay_triangles
from shapely import geometry
from shapely import difference, unary_union


import pyvista as pv

from .util import (
    create_ruled_surface,
    shapely_to_svg,
    split_linestring_by_angle,
    remove_sequential_duplicates,
    ensure_closed,
)


@dataclass
class Decomposer:
    upcut_kerf=0.1
    buffer:float=0
    tolerance=0.05
    split_angle_deg=75
    segment_target_length:float=1.0
    _length_counts:list[int]|None = None

    def decompose_many(self, airfoils:list[Airfoil]):
        result = []
        for airfoil in airfoils:
            result.append(self.decompose(airfoil))
        return result

    def decompose(self, airfoil:Airfoil):
        lsb = airfoil.get_with_holes(upcut_width=self.buffer*2+self.upcut_kerf, tolerance=self.tolerance)
        if self.buffer>0:
            lsb = lsb.buffer(self.buffer, quad_segs=1, join_style="mitre")
        lsb = np.array(lsb.boundary.coords)[:-1]
        
        # change starting point to upper trailing edges
        lsb = np.roll(lsb,-(lsb[:,0]+lsb[:,1]).argmax()-1, axis=0)[::-1]

        # pick out the leading edge point
        leading_edge_split = lsb[:,0].argmin()
        lsbc_upper = lsb[:leading_edge_split+1]
        lsbc_lower = lsb[leading_edge_split:]

        upper_chunks = split_linestring_by_angle(lsbc_upper,split_angle_deg=self.split_angle_deg)
        lower_chunks = split_linestring_by_angle(lsbc_lower,split_angle_deg=self.split_angle_deg)

        decomposed = upper_chunks + lower_chunks

        interpolated_chunks = []

        # we previously used this and it decomposed to a different number of chunks
        if self._length_counts is None:
            self._length_counts = [len(item) for item in decomposed]
        elif len(decomposed)!=len(self._length_counts):
            raise ValueError(f"The airfoil was decomposed into {len(decomposed)} parts, but the last one was decomposed into {len(self._length_counts)} parts.")
        

        for chunk_index, chunk in enumerate(decomposed):
            if len(chunk)<=2:
                interpolated_chunks.append(chunk)
            else:
                
                if self._length_counts is None:
                    ls_len = np.linalg.norm(np.diff(chunk, axis=0), axis=1).sum()
                    max_segment_length = self.segment_target_length
                    assert isinstance(max_segment_length, float), f"segment_length_targets must either be a float or a list of floats the same length as the decomposed line segments: {len(decomposed)}"
                    desired_segments = int(np.ceil(ls_len/max_segment_length))
                else:
                    desired_segments = self._length_counts[chunk_index]
                

                bspline, u = make_splprep(chunk.transpose())

                # Evaluate the spline at many points for smooth curve
                u_new = np.linspace(0, 1, desired_segments)
                interpolated_chunks.append(bspline(u_new).transpose())
        return interpolated_chunks
        

@dataclass
class Hole:
    diameter_mm:float
    position:np.ndarray
    def __post_init__(self):
        assert self.position.shape == (2,), "position must have shape `(2)`"

@dataclass
class Airfoil:
    points:np.ndarray = field()
    holes:list[Hole] = field(default_factory=list)

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
    
    def with_translation(self, translation:ArrayLike)->Airfoil:
        translation = np.array(translation)
        assert translation.shape==(2,), "Translation must be an ndarray of shape (2,)"
        return replace(
            self,
            points = self.points+translation.reshape(1,-1),
            holes = [replace(hole,position=hole.position+translation) for hole in self.holes]
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
            holes  = [replace(hole, position=hole.position@rotation_matrix) for hole in self.holes]
        )

    def show(self):
        from IPython.display import display
        display(LineString(self.points))
    
    def linestring(self) -> LineString:
        return LineString(self.points)
    
    def polygon(self) -> Polygon:
        return Polygon(self.points)

    def get_with_holes(self, upcut_width=1.3, tolerance=0.05) -> Polygon:
        shapes = [Point(hole.position).buffer(hole.diameter_mm/2) for hole in self.holes]
        height=50
        upcuts = [
            geometry.box(
                *(hole.position-np.array([upcut_width/2,-height])),
                *(hole.position+np.array([upcut_width/2,0]))
            ) for hole in self.holes
        ]
        
        return difference(
            self.polygon().simplify(tolerance=tolerance),
            unary_union(shapes+upcuts)
        )
    
    @deprecated("Use Decomposer.decompose instead")
    def decompose(
            self,
            upcut_kerf=0.1,
            buffer:float=0,
            tolerance=0.05,
            split_angle_deg=75,
            segment_target_length_or_counts:float|list[int]=1.0,
        ):
        lsb = self.get_with_holes(upcut_width=buffer*2+upcut_kerf, tolerance=tolerance)
        if buffer>0:
            lsb = lsb.buffer(buffer, quad_segs=1, join_style="mitre")
        lsb = np.array(lsb.boundary.coords)[:-1]
        
        # change starting point to upper trailing edge
        lsb = np.roll(lsb,-(lsb[:,0]+lsb[:,1]).argmax()-1, axis=0)[::-1]

        # pick out the leading edge point
        leading_edge_split = lsb[:,0].argmin()
        lsbc_upper = lsb[:leading_edge_split+1]
        lsbc_lower = lsb[leading_edge_split:]

        upper_chunks = split_linestring_by_angle(lsbc_upper,split_angle_deg=split_angle_deg)
        lower_chunks = split_linestring_by_angle(lsbc_lower,split_angle_deg=split_angle_deg)

        decomposed = upper_chunks + lower_chunks

        interpolated_chunks = []

        assert isinstance(segment_target_length_or_counts, float) or (isinstance(segment_target_length_or_counts, list) and len(decomposed)==len(segment_target_length_or_counts)), f"segment_length_targets must either be a float or a list of floats the same length as the decomposed line segments: {len(decomposed)}"
        for chunk_index, chunk in enumerate(decomposed):
            if len(chunk)<=2:
                interpolated_chunks.append(chunk)
            else:
                
                if isinstance(segment_target_length_or_counts, float):
                    ls_len = np.linalg.norm(np.diff(chunk, axis=0), axis=1).sum()
                    max_segment_length = segment_target_length_or_counts
                    assert isinstance(max_segment_length, float), f"segment_length_targets must either be a float or a list of floats the same length as the decomposed line segments: {len(decomposed)}"
                    desired_segments = int(np.ceil(ls_len/max_segment_length))
                elif isinstance(segment_target_length_or_counts, list):
                    desired_segments = int(segment_target_length_or_counts[chunk_index])
                

                bspline, u = make_splprep(chunk.transpose())

                # Evaluate the spline at many points for smooth curve
                u_new = np.linspace(0, 1, desired_segments)
                interpolated_chunks.append(bspline(u_new).transpose())
        return interpolated_chunks
    
    @classmethod
    @deprecated("please use Decomposer.decompose")
    def decompose_together(
            cls,
            a:Airfoil,
            b:Airfoil,
            upcut_kerf=0.1,
            buffer:float=0,
            tolerance=0.05,
            split_angle_deg=75,
            segment_target_length:float=1.0
        ):
        ad = a.decompose(
            upcut_kerf=upcut_kerf,
            buffer=buffer,
            tolerance=tolerance,
            split_angle_deg=split_angle_deg,
            segment_target_length_or_counts=segment_target_length
        )
        bd = b.decompose(
            upcut_kerf=upcut_kerf,
            buffer=buffer,
            tolerance=tolerance,
            split_angle_deg=split_angle_deg,
            segment_target_length_or_counts=[len(chunk) for chunk in ad]
        )
        return ad, bd
    
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
    
    def to_svg(self):
        return shapely_to_svg(LineString(self.points))
    
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
    
@dataclass
class WingSegment:
    left:Airfoil
    right:Airfoil
    length:float

    def __repr__(self) -> str:
        return f"<AirfoilPair length={self.length:.1f} left={self.left} right={self.right} />"

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
        
        # edgea = pv.PolyData(a_3d)
        # edgeb = pv.PolyData(b_3d)
        # mesha = edgea.delaunay_2d(edge_source=edgea)
        # meshb = edgeb.delaunay_2d(edge_source=edgeb)
        lengths = [len(item) for item in ad]
        mesha = self.left.to_mesh(decomposer).rotate_x(90).rotate_z(90).translate((-self.length/2,0,0))
        meshb = self.right.to_mesh(decomposer).rotate_x(90).rotate_z(90).translate(( self.length/2,0,0))

        meshc = create_ruled_surface(a_3d,b_3d)
        mesh_target = (mesha + meshb + meshc).clean().fill_holes(hole_size=20)
        mesh_target = mesh_target.compute_normals(auto_orient_normals=True)
        #assert mesh_target.is_manifold
        return mesh_target
