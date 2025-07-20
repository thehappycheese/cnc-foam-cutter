import pandas as pd

import numpy as np
from numpy.typing import ArrayLike

import pyvista as pv

from .._Decomposer import Decomposer
from airfoil.util.array_helpers import blur1d, map_to_range, remove_sequential_duplicates

from .cnc_machine_mesh import axis
from ..util.pyvista_helpers import create_ruled_surface
from ..util.path_planning import compensate_feedrate, project_line_to_plane
from airfoil.util.linestring_helpers import (
    deflection_angle_padded,
    ensure_closed,
)
from dataclasses import dataclass, replace, field
from .._WingSegment import WingSegment

@dataclass
class MachineSetup:
    wing_segment:WingSegment
    foam_width :float
    foam_depth :float
    foam_height:float
    plane_spacing:float
    decomposer:Decomposer = field(default_factory=lambda:Decomposer())
    max_cut_speed_mm_s:float = 200
    min_cut_speed_mm_s:float = 100
    travel_speed:float       = 1000
    
    def with_recentered_part(self):
        foam_center = np.array([
            0,
            self.foam_depth/2,
            self.foam_height/2,
        ])
        offset = foam_center - self.wing_segment.bounding_center()
        return replace(
            self,
            wing_segment = self.wing_segment.with_translation(offset[-2:])
        )

    def plot(self, state:tuple[float,float,float,float]|ArrayLike):
        _state = np.array(state)
        mesh_foam = pv.Box((
            -self.foam_width/2,self.foam_width/2,
            0,self.foam_depth,
            0,self.foam_height
        ))
        state_a, state_b = self.state_to_line(*_state)
        mesh_state = pv.Line(state_a,state_b)
        decomposer = Decomposer() # TODO: use the class decomposer?
        mesh_target = self.wing_segment.to_mesh(decomposer)

        a,b, speed = self.prepare_cut_surface()

        cut_surface = create_ruled_surface(a,b)
        cut_surface.cell_data["speed mm/s"] = speed[1:]

        instructions = self.instructions()
        ia = np.insert(instructions[:,1:3], 0, -self.plane_spacing/2, axis=-1)
        ib = np.insert(instructions[:,3:5], 0,  self.plane_spacing/2, axis=-1)

        pt = pv.Plotter()
        pt.add_mesh(pv.MultipleLines(a),"green")
        pt.add_mesh(pv.MultipleLines(b),"green")

        pt.add_mesh(pv.MultipleLines(ia),"purple")
        pt.add_mesh(pv.MultipleLines(ib),"purple")

        pt.add_mesh(
            mesh_foam.extract_all_edges(),
            color="teal",
            line_width=2,
        )
        pt.add_mesh(
            cut_surface,
            scalars="speed mm/s",
            cmap="viridis",
            opacity=0.5
        )
        pt.add_mesh(mesh_state, color="red", line_width=2)
        if mesh_target:
            pt.add_mesh(mesh_target)
        pt.add_mesh(axis(
            (-self.plane_spacing/2, *_state[:2]), side="L"
        ), color="white", opacity=0.1)
        pt.add_mesh(axis(
            ( self.plane_spacing/2, *_state[2:]), side="R"
        ), color="white", opacity=0.1)
        pt.camera_position = (
            (-self.foam_width*1.1,-self.foam_width*3,self.foam_height*3),
            (-self.foam_width*0.3,0,0),
            (0,0,1)
        )
        pt.enable_parallel_projection()
        pt.show()


    def state_to_line(self, x:float, y:float, z:float, a:float):
        return (
            (-self.plane_spacing/2,x,y),
            ( self.plane_spacing/2,z,a),
        )

    def states_to_curves(self,states):
        x,y,z,a=states.T
        return (
            np.vstack((np.ones_like(x) * -self.plane_spacing/2, x,y)).T,
            np.vstack((np.ones_like(x) *  self.plane_spacing/2, z,a)).T,
        )
    
    def prepare_cut_surface(self):
        a, b = self.wing_segment.decompose(self.decomposer)
        a = ensure_closed(remove_sequential_duplicates(np.concat(a)))
        b = ensure_closed(remove_sequential_duplicates(np.concat(b)))
        a_3d = np.insert(a, 0, -self.wing_segment.length/2, axis=-1)
        b_3d = np.insert(b, 0,  self.wing_segment.length/2, axis=-1)
        afa_projected = []
        afb_projected = []
        for a_3di, b_3di in zip(
            a_3d,
            b_3d,
        ):
            afa_projected.append(project_line_to_plane(a_3di, b_3di, "yz", -self.plane_spacing/2))
            afb_projected.append(project_line_to_plane(a_3di, b_3di, "yz",  self.plane_spacing/2))
        afa_projected = np.array(afa_projected)
        afb_projected = np.array(afb_projected)
        assert all(np.linalg.norm(a,axis=-1)!=0)
        assert all(np.linalg.norm(b,axis=-1)!=0)
        speed = map_to_range(
            blur1d(
                np.max([
                    deflection_angle_padded(a), # error on NAN
                    deflection_angle_padded(b),
                ],axis=0),
                count=31,
                std=6
            ),
            self.max_cut_speed_mm_s,
            self.min_cut_speed_mm_s
        )
        speed_multiplier = (
             (np.linalg.norm(np.diff(afa_projected))/np.linalg.norm(np.diff(a)))
            +(np.linalg.norm(np.diff(afb_projected))/np.linalg.norm(np.diff(b)))
        )/2
        return afa_projected, afb_projected, (speed*speed_multiplier)

    def instructions(self, record_name:str|None=None):
        a,b,speed = self.prepare_cut_surface()
        ab_all = np.concat([a,b], axis=0)
        max_y_lead_in_out = np.max(ab_all, axis=0)[1]
        li = np.array([
            [                 0,    self.foam_height ],
            [                -5,    self.foam_height ],
            [                -5, self.foam_height+20 ],
            [ self.foam_depth+5, self.foam_height+20 ],
            [ max(self.foam_depth+5, max_y_lead_in_out+5), self.foam_height/2 ],
        ])
        lo = np.array([
            [ self.foam_depth+5, self.foam_height/2],
        ])
        # li = linear_resampling_to_length(li,3)
        # lo = linear_resampling_to_length(lo,3)
        instructions = np.concat([
            np.concat(
                [
                    np.full((len(li),1), self.travel_speed),
                    li,
                    li
                ],
                axis=-1
            ),
            np.concat([speed.reshape(-1,1), a[:,1:], b[:,1:]], axis=-1),
            np.concat(
                [
                    np.full((len(lo),1), self.travel_speed),
                    lo,
                    lo
                ],
                axis=-1
            ),
        ])

        feedrate_compensation = np.array([compensate_feedrate(*i) for i in np.diff(instructions[:,1:],n=1,axis=0)])
        feedrate_compensation = np.insert(feedrate_compensation,1,0)
        instructions[:,0]*=feedrate_compensation

        if record_name is not None:
            rec = (
                f'''{{\n'''
                f'''    "self": {self}\n'''
                f'''    "left": {self.wing_segment.left.points}\n'''
                f'''    "right": {self.wing_segment.right.points}\n'''
                f'''}}\n'''
            )
            from pathlib import Path
            
            folder = Path("./data/records/")
            folder.mkdir(exist_ok=True)
            file = folder / f"{pd.Timestamp.now():%Y-%m-%d %H%M} {record_name}.txt"
            file.write_text(rec)

        return instructions
