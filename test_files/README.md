# Test files

Put sample Revit files (.rvt / .rfa) here for the RVT Bridge benchmark.
Everything in this folder except this README is ignored by Git, so client data never leaves this machine.

A good test set:
- 20–30 real projects
- different Revit versions (2019 → 2026)
- small, medium and large (over 100 MB)
- some workshared (central) models and some families (.rfa)

Run the benchmark:

```powershell
.venv\Scripts\python -m naksha_rvt_bridge batch test_files -o build\rvt_benchmark
```
