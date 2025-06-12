import numpy as np

def wing_cube_loading(weight, area):
    """Note that switching between kg and m2 vs pounds and ft^2 happens not to make much difference in the result.
    The final number is supposed to be unit-ess anyway
    """
    return weight/area**1.5

def _angle_slope(x_b:float, angle:float):
    return np.abs(x_b) * np.tan(np.deg2rad(angle))

def compound_dihedral_rise(x_b:float, dihedral:float, compound_dihedral:float, compound_break:float):
    return np.where(np.abs(x_b)<compound_break,
        _angle_slope(x_b, dihedral),
        _angle_slope(compound_break, dihedral) + _angle_slope(np.abs(x_b)-compound_break, compound_dihedral)
    )