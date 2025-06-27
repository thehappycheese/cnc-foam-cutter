# Four Axis CNC Hotwire Foam Cutting Tools (With Airfoil Shape Generation)

This repo contains a number of notebooks and a library currently named `airfoil`
that contains utilities for generating 3d meshes and preparing instructions for
slicing shapes from Foam using a Hot wire.

> I am likely to choose a new name, since the very similar `airfoils` is already taken on PyPi.

I am primarily interested in meshes defined lofting between 2D shapes placed on
parallel planes (such a wing segment defined by two parallel airfoils for
RC/Model Aircraft)

![hero](./readme-assets/hero.png)

I re-implemented NACA4 and NACA5 airfoil generation since I wasn't happy with the
flexibility of existing packages. The implementations aren't bulletproof and
super well tested yet, but the API is flexible as it allows definition by named
parameters or by the NACA designation string.

## `Airfoil`, `Hole`, `Hinge`

```python
from airfoil import  Airfoil, Hole, Hinge
```

- `Airfoil` represents a single cross section of a wing, including cut-outs such as holes, or hinge cuts.
- Cannot currently represent a multi-polygon.
- Create 
  - using factory class-methods like
    - `af = Airfoil.from_naca_designation("2213", chord_length=100)` for 4 digit NACA foils
    - `af = Airfoil.from_naca_designation("23012", chord_length=100)` for 5 digit NACA foils
  - Or from a list of `[x,y]` coordinates like `af = Airfoil([[0.0,0.0],...])`
- Manipulate
  - `af.with_rotation(5).with_translation((10,0)).with_scale(1.2)` for affine transformations
  - `af.with_chord(80)` like the `with_scale` function except you provide the desired final x-size of the airfoils points
  - `af.with_holes([Hole(diameter=10, position=(50,0))])`
  - `af.with_hinge(Hinge(position=(80,0)), upper_thickness=3.0)` where 
   `upper_thickness=3.0` is an optional parameter that vertically 
   repositions the hinge to leave that much material thickness from the
   top surface of the wing to the top of the hinge cut.
- Convert
  - `af.polygon()` returns a `shapely.Polygon`
  - `af.to_mesh()` returns a `pyvista` mesh object
- Plot
  - `af.plot_raw()` reliable 2d plot of the airfoil's shape without holes or hinge cutouts. (helpful if other plot mechanisms are failing due to degenerate or malformed geometry)
  - `af.plot()` 2d plot each line in the "decomposed" outline of the airfoil, including hole and hinge cutouts.

```python
af = (
    Airfoil.from_naca_designation("23012", chord_length=100)
    .with_hinge(Hinge((80,0), height=10),upper_thickness=2)
    .with_holes([Hole(8,(20,2))])
)
```

![plot_raw](./readme-assets/airfoil.plot_raw.png)
![plot](./readme-assets/airfoil.plot.png)

> Note: Holes include a thin cut to the upper surface of the
> airfoil such that the final shape is a single polygon with no
> interior holes or islands (see `af.plot()` image above). This behavior is hard coded into `Decomposer` see below.

## `Decomposer`

```python
from airfoil import Decomposer

example_decomposer = Decomposer()
```

- `Decomposer` is a collection of stateful helper functions that
  apply boolean operations and re-segmentation of the airfoil shape.
  subtraction of the holes and hinges from the
  airfoil outline and consistently re-segments one or more airfoil
  such that each "side" has the same number of points.
- The first time an instance is used
  (`example_decomposer.decompose(example_airfoil)`),
  it remembers how many 'sides' it broke the first airfoil shape
  into, and how many points each side had. Every subsequent call
  it attempts to match the first result even if the airfoil is
  much bigger or smaller.
- Consistent segmentation makes it easy to interpolate or loft
  between similar airfoils.
- `Decomposer` is often not used directly, but provided as
  optional configuration to other functions (e.g.
  `af.plot(decomposer=Decomposer(split_angle_deg=30))` allows
  configuring the threshold angle at which the LineString defining
  an airfoil perimeter is split into chunks prior to
  re-segmentation)

# `util`

```python
from airfoil.util.array_helpers      import (
  remove_sequential_duplicates, # reduce contiguous runs of duplicates to a single occurrence
  blur1d, # smear/smooth values by applying a gaussian convolution
  map_to_range, # scale and translate array values to fall within specified minimum and maximum
  create_array_interpolator # similar to np.interp except the interolation can occur between multidimentional arrays. (who knows why numpy doesn't just support this directly?)
)
from airfoil.util.linestring_helpers import (
  is_ccw, # tests if a list of coordinates is counterclockwise (same as shapely.is_ccw except it operates on (n,2) numpy array)
  ensure_closed, # add an extra point to the end of a list of coordinates to close the loop only if needed
  split_linestring_by_angle,
  resample_long_segments,
  resample_spline_fallback_linear,
  resample_linear,
  resample_linear_to_number_of_segments,
  resample_linear_to_segment_length,
  deflection_angle,
  split_and_roll,
  split_and_roll_at_top_right,
  resample_shapes,
)
from airfoil.util.path_planning import ...
from airfoil.util.pyvista_helpers import (
  create_ruled_surface,
  mesh_from_polygon, # creates a triangulated pyvista mesh from a shapely polygon
  make_mesh_from_side_surfaces, # loft defined between two 2d polygons and a distance. TODO: possibly rename

)
from airfoil.util.shapely_helpers import (
  plot_shapely_directional, # plot list of geometries using matplotlib with arrow linestring direction indicators.
  shapely_to_svg, # list of geometries to full SVG document TODO: why is this not just built into shapely
  
)
from airfoil.util.functools import compose # TODO: may be unused
```

- `airfoil.util`
  - `airfoil.util.linestring_helpers` helpers that deal with 2D LineStrings
    stored as numpy arrays in the shape `(n,2)` where `n` is the number of points.
  - `airfoil.util.array_helpers`
