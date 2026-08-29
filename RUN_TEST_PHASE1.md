# D&D v26 Phase 1

This build starts from the last working v24 base and adds the first production logic pass.

## Start backend
```powershell
docker compose down
docker compose up --build
```

## Start desktop in another terminal
```powershell
cd desktop
python -m pip install -r requirements.txt
python main.py
```

## Test order
1. Register/login.
2. Confirm only quikinnnproducer@gmail.com sees Admin.
3. Add an artist.
4. Add an MP3 beat and a co-producer.
5. Attach the beat to the artist.
6. Create MP3 license.
7. Create WAV license for the same beat and another artist.
8. Verify percentages are automatic and not editable.
9. Verify notifications for registered co-producers.
10. Close with X: app should hide to Windows tray. Right-click tray -> Quit D&D exits.
