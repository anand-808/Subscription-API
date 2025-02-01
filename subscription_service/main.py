from fastapi import FastAPI, Depends, HTTPException, status, Header, Query
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime
import requests
from sqlalchemy import create_engine, Column, Integer, String, DateTime, Boolean
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session

# Database configuration
SQLALCHEMY_DATABASE_URL = "sqlite:///./subscriptions.db"
engine = create_engine(
    SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False}
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


# Database model
class Subscription(Base):
    __tablename__ = "subscriptions"

    id = Column(Integer, primary_key=True, index=True)
    notification_url = Column(String, nullable=False)
    event_type = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    is_active = Column(Boolean, default=True)


Base.metadata.create_all(bind=engine)


# Pydantic schemas
class SubscriptionCreate(BaseModel):
    notification_url: str
    event_type: Optional[str] = None


class SubscriptionUpdate(BaseModel):
    notification_url: Optional[str] = None
    event_type: Optional[str] = None
    is_active: Optional[bool] = None


class SubscriptionResponse(BaseModel):
    id: int
    notification_url: str
    event_type: Optional[str]
    created_at: datetime
    is_active: bool

    class Config:
        orm_mode = True


# Authentication setup
VALID_TOKEN = "secret-token"
http_bearer = HTTPBearer(auto_error=False)


async def authenticate(
        credentials: Optional[HTTPAuthorizationCredentials] = Depends(http_bearer),
        x_access_token: Optional[str] = Header(None),
        plain_token: Optional[str] = Query(None),
):
    token = None
    if credentials and credentials.scheme == "Bearer":
        token = credentials.credentials
    elif x_access_token:
        token = x_access_token
    elif plain_token:
        token = plain_token

    if not token or token != VALID_TOKEN:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing credentials",
        )
    return token


# FastAPI application
app = FastAPI()


# Database dependency
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# API endpoints
@app.get("/subscriptions/", response_model=List[SubscriptionResponse])
def list_subscriptions(
        db: Session = Depends(get_db),
        token: str = Depends(authenticate)
):
    """List all subscriptions"""
    return db.query(Subscription).all()


@app.post("/subscriptions/", response_model=SubscriptionResponse, status_code=status.HTTP_201_CREATED)
def create_subscription(
        subscription: SubscriptionCreate,
        db: Session = Depends(get_db),
        token: str = Depends(authenticate)
):
    """Create a new subscription"""
    db_sub = Subscription(**subscription.dict())
    db.add(db_sub)
    db.commit()
    db.refresh(db_sub)
    return db_sub


@app.patch("/subscriptions/{sub_id}", response_model=SubscriptionResponse)
def update_subscription(
        sub_id: int,
        subscription: SubscriptionUpdate,
        db: Session = Depends(get_db),
        token: str = Depends(authenticate)
):
    """Update an existing subscription"""
    db_sub = db.query(Subscription).filter(Subscription.id == sub_id).first()
    if not db_sub:
        raise HTTPException(status_code=404, detail="Subscription not found")

    update_data = subscription.dict(exclude_unset=True)
    for key, value in update_data.items():
        setattr(db_sub, key, value)

    db.commit()
    db.refresh(db_sub)
    return db_sub


@app.delete("/subscriptions/{sub_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_subscription(
        sub_id: int,
        db: Session = Depends(get_db),
        token: str = Depends(authenticate)
):
    """Delete a subscription"""
    db_sub = db.query(Subscription).filter(Subscription.id == sub_id).first()
    if not db_sub:
        raise HTTPException(status_code=404, detail="Subscription not found")

    db.delete(db_sub)
    db.commit()
    return


@app.post("/subscriptions/{sub_id}/notify")
def notify_subscription(
        sub_id: int,
        db: Session = Depends(get_db),
        token: str = Depends(authenticate)
):
    """Send notification to subscription URL"""
    subscription = db.query(Subscription).filter(Subscription.id == sub_id).first()
    if not subscription:
        raise HTTPException(status_code=404, detail="Subscription not found")

    if not subscription.is_active:
        raise HTTPException(status_code=400, detail="Inactive subscription")

    try:
        response = requests.post(
            subscription.notification_url,
            json={
                "status": "success",
                "subscription_id": sub_id,
                "event_type": subscription.event_type,
                "timestamp": datetime.utcnow().isoformat()
            }
        )
        response.raise_for_status()
    except requests.RequestException as e:
        raise HTTPException(
            status_code=500,
            detail=f"Notification failed: {str(e)}"
        )

    return {"message": "Notification sent successfully"}