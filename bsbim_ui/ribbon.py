"""Revit-style ribbon: tab row in Blender's top bar, command row in the 3D view header.

Tab and panel order follow Revit 2027 (see docs/REVIT_WORKFLOW.md section 3).
Commands that are not built yet are shown greyed out, so the layout already matches Revit.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import bpy


@dataclass(frozen=True)
class Cmd:
    label: str
    icon: str
    op: str = ""                       # operator id, "" = not built yet (greyed)
    kwargs: dict = field(default_factory=dict)
    tip: str = ""


def tool(label: str, icon: str, tool_id: str) -> Cmd:
    """Activate one of Bonsai's authoring tools."""
    return Cmd(label, icon, "wm.tool_set_by_id", {"name": tool_id})


TABS: dict[str, list[tuple[str, list[Cmd]]]] = {
    "ARCHITECTURE": [
        ("Build", [
            tool("Wall", "MOD_BUILD", "bim.wall_tool"),
            tool("Door", "MESH_PLANE", "bim.door_tool"),
            tool("Window", "MESH_GRID", "bim.window_tool"),
            tool("Column", "MESH_CYLINDER", "bim.column_tool"),
            tool("Roof", "MESH_CONE", "bim.roof_tool"),
            tool("Ceiling", "MESH_PLANE", "bim.covering_tool"),
            tool("Floor", "MESH_PLANE", "bim.slab_tool"),
        ]),
        ("Circulation", [
            tool("Railing", "MOD_LATTICE", "bim.railing_tool"),
            tool("Stair", "SORT_ASC", "bim.stair_flight_tool"),
        ]),
        ("Datum", [
            Cmd("Level", "TRIA_UP_BAR", "bsbim.add_level"),
            Cmd("Grid", "GRID", "bsbim.add_grid"),
        ]),
    ],
    "STRUCTURE": [
        ("Structure", [
            Cmd("Beam", "IPO_LINEAR", "bsbim.place_beam", tip="Beam (BM): click start and end points"),
            tool("Wall", "MOD_BUILD", "bim.wall_tool"),
            Cmd("Column", "MESH_CYLINDER", "bsbim.place_column", tip="Structural Column (CL): click to place"),
            tool("Floor", "MESH_PLANE", "bim.slab_tool"),
            Cmd("Truss", "MOD_LATTICE"),
            Cmd("Brace", "IPO_LINEAR", "bsbim.place_beam", {"brace": True}, "Brace: click start and end points"),
            Cmd("Beam System", "MESH_GRID"),
        ]),
        ("Connection", [Cmd("Connection", "LINKED")]),
        ("Foundation", [
            tool("Isolated", "MESH_CUBE", "bim.footing_tool"),
            Cmd("Wall", "MOD_SOLIDIFY"),
            tool("Slab", "MESH_PLANE", "bim.slab_tool"),
        ]),
        ("Datum", [
            Cmd("Level", "TRIA_UP_BAR", "bsbim.add_level"),
            Cmd("Grid", "GRID", "bsbim.add_grid"),
        ]),
        ("Work Plane", [Cmd("Ref Plane", "SNAP_GRID")]),
    ],
    "SYSTEMS": [
        ("HVAC", [
            tool("Duct", "MOD_FLUIDSIM", "bim.duct_tool"),
            Cmd("Duct Fitting", "MOD_FLUIDSIM"),
            Cmd("Air Terminal", "FORCE_WIND"),
        ]),
        ("Mechanical", [Cmd("Mechanical Equipment", "MESH_CUBE")]),
        ("Plumbing & Piping", [
            tool("Pipe", "MESH_CYLINDER", "bim.pipe_tool"),
            tool("Plumbing Fixture", "MATFLUID", "bim.sanitary_terminal_tool"),
            Cmd("Sprinkler", "MOD_OCEAN"),
        ]),
        ("Electrical", [
            tool("Cable Tray", "MOD_ARRAY", "bim.cable_carrier_tool"),
            Cmd("Conduit", "CURVE_PATH"),
            tool("Electrical Equipment", "MESH_CUBE", "bim.electric_appliance_tool"),
            tool("Lighting Fixture", "LIGHT_POINT", "bim.light_fixture_tool"),
        ]),
    ],
    "INSERT": [
        ("Link", [
            Cmd("Open Revit File", "FILE_3D", "bsbim.import_rvt"),
            Cmd("Open IFC", "FILE_FOLDER", "bim.load_project"),
        ]),
        ("Load from Library", [Cmd("Load Family", "ASSET_MANAGER")]),
    ],
    "ANNOTATE": [
        ("Dimension", [Cmd("Aligned", "DRIVER_DISTANCE")]),
        ("Text", [Cmd("Text", "FONT_DATA")]),
        ("Tag", [Cmd("Tag by Category", "BOOKMARKS")]),
    ],
    "ANALYZE": [
        ("Check", [Cmd("Model Quality", "INFO", "bsbim.model_report")]),
        ("Coordination", [Cmd("Interference Check", "SELECT_INTERSECT")]),
    ],
    "VIEW": [
        ("Create", [
            Cmd("3D View", "VIEW3D", "bsbim.open_view", {"kind": "3D"}),
            Cmd("Section", "MOD_BOOLEAN"),
            Cmd("Sheet", "FILE"),
        ]),
        ("Graphics", [Cmd("Visibility/Graphics", "HIDE_OFF")]),
        ("User Interface", [Cmd("Blender Mode", "BLENDER", "bsbim.toggle_revit_ui")]),
    ],
    "MANAGE": [
        ("Settings", [Cmd("Project Units", "SETTINGS")]),
    ],
}

