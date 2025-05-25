from __future__ import annotations
from dataclasses import dataclass, field, replace

import pandas as pd
import numpy as np

from scipy.interpolate import make_splprep
import matplotlib.pyplot as plt
from matplotlib.axes import Axes

import airfoils as afs

from shapely import LineString, Polygon, is_ccw, Point
from shapely import geometry
from shapely.plotting import plot_line, patch_from_polygon
from shapely.affinity import translate, rotate, scale, skew
from shapely import difference, unary_union

from util.path_planning import intro_path
from util.gatekept_itertools import split_indexable, sliding_window
from util.shapely_helpers import split_linestring_by_angle


@dataclass
class Hole:
    diameter_mm:float
    position:np.ndarray
    def __post_init__(self):
        assert self.position.shape == (2,), "position must have shape `(2)`"

@dataclass
class Airfoil:
    points:np.ndarray
    holes:list[Hole] = field(default_factory=list)

    def __post_init__(self) -> None:
        assert self.points.shape[1]==2, "points must have shape (n, 2)" 
        assert self.points.shape[0]>4, f"need more points. only got {len(self.points)=}"
        assert (self.points[0]==self.points[-1]).all(), "first and last point must be the same"
        assert is_ccw(LineString(self.points)), "Points must be counterclockwise from trailing edge"
    
    @classmethod
    def from_naca(
            cls,
            max_camber:float,
            max_camber_position:float,
            thickness:float,
            chord_length_mm:float
        ):
        upper, lower = afs.gen_NACA4_airfoil(
            max_camber, 
            max_camber_position, 
            thickness,
            200
        )
        selig = np.vstack((upper.transpose()[::-1], lower.transpose()))
        average_terminator = (selig[0]+selig[-1])/2
        selig = np.concatenate([
            [average_terminator],
            selig,
            [average_terminator]
        ])
        return Airfoil(selig*chord_length_mm)
    
    def with_holes(self, holes:list[Hole]) -> Airfoil:
        return replace(self, holes=holes)
    
    def with_translation(self, translation:np.ndarray)->Airfoil:
        assert translation.shape==(2,), "Translation must be an ndarray of shape (2,)"
        return replace(
            self,
            points = self.points+translation.reshape(1,-1),
            holes = [replace(hole,position=hole.position+translation) for hole in self.holes]
        )

    def show(self):
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
        
        return difference(self.polygon().simplify(tolerance=tolerance),unary_union(shapes+upcuts))
    
    def decompose(self, upcut_kerf=0.1, buffer:float=0, tolerance=0.05, split_angle_deg=75, segment_target_length_or_counts:float|list[float]=1.0):
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
                    desired_segments = segment_target_length_or_counts[chunk_index]
                

                bspline, u = make_splprep(chunk.transpose())

                # Evaluate the spline at many points for smooth curve
                u_new = np.linspace(0, 1, desired_segments)
                interpolated_chunks.append(bspline(u_new).transpose())
        return interpolated_chunks
    
    def plot(self, ax:Axes|None=None, decompose_args:None|dict=None):
        if ax is None:
            fig,ax = plt.subplots(figsize=(10,10))
        if decompose_args is None:
            real_decompose_args = {}
        else:
            real_decompose_args = decompose_args
        decomposed = self.decompose(**real_decompose_args)
        for chunk in decomposed:
            ax.plot(*chunk.transpose(),"o-",markersize=2)
        ax.set_aspect("equal")
        return ax, [len(chunk) for chunk in decomposed]
        