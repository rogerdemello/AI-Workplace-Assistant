from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from typing import List, Optional
from datetime import datetime, timedelta
from uuid import UUID
import secrets
import hashlib
from sqlalchemy.orm import Session

from ...config import settings
from ...database import get_db
from ...core.time import utcnow_naive
from ...auth import get_current_user
from ...models.calendar_integration import CalendarIntegration
from ...models.user import User
from ...services.calendar import CalendarService

router = APIRouter(prefix="/integrations", tags=["integrations"])


# ============== Request/Response Models ==============

class CalendarEventRequest(BaseModel):
    """Request model for creating a calendar event."""
    title: str = Field(..., description="Event title")
    start_time: datetime = Field(..., description="Event start time (ISO format)")
    end_time: datetime = Field(..., description="Event end time (ISO format)")
    attendees: List[str] = Field(default_factory=list, description="List of attendee email addresses")
    description: Optional[str] = Field(None, description="Event description")
    location: Optional[str] = Field(None, description="Event location")
    timezone: str = Field(default="UTC", description="Timezone for the event")


class CalendarEventResponse(BaseModel):
    """Response model for a calendar event."""
    id: str
    title: str
    start_time: str
    end_time: str
    attendees: List[str]
    status: str
    provider: str
    web_link: Optional[str] = None


class CalendarAvailabilityResponse(BaseModel):
    """Response model for calendar availability."""
    availability: List[dict]
    provider: str


class OAuthCallbackRequest(BaseModel):
    """Request model for OAuth callback."""
    code: str = Field(..., description="Authorization code from OAuth provider")
    state: str = Field(..., description="State parameter for CSRF protection")
    redirect_uri: Optional[str] = Field(default=None, description="OAuth redirect URI used during auth")


class OAuthTokensResponse(BaseModel):
    """Response model for OAuth tokens."""
    access_token: str
    refresh_token: Optional[str]
    token_type: str
    expires_in: int


class UserCalendarConfig(BaseModel):
    """User calendar configuration stored in database."""
    user_id: UUID
    provider: str
    access_token: str
    refresh_token: Optional[str] = None
    expires_at: Optional[datetime] = None


# ============== Helper Functions ==============

def generate_state() -> str:
    """Generate a random state string for OAuth CSRF protection."""
    return secrets.token_urlsafe(32)


def hash_state(state: str) -> str:
    """Hash state for storage/comparison."""
    return hashlib.sha256(state.encode()).hexdigest()


def get_user_calendar_token(
    user_id: UUID, 
    provider: str, 
    db: Session
) -> Optional[dict]:
    """
    Retrieve stored calendar tokens for a user.
    
    Returns token metadata for the user's provider connection.
    """
    row = db.query(CalendarIntegration).filter(
        CalendarIntegration.user_id == user_id,
        CalendarIntegration.provider == provider,
    ).first()

    if not row:
        return None

    return {
        "access_token": row.access_token,
        "refresh_token": row.refresh_token,
        "token_type": row.token_type,
        "expires_at": row.expires_at,
        "connected_at": row.connected_at,
        "oauth_state_hash": row.oauth_state_hash,
        "oauth_state_expires_at": row.oauth_state_expires_at,
    }


def store_user_calendar_token(
    user_id: UUID,
    provider: str,
    access_token: str,
    refresh_token: Optional[str],
    expires_in: int,
    db: Session
) -> None:
    """
    Store calendar tokens for a user.
    
    Store or update OAuth tokens for the user/provider pair.
    """
    row = db.query(CalendarIntegration).filter(
        CalendarIntegration.user_id == user_id,
        CalendarIntegration.provider == provider,
    ).first()

    expires_at = utcnow_naive() + timedelta(seconds=max(0, expires_in))

    if not row:
        row = CalendarIntegration(
            user_id=user_id,
            provider=provider,
        )
        db.add(row)

    row.access_token = access_token
    row.refresh_token = refresh_token
    row.token_type = "Bearer"
    row.expires_at = expires_at
    row.connected_at = utcnow_naive()
    row.oauth_state_hash = None
    row.oauth_state_expires_at = None

    db.commit()


def store_oauth_state(user_id: UUID, provider: str, state: str, db: Session) -> None:
    """Store hashed state for callback verification."""
    row = db.query(CalendarIntegration).filter(
        CalendarIntegration.user_id == user_id,
        CalendarIntegration.provider == provider,
    ).first()

    if not row:
        row = CalendarIntegration(user_id=user_id, provider=provider)
        db.add(row)

    row.oauth_state_hash = hash_state(state)
    row.oauth_state_expires_at = utcnow_naive() + timedelta(minutes=10)
    db.commit()


