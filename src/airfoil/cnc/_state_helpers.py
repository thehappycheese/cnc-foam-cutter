import numpy as np

def state_to_3d_points(x:float, y:float, z:float, a:float, spacing=220):
    return (
        (-spacing/2,x,y),
        ( spacing/2,z,a),
    )

def states_to_3d_points(x:np.ndarray, y:np.ndarray, z:np.ndarray, a:np.ndarray, spacing=220):
    return (
        np.insert(np.vstack([x,y]).transpose(),0, -spacing/2, axis=-1),
        np.insert(np.vstack([z,a]).transpose(),0,  spacing/2, axis=-1),
    )

def states_to_curves(states,spacing=220):
    x,y,z,a=states.T
    return (
        np.vstack((np.ones_like(x)* -spacing/2, x,y)).transpose(),
        np.vstack((np.ones_like(x)*  spacing/2, z,a)).transpose(),
    )

def interpolate_states(a,b,mix):
    ab= b-a
    return a+ mix*ab