TAB_LABELS = {
    "ARCHITECTURE": "Architecture", "STRUCTURE": "Structure", "SYSTEMS": "Systems", "INSERT": "Insert",
    "ANNOTATE": "Annotate", "ANALYZE": "Analyze", "VIEW": "View", "MANAGE": "Manage",
}

# Contextual tab, shown like Revit's green "Modify | <Category>" tab while something is selected.
MODIFY: list[tuple[str, list[Cmd]]] = [
    ("Modify", [
        Cmd("Move", "EMPTY_ARROWS", "transform.translate"),
        Cmd("Copy", "DUPLICATE", "bim.override_object_duplicate_move_macro"),
        Cmd("Rotate", "DRIVER_ROTATIONAL_DIFFERENCE", "transform.rotate"),
        Cmd("Mirror", "MOD_MIRROR"),
        Cmd("Array", "MOD_ARRAY"),
        Cmd("Align", "ALIGN_LEFT"),
        Cmd("Delete", "TRASH", "bim.override_object_delete"),
    ]),
]

_VALID_ICONS: set[str] | None = None


def icon(name: str) -> str:
    """Use the icon if this Blender version has it, else a neutral dot (an unknown icon would raise)."""
    global _VALID_ICONS
    if _VALID_ICONS is None:
        _VALID_ICONS = set(bpy.types.UILayout.bl_rna.functions["label"].parameters["icon"].enum_items.keys())
    return name if name in _VALID_ICONS else "DOT"


def draw_commands(layout, panels: list[tuple[str, list[Cmd]]]) -> None:
    """One ribbon row: panels separated, each with a small title and its buttons."""
    for i, (title, cmds) in enumerate(panels):
        if i:
            layout.separator(factor=1.5)
        group = layout.row(align=True)
        group.label(text=f"{title}:")
        for c in cmds:
            cell = group.row(align=True)
            if not c.op:
                cell.enabled = False
                cell.operator("bsbim.not_ready", text=c.label, icon=icon(c.icon)).feature = c.label
                continue
            props = cell.operator(c.op, text=c.label, icon=icon(c.icon))
            for k, v in c.kwargs.items():
                setattr(props, k, v)
