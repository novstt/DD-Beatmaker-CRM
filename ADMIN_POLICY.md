D&D v26 Admin Policy
========================

The only administrator account is:
    quikinnnproducer@gmail.com

Admin access must be enforced server-side. Hiding the Admin navigation item
in the desktop client is not sufficient. Every admin API endpoint must verify
the authenticated user's normalized email against this allow-list.

All other accounts are regular users regardless of client-side state.

For testing, verify:
1. quikinnnproducer@gmail.com sees Admin and can access admin endpoints.
2. Any other account does not see Admin and receives 403 from admin endpoints.
3. Changing client-side flags cannot grant admin access.
