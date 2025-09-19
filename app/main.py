import os
import logging
from fastapi import FastAPI, Depends, UploadFile, File, HTTPException
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlalchemy import text, select
from pydantic import BaseModel
from cryptography.fernet import Fernet
import aiofiles
from passlib.context import CryptContext

# ======================================================
# CONFIG
# ======================================================
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite+aiosqlite:///./glrchain.db")
SECRET_KEY = os.getenv("SECRET_KEY")

if not SECRET_KEY:
    SECRET_KEY = Fernet.generate_key().decode()
    logging.warning("⚠️ No SECRET_KEY found, generating one automatically.")

engine = create_async_engine(DATABASE_URL, echo=False, future=True)
AsyncSessionLocal = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

cipher = Fernet(SECRET_KEY.encode() if isinstance(SECRET_KEY, str) else SECRET_KEY)
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

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
from app.models import Base, User

class Report(BaseModel):
    reporter: str
    location: str
    description: str

class UserCreate(BaseModel):
    username: str
    password: str

class UserLogin(BaseModel):
    username: str
    password: str

# ======================================================
# DEPENDENCIES
# ======================================================
async def get_db():
    async with AsyncSessionLocal() as session:
        yield session

# ======================================================
# STARTUP: Auto-create tables
# ======================================================
@app.on_event("startup")
async def startup():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    logger.info("✅ Database tables created or verified.")

# ======================================================
# AUTH ROUTES
# ======================================================
@app.post("/signup")
async def signup(user: UserCreate, db: AsyncSession = Depends(get_db)):
    hashed_pw = pwd_context.hash(user.password)

    # Check if username exists
    result = await db.execute(select(User).where(User.username == user.username))
    existing_user = result.scalar_one_or_none()
    if existing_user:
        raise HTTPException(status_code=400, detail="❌ Username already taken")

    new_user = User(username=user.username, hashed_password=hashed_pw)
    db.add(new_user)
    await db.commit()
    return {"message": "✅ User registered successfully"}

@app.post("/login")
async def login(user: UserLogin, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(User).where(User.username == user.username))
    db_user = result.scalar_one_or_none()
    if not db_user:
        raise HTTPException(status_code=401, detail="❌ Invalid username or password")

    if not pwd_context.verify(user.password, db_user.hashed_password):
        raise HTTPException(status_code=401, detail="❌ Invalid username or password")

    return {"message": "✅ Login successful"}

# ======================================================
# EXISTING ROUTES
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
    encrypted_desc = cipher.encrypt(report.description.encode()).decode()
    logger.info(f"Encrypted galamsey report from {report.reporter} at {report.location}")

    await db.execute(
        text("INSERT INTO reports (reporter, location, description) VALUES (:r, :l, :d)"),
        {"r": report.reporter, "l": report.location, "d": encrypted_desc}
    )
    await db.commit()

    return {"message": "Report received ✅ Encrypted and stored securely."}

@app.post("/upload-evidence")
async def upload_evidence(file: UploadFile = File(...)):
    save_path = f"evidence/{file.filename}"
    os.makedirs("evidence", exist_ok=True)
    async with aiofiles.open(save_path, "wb") as out_file:
        content = await file.read()
        await out_file.write(content)

    return {"message": f"Evidence file {file.filename} uploaded successfully ✅"}

@app.get("/intel")
async def get_intel():
    fake_alerts = [
        {"location": "Eastern Region", "risk": "High", "pattern": "Unlicensed excavation detected"},
        {"location": "Western Region", "risk": "Medium", "pattern": "River pollution signals"}
    ]
    return {"alerts": fake_alerts, "note": "AI module running (demo mode)"}
