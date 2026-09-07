# D&D Beatmaker CRM — updated working source

This package contains the source files from the supplied project archive, with the current release fixes applied.

Main changes:
- explicit Messenger on license creation (not stored on beats);
- immutable license split snapshots including external producers;
- registered/external producer check;
- new Sent Loops, Non-Profit Tracks and Mixing CRM sections;
- mixing is a separate 100% service fee;
- local backup enabled by default and richer backup export/import;
- welcome screen on first launch and when app version changes;
- lighter background sync;
- Windows tray notifications for new notifications;
- fixed Light theme typo and added Midnight/OLED themes;
- added missing Beat audio fields used by the audio API;
- fixed icon loading to use the executable/source directory and tolerate missing optional icons.

The supplied archive did not contain the root-level launcher main.py, so this package preserves the files that were actually present in the uploaded archive.


## 1.0.4
Added a root-level `main.py` launcher so running `python main.py` from the project root always starts the updated desktop application in `desktop/main.py`. Version bumped to 1.0.4 so the Welcome/What's New screen is shown again.
