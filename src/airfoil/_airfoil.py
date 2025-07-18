from __future__ import annotations
from dataclasses import dataclass, field, replace
from typing import Literal
from pathlib import Path

import numpy as np
from numpy.typing import ArrayLike

import matplotlib.pyplot as plt
from matplotlib.axes import Axes

from shapely import LineString, Polygon, Point, constrained_delaunay_triangles, intersection

import pyvista as pv

from .naca import naca, naca4, naca5
from .util.array_helpers import remove_sequential_duplicates
from .util.linestring_helpers import ensure_closed, is_ccw

from ._Decomposer import Decomposer

@dataclass
class Hole:
    diameter_mm:float
    position:tuple[float,float]|np.ndarray
    def __post_init__(self):
        self.position = np.array(self.position)
        assert self.position.shape == (2,), "position must have shape `(2)`"
    
    def to_polygon(self):
        return Point(self.position).buffer(self.diameter_mm/2)

@dataclass
class Hinge:
    position: tuple[float,float]|np.ndarray
    angle_deg: float = 60
    rotation_deg: float = -20
    height: float = 300.0
    
    def __post_init__(self):
        self.position = np.array(self.position)
        assert self.position.shape == (2,), "upper_point must have shape `(2)`"
        assert 0 < self.angle_deg <= 180, "angle_deg must be between 0 and 180 degrees"
    
    def to_polygon(self) -> Polygon:
        """Generate the equilateral triangle polygon based on parameters."""
        # Calculate the base width from the angle and height
        # For an equilateral triangle, if we know the angle at the top and height,
        # we can calculate the base width
        half_base = self.height * np.tan(np.deg2rad(self.angle_deg / 2))
        
        # Create triangle points relative to origin (upper point at origin, pointing down)
        triangle_points = np.array([
            [0, 0],  # upper point
            [-half_base, -self.height],  # bottom left
            [half_base, -self.height],   # bottom right
            [0, 0]   # close the triangle
        ])
        
        # Apply rotation
        if self.rotation_deg != 0:
            rotation_rad = np.deg2rad(self.rotation_deg)
            rotation_matrix = np.array([
                [np.cos(rotation_rad), -np.sin(rotation_rad)],
                [np.sin(rotation_rad),  np.cos(rotation_rad)]
            ])
            triangle_points = triangle_points @ rotation_matrix
        
        # Translate to the actual upper point position
        triangle_points = triangle_points + self.position.reshape(1, -1)
        
        return Polygon(triangle_points)

