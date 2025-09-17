import os
import logging
from fastapi import FastAPI, Depends
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from pydantic import BaseModel
from cryptography.fernet import Fernet

# ======================================================
#  CONFIG
# ======================================================
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./glrchain.db")
SECRET_KEY = os.getenv("SECRET_KEY", Fernet.generate_key().decode())

engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False} if "sqlite" in DATABASE_URL else {})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

cipher = Fernet(SECRET_KEY.encode() if isinstance(SECRET_KEY, str) else SECRET_KEY)

# Logging setup
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("glrchain")

# ======================================================
#  FASTAPI INIT
# ======================================================
app = FastAPI(
    title="GLRChain Backend",
    description="Backend API for GLRChain - Ghana Lands & Natural Resources",
    version="1.0.0"
)

# ======================================================
#  MODELS
# ======================================================
class Report(BaseModel):
    reporter: str
    location: str
    description: str

# ======================================================
#  DEPENDENCY
# ======================================================
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# ======================================================
#  ROUTES
# ======================================================
@app.get("/")
def home():
    return {"status": "GLRChain backend running 🚀", "mission": "Protect Ghana’s lands & fight illegal mining (galamsey)"}

@app.get("/health")
def health():
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return {"database": "ok", "status": "healthy"}
    except Exception as e:
        logger.error(f"DB check failed: {e}")
        return {"database": "error", "status": "unhealthy"}

@app.post("/report")
def report_case(report: Report, db=Depends(get_db)):
    """
    Citizens or field officers can report illegal mining activities.
    Data is encrypted for security.
    """
    encrypted_desc = cipher.encrypt(report.description.encode()).decode()
    logger.info(f"Encrypted galamsey report from {report.reporter} at {report.location}")

    # Store to DB (later replace with proper ORM model)
    with engine.connect() as conn:
        conn.execute(
            text("CREATE TABLE IF NOT EXISTS reports (id INTEGER PRIMARY KEY AUTOINCREMENT, reporter TEXT, location TEXT, description TEXT)")
        )
        conn.execute(
            text("INSERT INTO reports (reporter, location, description) VALUES (:r, :l, :d)"),
            {"r": report.reporter, "l": report.location, "d": encrypted_desc}
        )
        conn.commit()

    return {"message": "Report received ✅ Encrypted and stored securely."}

@app.get("/intel")
def get_intel():
    """
    AI / Algorithm stub for detecting suspicious mining activity.
    Future: connect ML models, satellite feeds, drones, etc.
    """
    fake_alerts = [
        {"location": "Eastern Region", "risk": "High", "pattern": "Unlicensed excavation detected"},
        {"location": "Western Region", "risk": "Medium", "pattern": "River pollution signals"}
    ]
    return {"alerts": fake_alerts, "note": "AI module running (demo mode)"}
