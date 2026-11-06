from __future__ import annotations

import bpy

from . import operators


class BSBIM_PT_main(bpy.types.Panel):
    bl_label = "BS BIM"
    bl_idname = "BSBIM_PT_main"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "BS BIM"

    def draw(self, context):
        layout = self.layout
        if not operators.bonsai_ready():
            layout.label(text="Bonsai is not enabled", icon="ERROR")

        box = layout.box()
        box.label(text="Project", icon="HOME")
        box.operator("bsbim.new_project", icon="FILE_NEW")
        box.operator("bim.load_project", text="Open IFC Project", icon="FILE_FOLDER")

        box = layout.box()
        box.label(text="Revit", icon="IMPORT")
        box.operator("bsbim.import_rvt", icon="FILE_3D")

        box = layout.box()
        row = box.row()
        row.label(text="Quality", icon="CHECKMARK")
        if operators.last_report:
            row.operator("bsbim.clear_report", text="", icon="X")
        box.operator("bsbim.model_report", icon="INFO")
        col = box.column(align=True)
        for line in operators.last_report[:40]:
            col.label(text=line)


class BSBIM_MT_topbar(bpy.types.Menu):
    bl_label = "BS BIM"
    bl_idname = "BSBIM_MT_topbar"

    def draw(self, context):
        layout = self.layout
        layout.operator("bsbim.new_project", icon="FILE_NEW")
        layout.operator("bim.load_project", text="Open IFC Project", icon="FILE_FOLDER")
        layout.separator()
        layout.operator("bsbim.import_rvt", icon="FILE_3D")
        layout.separator()
        layout.operator("bsbim.model_report", icon="INFO")


def draw_topbar(self, context):
    self.layout.menu(BSBIM_MT_topbar.bl_idname)


classes = (BSBIM_PT_main, BSBIM_MT_topbar)
