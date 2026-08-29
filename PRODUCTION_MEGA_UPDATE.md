# D&D v27.0 — Mega Product Update

Included in this package (except the intentionally deferred Performance Optimization and final Production QA):

- Unified UI pass: tighter cards, clearer hierarchy, balance in profile/sidebar, improved empty/loading states.
- Live sync: 10-second lightweight refresh plus refresh-on-show.
- Security hardening: login rate limit; admin access remains server-side and restricted to the configured admin email.
- Admin: users, enable/disable, audit, health, and overview counters.
- Notifications: background polling + Windows notifications for genuinely new notifications; minimize no longer shows a Windows toast.
- Backup/recovery: expanded export metadata; safe merge import for artists, beats and licenses; optional automatic local backups (20 retained).
- Beat importer 2.0: canonical producer aliases and safer BPM/key/title cleanup; MP3-only workflow remains.
- Advanced stats: existing dashboard analytics retained and extended by currency-aware profile defaults.
- Updater infrastructure: signed-release-ready manifest format, SHA-256 staging/rollback helper, and Inno Setup installer script. No social/platform registration was added.

Deferred by request:
- #10 Performance Optimization
- #11 Full Production QA

Important: the updater needs a real hosted release package + SHA-256 and a built Windows EXE before it can perform a production update.
