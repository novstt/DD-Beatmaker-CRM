# D&D v25

Major logic reset:
- Google Drive integration removed from the app.
- Beats are local catalog records with optional MP3 attachments.
- Add Beat no longer asks who is producer/messenger.
- License creation now defines Producer/Messenger role and percentages.
- Co-producers can be external names or existing D&D users; existing users receive a notification.
- Artist list shows username, platform, status, beats sent, licenses and cash readiness immediately.
- Local MP3 playback and drag-and-drop are supported.
- Added an Admin page for admin accounts.
- Added lightweight API caching and removed repeated notification calls.

## MP3 storage
MP3 files are copied to the OS application-data directory under `D&D/audio`. They are not uploaded to the backend.
