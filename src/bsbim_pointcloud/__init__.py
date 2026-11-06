"""BS BIM point cloud converter (runs as a separate process, like the RVT Bridge).

Reads open scan formats and writes a compact cache (.npz) that the Blender add-on displays:
    E57 (pye57, MIT) · LAS/LAZ (laspy BSD-2 + lazrs MIT) · PLY · PTS · XYZ (built in)

Autodesk ReCap .rcp/.rcs has no open-source reader: export it to E57 from ReCap (or another tool).
"""

__version__ = "0.1.0"

SUFFIXES = (".e57", ".las", ".laz", ".ply", ".pts", ".xyz", ".txt")
RECAP_SUFFIXES = (".rcp", ".rcs")
