from warnings import deprecated
import numpy as np
from typing import Callable, TYPE_CHECKING

from ._airfoil import Airfoil

def calculated_wing_cube_loading(weight, area):
    """TODO: check the documentation below:
    
    Note that I think switching between (kg, m**2) vs (pounds, ft**2) happens not to make much difference in the result.
    The final number is supposed to be unitless anyway

    this just helps calculate weight/area**1.5 and accounts for the non linear scaling of lift to airplane size
    """
    return weight/area**1.5

def angle_degrees_to_slope(angle_degrees:float):
    return np.tan(np.deg2rad(angle_degrees))

@deprecated("Use auto_piecewise or auto_interpolate")
def compound_dihedral_rise(x_b:float, dihedral:float, compound_dihedral:float, compound_break:float):
    return np.where(np.abs(x_b)<compound_break,
        np.abs(x_b) * angle_degrees_to_slope(dihedral),
        compound_break * angle_degrees_to_slope(dihedral) + (np.abs(x_b)-compound_break)*angle_degrees_to_slope(compound_dihedral)
    )

def auto_piecewise(funcs: list[tuple[float, Callable[[float],float]]]):
    """Create a function that samples a list of functions.
    The first function alway's starts from `x=0`. Each function must be specified 
    with the upper limit of its domain in a list of tuples like:

    ```python
    f = auto_piecewise([
        (10, lambda x: x*0.5  + 5),    
        (20, lambda x: x*2.0 - 1),
    ])
    ```

    in the example above the result `f` will start at a y-intercept of 5 and have a slope of 0.5
    from 0 to 10 followed by a slope of 2.0 from 10 to 20.
    The function will be automatically continuous at `x=10`
    
    To ensure the result is a continuous function, the following rules are applied:
    - Each function is evaluated as if from `x = 0` to `x = o_n - o_{n-1}`
      where `o_n` os the upper limit specified for the `n`th function
      - This makes it easier to design the curve you need without offsetting the function to match the end of the last function
    - The y-intercept is discarded for all functions except the first.
      i.e. the output of the function is automatically vertically offset so
      the end of the last segment matches the beginning of the next.
    
    The resulting function returns `None` if the input is larger than the last limit. 
    """
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
    """Mirror a function over the Y-axis by injecting `func(abs(x))`"""
    return lambda x: func(np.abs(x))

def ellipse_quadrant(rx:float, ry:float, x:float):
    theta = np.arccos(x/rx)
    return ry * np.sin(theta)

def calculate_wing_area(x, leading_edge, trailing_edge):
    v = leading_edge-trailing_edge
    return (np.diff(x) * (v[1:]+v[:-1])/2).sum()

def auto_interpolate(points):
    """creates a function that wraps `np.interp()` where `points` must be in the shape (n,2) where n is the number of points.
    """
    return lambda x: np.interp(x, *np.array(points).T)

def create_airfoil_sampler(
    airfoil         : Callable[[float], Airfoil],
    leading_edge    : Callable[[float], float],
    dihedral        : Callable[[float], float],
    chord           : Callable[[float], float],
    washout         : Callable[[float], float],
    rotation_center : Callable[[float], float],
) -> Callable[[float], Airfoil]:
    return lambda x: (
        airfoil(x)
        .with_chord(chord(x))
        .with_translation((-rotation_center(x),0))
        .with_rotation(washout(x))
        .with_translation((rotation_center(x),0))
        .with_translation((-leading_edge(x), dihedral(x)))
    )
