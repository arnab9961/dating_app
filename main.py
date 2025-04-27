import os
import json
from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.security import APIKeyHeader
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Dict, List
import requests
from apscheduler.schedulers.background import BackgroundScheduler
from datetime import datetime
import logging
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# API credentials from environment variables
API_KEY = os.getenv("API_KEY")
OPENAI_ENDPOINT = os.getenv("OPENAI_ENDPOINT")
MODEL = os.getenv("MODEL")

# Store for notifications
notifications_store = []

# FastAPI app
app = FastAPI(title="Dating Quote Notification API")

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# API key security
api_key_header = APIKeyHeader(name="X-API-Key")

def verify_api_key(api_key: str = Depends(api_key_header)):
    """Verify the API key."""
    if api_key != API_KEY:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid API Key"
        )
    return api_key

# Models
class Quote(BaseModel):
    """Quote model."""
    content: str
    created_at: str

class Schedule(BaseModel):
    """Schedule model for setting notification timing."""
    time: str  # Format: "HH:MM" in 24-hour format

class ScheduleResponse(BaseModel):
    """Response model for scheduling."""
    message: str
    schedule_time: str

# Store for schedule
schedule_time = "09:00"  # Default schedule time

def generate_dating_quote() -> str:
    """Generate a dating quote using OpenAI API."""
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {API_KEY}"
    }
    
    data = {
        "model": MODEL,
        "messages": [
            {"role": "system", "content": "You are a helpful assistant specialized in creating inspirational and thoughtful dating quotes."},
            {"role": "user", "content": "Generate a short inspirational quote about dating and relationships."}
        ],
        "max_tokens": 100
    }
    
    try:
        response = requests.post(OPENAI_ENDPOINT, headers=headers, json=data)
        response.raise_for_status()
        result = response.json()
        quote = result["choices"][0]["message"]["content"].strip()
        return quote
    except Exception as e:
        logger.error(f"Error generating quote: {str(e)}")
        return "Love is a journey, not a destination."

def create_notification():
    """Create a new dating quote notification."""
    quote = generate_dating_quote()
    notification = {
        "content": quote,
        "created_at": datetime.now().isoformat()
    }
    notifications_store.append(notification)
    logger.info(f"New notification created: {quote}")

# Initialize scheduler
scheduler = BackgroundScheduler()

def update_scheduler():
    """Update the scheduler with the current schedule time."""
    # Remove all existing jobs
    scheduler.remove_all_jobs()
    
    # Parse the schedule time
    hour, minute = map(int, schedule_time.split(':'))
    
    # Add the job with the updated schedule
    scheduler.add_job(
        create_notification, 
        'cron', 
        hour=hour, 
        minute=minute, 
        id='daily_quote'
    )
    
    logger.info(f"Scheduler updated: Daily notification at {schedule_time}")

# Routes
@app.get("/")
async def root():
    """Root endpoint."""
    return {"message": "Welcome to the Dating Quote Notification API"}

@app.get("/quotes", response_model=List[Quote])
async def get_quotes(api_key: str = Depends(verify_api_key)):
    """Get all dating quotes."""
    return notifications_store

@app.post("/quotes/generate", response_model=Quote)
async def generate_quote(api_key: str = Depends(verify_api_key)):
    """Generate a new dating quote on demand."""    
    create_notification()
    return notifications_store[-1]

@app.post("/schedule", response_model=ScheduleResponse)
async def set_schedule(schedule_data: Schedule, api_key: str = Depends(verify_api_key)):
    """Set the schedule for daily notifications."""
    global schedule_time
    schedule_time = schedule_data.time
    update_scheduler()
    
    return {
        "message": "Schedule updated successfully",
        "schedule_time": schedule_time
    }

@app.get("/schedule", response_model=ScheduleResponse)
async def get_schedule(api_key: str = Depends(verify_api_key)):
    """Get the current schedule."""
    return {
        "message": "Current schedule",
        "schedule_time": schedule_time
    }

# Startup and shutdown events
@app.on_event("startup")
async def startup_event():
    """Execute on application startup."""
    # Create initial quote
    create_notification()
    
    # Initialize the scheduler
    update_scheduler()
    
    # Start the scheduler
    if not scheduler.running:
        scheduler.start()
    
    logger.info("Application started successfully")

@app.on_event("shutdown")
async def shutdown_event():
    """Execute on application shutdown."""
    # Shutdown the scheduler
    if scheduler.running:
        scheduler.shutdown()
    
    logger.info("Application shutdown complete")

# Run the app
if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)