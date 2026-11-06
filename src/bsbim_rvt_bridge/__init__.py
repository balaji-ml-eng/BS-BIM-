"""BS BIM RVT Bridge: converts Revit files (.rvt/.rfa/.rte/.rft) to IFC.

Design rules:
- Runs as a separate process from Blender (``python -m bsbim_rvt_bridge``).
  This keeps third-party readers isolated: a crash cannot take BS BIM down,
  and a reader can be swapped or removed without touching the rest of the product.
- We never reverse engineer Revit ourselves. Backends wrap existing open-source,
  clean-room readers or official Autodesk routes. See LICENSES.md.
"""

__version__ = "0.1.0"

REVIT_SUFFIXES = (".rvt", ".rfa", ".rte", ".rft")
