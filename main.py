from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.database import engine, Base
from app.models import User, Task
from app.routers import auth, tasks, productivity

# Create tables
Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="DayTrack API",
    description="Personal daily task planner with productivity analytics",
    version="1.0.0"
)

# ─── CORS (for React) ──────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # React dev server
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(auth.router)
app.include_router(tasks.router)
app.include_router(productivity.router)

@app.get("/")
def root():
    return {"message": "DayTrack API is running!"}

@app.get("/health")
def health():
    return {"status": "healthy"}