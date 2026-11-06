# BS BIM: Revit working style specification

**Goal:** a Revit user who does **structural and MEP** work for **US and UK** clients can open BS BIM and work without retraining. Blender and Bonsai do the work underneath, but the user sees Revit concepts, Revit names, Revit shortcuts and Revit mouse behaviour.

**Rule for every feature:** first write down how Revit does it, then build the same behaviour. If we can't match it exactly, the difference must be small and documented here.

Status key: ✅ Bonsai already has the engine · 🔧 we wrap Bonsai in Revit-style UI · 🆕 we build it

---

## 1. Principles
1. **Revit words only** in the UI: Family, Type, Level, Grid, View, Sheet, Edit Type, Type Properties, Visibility/Graphics. No Blender or IFC terms in front of the user.
2. **Hide Blender.** BS BIM opens in its own workspace with the Blender editors, menus and modes hidden. Power users can still switch to the "Blender" workspace.
3. **Same muscle memory:** shortcuts, mouse, selection, Esc to cancel, and Tab to cycle.
4. **IFC underneath:** everything is still saved as clean IFC, which is our selling point.
5. **Test with real Revit users.** Each phase is accepted only when 2–3 Revit MEP/structural users say it "feels like Revit" (see section 10).

## 2. Screen layout

```
┌──────────────────────────────────────────────────────────────────────┐
│ Quick Access Toolbar   |   File  Structure  Systems  Insert  Annotate│  ← Ribbon tabs 🆕
│                                  Analyze  View  Manage  Modify       │
│ [Beam] [Column] [Wall] [Floor] [Brace] [Foundation] ...              │  ← Ribbon panels 🆕
├──────────────────────────────────────────────────────────────────────┤
│ Options Bar: Level 1 ▾  Height: 10' 0"  Chain ☑  Offset 0"           │  ← Options Bar 🆕
├──────────────┬───────────────────────────────────────────────────────┤
│ Properties   │                                                       │
│ [W12x26   ▾] │                                                       │
│ Edit Type    │          Drawing area (plan / 3D / section)           │
│ Constraints  │                                                       │
│ Ref Level..  │                                                       │
├──────────────┤                                                       │
│Project Browser│                                                      │
│ ▸ Views      │                                                       │
│ ▸ Schedules  ├───────────────────────────────────────────────────────┤
│ ▸ Sheets     │ View Control Bar: 1/8"=1'-0" ▢Coarse ◐Shaded ☀ ...    │ 🆕
├──────────────┴───────────────────────────────────────────────────────┤
│ Status bar: "Click to enter beam start point"                        │ 🔧
└──────────────────────────────────────────────────────────────────────┘
```

## 3. Ribbon (focused on structure and MEP)

**Reference: Revit 2027.3, observed on 2026-11-06** (screenshots kept locally in `H:\Bala Data\BSBIM_Reference`, never in Git):
- Tab order: File · Architecture · **Structure** · Concrete · Steel · **Systems** · Insert · Annotate · Analyze · Massing & Site · Collaborate · View · Manage · Add-Ins · Modify
- **Structure** tab panels, left to right: Select (Modify) | **Structure**: Beam, Wall, Column, Floor, Truss, Brace, Beam System | **Connection**: Connection, Connection Automation | **Foundation**: Isolated, Wall, Slab | **Model**: Component, Model Text, Model Line, Model Group | **Opening**: By Face, Shaft, Wall, Vertical, Dormer | **Datum**: Level, Grid | **Work Plane**: Set, Show, Ref Plane, Viewer
- **Systems** tab panels: Select (Modify) | **HVAC**: Duct, Duct Placeholder, Duct Fitting, Duct Accessory, Convert to Flex Duct, Flex Duct, Air Terminal | **Fabrication**: Fabrication Part, Multi-Point Routing | **MEP Detailing** | **P&ID Collaboration** | **Mechanical**: Mechanical Equipment, Mechanical Control Device | **Plumbing & Piping**: Pipe, Pipe Placeholder, Parallel Pipes, Plumbing Equipment, Plumbing Fixture, Sprinkler | **Electrical**: Wire, Cable Tray, Conduit, Parallel Conduits, Electrical Equipment, Device, Lighting Fixture | **Model**: Component | **Work Plane**
- Status bar idle text: "Click to select, TAB for alternates, CTRL adds, SHIFT unselects."
- Project Browser groups (structural sample): Views (all) → Structural Plans, 3D Views, Elevations (Building Elevation), Sections (Building Section), Detail Views (Detail), Renderings, ... Legends, Schedules/Quantities, Sheets, Families, Groups, Revit Links

