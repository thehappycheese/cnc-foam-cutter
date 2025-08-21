from warnings import deprecated
import numpy as np
from typing import Callable

from ._airfoil import Airfoil

def calculated_wing_cube_loading(weight, area):
    """TODO: check the documentation below:
    
    Note that I think switching between (kg, m**2) vs (pounds, ft**2) happens not to make much difference in the result.
    The final number is supposed to be unitless anyway

    this just helps calculate weight/area**1.5 and accounts for the non linear scaling of lift to airplane size
    """
    return weight/area**1.5

def angle_degrees_to_slope(angle_degrees:float):
    """`tan(angle_degrees / 180 * PI)` this is just a dumb wrapper for the `np.tan(np.deg2rad())` functions"""
    return np.tan(np.deg2rad(angle_degrees))

def auto_piecewise(funcs: list[tuple[float, Callable[[float],float]]]):
    """Create a function that samples a list of functions.

    The first function is evaluated normally, then subsequent functions are
    evaluated with special rules to ensure the output is continuous (see below)

    Each function must be specified with the upper limit of its domain
    in a list of tuples like the following example:

    ```python
    f = auto_piecewise([
        (10, lambda x: x*0.5 + 5), # f1 [ 0, 10]
        (20, lambda x: x*2.0    ), # f2 (10, 20]
        (25, lambda x: -x**2    ), # f3 (20, 25]
    ])
    ```

    ```text
    30-|           ..
       |          .   .
       |         .     .
       |        .      .
    10-|       .        .
       |   ...          .
     5-|...              .
       |                 
       |
       |
     0-|-------------------
             10      20  25
    ```

    In the example above

    - the function `f(x)` is defined from x=0 to x=20 (sampling outside this range returns None) 
    - `f` will have a y-intercept of 5
    - `f` will have a slope of 0.5 from 0 to 10
    - `f` will have a slope of 2.0 from 10 to 20
    - `f` will have a slope of -2*(x-20) from 20 to 25
    - `f` will be automatically continuous at `x=10` and `x=20`
    
    To ensure the result is a continuous function, the following rules are applied:
    - Each function is evaluated as if from `x = 0` to `x = o_n - o_{n-1}`
      where `o_n` os the upper limit specified for the `n`th function
      - This makes it easier to design the curve you need without manually 
        offsetting the function to match the end of the last function
    - The y-intercept is discarded for all functions except the first.
      i.e. the output of the function is automatically vertically offset so
      the end of the last segment matches the beginning of the next.
    """
    def _inner_auto_piecewise(x:float):
        if x<0:
            return np.nan
        offset_y = 0
        offset_x = 0
        for index, (limit, func) in enumerate(funcs):
            f0 = 0 if index==0 else func(0)
            if x<=limit:
                return offset_y + func(x-offset_x)-f0
            else:
                offset_y+=func(limit-offset_x)-f0
                offset_x=limit
        return np.nan
    return np.vectorize(_inner_auto_piecewise)

def mirror[T](func:Callable[[float],T]):
    """Mirror a function over the Y-axis by injecting `func(abs(x))`"""
    return lambda x: func(np.abs(x))

def ellipse_quadrant(rx:float, ry:float, x:float):
    """Positive quadrant of an ellipse centered at the origin as a function of x.
    Caller must ensure that `x x>=0 and x>=rx` or `np.nan` values will be returned without warning"""
    theta = np.arccos(x/rx)
    return ry * np.sin(theta)

def auto_interpolate(points)->Callable[[float],float]:
    """Returns a new function that interpolates between a list of `n` points where
    `points` must be in the shape (n,2)

    `points` must be ordered such that x-coordinates are strictly increasing.
    
    ```python
    f = auto_interpolate([
        (0, 1),
        (8, 5)
    ])
    f(4)  # interpolates between (0,1) and (8,5) at x=4
    ```

    >>> 3.0
    
    This is a convenience wrapper for that `np.interp` like     
    `return lambda x: np.interp(x, *np.array(points).T)`
    """
    return lambda x: np.interp(x, *np.array(points).T)

@deprecated("Use Airfoil.create_sampler instead")
def create_airfoil_sampler(
    airfoil         : Callable[[float], Airfoil],
    leading_edge    : Callable[[float], float] = lambda x: 0,
    dihedral        : Callable[[float], float] = lambda x: 0,
    chord           : Callable[[float], float] = lambda x: 100,
    washout         : Callable[[float], float] = lambda x: 0,
    rotation_center : Callable[[float], float] = lambda x: 0,
) -> Callable[[float], Airfoil]:
    return lambda x: (
        airfoil(x)
        .with_chord(chord(x))
        .with_translation((-rotation_center(x),0))
        .with_rotation(washout(x))
        .with_translation((rotation_center(x),0))
        .with_translation((-leading_edge(x), dihedral(x)))
    )
