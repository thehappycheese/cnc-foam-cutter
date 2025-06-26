from __future__ import annotations
import warnings
from airfoil._Decomposer import Decomposer
from airfoil._airfoil import Airfoil
from airfoil.util.array_helpers import remove_sequential_duplicates
from airfoil.util.linestring_helpers import ensure_closed
from airfoil.util.pyvista_helpers import create_ruled_surface


import numpy as np
from numpy.typing import ArrayLike

import pyvista as pv


from dataclasses import dataclass, replace


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

        mesha = self.left.to_mesh(decomposer).rotate_x(90).rotate_z(90).translate((-self.length/2,0,0)).flip_faces()
        meshb = self.right.to_mesh(decomposer).rotate_x(90).rotate_z(90).translate(( self.length/2,0,0))

        meshc = create_ruled_surface(a_3d,b_3d)
        mesh_target = pv.merge([mesha, meshb, meshc]).clean().fill_holes(hole_size=20)
        mesh_target = mesh_target.compute_normals(auto_orient_normals=True)
        if not mesh_target.is_manifold:
            warnings.warn("Non-Manifold result from WingSegment.to_mesh()")
        mesh_target=mesh_target.compute_normals(
            cell_normals=False,
            point_normals=True,
            split_vertices=True,
            #feature_angle=smooth_angle,
            auto_orient_normals=True
        )
        return mesh_target
    
    @classmethod
    def plot_wing_segments(cls, segments:list[WingSegment], pt:pv.Plotter|None=None, decomposer:Decomposer|None=None):
        if pt is None:
            pt = pv.Plotter()
        wing_meshes = WingSegment.to_meshes(segments=segments, decomposer=decomposer)
        for m in wing_meshes:
            pt.add_mesh(m.rotate_x(-4).translate((0,0,60)))
        return pt
    
    @classmethod
    def to_meshes(cls, segments:list[WingSegment], decomposer:Decomposer|None=None, add_mirrored:bool=False):
        if decomposer is None:
            decomposer = Decomposer()
        o = 0
        wing_meshes = []
        for segment in segments:
            o += segment.length/2
            msh = segment.to_mesh(decomposer)
            wing_meshes.append(msh.translate([o,0,0]))
            if add_mirrored:
                wing_meshes.append(msh.scale([-1,1,1]).translate([-o,0,0]).flip_faces())
            o += segment.length/2
        return wing_meshes