BS BIM copies this **panel order and naming** exactly for the Structure and Systems tabs.


| Tab | Panel → commands | Engine |
|---|---|---|
| **Structure** | Structure: Beam, Wall, Column, Floor, Truss, Brace, Beam System · Foundation: Isolated, Wall, Slab · Reinforcement (later) · Datum: Level, Grid · Work Plane: Ref Plane | ✅ beam, column, member, wall, slab, footing, pile tools 🔧 |
| **Systems** | HVAC: Duct, Duct Placeholder, Duct Fitting, Duct Accessory, Air Terminal · Mechanical Equipment · Plumbing & Piping: Pipe, Pipe Fitting, Pipe Accessory, Plumbing Fixture, Sprinkler · Electrical: Cable Tray, Conduit, Wire, Electrical Equipment, Lighting Fixture | ✅ duct, pipe, cable carrier tools, bends, transitions, ports, systems 🔧 · placeholders and wires 🆕 |
| **Insert** | Link IFC, Link Revit (via RVT Bridge), Link CAD, Load Family (type library), Import | 🔧 / ✅ RVT Bridge |
| **Annotate** | Aligned Dimension, Spot Elevation, Text, Tag by Category, Tag All, Keynote, Detail Line | ✅ annotations 🔧 |
| **Analyze** | Check Duct Systems, Check Pipe Systems, Interference Check (clash), Analytical model | ✅ clash, structural 🔧 · system checks 🆕 |
| **View** | Visibility/Graphics, Plan View, 3D View, Section, Elevation, Callout, Sheet, Schedule, Thin Lines, Tile, Close Inactive | ✅ drawings, sheets 🔧 · V/G 🆕 |
| **Manage** | Project Units, Object Styles, Project Parameters, Shared Parameters, MEP Settings, Routing Preferences, Transfer Standards, Purge | 🆕 mostly |
| **Modify** (contextual) | Move, Copy, Rotate, Mirror, Array, Align, Trim/Extend, Split, Offset, Pin, Delete, Match Type, plus element-specific tools (Edit Profile, Join, Add Bend, ...) | ✅ partly 🔧 |

## 4. Keyboard shortcuts

Revit uses **two-letter sequences** (type W then A). Blender has no such feature, so we build a **shortcut engine** 🆕:
- A letter key starts a short listen (about 1 s) for the second letter. The status bar shows the matching commands.
- **Import the user's own Revit `KeyboardShortcuts.xml`** (Revit: View → User Interface → Keyboard Shortcuts → Export). This copies company custom shortcuts exactly. It is our strongest "feels like Revit" feature.
- Built-in defaults below. **Verify against an exported Revit file before release.**

