"""Properties palette, laid out like Revit's.

    ┌──────────────────────────────┐
    │ W Shapes                     │  Type Selector (family on top, type below)
    │ W12x26                    ▾  │
    │ Structural Framing (1)  Edit Type │
    │ Constraints                  │
    │   Reference Level   Level 2  │
    │   z-Justification   Top      │
    │ Dimensions                   │
    │   Length          20' - 0"   │
    │ Identity Data                │
    │   Mark / Comments            │
    └──────────────────────────────┘
With nothing selected it shows the active view (Revit shows view properties then).
While a placement tool runs, the Type Selector picks the type for new elements.
"""

from __future__ import annotations

import bpy

from . import revit_ui, structure

Z_JUSTIFICATION = {"8": "Top", "7": "Top", "9": "Top", "5": "Center", "4": "Center", "6": "Center",
                   "2": "Bottom", "1": "Bottom", "3": "Bottom", "10": "Origin"}


def _tool():
    import bonsai.tool as tool
    return tool


def _fmt(metres: float) -> str:
    from .tools import fmt_m
    return fmt_m(metres)


def _type_class(entity) -> str | None:
    import ifcopenshell.util.type
    types = ifcopenshell.util.type.get_applicable_types(entity.is_a(), schema=structure.ifc_file().schema)
    return types[0] if types else None


def _types_of(ifc_class: str):
    f = structure.ifc_file()
    return sorted(f.by_type(ifc_class), key=lambda t: ((t.ElementType or ""), t.Name or ""))


# ------------------------------------------------------------------ type selector
class BSBIM_OT_choose_type(bpy.types.Operator):
    """Type Selector: choose a family type"""

    bl_idname = "bsbim.choose_type"
    bl_label = "Type Selector"
    ifc_class: bpy.props.StringProperty()
    target: bpy.props.EnumProperty(items=[("SELECTION", "Selection", ""), ("COLUMN", "New column", ""),
                                          ("BEAM", "New beam", ""), ("BRACE", "New brace", "")])

    def invoke(self, context, event):
        ifc_class, target = self.ifc_class, self.target

        def draw(menu, _context):
            layout = menu.layout
            family = None
            for t in _types_of(ifc_class):
                if t.ElementType != family:
                    family = t.ElementType
                    layout.label(text=family or "(no family)")
                op = layout.operator("bsbim.set_type", text=f"    {t.Name}")
                op.type_id, op.target = t.id(), target

        context.window_manager.popup_menu(draw, title="Type Selector")
        return {"FINISHED"}


class BSBIM_OT_set_type(bpy.types.Operator):
    bl_idname = "bsbim.set_type"
    bl_label = "Set Type"
    bl_options = {"REGISTER", "UNDO"}
    type_id: bpy.props.IntProperty()
    target: bpy.props.StringProperty()

    def execute(self, context):
        wm = context.window_manager
        if self.target == "COLUMN":
            wm.bsbim_new_column_type = self.type_id
        elif self.target == "BEAM":
            wm.bsbim_new_beam_type = self.type_id
        elif self.target == "BRACE":
            wm.bsbim_new_brace_type = self.type_id
        else:
            tool = _tool()
            for obj in context.selected_objects:
                if tool.Ifc.get_entity(obj):
                    bpy.ops.bim.assign_type(relating_type=self.type_id, related_object=obj.name)
        return {"FINISHED"}


class BSBIM_OT_edit_type(bpy.types.Operator):
    """Edit Type: show the type's properties"""

    bl_idname = "bsbim.edit_type"
    bl_label = "Type Properties"
    type_id: bpy.props.IntProperty()

    def invoke(self, context, event):
        return context.window_manager.invoke_popup(self, width=380)

    def draw(self, context):
        import ifcopenshell.util.element as E
        t = structure.ifc_file().by_id(self.type_id)
        col = self.layout.column()
        col.label(text=f"Family:  {t.ElementType or '-'}")
        col.label(text=f"Type:  {t.Name}")
        col.separator()
        material = E.get_material(t)
        if material and material.is_a("IfcMaterialProfileSet"):
            mp = material.MaterialProfiles[0]
            col.label(text="Structural")
            col.label(text=f"    Structural Material:  {mp.Material.Name if mp.Material else '-'}")
            col.label(text="Dimensions")
            unit = 1.0 / _units_per_m()
            for attr, label in (("OverallDepth", "d"), ("OverallWidth", "bf"), ("WebThickness", "tw"),
                                ("FlangeThickness", "tf"), ("XDim", "b"), ("YDim", "h"), ("Depth", "d"),
                                ("Width", "b"), ("Thickness", "t"), ("WallThickness", "t"), ("Radius", "r")):
                value = getattr(mp.Profile, attr, None)
                if isinstance(value, float):
                    col.label(text=f"    {label}:  {_fmt(value * unit)}")
        elif material and material.is_a("IfcMaterialLayerSet"):
            col.label(text="Construction")
            unit = 1.0 / _units_per_m()
            for layer in material.MaterialLayers:
                col.label(text=f"    {layer.Material.Name if layer.Material else '-'}:  {_fmt(layer.LayerThickness * unit)}")

    def execute(self, context):
        return {"FINISHED"}


