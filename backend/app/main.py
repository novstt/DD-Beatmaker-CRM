from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text

from app.config import settings
from app.database import Base, engine, SessionLocal
from app.auth import ensure_admin
from app.routers import auth, artists, beats, licenses, stats, admin, notifications, workspace, system
import app.workspace_models  # register Phase 2 tables


@asynccontextmanager
async def lifespan(app: FastAPI):
    print("STARTUP 1: lifespan started", flush=True)

    print("STARTUP 2: create_all starting", flush=True)
    Base.metadata.create_all(bind=engine)
    print("STARTUP 3: create_all finished", flush=True)

    # Lightweight forward migrations for the desktop app.
    print("STARTUP 4: migrations starting", flush=True)

    with engine.begin() as conn:
        print("STARTUP 5: database connected", flush=True)

        conn.execute(text("ALTER TABLE licenses ADD COLUMN IF NOT EXISTS mailing_share_percent NUMERIC(5,2) DEFAULT 0"))

        conn.execute(text("ALTER TABLE licenses ADD COLUMN IF NOT EXISTS mailing_share_percent NUMERIC(5,2) DEFAULT 0"))
        conn.execute(text("ALTER TABLE licenses ADD COLUMN IF NOT EXISTS producer_share_percent NUMERIC(5,2) DEFAULT 0"))
        conn.execute(text("ALTER TABLE licenses ADD COLUMN IF NOT EXISTS is_producer BOOLEAN DEFAULT FALSE"))
        conn.execute(text("ALTER TABLE licenses ADD COLUMN IF NOT EXISTS is_messenger BOOLEAN DEFAULT FALSE"))
        conn.execute(text("ALTER TABLE licenses ADD COLUMN IF NOT EXISTS currency VARCHAR(3) NOT NULL DEFAULT 'USD'"))
        conn.execute(text("ALTER TABLE workspace_goals ADD COLUMN IF NOT EXISTS currency VARCHAR(3) NOT NULL DEFAULT 'USD'"))
        conn.execute(text("ALTER TABLE users ADD COLUMN IF NOT EXISTS currency VARCHAR(3) NOT NULL DEFAULT 'USD'"))
        conn.execute(text("CREATE TABLE IF NOT EXISTS beat_credits (id SERIAL PRIMARY KEY, beat_id INTEGER NOT NULL REFERENCES beats(id) ON DELETE CASCADE, user_id INTEGER REFERENCES users(id) ON DELETE SET NULL, display_name VARCHAR(150) NOT NULL, handle VARCHAR(150), share_percent NUMERIC(5,2) DEFAULT 0)"))
        conn.execute(text("CREATE TABLE IF NOT EXISTS admin_audit_logs (id SERIAL PRIMARY KEY, admin_user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE, action VARCHAR(80) NOT NULL, target_user_id INTEGER REFERENCES users(id) ON DELETE SET NULL, detail TEXT, created_at TIMESTAMPTZ NOT NULL DEFAULT NOW())"))
        conn.execute(text("CREATE TABLE IF NOT EXISTS license_versions (id SERIAL PRIMARY KEY, license_id INTEGER NOT NULL REFERENCES licenses(id) ON DELETE CASCADE, version_no INTEGER NOT NULL DEFAULT 1, snapshot_json TEXT NOT NULL, created_at TIMESTAMPTZ NOT NULL DEFAULT NOW())"))
        conn.execute(text("ALTER TABLE licenses ADD COLUMN IF NOT EXISTS messenger_id INTEGER REFERENCES users(id) ON DELETE SET NULL"))
        conn.execute(text("ALTER TABLE licenses ADD COLUMN IF NOT EXISTS messenger_name VARCHAR(150)"))
        conn.execute(text("ALTER TABLE beats ADD COLUMN IF NOT EXISTS audio_filename VARCHAR(255)"))
        conn.execute(text("ALTER TABLE beats ADD COLUMN IF NOT EXISTS audio_path VARCHAR(1000)"))
        conn.execute(text("CREATE TABLE IF NOT EXISTS loop_sends (id SERIAL PRIMARY KEY, user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE, artist_id INTEGER NOT NULL REFERENCES artists(id) ON DELETE CASCADE, source VARCHAR(120), artist_username VARCHAR(255), loop_name VARCHAR(150) NOT NULL, audio_filename VARCHAR(255), audio_path VARCHAR(1000), notes TEXT, reminder_at TIMESTAMPTZ, done BOOLEAN NOT NULL DEFAULT FALSE, created_at TIMESTAMPTZ NOT NULL DEFAULT NOW())"))
        conn.execute(text("CREATE TABLE IF NOT EXISTS non_profit_tracks (id SERIAL PRIMARY KEY, user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE, artist_id INTEGER NOT NULL REFERENCES artists(id) ON DELETE CASCADE, track_name VARCHAR(150) NOT NULL, audio_filename VARCHAR(255), audio_path VARCHAR(1000), purchase_intent VARCHAR(30) NOT NULL DEFAULT 'unknown', uploaded_platform VARCHAR(120), upload_url VARCHAR(1000), notes TEXT, created_at TIMESTAMPTZ NOT NULL DEFAULT NOW())"))
        conn.execute(text("CREATE TABLE IF NOT EXISTS mixing_services (id SERIAL PRIMARY KEY, user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE, license_id INTEGER NOT NULL REFERENCES licenses(id) ON DELETE CASCADE, mixer_user_id INTEGER REFERENCES users(id) ON DELETE SET NULL, mixer_name VARCHAR(150) NOT NULL, price NUMERIC(12,2) NOT NULL, currency VARCHAR(3) NOT NULL DEFAULT 'USD', notes TEXT, created_at TIMESTAMPTZ NOT NULL DEFAULT NOW())"))

    db = SessionLocal()
    try:
        ensure_admin(db)
    finally:
        db.close()
    yield


app = FastAPI(
    title="Beatmaker App API",
    version="1.0.0",
    description="Backend for a multi-user beatmaker CRM and analytics application.",
    lifespan=lifespan,
)

origins = [x.strip() for x in settings.CORS_ORIGINS.split(",") if x.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins or ["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router, prefix="/api/auth", tags=["Auth"])
app.include_router(artists.router, prefix="/api/artists", tags=["Artists"])
app.include_router(beats.router, prefix="/api/beats", tags=["Beats"])
app.include_router(licenses.router, prefix="/api/licenses", tags=["Licenses"])
app.include_router(stats.router, prefix="/api/stats", tags=["Stats"])
app.include_router(admin.router, prefix="/api/admin", tags=["Admin"])
app.include_router(notifications.router, prefix="/api/notifications", tags=["Notifications"])
app.include_router(workspace.router, prefix="/api/workspace", tags=["Workspace"])
app.include_router(system.router, prefix="/api/system", tags=["System"])


@app.get("/health")
def health():
    return {"status": "ok"}
