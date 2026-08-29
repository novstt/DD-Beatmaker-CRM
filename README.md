# D&D v26 — Logic & Reliability Pass

## Core rules
- Artist → attach beat → create license.
- One beat can have unlimited licenses for different artists and license formats.
- License percentages are NEVER entered manually.
- If the seller is a producer on the beat: producers split 100% equally.
- If the seller is not a producer: seller is the messenger at a fixed 10%; producers split the remaining 90% equally.
- External producers are allowed. If a matching D&D account exists, that user receives a notification.
- Artist ↔ Beat status is stored independently from the beat itself.
- License splits are snapshotted in `license_splits`, so later beat edits cannot rewrite old financial history.
- Deleting a beat archives it instead of destroying license history.

## Audio
- MP3 only.
- Stored locally in the Windows app-data directory.
- No Google Drive dependency.

## Desktop background mode
- Clicking the window X hides D&D to the Windows system tray.
- Tray menu: Open D&D / Quit D&D.
- Background polling checks connectivity and unread notifications without blocking the UI.
- The tray icon is the only way to fully quit from the normal UI.

## Online deployment
The desktop client reads `DD_API_URL`. Local development uses `http://127.0.0.1:8000`. For real multi-user online use, deploy the FastAPI backend + PostgreSQL behind HTTPS and set `DD_API_URL=https://your-domain` before building/distributing the desktop app.

## Run
```powershell
cd backend
pip install -r requirements.txt
# configure environment
uvicorn app.main:app --host 0.0.0.0 --port 8000
```
Desktop:
```powershell
cd desktop
pip install -r requirements.txt
$env:DD_API_URL="http://127.0.0.1:8000"
python main.py
```
