import numpy as np

def naca4_camber(x:np.ndarray, max_camber_position:float, max_camber:float) -> np.ndarray:
    p = max_camber_position
    m = max_camber
    return np.choose(
        x<p, 
        [
            m / (1-p)**2 * (1 - 2*p+2*p*x - x**2),
            m / p**2 * (2*p*x - x**2),
        ]
    )

def naca4_camber_dyc_dx(x:np.ndarray, max_camber_position:float, max_camber:float)->np.ndarray:
    p = max_camber_position
    m = max_camber
    return np.choose(
        x<p, 
        [
            m * (2*p-2*x)/(1-p)**2,
            m * (2*p-2*x)/p**2,
        ]
    )

def naca4_thickness(x:np.ndarray, max_thickness:float) -> np.ndarray:
    t = max_thickness
    return t/0.2*(0.2969*np.sqrt(x) - 0.1260*x-0.3516*x**2 + 0.2843*x**3 - 0.1015*x**4)

def naca4 (max_thickness:float, max_camber:float, max_camber_position:float):
    """
    based on https://web.stanford.edu/~cantwell/AA200_Course_Material/The%20NACA%20airfoil%20series.pdf
    """
    
    def _naca4(n:int=200)->tuple[np.ndarray,np.ndarray]:
        beta = np.linspace(0, np.pi, n)
        x = 0.5 * (1 - np.cos(beta))
        #x = np.linspace(0,1,n)
        thickness = naca4_thickness(
            x,
            max_thickness=max_thickness
        )
        if max_camber==0:
            camber = np.zeros_like(x)
            dyc_dx = np.zeros_like(x)
        else:
            camber    = naca4_camber(
                x,
                max_camber_position=max_camber_position,
                max_camber=max_camber
            )
            dyc_dx     = naca4_camber_dyc_dx(
                x,
                max_camber_position=max_camber_position,
                max_camber=max_camber
            )
        theta     = np.arctan(dyc_dx)
        upper_x = x      - thickness*np.sin(theta)
        upper_y = camber + thickness*np.cos(theta)
        lower_x = x      + thickness*np.sin(theta)
        lower_y = camber - thickness*np.cos(theta)
        return (
            np.vstack([upper_x,upper_y]).transpose(),
            np.vstack([lower_x,lower_y]).transpose(),
        )
    return _naca4