@dataclass
class Airfoil:
    points:np.ndarray = field()
    holes:list[Hole] = field(default_factory=list)
    hinge:Hinge|None = None

    def __repr__(self) -> str:
        size = np.max(self.points,axis=0) - np.min(self.points,axis=0)
        return f"<Airfoil p={len(self.points)} h={len(self.holes)} w={size[0]:.1f} h={size[1]:.1f} />"
    
    def __post_init__(self) -> None:
        assert self.points.shape[1]==2, "points must have shape (n, 2)" 
        assert self.points.shape[0]>4, f"need more points. only got {len(self.points)=}"
        assert (self.points[0]==self.points[-1]).all(), "first and last point must be the same"
        if not is_ccw(self.points):
            self.points = self.points[::-1]
            if not is_ccw(self.points):
                raise ValueError("Something is wrong with the input points. Not able to be sorted into a counterclockwise direction")
        
    @classmethod
    def from_upper_lower(
        cls,
        upper:np.ndarray,
        lower:np.ndarray,
    ):
        selig = np.vstack((upper[::-1], lower[1:]))
        average_terminator = (selig[0]+selig[-1])/2
        selig = np.concatenate([
            [average_terminator],
            selig,
            [average_terminator]
        ])
        return Airfoil(selig)
    @classmethod
    def from_naca4(
            cls,
            max_camber:float,
            max_camber_position:float,
            max_thickness:float,
            chord_length:float,
            points:int=100,
        ):
        upper, lower = naca4(
            max_thickness=max_thickness, 
            max_camber_position=max_camber_position, 
            max_camber=max_camber,
        )(n=points)
        return Airfoil.from_upper_lower(upper,lower).with_chord(chord_length)
    
    @classmethod
    def from_naca5(
        cls,
        type: Literal["standard","reflex"],
        design_lift_coefficient: float,
        max_camber_position: float,
        max_thickness: float,
        chord_length:float,
        points:int=100,
    ):
        upper, lower = naca5(
            type=type,
            design_lift_coefficient=design_lift_coefficient,
            max_camber_position=max_camber_position,
            max_thickness=max_thickness
        )(n=points)
        return Airfoil.from_upper_lower(upper*chord_length, lower*chord_length)
    
    @classmethod
    def from_naca_designation(cls, designation:str, chord_length:float, points:int=100):
        upper, lower = naca(designation, points)
        return Airfoil.from_upper_lower(upper*chord_length, lower*chord_length)

    @classmethod
    def from_airfoiltools_website(cls, reference:str, cache_dir:Path|str|None=None) -> Airfoil:
        """
        e.g. `Airfoil.from_airfoiltools_website("naca23012-il").with_scale((100,100))`
        is equivalent to `Airfoil.from_naca_designation("23012",chord_length=100)`
        
        Args:
            reference: The airfoil reference string
            cache_dir: Directory to store cached airfoil data (default: "./data")
        """
        coord_lines = None
        if cache_dir is not None:
            cache_path = Path(cache_dir)
            cache_path.mkdir(parents=True, exist_ok=True)
            cache_file = cache_path / f"{reference}.txt"
            if cache_file.exists():
                cached_data = cache_file.read_text().strip()
                _name, *coord_lines = cached_data.splitlines()
        if coord_lines is None:
            import requests
            response = requests.get(f"http://airfoiltools.com/airfoil/seligdatfile?airfoil={reference}")
            response.raise_for_status()  # Raise an exception for bad status codes
            
            if cache_dir is not None:
                cache_path = Path(cache_dir)
                cache_path.mkdir(parents=True, exist_ok=True)
                cache_file = cache_path / f"{reference}.txt"
                cache_file.write_text(response.text)
            
            _name, *coord_lines = response.text.strip().splitlines()
        
        return cls(
            points=ensure_closed(np.array([list(map(float, item.strip().replace("  ", " ").split(" "))) for item in coord_lines]))
        )

    def with_holes(self, holes:list[Hole]) -> Airfoil:
        return replace(self, holes=holes)
    
    def with_hinge(self, hinge:Hinge|None, upper_thickness:float|None=None) -> Airfoil:
        if upper_thickness is not None and hinge is not None:
            shape = intersection(
                self.polygon(),
                LineString([[hinge.position[0],-500],[hinge.position[0],500]])
            )
            hinge = replace(
                hinge,
                position=np.array([
                    hinge.position[0],
                    np.array(shape.coords)[:,1].max()-upper_thickness,
                ])
            )
        return replace(self, hinge=hinge)
    
    def compute_chord(self)->float:
        """Naive measurement of chord by subtracting the minimum x coordinate from the maximum x coordinate"""
        return self.points[:,0].max()-self.points[:,0].min()

    def with_chord(self, new_chord:float) -> Airfoil:
        """Warning: lossy if repeated. Will not work as expected if shape has been rotated as it uses compute_chord"""
        return self.with_scale([new_chord/self.compute_chord()]*2)
    
    def with_translation(self, translation:ArrayLike)->Airfoil:
        translation = np.array(translation)
        assert translation.shape==(2,), "Translation must be an ndarray of shape (2,)"
        return replace(
            self,
            points = self.points+translation.reshape(1,-1),
            holes  = [replace(hole,position=hole.position+translation) for hole in self.holes],
            hinge  = None if self.hinge is None else replace(
                self.hinge, 
                position=self.hinge.position + translation
            ),
        )
    
    def with_rotation(self, rotation_deg:float)->Airfoil:
        rotation_rad = np.deg2rad(rotation_deg)
        rotation_matrix = np.array([
            [np.cos(rotation_rad), -np.sin(rotation_rad)],
            [np.sin(rotation_rad),  np.cos(rotation_rad)]
        ])
        return replace(
            self,
            points = self.points @ rotation_matrix,
            holes  = [replace(hole, position=hole.position@rotation_matrix) for hole in self.holes],
            hinge  = None if self.hinge is None else replace(
                self.hinge,
                upper_point  = self.hinge.position @ rotation_matrix,
                rotation_deg = self.hinge.rotation_deg + rotation_deg
            ),
        )
    
    def with_scale(self, scale:ArrayLike) -> Airfoil:
        scale = np.array(scale)
        assert scale.shape==(2,), "Scale must be an ndarray of shape (2,)"
        scale_reshaped = scale.reshape(-1,2)
        return replace(
            self,
            points = self.points * scale_reshaped,
            holes  = [replace(hole, position=hole.position*scale) for hole in self.holes],
            hinge   = None if self.hinge is None else replace(
                self.hinge,
                upper_point = self.hinge.position * scale,
            )
        )

    def show(self):
        from IPython.display import display
        display(LineString(self.points))
    
    def linestring(self) -> LineString:
        return LineString(self.points)
    
    def polygon(self) -> Polygon:
        return Polygon(self.points)
    
    def plot(
            self,
            ax:Axes|None=None,
            decomposer:Decomposer|None=None
        ):
        if ax is None:
            fig,ax = plt.subplots(figsize=(10,10))
        if decomposer is None:
            decomposer = Decomposer()
        decomposed = decomposer.decompose(self)
        for chunk in decomposed:
            ax.plot(*chunk.transpose(),"o-",markersize=2)
        ax.set_aspect("equal")
        return ax, [len(chunk) for chunk in decomposed]
    
    def plot_raw(
            self,
            ax:Axes|None=None,
            show_holes:bool = False,
            show_hinge:bool = False,
            marker_size=2,
            **kwargs,
        ):
        """plot outline, holes and hinge without performing boolean operations
        This is useful to diagnose issues (e.g. your hinge cut is dividing the airfoil into two parts, or a hole doesn't lie within the airfoil.)"""
        if ax is None:
            fig,ax = plt.subplots(figsize=(10,10))
        
        ax.plot(*self.points.transpose(),"o-",markersize=marker_size,**kwargs)
        if show_holes:
            for hole in self.holes:
                ax.plot(*np.array(hole.to_polygon().exterior.coords).transpose(), "o-", markersize=marker_size,**kwargs)
        if show_hinge and self.hinge is not None:
            ax.plot(*np.array(self.hinge.to_polygon().exterior.coords).transpose(), "o-", markersize=marker_size,**kwargs)

        ax.set_aspect("equal")
        return ax
    
    def to_mesh(
            self,
            decomposer:Decomposer|None = None
        ):
        if decomposer is None:
            decomposer = Decomposer()
        chunks = decomposer.decompose(self)
        s =  ensure_closed(remove_sequential_duplicates(np.concat(chunks)))
        pol = Polygon(s)
        triangles = constrained_delaunay_triangles(pol)
        # Collect all vertices and faces
        all_vertices = []
        all_faces = []
        vertex_offset = 0
        for triangle in triangles.geoms:
            if pol.contains(triangle.centroid):
                # Extract triangle vertices
                coords = np.array(triangle.exterior.coords[:-1])  # Remove duplicate last point
                # Add to vertex list
                all_vertices.extend(coords)
                # Create face indices (triangle with 3 vertices)
                face = [3, vertex_offset, vertex_offset + 1, vertex_offset + 2]
                all_faces.extend(face)
                vertex_offset += 3
        vertices_array = np.array(all_vertices)
        faces_array = np.array(all_faces)
        points_3d = np.insert(vertices_array, 2, 0, axis=-1)
        mesh = pv.PolyData(points_3d, faces_array)
        mesh = mesh.clean(tolerance=1e-6)
        return mesh#, [len(item) for item in chunks]
    
    def bounding_size(self):
        return self.points.max(axis=1)-self.points.min(axis=1)
    
    def bounding_center(self):
        return self.points.min(axis=1)+self.bounding_size()/2
    
