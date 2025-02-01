# event_listener/event_listener.py
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from datetime import datetime
import uvicorn
from typing import List, Dict
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI()

# Enable CORS for cross-origin requests
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# In-memory storage for received notifications
received_notifications = []


class Notification(BaseModel):
    status: str
    subscription_id: int
    event_type: str
    timestamp: datetime


@app.post("/receive", status_code=200)
async def receive_notification(notification: Notification):
    """Endpoint to receive notifications from subscription service"""
    try:
        # Store notification with timestamp
        received_notifications.append({
            "received_at": datetime.utcnow().isoformat(),
            "notification": notification.dict()
        })

        # Print to console for debugging
        print(f"\n📨 Received notification:")
        print(f"Subscription ID: {notification.subscription_id}")
        print(f"Event Type: {notification.event_type}")
        print(f"Status: {notification.status}")
        print(f"Timestamp: {notification.timestamp}")

        return {"message": "Notification processed successfully"}

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error processing notification: {str(e)}"
        )


@app.get("/notifications", response_model=List[Dict])
def get_notifications(limit: int = 10):
    """Get last N received notifications"""
    return received_notifications[-limit:]


@app.delete("/notifications", status_code=204)
def clear_notifications():
    """Clear all stored notifications (for testing)"""
    global received_notifications
    received_notifications.clear()
    return


@app.get("/")
def health_check():
    """Basic health check endpoint"""
    return {
        "status": "active",
        "listening_on": "http://localhost:8001",
        "endpoints": {
            "receive": "POST /receive",
            "get_notifications": "GET /notifications",
            "clear_notifications": "DELETE /notifications"
        }
    }


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8001)