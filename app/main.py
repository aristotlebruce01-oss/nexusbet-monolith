from dotenv import load_dotenv
load_dotenv()  # Load environment variables first!

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.routers import nexusbet, aviator

app = FastAPI(title="NexusBet Monolith API")

import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# CORS setup for your Vercel frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Startup hooks for database tables/seeds
@app.on_event("startup")
def startup_event():
    if hasattr(aviator, "startup_initialize_super_admin"):
        aviator.startup_initialize_super_admin()
    
        

# Health check route for your keep-alive ping
@app.get("/health")
def health_check():
    return {"status": "ok"}

# Mount the two apps under their new URL prefixes
app.include_router(nexusbet.router, prefix="/api", tags=["NexusBet"])
app.include_router(aviator.router, prefix="", tags=["Aviator"])


@app.on_event("startup")
async def on_startup():
    await nexusbet.db.users.create_index("email", unique=True)
    await nexusbet.db.users.create_index("referral_code", unique=True, sparse=True)
    await nexusbet.db.events.create_index("id", unique=True)
    await nexusbet.db.events.create_index("kickoff_at")
    await nexusbet.db.transactions.create_index("transaction_reference", unique=True, sparse=True)
    await nexusbet.db.audit_logs.create_index("at")
    await nexusbet.seed_admin()
    await nexusbet.normalize_legacy_football_events()
    await nexusbet.seed_events()
    await nexusbet.sync_league_catalog()
    await nexusbet.db.settings.update_one({"_id": "global"}, {"$setOnInsert": nexusbet.DEFAULT_SETTINGS}, upsert=True)
    logger.info("NexusBet backend ready")



@app.on_event("shutdown")
async def shutdown_db_client():
   # client.close() 
   pass

# Include your modular router correctly at the app level
app.include_router(nexusbet.router, prefix="/api/v1/nexusbet", tags=["NexusBet"])

app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
) 
