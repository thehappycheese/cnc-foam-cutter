from warnings import deprecated
import numpy as np
from typing import Callable

def calculated_wing_cube_loading(weight, area):
    """TODO: check the documentation below:
    
    Note that I think switching between (kg, m**2) vs (pounds, ft**2) happens not to make much difference in the result.
    The final number is supposed to be unitless anyway

    this just helps calculate weight/area**1.5 and accounts for the non linear scaling of lift to airplane size
    """
    return weight/area**1.5

@deprecated("Please use angle_degrees_to_slope() directly")
def sample_angle_degrees_to_slope(x_b:float, angle_degrees:float):
    return x_b * angle_degrees_to_slope()

def angle_degrees_to_slope(angle_degrees:float):
    return np.tan(np.deg2rad(angle_degrees))

def compound_dihedral_rise(x_b:float, dihedral:float, compound_dihedral:float, compound_break:float):
    return np.where(np.abs(x_b)<compound_break,
        np.abs(x_b) * angle_degrees_to_slope(dihedral),
        compound_break * angle_degrees_to_slope(dihedral) + (np.abs(x_b)-compound_break)*angle_degrees_to_slope(compound_dihedral)
    )

def auto_piecewise(funcs: list[tuple[float, Callable[[float],float]]]):
    def _inner_auto_piecewise(x:float):
        offset_y = 0
        offset_x = 0
        for index, (limit, func) in enumerate(funcs):
            f0 = 0 if index==0 else func(0)
            if x<=limit:
                return offset_y + func(x-offset_x)-f0
            else:
                offset_y+=func(limit-offset_x)-f0
                offset_x=limit
    return _inner_auto_piecewise

def mirror(func:Callable[[float],float]):
    return lambda x: func(np.abs(x))

def ellipse_quadrant(rx:float, ry:float, x:float):
    theta = np.arccos(x/rx)
    return ry * np.sin(theta)

def calculate_wing_area(x, leading_edge, trailing_edge):
    v = leading_edge-trailing_edge
    return (np.diff(x) * (v[1:]+v[:-1])/2).sum()

def auto_interpolate(points):
    return lambda x: np.interp(x, *np.array(points).T)
