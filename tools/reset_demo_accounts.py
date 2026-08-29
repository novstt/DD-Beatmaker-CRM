"""Reset test/demo data for the SLV and DE PLUG accounts while keeping the user accounts.

Run from the project root:
    python tools/reset_demo_accounts.py

The script is intentionally explicit about the two accounts and does not delete users.
It removes their CRM/workspace records, owned beats, licenses, notifications and
collaboration links. This is intended for a test database before a clean hand-off.
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))
from sqlalchemy import text
from app.database import SessionLocal

TARGETS = {
    "SLV": {"usernames": {"slv", "slv1", "@slv"}, "emails": {"quikinnnproducer@gmail.com"}},
    "DE PLUG": {"usernames": {"de plug", "deplug", "deplugboy", "@deplugboy", "de_plug"}, "emails": set()},
}


def main():
    db = SessionLocal()
    try:
        rows = db.execute(text("SELECT id, username, email FROM users")).mappings().all()
        targets=[]
        for row in rows:
            u=str(row["username"] or "").strip().casefold()
            e=str(row["email"] or "").strip().casefold()
            for label, cfg in TARGETS.items():
                if u in {x.casefold() for x in cfg["usernames"]} or e in {x.casefold() for x in cfg["emails"]}:
                    targets.append((label, int(row["id"]), row["username"], row["email"]))
                    break
        if not targets:
            print("No SLV/DE PLUG accounts found. Nothing changed.")
            return
        print("Accounts to reset:")
        for t in targets: print(f"  - {t[0]}: id={t[1]}, username={t[2]}, email={t[3]}")
        print("Users themselves are preserved.")

        for label, uid, username, email in targets:
            # IDs of artists and owned beats are captured before deletion.
            artist_ids=[r[0] for r in db.execute(text("SELECT id FROM artists WHERE created_by=:uid"),{"uid":uid}).all()]
            artist_ids += [r[0] for r in db.execute(text("SELECT artist_id FROM user_artists WHERE user_id=:uid"),{"uid":uid}).all()]
            artist_ids=sorted(set(artist_ids))
            beat_ids=[r[0] for r in db.execute(text("SELECT id FROM beats WHERE user_id=:uid"),{"uid":uid}).all()]

            # License children first.
            db.execute(text("DELETE FROM license_events WHERE license_id IN (SELECT id FROM licenses WHERE user_id=:uid)"),{"uid":uid})
            db.execute(text("DELETE FROM license_splits WHERE license_id IN (SELECT id FROM licenses WHERE user_id=:uid)"),{"uid":uid})
            db.execute(text("DELETE FROM license_versions WHERE license_id IN (SELECT id FROM licenses WHERE user_id=:uid)"),{"uid":uid})
            db.execute(text("DELETE FROM licenses WHERE user_id=:uid"),{"uid":uid})

            # Workspace / CRM data.
            db.execute(text("DELETE FROM workspace_favorites WHERE user_id=:uid"),{"uid":uid})
            db.execute(text("DELETE FROM workspace_followups WHERE user_id=:uid"),{"uid":uid})
            db.execute(text("DELETE FROM workspace_goals WHERE user_id=:uid"),{"uid":uid})
            db.execute(text("DELETE FROM workspace_tags WHERE user_id=:uid"),{"uid":uid})
            db.execute(text("DELETE FROM notifications WHERE user_id=:uid"),{"uid":uid})

            # Collaboration/sending records owned by the account.
            db.execute(text("DELETE FROM beat_sends WHERE user_id=:uid"),{"uid":uid})
            db.execute(text("DELETE FROM beat_producers WHERE user_id=:uid"),{"uid":uid})
            db.execute(text("DELETE FROM beat_credits WHERE user_id=:uid"),{"uid":uid})
            db.execute(text("DELETE FROM user_artists WHERE user_id=:uid"),{"uid":uid})

            # Remove owned beats. Other users' licenses reference beats with ON DELETE SET NULL.
            if beat_ids:
                db.execute(text("DELETE FROM beats WHERE user_id=:uid"),{"uid":uid})

            # Delete artists created by the test account only when no other account still uses them.
            for aid in artist_ids:
                remaining=db.execute(text("SELECT COUNT(*) FROM user_artists WHERE artist_id=:aid"),{"aid":aid}).scalar_one()
                remaining_licenses=db.execute(text("SELECT COUNT(*) FROM licenses WHERE artist_id=:aid"),{"aid":aid}).scalar_one()
                if remaining==0 and remaining_licenses==0:
                    db.execute(text("DELETE FROM artists WHERE id=:aid AND created_by=:uid"),{"aid":aid,"uid":uid})

            # Keep profile settings but reset test-visible theme/currency to sane defaults.
            db.execute(text("UPDATE users SET theme='dark', currency='USD' WHERE id=:uid"),{"uid":uid})
            print(f"Reset: {label}")

        db.commit()
        print("Done. SLV and DE PLUG accounts are empty but still exist and can be logged in.")
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()

if __name__ == "__main__":
    main()
