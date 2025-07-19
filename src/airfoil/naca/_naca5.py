from typing import Literal
import numpy as np
from ._naca4 import naca4_thickness
from scipy.interpolate import interp1d

def naca5_camber_standard(x, k1, r):
    """Camber (standard) combining front and back sections"""
    y_c = np.choose(
        x < r,
        [
            (k1 * r**3 / 6) * (1 - x),  # back: r ≤ x ≤ 1
            (k1 / 6) * (x**3 - 3*r*x**2 + r**2*(3 - r)*x)  # front: 0 ≤ x < r
        ]
    )
    return y_c

def naca5_gradient_standard(x, k1, r):
    """Gradient dy_c/dx for standard camber combining front and back sections"""
    dy_c_dx = np.choose(
        x < r,
        [
            -(k1 * r**3 / 6),  # back: constant gradient
            (k1 / 6) * (3*x**2 - 6*r*x + r**2*(3 - r))  # front: variable gradient
        ]
    )
    return dy_c_dx

def naca5_camber_reflex(x, k1, k2_k1, r):
    """Camber (reflex) combining front and back sections"""
    y_c = np.choose(
        x < r,
        [
            (k1 / 6) * (k2_k1*(x - r)**3 - k2_k1*(1 - r)**3*x - r**3*x + r**3),  # back: r ≤ x ≤ 1
            (k1 / 6) * ((x - r)**3 - k2_k1*(1 - r)**3*x - r**3*x + r**3)  # front: 0 ≤ x < r
        ]
    )
    return y_c

def naca5_gradient_reflex(x, k1, k2_k1, r):
    """Gradient dy_c/dx for reflex camber combining front and back sections"""
    dy_c_dx = np.choose(
        x < r,
        [
            (k1 / 6) * (3*k2_k1*(x - r)**2 - k2_k1*(1 - r)**3 - r**3),  # back: r ≤ x ≤ 1
            (k1 / 6) * (3*(x - r)**2 - k2_k1*(1 - r)**3 - r**3)  # front: 0 ≤ x < r
        ]
    )
    return dy_c_dx


# Lookup tables for NACA5 parameters (design CL = 0.3)
NACA5_STANDARD_TABLE = {
    'p': np.array([0.05, 0.10, 0.15, 0.20, 0.25]),
    'r': np.array([0.0580, 0.126, 0.2025, 0.290, 0.391]),
    'k1': np.array([361.40, 51.640, 15.957, 6.643, 3.230])
}
NACA5_REFLEX_TABLE = {
    'p': np.array([0.10, 0.15, 0.20, 0.25]),
    'r': np.array([0.130, 0.217, 0.318, 0.441]),
    'k1': np.array([51.990, 15.793, 6.520, 3.191]),
    'k2_k1': np.array([0.000764, 0.00677, 0.0303, 0.1355])
}

