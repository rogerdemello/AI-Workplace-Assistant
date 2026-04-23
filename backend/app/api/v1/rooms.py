from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from typing import List, Optional
from uuid import UUID
from datetime import datetime, timedelta, time
from pydantic import BaseModel, ConfigDict

from ...database import get_db
from ...core.time import utcnow_naive
from ...auth import get_current_user, require_roles
from ...models.user import User, UserRole
from ...models.room import Room, RoomBooking

router = APIRouter(prefix="/rooms", tags=["rooms"])


# Pydantic Schemas
class RoomCreate(BaseModel):
    name: str
    capacity: int
    location: Optional[str] = None
    facilities: List[str] = []


class RoomUpdate(BaseModel):
    name: Optional[str] = None
    capacity: Optional[int] = None
    location: Optional[str] = None
    facilities: Optional[List[str]] = None
    is_active: Optional[bool] = None


class RoomResponse(BaseModel):
    id: UUID
    name: str
    capacity: int
    location: Optional[str]
    facilities: List[str]
    is_active: bool
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class RoomBookingCreate(BaseModel):
    room_id: UUID
    title: str
    start_time: datetime
    end_time: datetime


class RoomBookingResponse(BaseModel):
    id: UUID
    room_id: UUID
    user_id: UUID
    title: str
    start_time: datetime
    end_time: datetime
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class TimeSlot(BaseModel):
    start: str
    end: str
    available: bool


class AvailabilityResponse(BaseModel):
    room_id: UUID
    date: str
    available: bool
    slots: List[TimeSlot]


# Helper functions
def check_booking_conflict(db: Session, room_id: UUID, start_time: datetime, end_time: datetime, exclude_booking_id: UUID = None) -> Optional[RoomBooking]:
    """Check if there's a conflicting booking for the given time slot."""
    query = db.query(RoomBooking).filter(
        RoomBooking.room_id == room_id,
        RoomBooking.start_time < end_time,
        RoomBooking.end_time > start_time
    )
    if exclude_booking_id:
        query = query.filter(RoomBooking.id != exclude_booking_id)
    return query.first()


def get_available_slots(bookings: List[RoomBooking], date: datetime, slot_duration: int = 60) -> List[TimeSlot]:
    """Get available time slots for a given date based on existing bookings."""
    slots = []
    start_of_day = datetime.combine(date.date(), time(9, 0))  # Start at 9 AM
    end_of_day = datetime.combine(date.date(), time(18, 0))   # End at 6 PM
    
    current = start_of_day
    while current < end_of_day:
        slot_end = current + timedelta(minutes=slot_duration)
        
        # Check if this slot conflicts with any booking
        is_available = True
        for booking in bookings:
            if booking.start_time < slot_end and booking.end_time > current:
                is_available = False
                break
        
        slots.append(TimeSlot(
            start=current.strftime("%H:%M"),
            end=slot_end.strftime("%H:%M"),
            available=is_available
        ))
        current = slot_end
    
    return slots


# Admin routes - Room CRUD
@router.post("", response_model=RoomResponse, dependencies=[Depends(require_roles(["admin"]))])
def create_room(room: RoomCreate, db: Session = Depends(get_db)):
    """Create a new room (admin only)."""
    db_room = Room(
        name=room.name,
        capacity=room.capacity,
        location=room.location,
        facilities=room.facilities
    )
    db.add(db_room)
    db.commit()
    db.refresh(db_room)
    return db_room


@router.get("", response_model=List[RoomResponse])
def list_rooms(
    capacity: Optional[int] = Query(None, description="Filter by minimum capacity"),
    facilities: Optional[str] = Query(None, description="Comma-separated list of required facilities"),
    include_inactive: bool = Query(False, description="Include inactive rooms"),
    db: Session = Depends(get_db)
):
    """List all rooms with optional filters."""
    query = db.query(Room)
    
    if not include_inactive:
        query = query.filter(Room.is_active == True)
    
    if capacity:
        query = query.filter(Room.capacity >= capacity)
    
    if facilities:
        required_facilities = [f.strip() for f in facilities.split(",")]
        for facility in required_facilities:
            query = query.filter(Room.facilities.contains(facility))
    
    rooms = query.all()
    return rooms


@router.get("/{room_id}", response_model=RoomResponse)
def get_room(room_id: UUID, db: Session = Depends(get_db)):
    """Get a specific room by ID."""
    room = db.query(Room).filter(Room.id == room_id).first()
    if not room:
        raise HTTPException(status_code=404, detail="Room not found")
    return room


@router.patch("/{room_id}", response_model=RoomResponse, dependencies=[Depends(require_roles(["admin"]))])
def update_room(room_id: UUID, room_update: RoomUpdate, db: Session = Depends(get_db)):
    """Update a room (admin only)."""
    room = db.query(Room).filter(Room.id == room_id).first()
    if not room:
        raise HTTPException(status_code=404, detail="Room not found")
    
    if room_update.name is not None:
        room.name = room_update.name
    if room_update.capacity is not None:
        room.capacity = room_update.capacity
    if room_update.location is not None:
        room.location = room_update.location
    if room_update.facilities is not None:
        room.facilities = room_update.facilities
    if room_update.is_active is not None:
        room.is_active = room_update.is_active
    
    db.commit()
    db.refresh(room)
    return room


