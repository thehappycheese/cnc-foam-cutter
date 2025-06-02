import re
from typing import Union, Callable
from ._naca4 import naca4
from ._naca5 import naca5

def parse_naca(designation: str) -> Callable:
    """
    Parse NACA airfoil designation string and return appropriate airfoil generator function.
    
    Supported formats:
    - NACA 4-digit: "NACA2412", "2412" -> max_thickness=0.12, max_camber=0.02, max_camber_position=0.4
    - NACA 5-digit: "NACA23012", "23012" -> design_cl=0.3, max_camber_pos=0.15, max_thickness=0.12
    - NACA 5-digit reflex: "NACA23112", "23112" -> reflex airfoil with design_cl=0.3, max_camber_pos=0.15, max_thickness=0.12
    
    Parameters:
    - designation: NACA designation string (case insensitive)
    
    Returns:
    - Callable airfoil generator function
    
    Raises:
    - ValueError: If designation format is invalid or parameters are out of range
    """
    # Clean and normalize input
    designation = designation.upper().strip()
    designation = re.sub(r'^NACA\s*', '', designation)  # Remove "NACA" prefix if present
    
    # Remove any spaces or hyphens
    designation = re.sub(r'[\s\-]', '', designation)
    
    if not designation.isdigit():
        raise ValueError(f"Invalid NACA designation: must contain only digits, got '{designation}'")
    
    if len(designation) == 4:
        return _parse_naca4(designation)
    elif len(designation) == 5:
        return _parse_naca5(designation)
    else:
        raise ValueError(f"Invalid NACA designation length: expected 4 or 5 digits, got {len(designation)} digits")

def _parse_naca4(designation: str) -> Callable:
    """Parse 4-digit NACA designation"""
    if len(designation) != 4:
        raise ValueError(f"NACA 4-digit designation must be exactly 4 digits, got {len(designation)}")
    
    try:
        # Extract digits
        m_digit = int(designation[0])  # Maximum camber in percent of chord
        p_digit = int(designation[1])  # Position of maximum camber in tenths of chord
        tt_digits = int(designation[2:4])  # Maximum thickness in percent of chord
        
        # Convert to decimal values
        max_camber = m_digit / 100.0
        max_camber_position = p_digit / 10.0 if p_digit > 0 else 0.01  # Avoid division by zero
        max_thickness = tt_digits / 100.0
        
        # Validate parameters
        if max_thickness < 0.01 or max_thickness > 0.3:
            raise ValueError(f"Maximum thickness {max_thickness:.3f} out of range [0.01, 0.3]")
        
        if max_camber > 0 and (max_camber_position <= 0 or max_camber_position >= 1):
            raise ValueError(f"Maximum camber position {max_camber_position:.2f} out of range (0, 1)")
        
        return naca4(max_thickness, max_camber, max_camber_position)
        
    except (ValueError, IndexError) as e:
        raise ValueError(f"Invalid NACA 4-digit designation '{designation}': {str(e)}")

def _parse_naca5(designation: str) -> Callable:
    """Parse 5-digit NACA designation"""
    if len(designation) != 5:
        raise ValueError(f"NACA 5-digit designation must be exactly 5 digits, got {len(designation)}")
    
    try:
        # Extract digits
        l_digit = int(designation[0])    # Design lift coefficient * 20/3
        p_digit = int(designation[1])    # Position of maximum camber in twentieths of chord
        q_digit = int(designation[2])    # Reflex indicator (0=standard, 1=reflex)
        tt_digits = int(designation[3:5])  # Maximum thickness in percent of chord
        
        # Convert to decimal values
        design_lift_coefficient = l_digit * 3.0 / 20.0
        max_camber_position = p_digit / 20.0
        max_thickness = tt_digits / 100.0
        
        # Determine airfoil type
        if q_digit == 0:
            airfoil_type = "standard"
        elif q_digit == 1:
            airfoil_type = "reflex"
        else:
            raise ValueError(f"Invalid reflex indicator digit '{q_digit}': must be 0 (standard) or 1 (reflex)")
        
        # Validate parameters
        if design_lift_coefficient < 0.05 or design_lift_coefficient > 1.0:
            raise ValueError(f"Design lift coefficient {design_lift_coefficient:.3f} out of range [0.05, 1.0]")
        
        if max_camber_position < 0.05 or max_camber_position > 0.95:
            raise ValueError(f"Maximum camber position {max_camber_position:.3f} out of range [0.05, 0.95]")
        
        if max_thickness < 0.01 or max_thickness > 0.3:
            raise ValueError(f"Maximum thickness {max_thickness:.3f} out of range [0.01, 0.3]")
        
        return naca5(airfoil_type, design_lift_coefficient, max_camber_position, max_thickness)
        
    except (ValueError, IndexError) as e:
        raise ValueError(f"Invalid NACA 5-digit designation '{designation}': {str(e)}")

def naca_info(designation: str) -> dict:
    """
    Parse NACA designation and return parameter information without creating the airfoil.
    
    Parameters:
    - designation: NACA designation string
    
    Returns:
    - Dictionary containing parsed parameters and airfoil type information
    """
    # Clean and normalize input
    original_designation = designation
    designation = designation.upper().strip()
    designation = re.sub(r'^NACA\s*', '', designation)
    designation = re.sub(r'[\s\-]', '', designation)
    
    if not designation.isdigit():
        raise ValueError(f"Invalid NACA designation: must contain only digits")
    
    info = {
        'original_designation': original_designation,
        'cleaned_designation': designation,
        'series': None,
        'parameters': {}
    }
    
    if len(designation) == 4:
        info['series'] = 'NACA 4-digit'
        m_digit = int(designation[0])
        p_digit = int(designation[1])
        tt_digits = int(designation[2:4])
        
        info['parameters'] = {
            'max_camber': m_digit / 100.0,
            'max_camber_position': p_digit / 10.0 if p_digit > 0 else 0.01,
            'max_thickness': tt_digits / 100.0,
            'is_symmetric': m_digit == 0
        }
        
    elif len(designation) == 5:
        info['series'] = 'NACA 5-digit'
        l_digit = int(designation[0])
        p_digit = int(designation[1])
        q_digit = int(designation[2])
        tt_digits = int(designation[3:5])
        
        info['parameters'] = {
            'design_lift_coefficient': l_digit * 3.0 / 20.0,
            'max_camber_position': p_digit / 20.0,
            'max_thickness': tt_digits / 100.0,
            'type': 'reflex' if q_digit == 1 else 'standard',
            'is_reflex': q_digit == 1
        }
        
    else:
        raise ValueError(f"Invalid NACA designation length: expected 4 or 5 digits")
    
    return info

# Convenience function for quick airfoil generation
def naca(designation: str, n_points: int = 200) -> tuple:
    """
    Quick function to generate NACA airfoil coordinates from designation string.
    
    Parameters:
    - designation: NACA designation string
    - n_points: Number of points to generate (default: 200)
    
    Returns:
    - Tuple of (upper_surface, lower_surface) coordinate arrays
    """
    airfoil_generator = parse_naca(designation)
    return airfoil_generator(n_points)