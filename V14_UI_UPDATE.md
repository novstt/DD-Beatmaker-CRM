# Beatmaker v14 — Full UI Redesign

Based on working v13.1.

- Main window redesigned to the approved dark dashboard direction.
- Right-side account/notification column removed.
- Left navigation retained with compact account block at the bottom.
- Home redesigned with four summary cards, recent activity, quick actions, wide stats overview and license types.
- Removed Top Beats and Recent Sales from Home.
- Wider revenue activity graph uses real recent sale values.
- Global search moved into the main top bar.
- Notification badge uses backend unread-notification count.
- Smooth fade animation when switching tabs.
- Dark/Light toggle remains available.
- Existing business logic and backend routes are preserved.

Do not run docker compose down -v; keep the existing PostgreSQL volume.
