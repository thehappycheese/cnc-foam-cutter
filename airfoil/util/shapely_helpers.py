from pathlib import Path

import numpy as np

from shapely.geometry.base import BaseGeometry
from shapely.plotting import plot_line,plot_points,plot_polygon

from matplotlib.axes import Axes
import matplotlib.patches as patches
import matplotlib.pyplot as plt

from .array_helpers import sliding_window, split_indexable


def plot_shapely_simple(shps:list[BaseGeometry], ax:Axes|None=None):
    
    if ax is None:
        f, ax = plt.subplots()
    for shp in shps:
        match shp.geom_type:
            case "Point"|"MultiPoint":
                plot_points(shp,ax)
            case "Polygon" | "MultiPolygon":
                plot_polygon(shp,ax)
            case "Line" | "LineString" | "LinearRing":
                plot_line(shp,ax)
    ax.set_aspect("equal")


def plot_shapely(shps: list[BaseGeometry], ax: Axes | None = None, legend: list[str] | None | bool = None):
    """VIBE WARNING"""
    if ax is None:
        f, ax = plt.subplots()
    
    # Get matplotlib's default color cycle
    prop_cycle = plt.rcParams['axes.prop_cycle']
    colors = prop_cycle.by_key()['color']
    
    # Determine legend behavior
    show_legend = True
    if legend is False:
        show_legend = False
        legend_labels = []
    elif legend is None:
        legend_labels = [str(i) for i in range(len(shps))]
    else:
        legend_labels = legend
    
    # Track handles and labels for legend
    handles = []
    labels = []
    
    for i, shp in enumerate(shps):
        color = colors[i % len(colors)]  # Cycle through colors if more shapes than colors
        label = legend_labels[i] if i < len(legend_labels) else str(i)
        
        # Count existing artists before adding new ones
        existing_lines = len(ax.lines)
        existing_patches = len(ax.patches)
        existing_collections = len(ax.collections)
        
        match shp.geom_type:
            case "Point" | "MultiPoint":
                handle = plot_points(shp, ax, markersize=3, label=label)
                if handle and show_legend:
                    handles.append(handle)
                    labels.append(label)
                    
            case "Polygon" | "MultiPolygon":
                handle = plot_polygon(shp, ax, facecolor=color, alpha=0.7, edgecolor='black', linewidth=1, label=label)
                if handle and show_legend:
                    handles.append(handle)
                    labels.append(label)
                    
            case "Line" | "LineString" | "LinearRing":
                handle = plot_line(shp, ax, color=color, linewidth=2, label=label)
                if handle and show_legend:
                    handles.append(handle)
                    labels.append(label)
        
        # Now capture any new markers that were added and color them
        # Check for new line objects (which may contain markers)
        for line in ax.lines[existing_lines:]:
            if line.get_marker() != 'None':  # Line has markers
                line.set_markerfacecolor(color)
                line.set_markeredgecolor(color)
                line.set_markersize(3)
        
        # Check for new collections (scatter plots, etc.)
        for collection in ax.collections[existing_collections:]:
            # This handles PathCollection objects (from scatter plots)
            if hasattr(collection, 'set_facecolors'):
                collection.set_facecolors([color])
            if hasattr(collection, 'set_edgecolors'):
                collection.set_edgecolors([color])
            if hasattr(collection, 'set_sizes'):
                collection.set_sizes([9])  # markersize=3 corresponds to size=9 (3^2)
    
    ax.set_aspect("equal")
    
    # Add legend if we have handles and legend is enabled
    if handles and show_legend:
        ax.legend(handles, labels)
    
    return ax


def shapely_to_svg(shapes:list[BaseGeometry], output:Path|str):
    output_path = Path(output)
    output_path.write_text("\n".join([
        f"""<svg version="1.1" xmlns="http://www.w3.org/2000/svg" xmlns:xlink= "http://www.w3.org/1999/xlink">""",
        f"""    {'\n'.join(shape.svg() for shape in shapes)}""",
        f"""</svg>"""
    ]))


