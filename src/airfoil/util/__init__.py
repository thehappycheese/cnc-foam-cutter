from ._compensate_feedrate import compensate_feedrate
from._project_line_to_plane import project_line_to_plane
from ._array_helpers import (
    sliding_window,
    split_indexable,
    remove_sequential_duplicates,
    blur1d,
    map_to_range,
    create_array_interpolator,
)
from ._linestring_helpers import (
    deflection_angle,
    deflection_angle_padded,
    ensure_closed,
    is_ccw,
    remove_sequential_duplicates,
    split_and_roll,
    split_and_roll_at_top_right,
    split_linestring_by_angle,
    resample_spline_fallback_linear,
    resample_linear,
    resample_shapes,
)
from ._shapely_helpers import (
    plot_shapely,
    plot_shapely_directional,
)
from ._pyvista_helpers import (
    create_ruled_surface,
    make_mesh_from_side_surfaces
)