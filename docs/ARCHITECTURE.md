# Architecture

```
 ┌───────────────────────── Blender ─────────────────────────┐
 │  Bonsai (GPL-3)            bsbim_ui (our UI layer)        │
 │   IFC authoring  ◄─────── panel, menu, operators           │
 │                             │ vendored copy                │
 │                             ▼                              │
 │                        bsbim_core (our engine)            │
 └─────────────────────────────┬──────────────────────────────┘
                               │ subprocess (files only)
                               ▼
                   bsbim_rvt_bridge (separate program)
                     backends: rvt-rs | rvt-open* | RvtIO* | Revit add-in*
                     .rvt ──► IFC4 + JSON quality report
```
\* planned

## Why this split
| Rule | Reason |
|---|---|
| `bsbim_core` never imports `bpy` or `bonsai` | It is testable without Blender, reusable in the bridge and in cloud services, and the copyright stays fully ours |
| `bsbim_ui` holds no business logic | The UI can change, or move to another host app, without touching the engine |
| The RVT Bridge is a separate process | It isolates third-party readers (crashes, licenses, legal risk). It can be removed or replaced without touching the product |
| Backends sit behind one interface | Several readers can be compared on the same files, with the best one chosen per file |

## Units
IFC projects are created in **millimetres**. Template thicknesses and level elevations are in mm.
`geometry.edit_object_placement` is called with SI metres (`is_si=True`).
