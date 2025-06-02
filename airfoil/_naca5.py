from typing import Literal
import numpy as np
from ._naca4 import naca4_thickness

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



def get_naca5_parameters(type:Literal["standard","reflex"], camber_position:float):
    p = camber_position
    if type=="standard":
        r = (3.33333333333212 * p**3 + 0.700000000000909 * p**2 + 1.19666666666638 * p - 0.00399999999996247)
        k1 = (1514933.33335235 * p**4 - 1087744.00001147 * p**3 + 286455.266669048 * p**2 - 32968.4700001967 * p + 1420.18500000524)
        k2_k1 = None
    elif type=="reflex":
        r = (10.6666666666861 * p**3 - 2.00000000001601 * p**2 + 1.73333333333684 * p - 0.0340000000002413)
        k1 = (-27973.3333333385 * p**3 + 17972.8000000027 * p**2 - 3888.40666666711 * p + 289.076000000022)
        k2_k1 = (85.5279999999984 * p**3 - 34.9828000000004 * p**2 + 4.80324000000028 * p - 0.21526000000003)
    else:
        raise ValueError("invalid type parameter")
    
    return r,k1,k2_k1

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
    r, k1, k2_k1 = get_naca5_parameters(type, max_camber_position)
    
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