def verify_oauth_state(user_id: UUID, provider: str, state: str, db: Session) -> bool:
    """Verify callback state hash and expiration."""
    row = db.query(CalendarIntegration).filter(
        CalendarIntegration.user_id == user_id,
        CalendarIntegration.provider == provider,
    ).first()

    if not row or not row.oauth_state_hash or not row.oauth_state_expires_at:
        return False

    if row.oauth_state_expires_at < utcnow_naive():
        return False

    return secrets.compare_digest(row.oauth_state_hash, hash_state(state))


# ============== OAuth Endpoints ==============

@router.get("/calendar/google/auth")
async def google_oauth_redirect(
    redirect_uri: str = Query(..., description="OAuth redirect URI"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Redirect to Google OAuth authorization page.
    
    Returns the authorization URL that the frontend should redirect to.
    """
    state = generate_state()

    store_oauth_state(current_user.id, "google", state, db)
    
    auth_url = CalendarService.get_google_oauth_url(redirect_uri, state)
    
    return {
        "auth_url": auth_url,
        "state": state,
        "provider": "google"
    }


@router.get("/calendar/microsoft/auth")
async def microsoft_oauth_redirect(
    redirect_uri: str = Query(..., description="OAuth redirect URI"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Redirect to Microsoft OAuth authorization page.
    
    Returns the authorization URL that the frontend should redirect to.
    """
    state = generate_state()

    store_oauth_state(current_user.id, "microsoft", state, db)
    
    auth_url = CalendarService.get_microsoft_oauth_url(redirect_uri, state)
    
    return {
        "auth_url": auth_url,
        "state": state,
        "provider": "microsoft"
    }


@router.post("/calendar/{provider}/callback")
async def oauth_callback(
    provider: str,
    callback: OAuthCallbackRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Handle OAuth callback from Google or Microsoft.
    
    Exchanges authorization code for access and refresh tokens.
    """
    if provider not in ('google', 'microsoft'):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid provider. Must be 'google' or 'microsoft'"
        )
    
    if not verify_oauth_state(current_user.id, provider, callback.state, db):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired OAuth state"
        )

    redirect_uri = callback.redirect_uri or f"{settings.VITE_API_URL.rstrip('/')}/integrations/{provider}/callback"
    
    try:
        if provider == 'google':
            tokens = await CalendarService.exchange_google_code(
                callback.code, 
                redirect_uri
            )
        else:
            tokens = await CalendarService.exchange_microsoft_code(
                callback.code, 
                redirect_uri
            )
        
        # Store tokens for the user
        store_user_calendar_token(
            user_id=current_user.id,
            provider=provider,
            access_token=tokens.get('access_token', ''),
            refresh_token=tokens.get('refresh_token'),
            expires_in=tokens.get('expires_in', 3600),
            db=db
        )
        
        return {
            "status": "connected",
            "provider": provider,
            "expires_in": tokens.get('expires_in'),
            "expires_at": (utcnow_naive() + timedelta(seconds=tokens.get('expires_in', 3600))).isoformat()
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to complete OAuth: {str(e)}"
        )


@router.post("/calendar/{provider}/refresh")
async def refresh_calendar_token(
    provider: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Refresh the OAuth access token for a calendar provider.
    """
    if provider not in ('google', 'microsoft'):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid provider. Must be 'google' or 'microsoft'"
        )
    
    # Get stored refresh token
    token_data = get_user_calendar_token(current_user.id, provider, db)
    
    if not token_data or not token_data.get('refresh_token'):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No refresh token found. Please reconnect your calendar."
        )
    
    try:
        if provider == 'google':
            tokens = await CalendarService.refresh_google_token(
                token_data['refresh_token']
            )
        else:
            tokens = await CalendarService.refresh_microsoft_token(
                token_data['refresh_token']
            )
        
        # Update stored token
        store_user_calendar_token(
            user_id=current_user.id,
            provider=provider,
            access_token=tokens.get('access_token', ''),
            refresh_token=tokens.get('refresh_token', token_data['refresh_token']),
            expires_in=tokens.get('expires_in', 3600),
            db=db
        )
        
        return {
            "status": "refreshed",
            "expires_in": tokens.get('expires_in')
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to refresh token: {str(e)}"
        )


@router.get("/calendar/{provider}/status")
async def get_calendar_status(
    provider: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Check if user's calendar is connected.
    """
    if provider not in ('google', 'microsoft'):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid provider. Must be 'google' or 'microsoft'"
        )
    
    token_data = get_user_calendar_token(current_user.id, provider, db)
    
    return {
        "connected": bool(token_data and token_data.get("access_token")),
        "provider": provider,
        "has_refresh_token": bool(token_data and token_data.get("refresh_token")),
        "expires_at": token_data.get("expires_at").isoformat() if token_data and token_data.get("expires_at") else None,
        "connected_at": token_data.get("connected_at").isoformat() if token_data and token_data.get("connected_at") else None,
    }


# ============== Calendar Availability Endpoints ==============

@router.get("/calendar/availability")
async def get_calendar_availability(
    provider: str = Query(..., description="Calendar provider: google or microsoft"),
    start_date: datetime = Query(..., description="Start date for availability check"),
    end_date: datetime = Query(..., description="End date for availability check"),
    timezone: str = Query(default="UTC", description="Timezone for availability"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get calendar availability for the specified date range.
    
    Returns available time slots based on the user's calendar.
    """
    if provider not in ('google', 'microsoft'):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid provider. Must be 'google' or 'microsoft'"
        )
    
    token_data = get_user_calendar_token(current_user.id, provider, db)

    if not token_data or not token_data.get("access_token"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"{provider} calendar is not connected. Complete OAuth connection first."
        )

    access_token = token_data.get("access_token")
    refresh_token = token_data.get("refresh_token")
    
    calendar_service = CalendarService(provider, access_token, refresh_token)
    
    try:
        availability = await calendar_service.get_availability(
            start_date=start_date,
            end_date=end_date,
            timezone=timezone
        )
        
        return CalendarAvailabilityResponse(
            availability=availability,
            provider=provider
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get availability: {str(e)}"
        )


# ============== Calendar Event Endpoints ==============

@router.post("/calendar/events", response_model=CalendarEventResponse)
async def create_calendar_event(
    event: CalendarEventRequest,
    provider: str = Query(..., description="Calendar provider: google or microsoft"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Create a calendar event.
    
    Creates a new calendar event and sends invitations to attendees.
    """
    if provider not in ('google', 'microsoft'):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid provider. Must be 'google' or 'microsoft'"
        )
    
    # Validate time
    if event.end_time <= event.start_time:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="End time must be after start time"
        )
    
    token_data = get_user_calendar_token(current_user.id, provider, db)

    if not token_data or not token_data.get("access_token"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"{provider} calendar is not connected. Complete OAuth connection first."
        )

    access_token = token_data.get("access_token")
    refresh_token = token_data.get("refresh_token")
    
    calendar_service = CalendarService(provider, access_token, refresh_token)
    
    try:
        created_event = await calendar_service.create_event(
            title=event.title,
            start_time=event.start_time,
            end_time=event.end_time,
            attendees=event.attendees,
            description=event.description,
            location=event.location,
            timezone=event.timezone
        )

        if created_event.get("html_link") and not created_event.get("web_link"):
            created_event["web_link"] = created_event["html_link"]
        
        return CalendarEventResponse(**created_event)
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create event: {str(e)}"
        )


@router.get("/calendar/events")
async def list_calendar_events(
    provider: str = Query(..., description="Calendar provider: google or microsoft"),
    start_date: Optional[datetime] = Query(None, description="Filter events from this date"),
    end_date: Optional[datetime] = Query(None, description="Filter events until this date"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    List calendar events for the specified date range.
    """
    if provider not in ('google', 'microsoft'):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid provider. Must be 'google' or 'microsoft'"
        )
    
    # Get user's access token
    token_data = get_user_calendar_token(current_user.id, provider, db)
    
    if not token_data or not token_data.get("access_token"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Calendar not connected. Please connect your calendar first."
        )
    
    # Set default date range if not provided
    if not start_date:
        start_date = utcnow_naive()
    if not end_date:
        end_date = start_date + timedelta(days=7)
    
    calendar_service = CalendarService(
        provider, 
        token_data.get('access_token'),
        token_data.get('refresh_token')
    )
    
    try:
        events = await calendar_service.list_events(
            start_date=start_date,
            end_date=end_date,
            max_results=200,
        )
        
        return {
            "events": events,
            "provider": provider,
            "count": len(events),
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to list events: {str(e)}"
        )


@router.delete("/calendar/events/{event_id}")
async def delete_calendar_event(
    event_id: str,
    provider: str = Query(..., description="Calendar provider: google or microsoft"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Delete a calendar event.
    """
    if provider not in ('google', 'microsoft'):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid provider. Must be 'google' or 'microsoft'"
        )
    
    # Get user's access token
    token_data = get_user_calendar_token(current_user.id, provider, db)
    
    if not token_data or not token_data.get("access_token"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Calendar not connected. Please connect your calendar first."
        )

    calendar_service = CalendarService(
        provider,
        token_data.get("access_token"),
        token_data.get("refresh_token"),
    )

    try:
        deleted = await calendar_service.delete_event(event_id)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete event: {str(e)}"
        )

    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Calendar event not found"
        )
    
    return {
        "status": "deleted",
        "event_id": event_id,
        "provider": provider
    }
