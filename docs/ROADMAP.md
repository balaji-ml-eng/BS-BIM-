# Roadmap

Business model: **Option A**, open-source GPL product. Revenue comes from support, the content library, cloud services, RVT conversion and training.

## Status (2026-11-06)
- [x] Dev environment: portable Blender 5.1.2 + Bonsai 0.9.0 on H:
- [x] M0: repository, license register, tests, build and install script, headless Blender smoke test
- [x] `bsbim_core`: new project from template (mm units, contexts, site, building, storeys, 7 Indian-standard wall and slab types)
- [x] `bsbim_core`: model quality report and score
- [x] `bsbim_rvt_bridge`: CLI (`backends`, `info`, `convert`, `batch`), rvt-rs backend, automatic quality fallback
- [x] `bsbim_ui`: BS BIM panel and top menu (New Project, Open Revit File, Quality Report), preferences
- [x] `rvt` 0.15.0 installed (rvt-rs reader)
- [x] First real benchmark (2 confidential Revit 2024 models, ~150 MB each, results kept off Git):
  - Model A (Revit 2024 build 2024-04): 736 elements in 30 s. Walls, roof, doors, beams, columns, footings, pipes, ducts and conduits all came through on the correct storeys. Only 34% have their real shape (485 are placeholder boxes), and the reader decoded about 3% of the records Revit declares. Score 80.5.
  - Model B (same project, saved by Revit 2024 build 2025-09): **0 elements**. Only materials and levels were read. The newer 2024 update build is not yet supported by rvt-rs 0.15.
- [x] Honest scoring: the report separates real shapes from placeholder boxes, and adds Revit coverage %
- [x] `tools/render_preview.py`: headless preview images for visual checks
- [x] Public benchmark: 20 official Autodesk sample files (Revit 2020–2027, 6 MB–132 MB), stored in `H:\Bala Data\PublicSampleModels`
  - 20 of 20 converted, with no failures. Speed: 1–29 s per file.
  - The same model gives the same element count in every version (rac_basic 450, rst_basic 454), so element reading works for 2020–2027.
  - Real shape (not box): 12% on 2020–2022 and about 27% on 2024–2027 (rac_basic). rst_basic reaches 83% on 2024 but only 6–7% on 2025–2027 (a regression in rvt-rs).
  - Type and material data: weak on 2020–2023 architecture (45% / 35%), good on 2024+ (99% / 89%).
  - Snowdon Towers Arch 2024 (95 MB, 5,993 elements): score 86.5. Snowdon Structural 2024: score 95.8. Previews look correct.
  - Largest gaps: MEP (rme 2024: 89% boxes) and older versions (2020–2023: mostly boxes).
- [x] RvtIO backend code + `batch --backend all` compare mode (tests use a fake rvtio)
- [ ] Install RvtIO (needs user approval) and run the compare on all 22 files  ← **next**

## M1: RVT Bridge (weeks 3–14)
- [ ] Benchmark rvt-rs on 20–30 company files (Revit 2019–2026, small to large)
- [ ] rvt-open backend (needs Rust build or published wheels)
- [ ] RvtIO backend (.NET CLI)
- [ ] Mapping layer: Revit categories, families and types → clean IFC classes and BS BIM types
- [ ] Per-file best-backend selection
- [ ] Send fixes and test feedback upstream

## M2: Revit add-in (weeks 10–24)
- [ ] C# add-in on the official Revit API: export clean IFC with BS BIM mapping
- [ ] Import BS BIM IFC back as native Revit elements

