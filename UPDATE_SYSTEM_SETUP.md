# D&D Update System

## Build
From the project root on Windows:

```powershell
powershell -ExecutionPolicy Bypass -File .\build_release.ps1 -Version 1.0.0 -ManifestUrl "https://YOUR-HOST/update.json" -PackageUrl "https://YOUR-HOST/DD_1.0.0.zip"
```

Git is not required.

The output is placed in `release/`:
- `DD_1.0.0.zip` — update package containing the D&D client and bundled updater.
- `update.json` — manifest with version, package URL and SHA-256.

## Publishing
1. Host `DD_1.0.0.zip` at a stable HTTPS URL.
2. Host `update.json` at a stable HTTPS URL.
3. Build the next release with a higher version, e.g. `1.0.1`.
4. Update the URLs in the release command or `desktop/update_config.json`.

## Client flow
The client checks `desktop/update_config.json` (or `DD_UPDATE_MANIFEST_URL`) and compares semantic versions. On Update now it launches `updater/DDUpdater.exe`. The updater runs from a temporary copy, downloads the package, verifies SHA-256, waits for D&D to exit, swaps the installation directory with rollback protection, then starts the new `DD.exe`.

After a successful update the new client shows the existing in-app `What's New` dialog once, using `%APPDATA%\D&D\pending_update.json`.

Keep user data outside the installation directory so client updates never overwrite the database or user files.
