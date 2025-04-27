import os
from datetime import datetime
from typing import List

import httpx
from fastapi import FastAPI
from pydantic import BaseModel
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# API credentials from environment variables
API_KEY = os.getenv("API_KEY")
OPENAI_ENDPOINT = os.getenv("OPENAI_ENDPOINT")
MODEL = os.getenv("MODEL")

# Initialize API
app = FastAPI(title="Dating Suggestion Quotes API")

# Initialize scheduler
scheduler = AsyncIOScheduler()

class Quote(BaseModel):
    quote: str
    timestamp: str

quotes_history: List[Quote] = []

async def generate_quote():
    """Generate a dating suggestion quote using OpenAI."""
    try:
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {API_KEY}"
        }
        
        payload = {
            "model": MODEL,
            "messages": [
                {
                    "role": "system",
                    "content": "You are a dating coach specializing in creative date ideas. Provide a short, creative, and engaging dating suggestion. Keep it concise (maximum 2 sentences), romantic, and practical."
                },
                {
                    "role": "user",
                    "content": "Give me a fresh dating suggestion quote."
                }
            ],
            "max_tokens": 100,
            "temperature": 0.8
        }
        
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(OPENAI_ENDPOINT, json=payload, headers=headers)
            response.raise_for_status()
            data = response.json()
            quote = data["choices"][0]["message"]["content"].strip()
            return quote
            
    except Exception as e:
        print(f"Error generating quote: {str(e)}")
        return "Try a sunset picnic with your favorite foods and a great view - simple but memorable."

async def store_daily_quote():
    """Generate a quote and store it in history."""
    quote_text = await generate_quote()
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    quote = Quote(quote=quote_text, timestamp=timestamp)
    quotes_history.append(quote)
    
    # Keep only the last 30 quotes
    if len(quotes_history) > 30:
        quotes_history.pop(0)
    
    print(f"Daily quote generated at {timestamp}: {quote_text}")
    return quote

@app.get("/quotes", response_model=List[Quote])
async def get_quotes():
    """Get all stored quotes."""
    return quotes_history

@app.get("/latest", response_model=Quote)
async def get_latest_quote():
    """Get the most recent quote."""
    if not quotes_history:
        quote_text = await generate_quote()
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        quote = Quote(quote=quote_text, timestamp=timestamp)
        quotes_history.append(quote)
    return quotes_history[-1]

@app.post("/schedule/{hour}/{minute}", status_code=201)
async def set_schedule(hour: int, minute: int):
    """Set the daily schedule for quote generation."""
    # Remove existing jobs
    scheduler.remove_all_jobs()
    
    # Add new job with specified time
    scheduler.add_job(
        store_daily_quote, 
        CronTrigger(hour=hour, minute=minute),
        id="daily_quote"
    )
    
    return {
        "message": f"Quote generation scheduled for {hour:02d}:{minute:02d} every day",
        "schedule": f"{hour:02d}:{minute:02d}"
    }

@app.get("/current-schedule")
def get_schedule():
    """Get the current schedule information."""
    jobs = scheduler.get_jobs()
    if not jobs:
        return {"message": "No scheduled quote generation"}
    
    job = jobs[0]
    next_run = job.next_run_time.strftime("%Y-%m-%d %H:%M:%S")
    trigger = job.trigger
    
    schedule_info = {}
    if hasattr(trigger, 'fields'):
        for field in trigger.fields:
            if field.name == 'hour':
                schedule_info['hour'] = field.expressions[0]
            elif field.name == 'minute':
                schedule_info['minute'] = field.expressions[0]
                
    return {
        "next_run": next_run,
        "schedule": f"{schedule_info.get('hour', '00')}:{schedule_info.get('minute', '00')}"
    }

@app.post("/generate-now", response_model=Quote)
async def generate_now():
    """Manually generate a quote now."""
    return await store_daily_quote()

@app.on_event("startup")
async def startup_event():
    # Default schedule: 9:00 AM daily
    scheduler.add_job(
        store_daily_quote, 
        CronTrigger(hour=9, minute=0),
        id="daily_quote"
    )
    scheduler.start()
    print("Application started. Quote generation scheduler is running.")

@app.on_event("shutdown")
async def shutdown_event():
    scheduler.shutdown()

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
