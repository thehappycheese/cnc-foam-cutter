import numpy as np

def compensate_feedrate(dx, dy, dz, da):
    """GRBL control systems will (should?) interpret 4-axis feed-rate in 4D space.
    This makes our two toolheads move unexpectedly slowly.

    This function takes a planned relative movement of the toolhead and returns a compensation factor.

    ```python
    desired_feedrate = 500
    compensated_feedrate = desired_feedrate * compensate_feedrate(100,0,100,0)
    cnc.feed(compensated_feedrate, 100,0,100,0)
    ```

    This function returns the ratio between the maximum magnitude of XY and ZA toolheads and the magnitude of the vector
    XYZA.
    This roughly aims to move both toolheads at a speed as high as possible without either exceeding the specified feedrate."""
    xy_magnitude = np.sqrt(dx**2 + dy**2)
    za_magnitude = np.sqrt(dz**2 + da**2)
    total_4d_magnitude = np.sqrt(dx**2 + dy**2 + dz**2 + da**2)
    max_independent_magnitude = np.max([xy_magnitude,za_magnitude], axis=0)
    compensation_factor = total_4d_magnitude / max_independent_magnitude
    return compensation_factor