def get_naca5_parameters(type: Literal["standard","reflex"], camber_position: float, design_lift_coefficient: float = 0.3):
    """
    Get NACA5 parameters using lookup tables with interpolation and proper scaling.
    
    Parameters:
    - type: "standard" or "reflex"
    - camber_position: position of maximum camber (p)
    - design_lift_coefficient: design lift coefficient for scaling
    
    Returns:
    - r: position parameter
    - k1: first camber parameter (scaled)
    - k2_k1: second camber parameter ratio (reflex only, scaled)
    """
    # Scale factor for design lift coefficient (tables are for CL = 0.3)
    scale_factor = design_lift_coefficient / 0.3
    
    if type == "standard":
        table = NACA5_STANDARD_TABLE
        
        # Check bounds
        p_min, p_max = table['p'][0], table['p'][-1]
        if camber_position < p_min or camber_position > p_max:
            raise ValueError(f"camber_position must be between {p_min} and {p_max} for standard profiles")
        
        # Interpolate parameters
        r_interp = interp1d(table['p'], table['r'], kind='linear')
        k1_interp = interp1d(table['p'], table['k1'], kind='linear')
        
        r = float(r_interp(camber_position))
        k1 = float(k1_interp(camber_position)) * scale_factor
        k2_k1 = None
        
    elif type == "reflex":
        table = NACA5_REFLEX_TABLE
        
        # Check bounds
        p_min, p_max = table['p'][0], table['p'][-1]
        if camber_position < p_min or camber_position > p_max:
            raise ValueError(f"camber_position must be between {p_min} and {p_max} for reflex profiles")
        
        # Interpolate parameters
        r_interp = interp1d(table['p'], table['r'], kind='linear')
        k1_interp = interp1d(table['p'], table['k1'], kind='linear')
        k2_k1_interp = interp1d(table['p'], table['k2_k1'], kind='linear')
        
        r = float(r_interp(camber_position))
        k1 = float(k1_interp(camber_position)) * scale_factor
        k2_k1 = float(k2_k1_interp(camber_position)) * scale_factor
        
    else:
        raise ValueError("invalid type parameter")
    
    return r, k1, k2_k1

def naca5_camber(x: np.ndarray, type: Literal["standard","reflex"], k1: float, r: float, k2_k1: float|None = None) -> np.ndarray:
    """Calculate NACA5 camber line"""
    if type == "standard":
        return naca5_camber_standard(x, k1, r)
    elif type == "reflex":
        return naca5_camber_reflex(x, k1, k2_k1, r)
    else:
        raise ValueError("invalid type parameter")

def naca5_camber_dyc_dx(x: np.ndarray, type: Literal["standard","reflex"], k1: float, r: float, k2_k1: float|None = None) -> np.ndarray:
    """Calculate NACA5 camber gradient dy_c/dx"""
    if type == "standard":
        return naca5_gradient_standard(x, k1, r)
    elif type == "reflex":
        return naca5_gradient_reflex(x, k1, k2_k1, r)
    else:
        raise ValueError("invalid type parameter")

def naca5(
    type: Literal["standard","reflex"],
    design_lift_coefficient: float,
    max_camber_position: float,
    max_thickness: float,
):
    """
    Generate NACA5 airfoil coordinates
    
    Parameters:
    - type: "standard" or "reflex" camber type
    - design_lift_coefficient: design lift coefficient (0.05 to 1.0)
    - max_camber_position: position of maximum camber (0.05 to 0.95)
    - max_thickness: maximum thickness as fraction of chord
    """
    assert 0.05 <= design_lift_coefficient <= 1.00, "design_lift_coefficient must be between 0.05 and 1.0"
    assert 0.01 <= max_thickness <= 0.3, "maximum thickness must be between 0.01 and 0.3"
    assert 0.05 <= max_camber_position <= 0.95, "max_camber_position must be between 0.05 and 0.95"
    
    # Get NACA5 parameters
    r, k1, k2_k1 = get_naca5_parameters(type, max_camber_position, design_lift_coefficient)
    
    def _naca5(n: int = 200) -> tuple[np.ndarray, np.ndarray]:
        beta = np.linspace(0, np.pi, n)
        x = 0.5 * (1 - np.cos(beta))
        #x = np.linspace(0,1,n)
        
        thickness = naca4_thickness(x, max_thickness=max_thickness)
        
        camber = naca5_camber(x, type, k1, r, k2_k1)
        
        dyc_dx = naca5_camber_dyc_dx(x, type, k1, r, k2_k1)
        
        theta = np.arctan(dyc_dx)
        
        upper_x = x - thickness * np.sin(theta)
        upper_y = camber + thickness * np.cos(theta)
        lower_x = x + thickness * np.sin(theta)
        lower_y = camber - thickness * np.cos(theta)
        
        return (
            np.vstack([upper_x, upper_y]).transpose(),
            np.vstack([lower_x, lower_y]).transpose(),
        )
    
    return _naca5