@router.delete("/{room_id}", status_code=status.HTTP_204_NO_CONTENT, dependencies=[Depends(require_roles(["admin"]))])
def delete_room(room_id: UUID, db: Session = Depends(get_db)):
    """Delete a room (admin only) - soft delete by setting is_active to False."""
    room = db.query(Room).filter(Room.id == room_id).first()
    if not room:
        raise HTTPException(status_code=404, detail="Room not found")
    
    room.is_active = False
    db.commit()
    return None


# Availability check
@router.get("/{room_id}/availability", response_model=AvailabilityResponse)
def check_availability(
    room_id: UUID,
    date: str = Query(..., description="Date in YYYY-MM-DD format"),
    db: Session = Depends(get_db)
):
    """Check room availability for a specific date."""
    room = db.query(Room).filter(Room.id == room_id).first()
    if not room:
        raise HTTPException(status_code=404, detail="Room not found")
    
    try:
        requested_date = datetime.strptime(date, "%Y-%m-%d")
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid date format. Use YYYY-MM-DD")
    
    # Get all bookings for this room on the specified date
    start_of_day = datetime.combine(requested_date.date(), time(0, 0))
    end_of_day = datetime.combine(requested_date.date(), time(23, 59, 59))
    
    bookings = db.query(RoomBooking).filter(
        RoomBooking.room_id == room_id,
        RoomBooking.start_time >= start_of_day,
        RoomBooking.start_time <= end_of_day
    ).all()
    
    slots = get_available_slots(bookings, requested_date)
    has_available = any(slot.available for slot in slots)
    
    return AvailabilityResponse(
        room_id=room_id,
        date=date,
        available=has_available,
        slots=slots
    )


# Booking endpoints
@router.post("/book", response_model=RoomBookingResponse)
def book_room(
    booking: RoomBookingCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Book a room for a specific time slot."""
    # Verify room exists and is active
    room = db.query(Room).filter(Room.id == booking.room_id).first()
    if not room:
        raise HTTPException(status_code=404, detail="Room not found")
    if not room.is_active:
        raise HTTPException(status_code=400, detail="Room is not available")
    
    # Validate time range
    if booking.start_time >= booking.end_time:
        raise HTTPException(status_code=400, detail="End time must be after start time")
    
    if booking.start_time < utcnow_naive():
        raise HTTPException(status_code=400, detail="Cannot book for a past time")
    
    # Check for booking conflicts
    conflict = check_booking_conflict(db, booking.room_id, booking.start_time, booking.end_time)
    if conflict:
        raise HTTPException(
            status_code=409,
            detail=f"Room is already booked from {conflict.start_time} to {conflict.end_time}"
        )
    
    # Create the booking
    db_booking = RoomBooking(
        room_id=booking.room_id,
        user_id=current_user.id,
        title=booking.title,
        start_time=booking.start_time,
        end_time=booking.end_time
    )
    db.add(db_booking)
    db.commit()
    db.refresh(db_booking)
    
    return db_booking


@router.get("/bookings/my", response_model=List[RoomBookingResponse])
def get_my_bookings(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get current user's room bookings."""
    bookings = db.query(RoomBooking).filter(
        RoomBooking.user_id == current_user.id
    ).order_by(RoomBooking.start_time.desc()).all()
    return bookings


@router.get("/bookings", response_model=List[RoomBookingResponse], dependencies=[Depends(require_roles(["admin", "hr"]))])
def get_all_bookings(
    room_id: Optional[UUID] = Query(None, description="Filter by room ID"),
    date: Optional[str] = Query(None, description="Filter by date (YYYY-MM-DD)"),
    db: Session = Depends(get_db)
):
    """Get all room bookings (admin/HR only)."""
    query = db.query(RoomBooking)
    
    if room_id:
        query = query.filter(RoomBooking.room_id == room_id)
    
    if date:
        try:
            filter_date = datetime.strptime(date, "%Y-%m-%d")
            start_of_day = datetime.combine(filter_date.date(), time(0, 0))
            end_of_day = datetime.combine(filter_date.date(), time(23, 59, 59))
            query = query.filter(
                RoomBooking.start_time >= start_of_day,
                RoomBooking.start_time <= end_of_day
            )
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid date format. Use YYYY-MM-DD")
    
    bookings = query.order_by(RoomBooking.start_time.desc()).all()
    return bookings


@router.delete("/bookings/{booking_id}", status_code=status.HTTP_204_NO_CONTENT)
def cancel_booking(
    booking_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Cancel a room booking."""
    booking = db.query(RoomBooking).filter(RoomBooking.id == booking_id).first()
    if not booking:
        raise HTTPException(status_code=404, detail="Booking not found")
    
    # Check if user owns the booking or is admin
    if booking.user_id != current_user.id and current_user.role not in [UserRole.admin, UserRole.hr]:
        raise HTTPException(status_code=403, detail="Not authorized to cancel this booking")
    
    # Check if booking is in the past
    if booking.start_time < utcnow_naive():
        raise HTTPException(status_code=400, detail="Cannot cancel a past booking")
    
    db.delete(booking)
    db.commit()
    return None
