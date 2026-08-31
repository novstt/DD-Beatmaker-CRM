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
