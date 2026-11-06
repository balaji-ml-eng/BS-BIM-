"""BS BIM core: BIM engine logic built only on IfcOpenShell.

Rule: nothing in this package may import ``bpy`` or ``bonsai``. Keeping the
core independent of Blender and Bonsai means it can run in the command-line
bridge and in tests, and its licensing stays under our own control.

Imports inside this package must be relative (``from . import x``) because the
Blender extension vendors a copy of it as a sub-package.
"""

__version__ = "0.1.0"
