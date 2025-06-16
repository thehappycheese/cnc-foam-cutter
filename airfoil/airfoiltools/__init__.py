import numpy as np

import requests
from .._airfoil import Airfoil


def get_foil(reference:str)->Airfoil:

    response = requests.get(f"http://airfoiltools.com/airfoil/seligdatfile?airfoil={reference}")
    name, *coord_lines = response.text.strip().splitlines()
    return Airfoil(
        points=np.array([list(map(float, item.strip().replace("  ", " ").split(" "))) for item in coord_lines])
    )