## Structure first (user priority: Structure → Architecture → MEP)
- [x] US Structural template: feet-inches, Level 1/Level 2 (10'-0"), AISC steel from Bonsai's library with Revit names
      (W Shapes : W12x26, W Shapes-Column : W10x33, HSS-Hollow Structural Section-Column : HSS6x6x3/8, C Shapes, L-Angle),
      concrete beams and columns, floors, walls, Revit material names (Steel ASTM A992, Concrete, Normal Weight - 4 ksi)
- [x] UK Structural template: mm, concrete columns, beams, floors and walls (C30/C40)
- [ ] UK steel sections UB, UC, PFC, SHS, CHS (BS EN 10365/10210). Needs a verified dimension table.
- [x] Revit-style length format and input: `10' - 6 1/2"`, `4000`
- [x] Column placement: Depth (level below → current) / Height (current → level above), like Revit
- [x] Beam placement: two points, z-Justification Top at level, like Revit
- [x] Blender structural test: 18 checks (heights, depth, lengths, types, levels, saved IFC)
- [ ] Beam ends trimmed at column faces (Revit cutback joins)
- [x] Revit-style screen: File + Revit tabs, Structure ribbon in Revit 2027 order, contextual "Modify | <Category>" tab
- [x] Properties palette: Type Selector (Family / Type), Edit Type, Constraints, Dimensions, Identity Data, view properties
- [x] Project Browser: Views (all) > Structural Plans per level, 3D Views {3D}, Families
- [x] Click tools: Column (CL), Beam (BM, with preview line), Brace, Level (LL), Grid (GR, labelled 1-2-3 / A-B-C), snapping to grid intersections and columns
- [x] Revit mouse (middle pan, Shift+middle orbit, zoom at cursor, Ctrl/Shift select) and two-letter shortcuts (CL, BM, GR, LL, MV, RO, CO, DE, HH, HI, HR, ZF...)
- [x] Visual GUI test (tools/ui_screenshot.py) compared with Revit 2027 screenshots
- [x] Point clouds (Insert > Point Cloud): E57, LAS/LAZ, PLY, PTS, XYZ via a separate converter; GPU display with real colours,
      thinned to 3M points; link stored in the IFC and restored on reopen; Project Browser show/hide/remove;
      ReCap .rcp/.rcs refused with advice (no open-source reader). Tested on Union Station (6.4M points, E57)
- [x] Real interaction test with simulated mouse/keyboard (tools/ui_interaction_test.py): 18 checks pass
- [x] Revit-style click selection (tolerant pick, smallest element wins), immediate Delete, own pan/orbit
- [x] BS BIM screen saved as Blender's start-up layout; Bonsai no longer switches workspaces in Revit mode
- [x] Drawn Revit-style Properties palette + Project Browser dock (Blender sidebar and select-mode row removed); small stacked ribbon buttons; ribbon tab row, File tab, Quick Access row
- [ ] Open a Revit file together with its linked point cloud automatically (needs the link path from the RVT)
- [ ] Interactive (mouse) testing of the click tools by a person
- [ ] Grids with Revit bubbles (1, 2, 3 / A, B, C), place columns "At Grids"
- [ ] Floors, walls, isolated and wall foundations, braces

## Revit working style: see docs/REVIT_WORKFLOW.md (focus: structure + MEP, US + UK clients)

## M3: UI shell (weeks 5–18)
- [ ] Revit-like ribbon/toolbar: Wall, Door, Window, Floor, Roof, Stair, Column, Beam
- [ ] Project Browser (views, sheets, schedules), Properties panel, Type Selector
- [ ] Revit-style keyboard shortcuts (WA, DR, WN, ...)

## M4: Content library (weeks 6–30)
- [ ] Doors, windows, columns, beams, stairs, railings, furniture, basic MEP
- [ ] Title blocks, annotation styles, Indian authority drawing standards

## M5: Modeling tools (weeks 10–30)
## M6: Documentation: plans, sections, sheets, schedules, PDF/DWG (weeks 16–40)
## M7: `.bsbim` format + collaboration server (weeks 24–46)
## M8: One-click installer + auto update (weeks 8–12, ongoing)
## M9: Internal rollout (months 4–14)
## M10: Commercial launch (months 12–18)

## Known limitations of v0.1
- RVT conversion blocks only the status bar (modal); there is no cancel button yet.
- The model report reads all property sets, which may be slow on 100k+ element models.
- No open-source tool can **write** RVT. Clients who need RVT get IFC (Revit opens it) or, later, output from the Revit add-in.
