# D&D Update System

The desktop client now supports a real update flow:

1. It reads `update_config.json`.
2. It checks the configured manifest.
3. It compares the installed version with the manifest version.
4. If a newer version exists, D&D shows an in-app update dialog.
5. `Update now` starts `updater.exe` and closes the current client.
6. The updater downloads the ZIP, verifies SHA-256, validates ZIP paths, swaps the install directory, and launches the new D&D executable.

## Recommended hosting: GitHub Releases

The build script can derive the GitHub owner/repository from `git remote origin`.
The generated manifest URL is:

`https://github.com/<OWNER>/<REPO>/releases/latest/download/update.json`

For each release:

- Build with `build_release.ps1 -Version 0.29.0` (or the next version).
- Upload `release/DD_<VERSION>.zip` to the GitHub Release as an asset.
- Upload `release/update.json` to the same release with the exact filename `update.json`.

The generated `update.json` contains the package URL and SHA-256 hash.

## Development fallback

When running from source, the client can launch `updater/updater.py` directly. A packaged EXE uses `updater/DDUpdater.exe`.

## Important

The updater replaces only the installed desktop client directory. The PostgreSQL database and server data are not part of the desktop package and are not touched by the update.
