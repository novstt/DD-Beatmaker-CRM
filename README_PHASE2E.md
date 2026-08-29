# D&D v26 Phase 2E — Fix + Extensions

Fixes:
- Goals dialog no longer crashes on QAbstractSpinBox.
- Email persistence now uses a robust per-user preferences.json under the OS app-config directory, with QSettings fallback.
- Email is saved live as it is typed and after successful registration/login; password is never stored.

Added:
- License IDs displayed as D&D-LIC-000001.
- License PDF export.
- Invoice PDF export.
- Settings shows remembered email and allows forgetting it.

Test:
1. Restart D&D and confirm email remains in the login field.
2. Settings -> Forget remembered email -> restart and confirm the field is empty.
3. Home -> + Goal -> create and edit a goal.
4. Licenses -> double-click a sale -> generate License PDF and Invoice PDF.
