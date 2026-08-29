# D&D v27.0 Mega Update

This is the all-at-once product pass requested by the project owner.

## Included
- Full UI polish baseline (dark/light, cards, navigation, profile balance, cleaner spacing, player bar).
- Live sync every 10 seconds + refresh-on-show.
- Security hardening: server-side admin authorization and login rate limiting.
- Admin dashboard counters, users, audit log and system health.
- Notifications background polling; minimizing the window is silent (no Windows "still running" toast).
- Backup export/import expanded to artists, beats and licenses with safe merge rules.
- Optional automatic local backups every 10 minutes, retaining the latest 20.
- Beat importer 2.0: filename + optional ID3 title/artist metadata, producer alias normalization, BPM/key detection and metadata cleanup.
- Currency-aware statistics and revenue-by-format data.
- Updater infrastructure: version manifest, SHA-256 verified staging/rollback helper and Inno Setup script.
- No social/platform registration providers were added.

## Explicitly deferred
- Performance Optimization pass (#10).
- Full Production QA (#11).

## Run from source
Backend (project root):
```powershell
docker compose up --build
```
Desktop (second terminal):
```powershell
cd desktop
pip install -r requirements.txt
python main.py
```

## Updater release
Publish an update ZIP and a JSON manifest based on `updater/update.json.example`, fill in the real package URL and SHA-256, then set `DD_LATEST_VERSION` and `DD_UPDATE_URL` for the API.

## Windows installer
Install Inno Setup, build the EXE with `build_release.ps1`, then compile `installer/DD.iss`.
