"""Just import `naca` which parses NACA string specifiers/designations.

`naca4` and `naca5` offer named argument alternatives.

Other NACA serieses are not currently supported.
"""

from airfoil.naca._naca_parse import naca, naca_info
from airfoil.naca._naca4 import naca4
from airfoil.naca._naca5 import naca5