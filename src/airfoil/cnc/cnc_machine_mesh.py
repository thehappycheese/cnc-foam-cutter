import pyvista as pv
from typing import Literal

def carriage():
    noz = pv.Cone(
        center=(-1.2,0,0),
        height=2.4,
        radius=2.4,
        resolution=12
    )
    noz["colors"]="red"
    #print(noz.points.min(axis=0))
    #print(noz.points.max(axis=0))
    
    hex = pv.Polygon(
        center=(-2.4-3,0,0),
        radius=4,
        #fill=True,
        normal=(1,0,0)
    ).extrude((3,0,0),capping=True)
    tray = pv.Box((
        -50+1.5,-5.4,
        -10,10,
        -10,10))
    plate = pv.Box((
        -50,-47,
        -66/2,66/2,
        -66/2,66/2,
    ))#.color_labels("red")
    return noz+hex+tray+plate

def vrail(length=500, carriage_pos=0):
    rl = pv.Box((
          -40, 0,
        -10, 10,
          0,length,
    )).translate((-50,0,0))
    carr = carriage().translate((0,0,carriage_pos))
    return rl+carr

def hrail(length=500, vrail_length=500, vrail_pos=0, carriage_pos=0):

    h1 = pv.Box((
        -90-40,-90,
        0, length,
        -10,10,
    ))
    h2 = pv.Box((
        -90-40,-90,
        0, length,
        -10+80,10+80,
    ))
    return (
          (h1+ h2).translate((0,0,50))
        + vrail(length=vrail_length, carriage_pos=carriage_pos).translate((0,vrail_pos,0))
    )

def axis(position=(0,0,0),side:Literal["L","R"]="L",size=(500,500),bottom_limit= (60+40,80+40)):
    res = hrail(
        length       = size[0],
        vrail_length = size[1],
        vrail_pos    = position[1]+bottom_limit[0],
        carriage_pos = position[2]+bottom_limit[1],
    ).scale((
        1 if side=="L" else -1,
        1,
        1,
    )).translate((
        position[0],
        -bottom_limit[0],
        -bottom_limit[1],
    ))
    return res

def draw_machine(x:float, y:float, z:float, a:float, spacing=220, pt:pv.Plotter|None=None, opacity:float=1.0):
    bottom_limit = (100,100)
    axa = axis(
        position=(-spacing/2,x,y),
        side="L",
        bottom_limit=bottom_limit,
    )
    axb = axis(
        position=(spacing/2,z,a),
        side="R",
        bottom_limit=bottom_limit,
    )
    if pt is None:
        pt = pv.Plotter()
    pt.add_mesh(axa,color="white", opacity=opacity)
    pt.add_mesh(axb,color="white", opacity=opacity)
    pt.add_mesh(pv.Line(
        (-spacing/2,x,y),
        ( spacing/2,z,a),
    ),color="red")
    pt.camera_position = [
        (+spacing/2,-1000,300),
        (0,150,80),
        (0,0,1)
    ]
    return pt