def plot_shapely_directional(shps: list[BaseGeometry], ax: Axes | None = None, legend: list[str] | None | bool = None, arrow_spacing: int = 10):
    
    if ax is None:
        f, ax = plt.subplots()
    
    # Get matplotlib's default color cycle
    prop_cycle = plt.rcParams['axes.prop_cycle']
    colors = prop_cycle.by_key()['color']
    
    # Determine legend behavior
    show_legend = True
    if legend is False:
        show_legend = False
        legend_labels = []
    elif legend is None:
        legend_labels = [str(i) for i in range(len(shps))]
    else:
        legend_labels = legend
    
    # Track handles and labels for legend
    handles = []
    labels = []
    
    def get_direction_angle(p1, p2):
        """Calculate angle in radians for direction from p1 to p2"""
        dx = p2[0] - p1[0]
        dy = p2[1] - p1[1]
        return np.arctan2(dy, dx)
    
    def plot_directional_markers(coords, color, part_label=""):
        """Plot directional markers along a coordinate sequence"""
        coords = list(coords)
        if len(coords) < 2:
            return
        
        # End marker (empty circle)
        end_x, end_y = coords[-1]
        ax.plot(end_x, end_y, marker=(5, 0, 0), fillstyle='none', markersize=15, 
                markeredgecolor=color, markerfacecolor='white', markeredgewidth=1, 
                linestyle='None', zorder=8)
        
        # Start marker (right-pointing triangle)
        start_x, start_y = coords[0]
        ax.plot(start_x, start_y, marker=(5, 0, 0), markersize=8, 
                markerfacecolor=color, markeredgecolor='white', markeredgewidth=1, 
                linestyle='None', zorder=100)
        
        # Directional arrows along the path
        for i in range(1, len(coords) - 1, arrow_spacing):
            if i >= len(coords):
                break
            
            # Get direction from previous to next point
            prev_pt = coords[i-1]
            curr_pt = coords[i]
            next_pt = coords[i+1] if i+1 < len(coords) else coords[i]
            
            # Calculate direction angle and convert to degrees
            angle = get_direction_angle(prev_pt, next_pt)
            angle_degrees = np.degrees(angle) + 90  # +90 to match original orientation
            
            # Create rotated triangle arrow
            x, y = curr_pt
            ax.plot(x, y, marker=(3, 0, angle_degrees), markersize=9, 
                    markerfacecolor=color, markeredgecolor=color, markeredgewidth=0.5, 
                    linestyle='None', zorder=10)
        
        # Add part label if provided
        if part_label:
            mid_idx = 0
            mid_x, mid_y = coords[mid_idx]
            ax.annotate(
                part_label,
                xy=(mid_x,mid_y),
                xytext=(10,5),
                textcoords='offset points',
                fontsize=10,
                fontweight='bold',
                ha='center',
                va='center',
                bbox=dict(
                    boxstyle='round,pad=0.3',
                    facecolor='white',
                    edgecolor=color,
                    alpha=0.8
                ),
                zorder=11
            )
    
    for i, shp in enumerate(shps):
        color = colors[i % len(colors)]
        label = legend_labels[i] if i < len(legend_labels) else str(i)
        
        def fix_shapely_markers(artists, color):
            """Fix markers from Shapely plotting functions"""
            if isinstance(artists, tuple):
                # Handle tuple return (PathPatch, Line2D)
                for artist in artists:
                    if hasattr(artist, 'get_marker') and artist.get_marker() != 'None':
                        artist.set_markerfacecolor(color)
                        artist.set_markeredgecolor(color)
                        artist.set_markersize(2)
            elif hasattr(artists, 'get_marker') and artists.get_marker() != 'None':
                # Handle single Line2D return
                artists.set_markerfacecolor(color)
                artists.set_markeredgecolor(color)
                artists.set_markersize(2)
        
        match shp.geom_type:
            case "LineString" | "LinearRing":
                # Plot the line first
                artists = plot_line(shp, ax, color=color, linewidth=2, label=label)
                fix_shapely_markers(artists, color)
                plot_directional_markers(shp.coords, color)
                
                # Get handle for legend (first artist if tuple, otherwise the artist itself)
                handle = artists[0] if isinstance(artists, tuple) else artists
                if handle and show_legend:
                    handles.append(handle)
                    labels.append(label)
            
            case "Polygon":
                # Plot the polygon first
                artists = plot_polygon(shp, ax, facecolor=color, alpha=0.3, 
                                    edgecolor=color, linewidth=2, label=label)
                fix_shapely_markers(artists, color)
                
                # Plot exterior boundary with direction
                plot_directional_markers(shp.exterior.coords, color)
                
                # Plot interior boundaries (holes) with part labels
                for j, interior in enumerate(shp.interiors):
                    plot_directional_markers(interior.coords, color, f"H{j}")
                
                # Get handle for legend (first artist if tuple, otherwise the artist itself)
                handle = artists[0] if isinstance(artists, tuple) else artists
                if handle and show_legend:
                    handles.append(handle)
                    labels.append(label)
            
            case "MultiLineString":
                # Plot all parts with same color but label each part
                for j, line in enumerate(shp.geoms):
                    if j == 0:
                        artists = plot_line(line, ax, color=color, linewidth=2, label=label)
                        fix_shapely_markers(artists, color)
                        handle = artists[0] if isinstance(artists, tuple) else artists
                        if handle and show_legend:
                            handles.append(handle)
                            labels.append(label)
                    else:
                        artists = plot_line(line, ax, color=color, linewidth=2)
                        fix_shapely_markers(artists, color)
                    
                    plot_directional_markers(line.coords, color, str(j))
            
            case "MultiPolygon":
                # Plot all parts with same color but label each part
                for j, poly in enumerate(shp.geoms):
                    if j == 0:
                        artists = plot_polygon(poly, ax, facecolor=color, alpha=0.3, 
                                            edgecolor=color, linewidth=2, label=label)
                        fix_shapely_markers(artists, color)
                        handle = artists[0] if isinstance(artists, tuple) else artists
                        if handle and show_legend:
                            handles.append(handle)
                            labels.append(label)
                    else:
                        artists = plot_polygon(poly, ax, facecolor=color, alpha=0.3, 
                                           edgecolor=color, linewidth=2)
                        fix_shapely_markers(artists, color)
                    
                    # Plot exterior with part label
                    plot_directional_markers(poly.exterior.coords, color, str(j))
                    
                    # Plot interior boundaries (holes) with part labels
                    for k, interior in enumerate(poly.interiors):
                        plot_directional_markers(interior.coords, color, f"{j}H{k}")
            
            case "Point":
                # Simple point plotting
                x, y = shp.x, shp.y
                ax.plot(x, y, 'o', color=color, markersize=6, label=label)
                if show_legend:
                    handles.append(plt.Line2D([0], [0], marker='o', color=color, 
                                            linestyle='', markersize=6))
                    labels.append(label)
            
            case "MultiPoint":
                # Plot points with index numbers
                for j, point in enumerate(shp.geoms):
                    x, y = point.x, point.y
                    if j == 0:
                        line_handle = ax.plot(x, y, 'o', color=color, markersize=6, label=label)[0]
                        if show_legend:
                            handles.append(line_handle)
                            labels.append(label)
                    else:
                        ax.plot(x, y, 'o', color=color, markersize=6)
                    
                    # Add index number next to point
                    ax.text(x + 1, y + 1, str(j), fontsize=8, fontweight='bold',
                           ha='left', va='bottom', bbox=dict(boxstyle='round,pad=0.2',
                           facecolor='white', edgecolor=color, alpha=0.8))
    
    ax.set_aspect("equal")
    
    # Add legend if we have handles and legend is enabled
    if handles and show_legend:
        # Create additional legend entries for directional markers
        legend_handles = handles.copy()
        legend_labels = labels.copy()
        
        # Add start marker to legend
        start_marker = plt.Line2D([0], [0], marker=(5, 0, 0), markersize=8, 
                                 markerfacecolor='gray', markeredgecolor='white', markeredgewidth=1,
                                 linestyle='', label='Start')
        legend_handles.append(start_marker)
        legend_labels.append('Start')
        
        # Add end marker to legend
        end_marker = plt.Line2D([0], [0], marker=(5, 0, 0), fillstyle='none', markersize=15,
                               markeredgecolor='gray', markerfacecolor='white', markeredgewidth=1,
                               linestyle='', label='End')
        legend_handles.append(end_marker)
        legend_labels.append('End')
        
        # Add direction arrow to legend
        arrow_marker = plt.Line2D([0], [0], marker=(3, 0, 90), markersize=9,
                                 markerfacecolor='gray', markeredgecolor='gray', markeredgewidth=0.5,
                                 linestyle='', label='Direction')
        legend_handles.append(arrow_marker)
        legend_labels.append('Direction')
        
        ax.legend(legend_handles, legend_labels, bbox_to_anchor=(1.05, 0.5), loc='center left')
    
    return ax