# D&D v26 reliability / logic checklist

## Data & license logic
1. Artist can receive the same beat multiple times; each license is independent.
2. A license can only be created for a beat already attached to that artist.
3. A beat can have multiple producers; shares are never manually editable.
4. Seller is a producer if their D&D account is one of the beat producers.
5. Otherwise seller is messenger at exactly 10%; producers split the remaining 90% equally.
6. One producer = 100%; two producers = 50/50; three = equal thirds.
7. License splits are snapshotted in `license_splits`; editing the beat later does not change old licenses.
8. Same beat can have MP3, WAV, Trackout and Exclusive licenses for different artists.
9. External producers can exist without an account; linked accounts receive notifications.
10. Revenue from another user's sale of your producer credit appears in your earnings.

## Artist ↔ Beat
11. Attachment statuses: Sent, Wants to record, Recorded, Wants to buy, Bought, Not interested, Listened, No reply.
12. Beat status is separate from artist attachment status.
13. Duplicate artist/beat attachment is updated instead of duplicated.

## Audio / sync
14. Only MP3 accepted.
15. MP3 is stored locally for fast playback and uploaded to server storage for multi-device sync.
16. Failed uploads are queued locally and retried by background sync.
17. Deleting a beat archives it; sold-license history remains intact.

## Desktop
18. X hides the window to the Windows system tray.
19. Tray menu has Open D&D and Quit D&D.
20. Background timer checks connectivity and unread notifications without blocking the UI.
21. GET requests retry briefly; writes are not blindly retried to avoid duplicate sales.
22. API endpoint is configurable through DD_API_URL.

## Backend
23. PostgreSQL is persistent through Docker volume.
24. Audio is persistent through a separate Docker volume.
25. Health endpoint is available.
26. SQLAlchemy metadata creates cleanly on a fresh SQLite test database.
27. Python syntax compilation passes for desktop and backend.
