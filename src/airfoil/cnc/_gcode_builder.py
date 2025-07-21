from __future__ import annotations
from typing import Callable, Iterable
from dataclasses import dataclass, field

@dataclass
class GCodeBuilder:
    
    lines:list[str] = field(default_factory=list)

    def home(self) -> GCodeBuilder:
        self.lines.append("$H")
        return self
    
    def travel(self, x:float, y:float, z:float, a:float) -> GCodeBuilder:
        """`G0`"""
        self.lines.append(f"G0 X{x:.2f} Y{y:.2f} Z{z:.2f} A{a:.2f}")
        return self
    
    def absolute(self) -> GCodeBuilder:
        """`G90`"""
        self.lines.append(f"G90")
        return self
    
    def relative(self) -> GCodeBuilder:
        """`G91`"""
        self.lines.append(f"G91")
        return self
    
    def linear_move_with_feedrate(self, feed_rate:float, x:float, y:float, z:float, a:float) -> GCodeBuilder:
        """
        `G1 F# X# Y# Z# A#`

        NOTE: Feedrate is not compensated for 4 axis movement. this specifies the speed in 4D space.
        """
        self.lines.append(f"G1 F{feed_rate} X{x:.2f} Y{y:.2f} Z{z:.2f} A{a:.2f}")
        return self
    
    def set_feedrate(self, feed_rate:float) -> GCodeBuilder:
        """
        `G1 F#`

        NOTE: Feedrate is not compensated for 4 axis movement. this specifies the speed in 4D space.
        """
        self.lines.append(f"G1 F{feed_rate}")
        return self
    
    def linear_move(self, x:float, y:float, z:float, a:float) -> GCodeBuilder:
        """
        `G1 X# Y# Z# A#`
        """
        self.lines.append(f"G1 X{x:.2f} Y{y:.2f} Z{z:.2f} A{a:.2f}")
        return self
    
    def set_position(self, x:float, y:float, z:float, a:float) -> GCodeBuilder:
        """`G92`

        Set the position without moving the machine
        """
        self.lines.append(f"G92 X{x:.2f} Y{y:.2f} Z{z:.2f} A{a:.2f}")
        return self
    
    def metric(self) -> GCodeBuilder:
        self.lines.append("G21")
        return self
    
    def set_current(self, current:float) -> GCodeBuilder:
        """`M3 S???`
        current should be between 0.0 and 4.0 Amps"""
        MAX = 4
        MIN = 0
        if current<=MIN:
            self.lines.append("M3 S5")
        else:
            portion = (current-MIN)/(MAX-MIN)
            pwm_percent = (portion*0.8+0.1)*100
            self.lines.append(f"M3 S{pwm_percent:.1f}")
        return self
    
    def wrap_zero_current(self, block:Callable[[GCodeBuilder],GCodeBuilder]) -> GCodeBuilder:
        self.set_current(0)
        self.lines.extend(block(GCodeBuilder()).lines)
        self.set_current(0)
        return self

    def alarm_clear(self) -> GCodeBuilder:
        self.lines.append("$X")
        return self
    
    def alarm_soft_reset(self) -> GCodeBuilder:
        self.lines.append("\x18")
        return self
    
    def build(self) -> str:
        result = "\r\n".join(self.lines)
        return result

    def for_each[T](self, iterable:Iterable[T], func:Callable[[GCodeBuilder,T],GCodeBuilder])->GCodeBuilder:
        for item in iterable:
            self.lines.extend(func(GCodeBuilder(), item).lines)
        return self

