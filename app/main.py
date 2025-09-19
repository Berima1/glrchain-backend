import os
import logging
from fastapi import FastAPI, Depends, UploadFile, File
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlalchemy import text
from pydantic import BaseModel
from cryptography.fernet import Fernet
import aiofiles
import uvicorn

# ======================================================
# CONFIG
# ======================================================
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite+aiosqlite:///./glrchain.db")
SECRET_KEY = os.getenv("SECRET_KEY")

# Fix Fernet key issue
if not SECRET_KEY:
    print("⚠️ WARNING: SECRET_KEY not set, generating one...")
    SECRET_KEY = Fernet.generate_key().decode()

try:
    cipher = Fernet(SECRET_KEY.encode())
except Exception:
    print("⚠️ WARNING: Invalid SECRET_KEY, regenerating...")
    SECRET_KEY = Fernet.generate_key().decode()
    cipher = Fernet(SECRET_KEY.encode())

engine = create_async_engine(DATABASE_URL, echo=False, future=True)
AsyncSessionLocal = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("glrchain")

app = FastAPI(
    title="GLRChain Backend",
    description="Backend API for GLRChain - Fighting galamsey with AI, Blockchain, and Encryption",
    version="1.0.0"
)

# ======================================================
# MODELS
# ======================================================
class Report(BaseModel):
    reporter: str
    location: str
    description: str

# ======================================================
# DEPENDENCIES
# ======================================================
async def get_db():
    async with AsyncSessionLocal() as session:
        yield session

# ======================================================
# ROUTES
# ======================================================
@app.get("/")
async def home():
    return {
        "status": "GLRChain backend running 🚀",
        "mission": "Protect Ghana’s lands & fight illegal mining (galamsey)"
    }

@app.get("/health")
async def health():
    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        return {"database": "ok", "status": "healthy"}
    except Exception as e:
        logger.error(f"DB check failed: {e}")
        return {"database": "error", "status": "unhealthy"}

@app.post("/report")
async def report_case(report: Report, db: AsyncSession = Depends(get_db)):
    """
    Citizens or field officers can report illegal mining activities.
    Data is encrypted for security.
    """
    encrypted_desc = cipher.encrypt(report.description.encode()).decode()
    logger.info(f"Encrypted galamsey report from {report.reporter} at {report.location}")

    await db.execute(
        text("CREATE TABLE IF NOT EXISTS reports (id INTEGER PRIMARY KEY AUTOINCREMENT, reporter TEXT, location TEXT, description TEXT)")
    )
    await db.execute(
        text("INSERT INTO reports (reporter, location, description) VALUES (:r, :l, :d)"),
        {"r": report.reporter, "l": report.location, "d": encrypted_desc}
    )
    await db.commit()

    return {"message": "Report received ✅ Encrypted and stored securely."}

@app.post("/upload-evidence")
async def upload_evidence(file: UploadFile = File(...)):
    """
    Upload satellite image, drone footage, or field photo as evidence.
    """
    save_path = f"evidence/{file.filename}"
    os.makedirs("evidence", exist_ok=True)
    async with aiofiles.open(save_path, "wb") as out_file:
        content = await file.read()
        await out_file.write(content)

    return {"message": f"Evidence file {file.filename} uploaded successfully ✅"}

@app.get("/intel")
async def get_intel():
    """
    AI / Algorithm stub for detecting suspicious mining activity.
    Future: connect ML models, satellite feeds, drones, etc.
    """
    fake_alerts = [
        {"location": "Eastern Region", "risk": "High", "pattern": "Unlicensed excavation detected"},
        {"location": "Western Region", "risk": "Medium", "pattern": "River pollution signals"}
    ]
    return {"alerts": fake_alerts, "note": "AI module running (demo mode)"}

# ======================================================
# ENTRY POINT (Auto port binding for Render)
# ======================================================
if __name__ == "__main__":
    port = int(os.getenv("PORT", 8000))  # Render sets $PORT
    uvicorn.run("app.main:app", host="0.0.0.0", port=port, reload=False)
