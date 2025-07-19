from itertools import pairwise
import numpy as np
from dataclasses import dataclass
from airfoil import Airfoil, WingSegment
import matplotlib.pyplot as plt
import matplotlib.ticker as ticker

@dataclass
class SpitfireWing:
    half_span:float = 500
    dihedral_deg:float = 4
    washout_deg:float = 2
    
    def root_chord_centerline(self):
        return 100.0 / 222.5 * self.half_span
    
    def front_spar_from_leading_edge(self):
        return 24.5 / 222.5 * self.half_span
    
    def wing_axis_from_leading_edge(self):
        return 35.5 / 222.5 * self.half_span
    
    def flap_line(self, span_x:float)->float:
        return -0.2*span_x+120
    
    def leading_edge(self):
        return self._ellipse_quadrant(self.half_span, self.wing_axis_from_leading_edge(), num_points=50) * np.array([1,-1])
    
    def trailing_edge(self):
        return self._ellipse_quadrant(self.half_span, self.root_chord_centerline()-self.wing_axis_from_leading_edge(), num_points=50)
    
    def plot(self, section_positions:list[float]|None=None):
        leading_edge  = self.leading_edge()
        trailing_edge = self.trailing_edge()
        
        spar_y_position = -self.wing_axis_from_leading_edge() + self.front_spar_from_leading_edge()
        
        span_x = np.linspace(0,self.half_span)
        flap_line = self.flap_line(span_x)

        # Plot to visualize\
        if section_positions is not None:
            fig, axs = plt.subplots(2,1, figsize=(9,8))
            ax = axs[0]
            for pos in section_positions:
                ax.axvline(pos)
            for airfoil in self.create_airfoils(section_positions=section_positions):
                airfoil.plot_raw(ax=axs[1])
            axs[1].xaxis.set_major_locator(ticker.MultipleLocator(10.0))
            axs[1].yaxis.set_major_locator(ticker.MultipleLocator( 5.0))
            axs[1].grid()
        else:
            fig, ax = plt.subplots(figsize=(6,4))
        ax.plot(span_x, flap_line)
        ax.plot(*leading_edge.transpose(), '-o', markersize=3, label="Leading Edge")
        ax.plot(*trailing_edge.transpose(), '-o', markersize=3, label="Trailing Edge")
        ax.plot([0, self.half_span/2], [spar_y_position, spar_y_position], label="Front Spar")
        
        ax.legend()
        ax.grid(True)
        ax.axis('equal')
        ax.invert_yaxis()
        fig.tight_layout()
        
    
    def _ellipse_quadrant(self, rx, ry, num_points=100):
        # Semi-major and semi-minor axes
        a = rx
        b = ry
        theta = np.linspace(0, np.pi/2, num_points)
        # Parametric equations for ellipse
        x = a * np.cos(theta)
        y = b * np.sin(theta)
        
        return np.array([x, y]).transpose()
    
    def local_chord_length(self, span_x: float):
        return self.root_chord_centerline() * np.sqrt(1 - 4 * (span_x / (self.half_span * 2))**2)
    
    def local_chord_setback(self, span_x: float):
        leading_edge = self.leading_edge() * np.array([1,-1])
        return np.interp(span_x, *leading_edge[::-1].transpose())
    
    def local_thickness(self, span_x):
        # Should be changed a bit;
        # 13% to 9% where the outboard measurement of aurfoil thickness is taken at 160 from root
        return (0.13 - 0.09) * span_x / self.half_span + 0.09
    
    def local_washbout(self, span_x):
        span_fraction = span_x / self.half_span
        return -span_fraction * self.washout_deg

    def local_airfoil(self, span_x):
        rotation_center = -self.local_chord_length(span_x) * 0.2
        wing_slope = np.tan(np.deg2rad(self.dihedral_deg))
        af = (
            Airfoil.from_naca4(
                max_camber=0.02,
                max_camber_position=0.2,
                max_thickness=self.local_thickness(span_x),
                chord_length=self.local_chord_length(span_x),
            )
            .with_translation((-rotation_center, 0))
            .with_rotation(self.local_washbout(span_x))
            .with_translation((rotation_center, 0))
            .with_translation(
                (
                    #self.wing_axis_from_leading_edge() 
                    - self.local_chord_setback(span_x),
                    wing_slope * span_x
                )
            )
        )
        return af
    
    def create_airfoils(self, section_positions: list[float|int])->list[Airfoil]:
        results = []
        for section_position in section_positions:
            results.append(self.local_airfoil(section_position))
        return results
    
    def create_segments(
        self,
        section_positions:list[float|int],
    )->list[WingSegment]:
        segments = []
        for (posa,a), (posb, b) in pairwise(zip(section_positions, self.create_airfoils(section_positions=section_positions))):
            segments.append(WingSegment(a,b,posb-posa))
        return segments
