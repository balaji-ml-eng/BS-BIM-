# License register

Every third-party component Naksha uses or ships, and what its license means for us.
Update this file **before** adding any new dependency. Review it with a lawyer before the first commercial release.

Naksha itself is licensed **GPL-3.0-or-later** (see `LICENSE`). All Naksha code is written by us. No code is copied from Bonsai.

| Component | Version | License | How we use it | Shipped to customers? | Notes |
|---|---|---|---|---|---|
| Blender | 5.1.2 | GPL-2.0-or-later | Host application | Yes, bundled in a later installer | GPL: give buyers the source or a written offer |
| Bonsai | 0.9.0.post1 | GPL-3.0-or-later | BIM authoring inside Blender | Yes, bundled in a later installer | `naksha_ui` calls its operators (`bim.load_project`) and `bonsai.tool` |
| IfcOpenShell | 0.9.0.post1 | LGPL-3.0-or-later | IFC engine for `naksha_core` | Yes | LGPL: also usable from closed code if needed later |
| numpy | (bundled with Blender / pip) | BSD-3-Clause | Placement matrices | Yes | |
| rvt (rvt-rs) | 0.15.0 (planned) | Apache-2.0 | RVT Bridge backend | Yes, in the separate bridge | GPL-3 compatible. Keep its `NOTICE` file. Clean-room reader, not affiliated with Autodesk |
| pytest | 9.x | MIT | Tests only | No | |

## Rules
1. No dependency with an unknown, non-commercial, or "free for non-commercial use" license. For example, the DDC RVT converter **cannot** be bundled.
2. Never copy code from Bonsai or another project into `src/naksha_core`. Use Bonsai only through its public operators and APIs from `naksha_ui`.
3. Closed-source tools such as the ODA SDK may only run as a **separate program** that exchanges files. Never load them inside the Blender add-on.
4. Never use AGPL code in Naksha cloud services.
5. Product name, logo and marketing must not use "Revit", "Autodesk", "Blender" or "Bonsai" as our brand. Descriptive use ("opens Revit files") is fine.
