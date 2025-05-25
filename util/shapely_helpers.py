from pathlib import Path
from shapely.geometry.base import BaseGeometry

from .gatekept_itertools import split_indexable, sliding_window
import numpy as np

def shapely_to_svg(shape:BaseGeometry, output:Path|str):
    output_path = Path(output)
    output_path.write_text(
    f"""<svg version="1.1" xmlns="http://www.w3.org/2000/svg" xmlns:xlink= "http://www.w3.org/1999/xlink">
    {shape.svg()}
    </svg>
    """)

def split_linestring_by_angle(arr:np.ndarray, split_angle_deg:float=70)->list[np.ndarray]:
    arr_length, arr_dimentions = arr.shape
    assert arr_length>1
    assert arr_dimentions ==2
    angles = []
    lengths = []
    for [a,b,c] in sliding_window(arr, 3):
        ba = (a-b)/np.linalg.norm(a-b)
        cb = (b-c)/np.linalg.norm(b-c)
        lengths.append(np.linalg.norm(a-b))
        angles.append(np.acos(np.dot(ba, cb)))

    chunks = split_indexable(
        arr,
        np.where(abs(np.array(angles))>np.deg2rad(split_angle_deg))[0]+1
    )
    return chunks