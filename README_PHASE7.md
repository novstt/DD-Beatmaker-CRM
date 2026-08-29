# D&D v26 Phase 7 — Platform & Reliability

This phase builds on the last working Phase 6 base.

## Included
- Admin audit log with server-side records.
- Admin system health endpoint.
- License version snapshots; status changes create a version.
- License version history in the license detail window.
- Safe backup merge: existing artists are preserved, only missing artists are imported.
- Backup import is now functional in Settings.
- Artist score endpoint groundwork.
- Update channel/version endpoint and a desktop "Check for updates" action.
- Existing currency/profile, payment status, goals, live refresh, beats/CRM features are preserved.

## Test
1. Admin -> Audit Log; toggle a normal test user and confirm the action is logged.
2. Admin -> System Health; confirm API/database/version are healthy.
3. License -> change Pending/Paid; open license again and inspect Version History.
4. Settings -> Export backup, then Import backup on a clean test account; verify existing records are not overwritten.
5. Settings -> Check for updates; verify current D&D version is shown.
