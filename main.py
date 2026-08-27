from fastapi import FastAPI
from app.database import engine, Base

# Create tables
Base.metadata.create_all(bind=engine)

app = FastAPI(title="DayTrack API")

@app.get("/")
def root():
    return {"message": "DayTrack API is running!"}