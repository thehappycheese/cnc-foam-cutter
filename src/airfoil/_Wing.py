from __future__ import annotations
from itertools import pairwise
from typing import Callable

from ._airfoil import Airfoil
from ._WingSegment import WingSegment

import numpy as np
from numpy.typing import ArrayLike

import pyvista as pv
import matplotlib.pyplot as plt
from matplotlib.axes import Axes

from pydantic import BaseModel

class Wing(BaseModel):
    
    class Config:
        frozen=True

    segments:list[WingSegment]
    first_segment_is_central:bool
    mirrored:bool


    @classmethod
    def from_airfoil_sampler(
        cls,
        sampler:Callable[[float], Airfoil],
        positions:list[float],
        first_segment_is_central:bool,
        mirrored:bool
    ):
        segments = [
            WingSegment(
                left   = sampler(a),
                right  = sampler(b),
                length = b-a,
            )
            for a,b
            in pairwise(positions)
        ]
        return Wing(
            segments                 = segments,
            first_segment_is_central = first_segment_is_central,
            mirrored                 = mirrored,
        )
    
    def to_meshes(self):
        return WingSegment.to_meshes(
            segments=self.segments,
            add_mirrored=self.mirrored,
            first_segment_is_central = self.first_segment_is_central
        )
    
    def to_mesh(self):
        result = None
        for mesh in self.to_meshes():
            if result is None:
                result = mesh
            else:
                result += mesh
        return result
    