| Keys | Command | Keys | Command |
|---|---|---|---|
| WA | Wall | DT | Duct |
| BM | Beam (structural framing) | PI | Pipe |
| CL | Structural column | CT | Cable tray |
| SB | Structural floor | CN | Conduit |
| LL | Level | DF | Duct fitting |
| GR | Grid | PF | Pipe fitting |
| RP | Reference plane | DA | Duct accessory |
| DI | Aligned dimension | PA | Pipe accessory |
| TG | Tag by category | AT | Air terminal |
| VV / VG | Visibility/Graphics | ME | Mechanical equipment |
| HH / HI | Hide / Isolate element (temporary) | PX | Plumbing fixture |
| HC / IC | Hide / Isolate category | SK | Sprinkler |
| HR | Reset temporary hide/isolate | EE | Electrical equipment |
| ZF / ZA | Zoom to fit / Zoom all | LF | Lighting fixture |
| MV, CO, RO | Move, Copy, Rotate | EW | Wire |
| MM, AR, AL | Mirror, Array, Align | TR, SL, OF | Trim/Extend, Split, Offset |
| PN / UP | Pin / Unpin | DE | Delete |
| MA | Match type properties | PP | Properties palette |

## 5. Mouse and selection 🔧
| Action | Revit | Blender default → BS BIM change |
|---|---|---|
| Zoom | Wheel, zooms at the cursor | Wheel → turn on "zoom to mouse position" |
| Pan | Middle-drag | Middle-drag is orbit → **swap** |
| Orbit (3D) | Shift + middle-drag | Shift + middle is pan → **swap** |
| Select | Left-click | Same |
| Add / remove from selection | Ctrl / Shift + click | Shift adds → **remap** |
| Window select | Left→right selects only fully inside; right→left selects crossing | Box select only → 🆕 direction-aware |
| Cycle overlapping elements | Tab | 🆕 |
| Cancel | Esc (twice exits the tool) | 🔧 |
| Right-click | Context menu (Repeat, Cancel, Select All Instances, Zoom...) | 🆕 Revit-style menu |

## 6. Views and Project Browser 🔧🆕
- Every Revit view becomes a Bonsai **drawing** (camera plus view settings). Plans follow **levels**: creating a level offers "create plan views", as Revit does.
- Browser structure as in Revit's MEP/structural templates:
  ```
  Views (Discipline)
    Structural: Structural Plans (Level 1, Level 2...), 3D, Sections, Elevations
    Mechanical: HVAC Floor Plans, HVAC Ceiling Plans
    Plumbing:   Plumbing Plans
    Electrical: Lighting / Power Plans
  Legends · Schedules/Quantities · Sheets · Families · Groups · Revit Links (IFC links)
  ```
- Per-view settings: **View Range** (cut plane, top, bottom, view depth), **Detail Level** (Coarse, Medium, Fine; for example, a pipe as a single line in Coarse and double lines in Fine), **Visual Style**, **Scale**, **Discipline**, **View Template**, **V/G overrides** per category.

## 7. Properties palette 🆕 (wraps Bonsai attributes and property sets)
- **Type Selector** at the top (for example `W-Wide Flange : W12x26`), then **Edit Type** → Type Properties dialog with Duplicate and Rename.
- Instance properties in **Revit groups and order**:
  - Beam: Constraints (Reference Level, Start/End Level Offset, z-Justification, Lateral Justification) · Structural (Structural Usage, Cut Length) · Dimensions (Length) · Identity Data (Mark, Comments) · Phasing
  - Duct/Pipe: Constraints (Horizontal/Vertical Justification, Reference Level, Offset/Middle Elevation) · Mechanical (System Classification, System Type, System Name, Size, Flow, Velocity) · Dimensions · Identity Data
- Values are stored in **standard IFC property sets** where they exist (Pset_BeamCommon, Pset_DuctSegmentTypeCommon...). Revit-only values go into a `BSBIM_` property set.

## 8. Families and Types (Revit concept → IFC)
| Revit | BS BIM (IFC underneath) |
|---|---|
| System family (Wall, Floor, Duct, Pipe) | IfcWallType / IfcSlabType / IfcDuctSegmentType / IfcPipeSegmentType |
| Loadable family (column, beam, fitting, equipment) | Element type with a parametric profile or shape |
| Type (W12x26, 12"x8" duct) | IFC type + profile + property set |
| Instance | IFC element occurrence |
| Load Family | Load from a BS BIM type library (.ifc) ✅ Bonsai library system |
| Routing Preferences (fittings used per pipe type) | 🆕 rules: pipe type → elbow / tee / transition types, applied automatically while drawing |

