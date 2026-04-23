"""Celebration service for work anniversaries and birthdays."""

from datetime import datetime, timedelta
from typing import Dict, List, Optional
from dataclasses import dataclass

from sqlalchemy import extract
from sqlalchemy.orm import Session

from ..models.user import User
from ..models.celebration import Celebration, CelebrationType
from ..models.personal_fact import PersonalFact, PersonalFactType


@dataclass
class CelebrationInfo:
    """Data class for celebration information."""
    user_id: str
    employee_id: str
    name: str
    celebration_type: str
    celebration_date: str
    years_count: Optional[int] = None


def check_upcoming_work_anniversaries(
    db: Session,
    days_ahead: int = 7
) -> List[Dict]:
    """Get users with work anniversaries in the upcoming period.
    
    Args:
        db: Database session
        days_ahead: Number of days to look ahead (default: 7)
    
    Returns:
        List of users with work anniversaries this week
    """
    today = datetime.now().date()
    end_date = today + timedelta(days=days_ahead)
    
    # Get current month and day range for the next N days
    start_month, start_day = today.month, today.day
    end_month, end_day = end_date.month, end_date.day
    
    # Query celebrations of type work_anniversary
    celebrations = db.query(Celebration).join(User).filter(
        Celebration.celebration_type == CelebrationType.work_anniversary,
        User.status == "active"
    ).all()
    
    results = []
    for celeb in celebrations:
        if celeb.celebration_date is None:
            continue
            
        # Extract month and day from celebration_date
        celeb_month = celeb.celebration_date.month
        celeb_day = celeb.celebration_date.day
        
        # Check if celebration falls within the range (handling month boundary)
        if start_month == end_month:
            # Same month - simple range check
            if not (start_day <= celeb_day <= end_day):
                continue
        else:
            # Crosses month boundary
            if not ((start_day <= celeb_day <= 31) or (1 <= celeb_day <= end_day)):
                continue
        
        results.append({
            "user_id": str(celeb.user_id),
            "employee_id": celeb.user.employee_id if celeb.user else None,
            "name": celeb.user.name if celeb.user else None,
            "celebration_type": "work_anniversary",
            "celebration_date": celeb.celebration_date.isoformat(),
            "years_count": celeb.years_count
        })
    
    return results


def check_upcoming_birthdays(
    db: Session,
    days_ahead: int = 7
) -> List[Dict]:
    """Get users with birthdays in the upcoming period.
    
    Args:
        db: Database session
        days_ahead: Number of days to look ahead (default: 7)
    
    Returns:
        List of users with birthdays this week
    """
    today = datetime.now().date()
    end_date = today + timedelta(days=days_ahead)
    
    start_month, start_day = today.month, today.day
    end_month, end_day = end_date.month, end_date.day
    
    birthday_facts = db.query(PersonalFact, User).join(User, PersonalFact.user_id == User.id).filter(
        PersonalFact.fact_type == PersonalFactType.birthday,
        User.status == "active"
    ).all()
    
    results = []
    for fact, user in birthday_facts:
        fact_val = str(fact.fact_value)
        
        try:
            birth_date = datetime.strptime(fact_val, "%Y-%m-%d").date()
        except ValueError:
            try:
                birth_date = datetime.strptime(fact_val, "%m-%d").date()
            except ValueError:
                continue
        
        birthday_month = birth_date.month
        birthday_day = birth_date.day
        
        if start_month == end_month:
            if not (start_day <= birthday_day <= end_day):
                continue
        else:
            if not ((start_day <= birthday_day <= 31) or (1 <= birthday_day <= end_day)):
                continue
        
        results.append({
            "user_id": str(fact.user_id),
            "employee_id": user.employee_id,
            "name": user.name,
            "celebration_type": "birthday",
            "birth_date": fact_val,
            "years_count": None
        })
    
    return results


# Celebration message templates
CELEBRATION_MESSAGES = {
    "work_anniversary": [
        "Happy work anniversary! 🎉 You've been an amazing part of the team for {years} year(s). Thanks for all your hard work and dedication!",
        "Congratulations on {years} year(s) with us! 🎊 Your contributions make a real difference. Here's to many more!",
        "Happy anniversary! 🎂 {years} years of excellence! We're lucky to have you on the team.",
        "Wow, {years} years already! 🎈 Time flies when you're doing great work. Happy work anniversary!",
    ],
    "birthday": [
        "Happy Birthday! 🎉 🎂 Wish you a fantastic day filled with joy and celebration!",
        "Happy Birthday! 🎊 May your special day be as amazing as you are!",
        "🎉 It's your birthday! Have an absolutely wonderful celebration!",
        "Happy Birthday! 🎈 Here's to another great year ahead. Enjoy your day!",
    ]
}


def getCelebrationMessage(
    celebration_type: str,
    years_count: Optional[int] = None,
    name: Optional[str] = None
) -> str:
    """Generate a human-like celebration message.
    
    Args:
        celebration_type: Type of celebration ("work_anniversary" or "birthday")
        years_count: Number of years (for work anniversaries)
        name: Optional name to personalize message
    
    Returns:
        Human-like celebration message
    """
    import random
    
    if celebration_type not in CELEBRATION_MESSAGES:
        return "🎉 Congratulations!"
    
    messages = CELEBRATION_MESSAGES[celebration_type]
    message_template = random.choice(messages)
    
    # Format with years count if work anniversary
    if celebration_type == "work_anniversary" and years_count:
        message = message_template.format(years=years_count)
    else:
        message = message_template
    
    return message