# D&D — Google Drive browser connection

D&D uses Google's official installed-app OAuth flow with a local loopback redirect.
The browser handles the Google login; D&D never asks for your Google password.

## One-time setup

1. In Google Cloud, create/select a project.
2. Enable **Google Drive API**.
3. Configure the OAuth consent screen for your personal/testing use.
4. Create an OAuth client of type **Desktop app**.
5. Download the JSON credentials.
6. In D&D: **Settings → Google Drive → OAuth JSON** and select that JSON.
7. Click **Connect Google Drive**.
8. Authorize in the browser.
9. Click **Load folders** and select your beat folder.
10. Enter the producer username used for imported beats.
11. Enable **Auto import** if desired.

D&D requests only the read-only Drive scope:
`https://www.googleapis.com/auth/drive.readonly`

It can see/download Drive files but cannot edit or delete them.

The OAuth loopback flow is supported for Windows desktop apps by Google.
