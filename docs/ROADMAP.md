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
- [ ] Run the benchmark on real company RVT files  ← **next**

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
