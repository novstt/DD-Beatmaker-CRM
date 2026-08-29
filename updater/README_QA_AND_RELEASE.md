# D&D v27 — Final QA + Release layer

## 10. Performance
- Lightweight refresh is 30s, not 10s.
- Session refresh no longer clears every cache entry.
- Current entity caches are invalidated intentionally during lightweight sync.
- No Windows tray balloons are emitted.

## 11. Production QA
Run:
`python qa/production_qa.py`

Then run the manual two-account checklist in `RUN_PRODUCTION_QA.md`.

## 12. Windows release / updater
- `build_release.ps1` builds the GUI with PyInstaller.
- `installer/DD.iss` creates the Windows installer.
- `updater/updater.py` verifies SHA-256, stages a ZIP, swaps folders, and rolls back on failure.
- The updater is deliberately not hard-coded to a public URL; configure the release manifest before distribution.
