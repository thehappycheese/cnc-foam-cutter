from __future__ import annotations
from typing import Callable, Iterable
from dataclasses import dataclass, field
from itertools import pairwise
import numpy as np


@dataclass
class GCodeBuilder:
    
    lines:list[str] = field(default_factory=list)

    def extend(self, other:GCodeBuilder):
        return GCodeBuilder(lines=[*self.lines,*other.lines])
    def append(self, line:str)->GCodeBuilder:
        return GCodeBuilder(lines=[*self.lines, line])
        
    
    def extend_many(self, others:Iterable[GCodeBuilder]):
        result = GCodeBuilder(lines=[*self.lines])
        for other in others:
            result = result.extend(other)
        return result
    


    def home(self) -> GCodeBuilder:
        return self.append("$H")
    
    def travel(self, x:float, y:float, z:float, a:float) -> GCodeBuilder:
        """`G0`"""
        return self.append(f"G0 X{x:.2f} Y{y:.2f} Z{z:.2f} A{a:.2f}")
    
    def absolute(self) -> GCodeBuilder:
        """`G90`"""
        return self.append(f"G90")
    
    def relative(self) -> GCodeBuilder:
        """`G91`"""
        return self.append(f"G91")
    
    def linear_move_with_feedrate(self, feed_rate:float, x:float, y:float, z:float, a:float) -> GCodeBuilder:
        """
        `G1 F# X# Y# Z# A#`

        NOTE: Feedrate is not compensated for 4 axis movement. this specifies the speed in 4D space.
        """
        return self.append(f"G1 F{feed_rate:.2f} X{x:.2f} Y{y:.2f} Z{z:.2f} A{a:.2f}")
    
    def set_feedrate(self, feed_rate:float) -> GCodeBuilder:
        """
        `G1 F#`

        NOTE: Feedrate is not compensated for 4 axis movement. this specifies the speed in 4D space.
        """
        return self.append(f"G1 F{feed_rate:.2f}")
    
    def linear_move(self, x:float, y:float, z:float, a:float) -> GCodeBuilder:
        """
        `G1 X# Y# Z# A#`
        """
        return self.append(f"G1 X{x:.2f} Y{y:.2f} Z{z:.2f} A{a:.2f}")
    
    def set_position(self, x:float, y:float, z:float, a:float) -> GCodeBuilder:
        """`G92`

        Set the position without moving the machine
        """
        return self.append(f"G92 X{x:.2f} Y{y:.2f} Z{z:.2f} A{a:.2f}")
    
    def dwel(self, seconds:float) -> GCodeBuilder:
        """`G4 Pn.n`"""
        return self.append(f"G4 P{seconds:.1f}")
    
    def metric(self) -> GCodeBuilder:
        """`G21`
        
        Sets all measurements use millimeters.
        This should be the default for fluidnc and i dont normally need to call this.
        Note fluidnc may consider the A-axis to be unitless?
        I have not experienced this I think it depends on your config.yaml"""
        return self.append("G21")
        
    
    def set_current(self, current:float) -> GCodeBuilder:
        """`M3 S???`
        current should be between 0.0 and 4.0 Amps"""
        MAX = 4
        MIN = 0
        if current<=MIN:
            return self.append("M3 S5")
        else:
            portion = (current-MIN)/(MAX-MIN)
            pwm_percent = (portion*0.8+0.1)*100
            return self.append(f"M3 S{pwm_percent:.1f}")
    
    def wrap_zero_current(self, block:Callable[[GCodeBuilder],GCodeBuilder]) -> GCodeBuilder:
        result = self.set_current(0)
        result = result.extend(block(GCodeBuilder()))
        result = result.set_current(0)
        return result
    
    def wrapped_with(
            self,/,
            before:GCodeBuilder|None=None,
            after:GCodeBuilder|None=None,
            during:GCodeBuilder|None=None,
        ):
        result = self
        if before is not None:
            result=result.extend(before)
        if during is not None:
            result=result.extend(during)
        if after is not None:
            result=result.extend(after)
        return result

    def alarm_clear(self) -> GCodeBuilder:
        return self.append("$X")
    
    def alarm_soft_reset(self) -> GCodeBuilder:
        return self.append("\x18")
    
    def build(self) -> str:
        result = "\r\n".join(self.lines)
        return result
    
    def path_absolute(
            self,
            xyza     : np.ndarray,
            feedrate : np.ndarray,
            current  : np.ndarray|None=None
        ):
        
        assert len(feedrate)==len(xyza)-1, "Length of `feedrate` must be one less than length of `xyza`"
        if current is not None:
            assert len(current) ==len(xyza)-1, "Length of `current` must be one less than length of `xyza`"
        
        result:GCodeBuilder = self.travel(*xyza[0])
        last_feedrate = None
        last_current  = None

        for (
            (last_position, current_position),
            current_feedrate,
            current_current,
        ) in zip(
            pairwise(xyza),
            feedrate,
            current  if current  is not None else [None]*(len(xyza) - 1),
        ):
            diff = current_position - last_position
            feedrate_compensation = _compensate_feedrate(*diff)
            next_feedrate = np.round(current_feedrate * feedrate_compensation*2)/2

            if current_current is not None:
                next_current = np.round(current_current*10)/10
                if next_current != last_current:
                    result = result.set_current(next_current)
                    last_current = current_current
            
            if next_feedrate != last_feedrate:
                result = result.linear_move_with_feedrate(
                    next_feedrate,
                    *current_position
                )
                last_feedrate = next_feedrate
            else:
                result = result.linear_move(*current_position)
        
        return result


def _compensate_feedrate(dx, dy, dz, da):
    """GRBL control systems will (should?) interpret 4-axis feed-rate in 4D space.
    This makes our two toolheads move unexpectedly slowly.

    This function takes a planned relative movement of the toolhead and returns a compensation factor.

    ```python
    desired_feedrate = 500
    compensated_feedrate = desired_feedrate * compensate_feedrate(100,0,100,0)
    cnc.feed(compensated_feedrate, 100,0,100,0)
    ```

    This function returns the ratio between the maximum magnitude of XY and ZA toolheads and the magnitude of the vector
    XYZA.
    This roughly aims to move both toolheads at a speed as high as possible without either exceeding the specified feedrate."""
    xy_magnitude = np.sqrt(dx**2 + dy**2)
    za_magnitude = np.sqrt(dz**2 + da**2)
    total_4d_magnitude = np.sqrt(dx**2 + dy**2 + dz**2 + da**2)
    max_independent_magnitude = np.max([xy_magnitude,za_magnitude], axis=0)
    compensation_factor = total_4d_magnitude / max_independent_magnitude
    return compensation_factor