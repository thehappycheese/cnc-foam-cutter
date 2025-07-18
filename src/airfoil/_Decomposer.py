from __future__ import annotations
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from airfoil._airfoil import Airfoil
from airfoil.util.array_helpers import remove_sequential_duplicates
from airfoil.util.linestring_helpers import (
    resample_linear_to_number_of_segments,
    split_linestring_by_angle,
    resample_spline_fallback_linear,
)


import numpy as np
from scipy.interpolate import make_splprep
from shapely import Point, difference, geometry, unary_union


from dataclasses import dataclass
from warnings import warn


@dataclass
class Decomposer:
    upcut_kerf            :float          = 0.01
    buffer                :float          = 0
    tolerance             :float          = 0.05
    split_angle_deg       :float          = 70
    segment_target_length :float          = 1.0
    _length_counts        :list[int]|None = None

    def clone(self):
        import copy
        return copy.copy(self)

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
            result = [
                resample_spline_fallback_linear(
                    chunk,
                    lambda l: int(np.ceil(l/self.segment_target_length))
                )
                for chunk in chunks
            ]
            self._length_counts = [len(chunk) for chunk in result]
        else:
            result = [
                resample_spline_fallback_linear(
                    chunk,
                    lambda _: count
                )
                for chunk, count in zip(chunks, self._length_counts)
            ]

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