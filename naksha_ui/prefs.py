from __future__ import annotations

import json
from pathlib import Path

import bpy

_DEV_PATHS = Path(__file__).with_name("_dev_paths.json")


def _dev_default(key: str) -> str:
    """Default paths written by tools/build_extension.py for developer builds."""
    try:
        return json.loads(_DEV_PATHS.read_text(encoding="utf-8")).get(key, "")
    except (OSError, ValueError):
        return ""


class NakshaPreferences(bpy.types.AddonPreferences):
    bl_idname = __package__

    bridge_python: bpy.props.StringProperty(
        name="Bridge Python",
        description="python.exe that has naksha_rvt_bridge and the 'rvt' reader installed",
        subtype="FILE_PATH",
        default=_dev_default("python"),
    )
    bridge_src: bpy.props.StringProperty(
        name="Bridge source folder",
        description="Folder containing naksha_rvt_bridge and naksha_core (added to PYTHONPATH). Leave empty if installed",
        subtype="DIR_PATH",
        default=_dev_default("src"),
    )
    output_folder: bpy.props.StringProperty(
        name="Converted IFC folder",
        description="Where converted IFC files go. Empty = next to the Revit file",
        subtype="DIR_PATH",
        default="",
    )

    def draw(self, context):
        col = self.layout.column()
        col.label(text="RVT Bridge (runs as a separate program)")
        col.prop(self, "bridge_python")
        col.prop(self, "bridge_src")
        col.prop(self, "output_folder")


def get(context=None) -> NakshaPreferences:
    context = context or bpy.context
    return context.preferences.addons[__package__].preferences