def _units_per_m() -> float:
    from .tools import project_units_per_metre
    return project_units_per_metre()


class BSBIM_OT_edit_identity(bpy.types.Operator):
    """Edit Mark or Comments"""

    bl_idname = "bsbim.edit_identity"
    bl_label = "Identity Data"
    bl_options = {"REGISTER", "UNDO"}
    field: bpy.props.EnumProperty(items=[("Tag", "Mark", ""), ("Description", "Comments", "")])
    value: bpy.props.StringProperty(name="Value")

    def invoke(self, context, event):
        e = _tool().Ifc.get_entity(context.active_object)
        self.value = getattr(e, self.field) or ""
        return context.window_manager.invoke_props_dialog(self)

    def execute(self, context):
        import ifcopenshell.api
        tool = _tool()
        for obj in context.selected_objects:
            if e := tool.Ifc.get_entity(obj):
                ifcopenshell.api.run("attribute.edit_attributes", tool.Ifc.get(), product=e,
                                     attributes={self.field: self.value or None})
        return {"FINISHED"}


# ------------------------------------------------------------------ drawing
def _row(col, label: str, value: str):
    row = col.row()
    split = row.split(factor=0.5)
    split.label(text=label)
    split.label(text=value)


def _group(col, title: str):
    box = col.box()
    box.label(text=title)
    return box.column(align=True)


def _vertical_extent(obj):
    zs = [(obj.matrix_world @ v.co).z for v in obj.data.vertices] if obj.type == "MESH" and obj.data.vertices else [0.0]
    return min(zs), max(zs)


def _level_at(z: float):
    for level in structure.levels():
        if abs(structure.level_z(level) - z) < 1e-3:
            return level
    return None


def _draw_type_selector(col, family: str, name: str, ifc_class: str, target: str, type_id: int | None):
    box = col.box()
    box.label(text=family or "")
    row = box.row(align=True)
    op = row.operator("bsbim.choose_type", text=name or "(none)", icon="DOWNARROW_HLT")
    op.ifc_class, op.target = ifc_class, target
    return box


def _extrusion_length_m(entity) -> float | None:
    """Length of a profile-extruded member (beam, brace) in metres, from its body extrusion."""
    import ifcopenshell.util.representation as R
    body = R.get_representation(entity, "Model", "Body", "MODEL_VIEW")
    if body is None:
        return None
    stack = list(body.Items)
    while stack:
        item = stack.pop()
        if item.is_a("IfcExtrudedAreaSolid"):
            return item.Depth / _units_per_m()
        if item.is_a("IfcBooleanResult"):
            stack.append(item.FirstOperand)
        elif item.is_a("IfcMappedItem"):
            stack.extend(item.MappingSource.MappedRepresentation.Items)
    return None


