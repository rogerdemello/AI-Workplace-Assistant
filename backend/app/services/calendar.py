from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta
from uuid import UUID, uuid4
import httpx
import json
import base64
from ..config import settings
from ..core.time import utcnow_naive


class CalendarService:
    """Service for handling calendar operations with Google Calendar and Microsoft Graph."""
    
    # Google Calendar API base URL
    GOOGLE_CALENDAR_API = "https://www.googleapis.com/calendar/v3"
    # Microsoft Graph API base URL
    MICROSOFT_GRAPH_API = "https://graph.microsoft.com/v1.0"
    
    def __init__(self, provider: str, access_token: str, refresh_token: Optional[str] = None):
        """
        Initialize calendar service.
        
        Args:
            provider: 'google' or 'microsoft'
            access_token: OAuth access token
            refresh_token: Optional OAuth refresh token
        """
        if provider not in ('google', 'microsoft'):
            raise ValueError("Provider must be 'google' or 'microsoft'")
        
        self.provider = provider
        self.access_token = access_token
        self.refresh_token = refresh_token
    
    async def _make_request(
        self, 
        method: str, 
        url: str, 
        headers: Optional[Dict] = None,
        json_data: Optional[Dict] = None,
        params: Optional[Dict] = None
    ) -> Dict:
        """Make HTTP request to calendar API."""
        default_headers = {
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/json"
        }
        if headers:
            default_headers.update(headers)
        
        async with httpx.AsyncClient() as client:
            response = await client.request(
                method=method,
                url=url,
                headers=default_headers,
                json=json_data,
                params=params,
                timeout=30.0
            )
            response.raise_for_status()
            return response.json() if response.text else {}
    
    async def get_availability(
        self, 
        start_date: datetime, 
        end_date: datetime,
        timezone: str = "UTC"
    ) -> List[Dict[str, Any]]:
        if self.provider == 'google':
            return await self._get_google_availability(start_date, end_date, timezone)
        elif self.provider == 'microsoft':
            return await self._get_microsoft_availability(start_date, end_date, timezone)
        return self._generate_fallback_availability(start_date, end_date)
    
    async def _get_google_availability(
        self, 
        start_date: datetime, 
        end_date: datetime,
        timezone: str
    ) -> List[Dict]:
        """Get availability from Google Calendar."""
        # Primary calendar
        calendar_id = "primary"
        
        # Format time range for Google Calendar API
        time_min = start_date.isoformat() + "Z"
        time_max = end_date.isoformat() + "Z"
        
        url = f"{self.GOOGLE_CALENDAR_API}/calendars/{calendar_id}/events"
        params = {
            "timeMin": time_min,
            "timeMax": time_max,
            "singleEvents": True,
            "orderBy": "startTime",
            "maxResults": 2500
        }
        
        try:
            response = await self._make_request("GET", url, params=params)
            events = response.get("items", [])
            return self._process_google_events(events, start_date, end_date)
        except httpx.HTTPError:
            # Return simplified fallback for demo purposes
            return self._generate_fallback_availability(start_date, end_date)
    
    async def _get_microsoft_availability(
        self, 
        start_date: datetime, 
        end_date: datetime,
        timezone: str
    ) -> List[Dict]:
        """Get availability from Microsoft Graph."""
        url = f"{self.MICROSOFT_GRAPH_API}/me/calendar/getSchedule"
        
        body = {
            "startTime": {
                "dateTime": start_date.isoformat(),
                "timeZone": timezone
            },
            "endTime": {
                "dateTime": end_date.isoformat(),
                "timeZone": timezone
            },
            "schedules": ["Calendar"]
        }
        
        try:
            response = await self._make_request("POST", url, json_data=body)
            return self._process_microsoft_schedule(response.get("value", []))
        except httpx.HTTPError:
            # Return simplified fallback for demo purposes
            return self._generate_fallback_availability(start_date, end_date)
    
    def _process_google_events(
        self, 
        events: List[Dict], 
        start_date: datetime, 
        end_date: datetime
    ) -> List[Dict]:
        """Process Google Calendar events into availability slots."""
        availability = []
        current_date = start_date.date()
        
        while current_date <= end_date.date():
            day_start = datetime.combine(current_date, datetime.min.time()).replace(hour=9)
            day_end = datetime.combine(current_date, datetime.min.time()).replace(hour=17)
            
            # Find busy slots for this day
            busy_slots = []
            for event in events:
                event_start = event.get("start", {}).get("dateTime")
                event_end = event.get("end", {}).get("dateTime")
                
                if event_start and event_end:
                    try:
                        e_start = datetime.fromisoformat(event_start.replace("Z", "+00:00"))
                        e_end = datetime.fromisoformat(event_end.replace("Z", "+00:00"))
                        
                        if e_start.date() == current_date:
                            busy_slots.append({
                                "start": e_start.strftime("%H:%M"),
                                "end": e_end.strftime("%H:%M")
                            })
                    except (ValueError, TypeError):
                        continue
            
            # Generate available slots
            slots = self._generate_available_slots(busy_slots, current_date)
            
            availability.append({
                "date": current_date.isoformat(),
                "slots": slots
            })
            
            current_date += timedelta(days=1)
        
        return availability
    
    def _process_microsoft_schedule(self, schedule_data: List[Dict]) -> List[Dict]:
        """Process Microsoft Graph schedule data into availability."""
        availability = []
        
        for schedule in schedule_data:
            schedule_id = schedule.get("scheduleId", "Calendar")
            slots = schedule.get("availabilityView", "")
            
            # Parse availabilityView string (e.g., "000011110000")
            # 0 = free, 1 = busy, 2 = tentative, 3 = oof
            availability_slots = []
            
            # This is a simplified parsing - real implementation would be more complex
            if slots:
                # Generate 30-minute slots from 9 AM to 5 PM
                current_hour = 9
                for char in slots[:16]:  # 8 hours of 30-min slots
                    if char == "0":  # Free
                        availability_slots.append({
                            "start": f"{current_hour:02d}:00",
                            "end": f"{current_hour + 1:02d}:00",
                            "available": True
                        })
                    current_hour += 1 if current_hour % 2 == 1 else 0
            
            availability.append({
                "date": datetime.now().date().isoformat(),
                "slots": availability_slots if availability_slots else [
                    {"start": "09:00", "end": "17:00", "available": True}
                ]
            })
        
        return availability if availability else self._generate_fallback_availability(
            datetime.now(), 
            datetime.now() + timedelta(days=7)
        )
    
    def _generate_available_slots(
        self, 
        busy_slots: List[Dict], 
        date
    ) -> List[Dict]:
        """Generate available slots from busy slots."""
        if not busy_slots:
            return [{"start": "09:00", "end": "17:00", "available": True}]
        
        slots = []
        work_start = 9
        work_end = 17
        
        sorted_busy = sorted(busy_slots, key=lambda x: x["start"])
        
        current_hour = work_start
        for busy in sorted_busy:
            busy_start_hour = int(busy["start"].split(":")[0])
            
            if current_hour < busy_start_hour:
                slots.append({
                    "start": f"{current_hour:02d}:00",
                    "end": f"{busy_start_hour:02d}:00",
                    "available": True
                })
            
            busy_end_hour = int(busy["end"].split(":")[0])
            current_hour = max(current_hour, busy_end_hour)
        
        if current_hour < work_end:
            slots.append({
                "start": f"{current_hour:02d}:00",
                "end": f"{work_end:02d}:00",
                "available": True
            })
        
        return slots if slots else [{"start": "09:00", "end": "17:00", "available": True}]
    
    def _generate_fallback_availability(
        self, 
        start_date: datetime, 
        end_date: datetime
    ) -> List[Dict]:
        """Generate fallback availability data for demo purposes."""
        availability = []
        current_date = start_date.date()
        
        while current_date <= end_date.date():
            if current_date.weekday() < 5:  # Weekdays only
                availability.append({
                    "date": current_date.isoformat(),
                    "slots": [{"start": "09:00", "end": "17:00", "available": True}]
                })
            current_date += timedelta(days=1)
        
        return availability
    
    async def create_event(
        self,
        title: str,
        start_time: datetime,
        end_time: datetime,
        attendees: List[str],
        description: Optional[str] = None,
        location: Optional[str] = None,
        timezone: str = "UTC"
    ) -> Dict[str, Any]:
        if self.provider == 'google':
            return await self._create_google_event(
                title, start_time, end_time, attendees, description, location, timezone
            )
        elif self.provider == 'microsoft':
            return await self._create_microsoft_event(
                title, start_time, end_time, attendees, description, location, timezone
            )
        return {
            "id": f"evt_{uuid4()}",
            "title": title,
            "start_time": start_time.isoformat(),
            "end_time": end_time.isoformat(),
            "attendees": attendees,
            "status": "confirmed"
        }

    async def list_events(
        self,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        max_results: int = 100,
    ) -> List[Dict[str, Any]]:
        """List events from provider calendar and normalize response shape."""
        start = start_date or utcnow_naive()
        end = end_date or (start + timedelta(days=7))
        max_results = max(1, min(max_results, 250))

        if self.provider == "google":
            return await self._list_google_events(start, end, max_results)
        if self.provider == "microsoft":
            return await self._list_microsoft_events(start, end, max_results)
        return []

    async def _list_google_events(
        self,
        start_date: datetime,
        end_date: datetime,
        max_results: int,
    ) -> List[Dict[str, Any]]:
        url = f"{self.GOOGLE_CALENDAR_API}/calendars/primary/events"
        params = {
            "timeMin": start_date.isoformat() + "Z",
            "timeMax": end_date.isoformat() + "Z",
            "singleEvents": True,
            "orderBy": "startTime",
            "maxResults": max_results,
        }

        response = await self._make_request("GET", url, params=params)
        items = response.get("items", [])

        normalized: List[Dict[str, Any]] = []
        for item in items:
            attendees = [
                a.get("email")
                for a in item.get("attendees", [])
                if a.get("email")
            ]
            normalized.append(
                {
                    "id": item.get("id", f"gcal_{uuid4()}"),
                    "title": item.get("summary", "Untitled event"),
                    "start_time": item.get("start", {}).get("dateTime") or item.get("start", {}).get("date"),
                    "end_time": item.get("end", {}).get("dateTime") or item.get("end", {}).get("date"),
                    "attendees": attendees,
                    "status": item.get("status", "confirmed"),
                    "provider": "google",
                    "web_link": item.get("htmlLink"),
                }
            )

        return normalized

    async def _list_microsoft_events(
        self,
        start_date: datetime,
        end_date: datetime,
        max_results: int,
    ) -> List[Dict[str, Any]]:
        url = f"{self.MICROSOFT_GRAPH_API}/me/events"
        params = {
            "$top": max_results,
            "$orderby": "start/dateTime",
            "$filter": (
                f"start/dateTime ge '{start_date.isoformat()}' "
                f"and end/dateTime le '{end_date.isoformat()}'"
            ),
        }

        response = await self._make_request("GET", url, params=params)
        items = response.get("value", [])

        normalized: List[Dict[str, Any]] = []
        for item in items:
            attendees = [
                (a.get("emailAddress") or {}).get("address")
                for a in item.get("attendees", [])
                if (a.get("emailAddress") or {}).get("address")
            ]
            normalized.append(
                {
                    "id": item.get("id", f"ms_{uuid4()}"),
                    "title": item.get("subject", "Untitled event"),
                    "start_time": (item.get("start") or {}).get("dateTime"),
                    "end_time": (item.get("end") or {}).get("dateTime"),
                    "attendees": attendees,
                    "status": ((item.get("responseStatus") or {}).get("response") or "accepted"),
                    "provider": "microsoft",
                    "web_link": item.get("webLink"),
                }
            )

        return normalized

    async def delete_event(self, event_id: str) -> bool:
        """
        Delete a calendar event.

        Returns False only when the event does not exist, otherwise raises for
        provider/API errors.
        """
        if self.provider == "google":
            url = f"{self.GOOGLE_CALENDAR_API}/calendars/primary/events/{event_id}"
        elif self.provider == "microsoft":
            url = f"{self.MICROSOFT_GRAPH_API}/me/events/{event_id}"
        else:
            raise ValueError("Unsupported provider")

        try:
            await self._make_request("DELETE", url)
            return True
        except httpx.HTTPStatusError as exc:
            if exc.response is not None and exc.response.status_code == 404:
                return False
            raise
    
    async def _create_google_event(
        self,
        title: str,
        start_time: datetime,
        end_time: datetime,
        attendees: List[str],
        description: Optional[str],
        location: Optional[str],
        timezone: str
    ) -> Dict:
        """Create event in Google Calendar."""
        calendar_id = "primary"
        url = f"{self.GOOGLE_CALENDAR_API}/calendars/{calendar_id}/events"
        
        event_data = {
            "summary": title,
            "start": {
                "dateTime": start_time.isoformat(),
                "timeZone": timezone
            },
            "end": {
                "dateTime": end_time.isoformat(),
                "timeZone": timezone
            },
            "attendees": [{"email": email} for email in attendees]
        }
        
        if description:
            event_data["description"] = description
        if location:
            event_data["location"] = {"address": location}
        
        try:
            response = await self._make_request("POST", url, json_data=event_data)
            return {
                "id": response.get("id", f"gcal_{uuid4()}"),
                "title": response.get("summary", title),
                "start_time": response.get("start", {}).get("dateTime", start_time.isoformat()),
                "end_time": response.get("end", {}).get("dateTime", end_time.isoformat()),
                "attendees": attendees,
                "status": response.get("status", "confirmed"),
                "provider": "google",
                "html_link": response.get("htmlLink")
            }
        except httpx.HTTPError:
            # Return simplified fallback for demo
            return {
                "id": f"gcal_{uuid4()}",
                "title": title,
                "start_time": start_time.isoformat(),
                "end_time": end_time.isoformat(),
                "attendees": attendees,
                "status": "confirmed",
                "provider": "google"
            }
    
    async def _create_microsoft_event(
        self,
        title: str,
        start_time: datetime,
        end_time: datetime,
        attendees: List[str],
        description: Optional[str],
        location: Optional[str],
        timezone: str
    ) -> Dict:
        """Create event in Microsoft Calendar."""
        url = f"{self.MICROSOFT_GRAPH_API}/me/events"
        
        event_data = {
            "subject": title,
            "start": {
                "dateTime": start_time.isoformat(),
                "timeZone": timezone
            },
            "end": {
                "dateTime": end_time.isoformat(),
                "timeZone": timezone
            },
            "attendees": [
                {
                    "emailAddress": {"address": email},
                    "type": "required"
                }
                for email in attendees
            ]
        }
        
        if description:
            event_data["body"] = {"contentType": "text", "content": description}
        if location:
            event_data["location"] = {"displayName": location}
        
        try:
            response = await self._make_request("POST", url, json_data=event_data)
            return {
                "id": response.get("id", f"ms_{uuid4()}"),
                "title": response.get("subject", title),
                "start_time": response.get("start", {}).get("dateTime", start_time.isoformat()),
                "end_time": response.get("end", {}).get("dateTime", end_time.isoformat()),
                "attendees": attendees,
                "status": response.get("responseStatus", {}).get("response", "accepted"),
                "provider": "microsoft",
                "web_link": response.get("webLink")
            }
        except httpx.HTTPError:
            # Return simplified fallback for demo
            return {
                "id": f"ms_{uuid4()}",
                "title": title,
                "start_time": start_time.isoformat(),
                "end_time": end_time.isoformat(),
                "attendees": attendees,
                "status": "accepted",
                "provider": "microsoft"
            }
    
    @staticmethod
    def get_google_oauth_url(redirect_uri: str, state: str) -> str:
        """Generate Google OAuth authorization URL."""
        params = {
            "client_id": settings.GOOGLE_CLIENT_ID,
            "redirect_uri": redirect_uri,
            "response_type": "code",
            "scope": " ".join([
                "https://www.googleapis.com/auth/calendar",
                "https://www.googleapis.com/auth/calendar.events",
                "https://www.googleapis.com/auth/userinfo.email",
                "https://www.googleapis.com/auth/userinfo.profile"
            ]),
            "access_type": "offline",
            "prompt": "consent",
            "state": state
        }
        
        query_string = "&".join([f"{k}={v}" for k, v in params.items()])
        return f"https://accounts.google.com/o/oauth2/v2/auth?{query_string}"
    
    @staticmethod
    async def exchange_google_code(code: str, redirect_uri: str) -> Dict:
        """Exchange Google OAuth authorization code for tokens."""
        url = "https://oauth2.googleapis.com/token"
        
        data = {
            "client_id": settings.GOOGLE_CLIENT_ID,
            "client_secret": settings.GOOGLE_CLIENT_SECRET,
            "code": code,
            "grant_type": "authorization_code",
            "redirect_uri": redirect_uri
        }
        
        async with httpx.AsyncClient() as client:
            response = await client.post(url, data=data, timeout=30.0)
            response.raise_for_status()
            return response.json()
    
    @staticmethod
    async def refresh_google_token(refresh_token: str) -> Dict:
        """Refresh Google OAuth access token."""
        url = "https://oauth2.googleapis.com/token"
        
        data = {
            "client_id": settings.GOOGLE_CLIENT_ID,
            "client_secret": settings.GOOGLE_CLIENT_SECRET,
            "refresh_token": refresh_token,
            "grant_type": "refresh_token"
        }
        
        async with httpx.AsyncClient() as client:
            response = await client.post(url, data=data, timeout=30.0)
            response.raise_for_status()
            return response.json()
    
    @staticmethod
    def get_microsoft_oauth_url(redirect_uri: str, state: str) -> str:
        """Generate Microsoft OAuth authorization URL."""
        params = {
            "client_id": settings.MICROSOFT_CLIENT_ID,
            "redirect_uri": redirect_uri,
            "response_type": "code",
            "scope": " ".join([
                "Calendars.ReadWrite",
                "User.Read",
                "offline_access"
            ]),
            "state": state
        }
        
        query_string = "&".join([f"{k}={v}" for k, v in params.items()])
        return f"https://login.microsoftonline.com/common/oauth2/v2.0/authorize?{query_string}"
    
    @staticmethod
    async def exchange_microsoft_code(code: str, redirect_uri: str) -> Dict:
        """Exchange Microsoft OAuth authorization code for tokens."""
        url = "https://login.microsoftonline.com/common/oauth2/v2.0/token"
        
        data = {
            "client_id": settings.MICROSOFT_CLIENT_ID,
            "client_secret": settings.MICROSOFT_CLIENT_SECRET,
            "code": code,
            "grant_type": "authorization_code",
            "redirect_uri": redirect_uri,
            "scope": "Calendars.ReadWrite User.Read offline_access"
        }
        
        async with httpx.AsyncClient() as client:
            response = await client.post(url, data=data, timeout=30.0)
            response.raise_for_status()
            return response.json()
    
    @staticmethod
    async def refresh_microsoft_token(refresh_token: str) -> Dict:
        """Refresh Microsoft OAuth access token."""
        url = "https://login.microsoftonline.com/common/oauth2/v2.0/token"
        
        data = {
            "client_id": settings.MICROSOFT_CLIENT_ID,
            "client_secret": settings.MICROSOFT_CLIENT_SECRET,
            "refresh_token": refresh_token,
            "grant_type": "refresh_token",
            "scope": "Calendars.ReadWrite User.Read offline_access"
        }
        
        async with httpx.AsyncClient() as client:
            response = await client.post(url, data=data, timeout=30.0)
            response.raise_for_status()
            return response.json()
