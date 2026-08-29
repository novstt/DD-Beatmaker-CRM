# Clean test accounts

This build includes a safe reset utility for the two test accounts **SLV** and **DE PLUG**.
It preserves the user accounts/login credentials but removes their CRM data: artists,
owned beats, licenses, goals, follow-ups, notifications, sends and collaboration links.

Run with Docker/backend environment available:

```powershell
python tools/reset_demo_accounts.py
```

The script is intentionally limited to the configured SLV/DE PLUG usernames/emails and
will not delete the users themselves.
