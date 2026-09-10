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


## 1.0.6 release notes
- `License.price` is gross sale value only. Personal income comes exclusively from immutable `LicenseSplit.amount`.
- Messenger is a per-license role and receives 10% when selected; producer pool receives the remaining 90%.
- Registered and external producer credits both participate in splits.
- Backup import preserves historical `LicenseSplit.user_id` when present, preventing username/alias changes from redirecting old earnings.
- `/api/licenses/{id}/financial-summary` exposes gross, personal earnings, split totals and an integrity flag for QA.
- Reminder polling remains lightweight and is separate from full workspace refresh.

### Production deployment
The desktop client defaults to the production API URL. After deploying backend changes, verify the production `/health` endpoint and create a test sale before release. A local desktop run alone does not update the production backend.
