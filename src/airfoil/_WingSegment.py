from __future__ import annotations
from warnings import warn, deprecated
from ._Decomposer import Decomposer
from ._airfoil import Airfoil
from .util import (
    remove_sequential_duplicates,
    ensure_closed,
    create_ruled_surface
)

import numpy as np
from numpy.typing import ArrayLike

import pyvista as pv
import matplotlib.pyplot as plt
from matplotlib.axes import Axes

from pydantic import BaseModel

class WingSegment(BaseModel):
    
    class Config:
        frozen=True

    left:Airfoil
    right:Airfoil
    length:float

    def __repr__(self) -> str:
        return f"<WingSegment length={self.length:.1f} left={repr(self.left)} right={repr(self.right)} />"

    def with_translation(self, translation:ArrayLike) -> WingSegment:
        return self.model_copy(
            update={
                "left"  : self.left .with_translation(translation),
                "right" : self.right.with_translation(translation),
            }
        )
    
    def with_mirror(self) -> WingSegment:
        return self.model_copy(
            update={
                "left"  : self.right,
                "right" : self.left,
            }
        )
    
    def with_width(self, length:float) -> WingSegment:
        return self.model_copy(
            update={
                "length":length
            }
        )
    
    def with_rotation(self, rotation_deg:float) -> WingSegment:
        return self.model_copy(
            update={
                "left"  : self.left.with_rotation(rotation_deg),
                "right" : self.right.with_rotation(rotation_deg),
            }
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

        mesha = self.left.to_mesh(decomposer).rotate_x(90).rotate_z(90).translate((-self.length/2,0,0)).flip_faces()
        meshb = self.right.to_mesh(decomposer).rotate_x(90).rotate_z(90).translate(( self.length/2,0,0))

        meshc = create_ruled_surface(a_3d,b_3d)
        mesh_target = pv.merge([mesha, meshb, meshc]).clean().fill_holes(hole_size=20)
        mesh_target = mesh_target.compute_normals(auto_orient_normals=True)
        if not mesh_target.is_manifold:
            warn("Non-Manifold result from WingSegment.to_mesh()")
        mesh_target=mesh_target.compute_normals(
            cell_normals=False,
            point_normals=True,
            split_vertices=True,
            #feature_angle=smooth_angle,
            auto_orient_normals=True
        )
        return mesh_target
    
    def plot_2d(self, ax:Axes|None=None):
        if ax is None:
            _, ax = plt.subplots()
        l,r = self.decompose()
        for line in l+r:
            ax.plot(*line.transpose(), "o-", ms=2)
        ax.set_aspect("equal")
        return ax

    @classmethod
    def plot_wing_segments(cls, segments:list[WingSegment], pt:pv.Plotter|None=None, decomposer:Decomposer|None=None):
        if pt is None:
            pt = pv.Plotter()
        wing_meshes = WingSegment.to_meshes(segments=segments, decomposer=decomposer)
        for m in wing_meshes:
            pt.add_mesh(m.rotate_x(-4).translate((0,0,60)))
        return pt
    
    @classmethod
    def to_meshes(
        cls,
        segments:list[WingSegment],
        decomposer:Decomposer|None=None,
        add_mirrored:bool=False,
        share_decomposer:bool=False,
        first_segment_is_central:bool=True,
    ):
        if decomposer is None:
            decomposer = Decomposer()
        o = 0
        wing_meshes = []
        for i, segment in enumerate(segments):
            if share_decomposer:
                current_decomposer = decomposer
            else:
                current_decomposer = decomposer.clone()
            if not first_segment_is_central or i > 0:
                o += segment.length / 2
            msh = segment.to_mesh(current_decomposer)
            wing_meshes.append(msh.translate([o,0,0]))
            if add_mirrored and (i>0 or not first_segment_is_central):
                wing_meshes.append(msh.scale([-1,1,1]).translate([-o,0,0]).flip_faces())
            o += segment.length/2
        return wing_meshes

    @classmethod
    @deprecated("use to_meshes with share_decomposer=True")
    def to_meshes_unshared_decomposer(cls, segments:list[WingSegment], decomposer:Decomposer|None=None, add_mirrored:bool=False):
        o = 0
        wing_meshes = []
        for segment in segments:
            if decomposer is None:
                decomposer_ea = Decomposer()
            else:
                decomposer_ea = decomposer.clone()
            o += segment.length/2
            msh = segment.to_mesh(decomposer_ea)
            wing_meshes.append(msh.translate([o,0,0]))
            if add_mirrored:
                wing_meshes.append(msh.scale([-1,1,1]).translate([-o,0,0]).flip_faces())
            o += segment.length/2
        return wing_meshes
