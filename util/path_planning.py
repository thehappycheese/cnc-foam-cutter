import numpy as np

def intro_path(coords:np.ndarray) -> np.ndarray:
    coords = np.roll(coords,-(coords[:,0]+coords[:,1]).argmax()-1, axis=0)[::-1]
    start = coords[0]
    bottom_left = coords.min(axis=0)
    top_right = coords.max(axis=0)
    width, height = top_right-bottom_left
    padding = 10
    coords = np.vstack([
        [
            bottom_left - np.array([padding,padding]),
            bottom_left+np.array([-padding,height+padding]),
            top_right + np.array([padding,padding]),
            start + np.array([padding,0])
        ],
        coords,
        [
            coords[-1]+np.array([padding,0])
        ]
    ])
    coords = coords - coords.min(axis=0)
    return coords