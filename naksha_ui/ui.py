from __future__ import annotations

import bpy

from . import operators


class NAKSHA_PT_main(bpy.types.Panel):
    bl_label = "Naksha BIM"
    bl_idname = "NAKSHA_PT_main"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "Naksha"

    def draw(self, context):
        layout = self.layout
        if not operators.bonsai_ready():
            layout.label(text="Bonsai is not enabled", icon="ERROR")

        box = layout.box()
        box.label(text="Project", icon="HOME")
        box.operator("naksha.new_project", icon="FILE_NEW")
        box.operator("bim.load_project", text="Open IFC Project", icon="FILE_FOLDER")

        box = layout.box()
        box.label(text="Revit", icon="IMPORT")
        box.operator("naksha.import_rvt", icon="FILE_3D")

        box = layout.box()
        row = box.row()
        row.label(text="Quality", icon="CHECKMARK")
        if operators.last_report:
            row.operator("naksha.clear_report", text="", icon="X")
        box.operator("naksha.model_report", icon="INFO")
        col = box.column(align=True)
        for line in operators.last_report[:40]:
            col.label(text=line)


class NAKSHA_MT_topbar(bpy.types.Menu):
    bl_label = "Naksha"
    bl_idname = "NAKSHA_MT_topbar"

    def draw(self, context):
        layout = self.layout
        layout.operator("naksha.new_project", icon="FILE_NEW")
        layout.operator("bim.load_project", text="Open IFC Project", icon="FILE_FOLDER")
        layout.separator()
        layout.operator("naksha.import_rvt", icon="FILE_3D")
        layout.separator()
        layout.operator("naksha.model_report", icon="INFO")


def draw_topbar(self, context):
    self.layout.menu(NAKSHA_MT_topbar.bl_idname)


classes = (NAKSHA_PT_main, NAKSHA_MT_topbar)
