# D&D Final UI + Clean Test Accounts

This build is the reference-driven UI pass based on the approved D&D mockups.

## UI
- Dashboard follows the approved structure: KPI row, Revenue Overview + Goals, Top Artists, Recent Sales, Tasks & Notifications, and persistent player.
- Sidebar uses the compact Workspace/System hierarchy and shows the producer balance in green.
- Dashboard cards, spacing, borders, typography and purple accents were rebuilt around the reference layout rather than only recolored.
- Player is a wider persistent control bar.
- `SLV` is the display name for `slv`, `slv1`, `@slv`, `@prod.slv`, `@prod_slv` and `@quikinnnslv`.

## Test data reset
The project cannot alter a user's live PostgreSQL volume from the ZIP itself. To clean the two local test accounts while preserving their logins:

```powershell
python tools/reset_demo_accounts.py
```

The reset is deliberately limited to SLV and DE PLUG and removes their CRM/workspace records while keeping the accounts themselves.

## Validation
- Parser regression: PASS
- Producer alias/title cleanup: PASS
- Production preflight: 12/12 PASS (backend health is skipped unless the backend is running)