## 9. US and UK project templates 🆕 (replace the Indian sample template as default)
| | **US template** | **UK template** |
|---|---|---|
| Units | Feet and inches, shown as `10' - 6"`; areas in SF | Millimetres; areas in m² |
| Structural steel | AISC (W, HSS, WT, L, C, MC, HP) ✅ Bonsai US Steel library, 2,091 sections | UB, UC, PFC, CHS/SHS/RHS (BS EN 10365 / 10210) 🆕 library to build |
| Concrete | ACI 318 names (4000 psi) | BS EN 206 (C32/40) |
| Ducts | Rectangular, round and oval sizes in inches (SMACNA practice) | Sizes in mm (DW/144 practice) |
| Pipes | Copper Type L, steel Schedule 40, PVC Sch 40, cast iron (ASTM / ASME B36.10) | Copper EN 1057, steel EN 10255, PVC/ABS |
| Systems | Supply, Return, Exhaust Air · Domestic Hot/Cold Water · Sanitary · Fire Protection | Same (UK names: LTHW, CHW, MCWS, DHWS...) |
| Classification | OmniClass / UniFormat | Uniclass 2015 |
| Sheets | ARCH D 24"×36", US title block | ISO A1 / A0, UK title block, BS EN ISO 19650 file naming |
| Levels | Level 1, Level 2, Roof (US style) | Ground Floor, First Floor... (UK style) |

The template content will be checked against the firm's real Revit templates (.rte). We can read those with the RVT Bridge (level names, types, sizes) when available.

## 10. Acceptance tests ("does it feel like Revit?")
Each test is timed with a Revit user. Target: within 1.5× their Revit time, with no need to ask "how?".
1. Open BS BIM → New project (US template) → the Project Browser shows Structural Plans for Level 1 and Level 2.
2. Type **GR** → draw 4 grids. Type **CL** → place W10x33 columns at the grid intersections.
3. Type **BM** → choose W12x26 in the Type Selector → draw beams between columns. The Properties palette shows Reference Level and z-Justification.
4. Type **DT** → 24"x12" supply duct → draw 3 runs with a turn. Elbows are added automatically.
5. Type **PI** → 2" copper pipe → draw with a rise. Fittings are added automatically.
6. **VV** → hide Ducts in a structural plan. **HI** → isolate one beam. **HR** → reset.
7. Section view through the beam. Dimension it with **DI**. Tag it with **TG**.
8. Place the views on an ARCH D sheet → print to PDF.

## 11. Build order
| Phase | Content | Why first |
|---|---|---|
| **A: Revit shell** | BS BIM workspace (Blender hidden), Revit mouse, shortcut engine with Revit XML import, Ribbon (Structure + Systems tabs), Properties palette with Type Selector, Project Browser (levels and views) | Users feel it on day one |
| **B: US and UK templates** | Units, levels, US steel (from Bonsai), UK steel library, duct and pipe types, systems, title blocks | Correct content for real clients |
| **C: Structure workflow** | Grids → columns → beams → floors → foundations, Revit-like placement options (justification, chain, at grids) | Main client work |
| **D: MEP workflow** | Duct, pipe, cable tray and conduit drawing with automatic fittings (routing preferences), systems, equipment connection | Main client work |
| **E: Documentation** | View range, detail levels, V/G, tags, dimensions, schedules, sheets, PDF/DWG | Deliverables |

## 12. Inputs needed from the firm (kept confidential, never committed to Git)
1. Exported Revit `KeyboardShortcuts.xml` (from one MEP and one structural user)
2. Company Revit templates (.rte) for US and UK projects
3. A screenshot of a typical Revit screen (ribbon, browser, properties) from the team
4. 2–3 Revit users willing to test each phase
