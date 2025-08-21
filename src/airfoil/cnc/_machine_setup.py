import pandas as pd

import numpy as np
from numpy.typing import ArrayLike

import pyvista as pv

from .cnc_machine_mesh import axis
from ._gcode_builder import GCodeBuilder as gcb

from ..util import (
    create_ruled_surface,
    compensate_feedrate,
    project_line_to_plane,
    deflection_angle_padded,
    ensure_closed,
    blur1d,
    map_to_range,
    remove_sequential_duplicates,
)

from .._Decomposer import Decomposer
from .._WingSegment import WingSegment

from pydantic import BaseModel, Field

class MachineSetup(BaseModel):
    wing_segment       : WingSegment
    foam_depth         : float
    foam_height        : float
    plane_spacing      : float
    decomposer         : Decomposer = Field(default_factory=lambda:Decomposer())
    min_cut_speed_mm_s : float      = 100
    max_cut_speed_mm_s : float      = 200
    cut_current_amps   : float      = 1.85
    travel_speed       : float      = 1000
    
    def with_recentered_part(self):
        foam_center = np.array([
            0,
            self.foam_depth/2,
            self.foam_height/2,
        ])
        offset = foam_center - self.wing_segment.bounding_center()
        return self.model_copy(update={"wing_segment":self.wing_segment.with_translation(offset[-2:])})

    def plot(self, state:tuple[float,float,float,float]|ArrayLike|None=None):

        _state = np.array(state) if state is not None else np.array([0, self.foam_height, 0, self.foam_height])
        mesh_foam = pv.Box((
            -self.wing_segment.length/2,self.wing_segment.length/2,
            0,self.foam_depth,
            0,self.foam_height
        ))
        state_a, state_b = self.state_to_line(*_state)
        mesh_state = pv.Line(state_a,state_b)
        decomposer = Decomposer() # TODO: use the class decomposer?
        mesh_target = self.wing_segment.to_mesh(decomposer)

        a,b, speed = self._prepare_cut_surface()

        cut_surface = create_ruled_surface(a,b)
        cut_surface.cell_data["speed mm/s"] = speed[1:]

        instructions = self._instructions()
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
            (-self.wing_segment.length*1.1,-self.wing_segment.length*3,self.foam_height*3),
            (-self.wing_segment.length*0.3,0,0),
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
    
    def _prepare_cut_surface(self):
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
        assert all(np.linalg.norm(np.diff(a,axis=0),axis=-1)!=0)
        assert all(np.linalg.norm(np.diff(b,axis=0),axis=-1)!=0)
        speed = map_to_range(
            blur1d(
                np.max([
                    deflection_angle_padded(a), # error on NAN
                    deflection_angle_padded(b),
                ],axis=0),
                count=21,
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

    def _instructions(self, record_name:str|None=None):
        a,b,speed = self._prepare_cut_surface()
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

        # i dont remember why this was commented out,
        # but i seem to remember it prevents a bug. its not important enough to re-enable for now.
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

    def prepare_gcode(self):
        a, b = self.wing_segment.decompose(self.decomposer)
        a = ensure_closed(remove_sequential_duplicates(np.concat(a)))
        b = ensure_closed(remove_sequential_duplicates(np.concat(b)))
        assert all(np.linalg.norm(np.diff(a,axis=0),axis=-1)!=0)
        assert all(np.linalg.norm(np.diff(b,axis=0),axis=-1)!=0)
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
        
        # note: a/b swapped here on purpose. zy is left axes. xy is right axes
        xyza = np.concat([afb_projected[:,1:],afa_projected[:,1:]],axis=-1) 

        # enforce a speed limit based on curvature; since each side might be different, base it on the worst case:
        feedrate = map_to_range(
            blur1d(
                np.maximum(
                    deflection_angle_padded(a)[:-1], # error on NAN
                    deflection_angle_padded(b)[:-1],
                ),
                count=21,
                std=6
            ),
            self.max_cut_speed_mm_s,
            self.min_cut_speed_mm_s
        )

        # compensate for the fact that tooleads are at some distance from the foam surface and so can actually move faster
        # in some cases.
        speed_skew_multiplier = np.minimum(
            (np.linalg.norm(np.diff(afa_projected))/np.linalg.norm(np.diff(a))),
            (np.linalg.norm(np.diff(afb_projected))/np.linalg.norm(np.diff(b)))
        )
        feedrate *= speed_skew_multiplier

        # compensate for the 4D interpolation speed of the CNC machine
        # which makes the toolheads move slower than expected without this
        # because it treats the feedrate as applying to the 4d space, and not each 2d space independently
        feedrate *= np.array([compensate_feedrate(*item) for item in np.diff(xyza,axis=0)])
        

        # compute lead-in and lead-out
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


        result = (
            gcb()
            .absolute()
            .set_current(self.cut_current_amps)
            .path_absolute(
                xyza=np.concat([
                    np.tile(li,(1,2)),
                    [xyza[0]]
                ]),
                feedrate=np.concat([np.full(len(li)-1,self.travel_speed),[self.max_cut_speed_mm_s]])
            )
            .path_absolute(
                xyza     = xyza,
                feedrate = feedrate,
            )
            .path_absolute(
                xyza=np.concat([
                    [xyza[-1]],
                    np.tile(lo,(1,2))
                ]),
                feedrate=np.full(len(lo),self.max_cut_speed_mm_s)
            )
            .set_current(0)
        )
        return result.lines