def draw_element(col, context, obj, entity):
    import ifcopenshell.util.element as E
    tool = _tool()
    selected = [o for o in context.selected_objects if tool.Ifc.get_entity(o)]
    etype = E.get_type(entity)
    type_class = _type_class(entity)
    _draw_type_selector(col, etype.ElementType if etype else "", etype.Name if etype else "",
                        type_class or "", "SELECTION", etype.id() if etype else None)
    row = col.row()
    category = revit_ui.CATEGORY.get(entity.is_a(), entity.is_a()[3:])
    row.label(text=f"{category} ({len(selected)})")
    if etype:
        row.operator("bsbim.edit_type", text="Edit Type").type_id = etype.id()

    container = E.get_container(entity)
    cons = _group(col, "Constraints")
    if entity.is_a("IfcColumn"):
        zmin, zmax = _vertical_extent(obj)
        base, top = _level_at(zmin), _level_at(zmax)
        _row(cons, "Base Level", container.Name if container else "-")
        _row(cons, "Base Offset", _fmt(zmin - structure.level_z(base)) if base else _fmt(0.0))
        _row(cons, "Top Level", top.Name if top else "Unconnected")
        _row(cons, "Top Offset", _fmt(0.0) if top else "-")
        _row(cons, "Column Style", "Vertical")
    elif entity.is_a("IfcBeam") or entity.is_a("IfcMember"):
        usage = E.get_material(entity, should_skip_usage=False)
        cp = str(getattr(usage, "CardinalPoint", "") or "")
        _row(cons, "Reference Level", container.Name if container else "-")
        if container:
            zmin, zmax = _vertical_extent(obj)
            _row(cons, "Start Level Offset", _fmt(zmax - structure.level_z(container)))
            _row(cons, "End Level Offset", _fmt(zmax - structure.level_z(container)))
        _row(cons, "z-Justification", Z_JUSTIFICATION.get(cp, "Top"))
    else:
        _row(cons, "Level", container.Name if container else "-")

    if entity.is_a("IfcBeam") or entity.is_a("IfcMember"):
        dims = _group(col, "Dimensions")
        _row(dims, "Length", _fmt(length) if (length := _extrusion_length_m(entity)) is not None else "-")

    ident = _group(col, "Identity Data")
    row = ident.row()
    split = row.split(factor=0.5)
    split.label(text="Mark")
    split.operator("bsbim.edit_identity", text=entity.Tag or " ", emboss=True).field = "Tag"
    row = ident.row()
    split = row.split(factor=0.5)
    split.label(text="Comments")
    split.operator("bsbim.edit_identity", text=entity.Description or " ", emboss=True).field = "Description"


def draw_view(col, context):
    wm = context.window_manager
    view = wm.bsbim_active_view
    is_plan = view.startswith("PLAN:")
    box = col.box()
    box.label(text="Structural Plan" if is_plan else "3D View")
    box.label(text=view[5:] if is_plan else "{3D}")
    graphics = _group(col, "Graphics")
    _row(graphics, "Discipline", "Structural")
    if is_plan:
        _row(graphics, "Detail Level", "Coarse")
        extents = _group(col, "Extents")
        from .browser import PLAN_CUT_M, PLAN_BELOW_M
        from .tools import unit_system
        system = unit_system()
        _row(extents, "View Range: Cut Plane", _fmt(PLAN_CUT_M[system]))
        _row(extents, "View Range: Bottom", _fmt(-PLAN_BELOW_M[system]))
    else:
        _row(graphics, "Detail Level", "Medium")


class BSBIM_PT_properties(bpy.types.Panel):
    bl_label = "Properties"
    bl_idname = "BSBIM_PT_properties"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "BS BIM"
    bl_order = 1

    @classmethod
    def poll(cls, context):
        return revit_ui.revit_mode(context)

    def draw(self, context):
        col = self.layout.column()
        tool = _tool()
        if tool.Ifc.get() is None:
            col.label(text="No project open")
            return
        obj = context.active_object if context.selected_objects else None
        entity = tool.Ifc.get_entity(obj) if obj else None
        if entity is not None and not entity.is_a("IfcTypeObject"):
            draw_element(col, context, obj, entity)
            return
        # Nothing selected: the types used by the placement tools, then the view's properties
        wm = context.window_manager
        from .tools import _pick_type
        for label, cls, target, prop in (("New Structural Column", "IfcColumnType", "COLUMN", "bsbim_new_column_type"),
                                         ("New Beam", "IfcBeamType", "BEAM", "bsbim_new_beam_type")):
            t = _pick_type(cls, getattr(wm, prop))
            if t:
                sub = col.column()
                sub.label(text=label)
                _draw_type_selector(sub, t.ElementType, t.Name, cls, target, t.id())
        draw_view(col, context)


classes = (BSBIM_OT_choose_type, BSBIM_OT_set_type, BSBIM_OT_edit_type, BSBIM_OT_edit_identity, BSBIM_PT_properties)
