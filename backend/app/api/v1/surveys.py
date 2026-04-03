from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
from uuid import UUID

from ...database import get_db
from ...auth import get_current_user
from ...models.user import User
from ...models.survey import Survey, SurveyResponse

router = APIRouter(prefix="/surveys", tags=["surveys"])


class SurveyQuestion(BaseModel):
    id: str
    type: str  # "text", "rating", "choice", "multiple_choice"
    question: str
    options: Optional[List[str]] = None
    required: bool = True


class SurveyCreate(BaseModel):
    title: str
    description: Optional[str] = None
    questions: List[Dict[str, Any]]
    allow_anonymous: bool = False


class SurveyUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    questions: Optional[List[Dict[str, Any]]] = None
    is_active: Optional[bool] = None
    allow_anonymous: Optional[bool] = None


class SurveyResponseModel(BaseModel):
    id: UUID
    title: str
    description: Optional[str]
    questions: List[Dict[str, Any]]
    is_active: bool
    allow_anonymous: bool
    created_by: Optional[UUID]
    created_at: Any
    
    class Config:
        from_attributes = True


class SurveyListResponse(BaseModel):
    id: UUID
    title: str
    description: Optional[str]
    is_active: bool
    allow_anonymous: bool
    created_at: Any
    
    class Config:
        from_attributes = True


class SurveyRespond(BaseModel):
    responses: Dict[str, Any]
    anonymous: bool = False


class SurveyResponseCreate(BaseModel):
    survey_id: UUID
    responses: Dict[str, Any]


@router.post("", response_model=SurveyResponseModel, status_code=status.HTTP_201_CREATED)
def create_survey(
    survey: SurveyCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Create a new survey (Admin only)."""
    if current_user.role not in ["admin", "hr"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only admins and HR can create surveys"
        )
    
    new_survey = Survey(
        title=survey.title,
        description=survey.description,
        questions=survey.questions,
        allow_anonymous=survey.allow_anonymous,
        is_active=True,
        created_by=current_user.id
    )
    
    db.add(new_survey)
    db.commit()
    db.refresh(new_survey)
    
    return new_survey


@router.get("", response_model=List[SurveyListResponse])
def list_surveys(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    active_only: bool = True
):
    """List all surveys. Employees see active surveys, admins see all."""
    query = db.query(Survey)
    
    if active_only:
        query = query.filter(Survey.is_active == True)
    
    surveys = query.order_by(Survey.created_at.desc()).all()
    return surveys


@router.get("/all", response_model=List[SurveyListResponse])
def list_all_surveys(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """List all surveys including inactive ones (Admin/HR only)."""
    if current_user.role not in ["admin", "hr"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only admins and HR can view all surveys"
        )
    
    surveys = db.query(Survey).order_by(Survey.created_at.desc()).all()
    return surveys


@router.get("/{survey_id}", response_model=SurveyResponseModel)
def get_survey(
    survey_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get survey details by ID."""
    survey = db.query(Survey).filter(Survey.id == survey_id).first()
    if not survey:
        raise HTTPException(status_code=404, detail="Survey not found")
    
    return survey


@router.patch("/{survey_id}", response_model=SurveyResponseModel)
def update_survey(
    survey_id: UUID,
    survey_update: SurveyUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Update a survey (Admin only)."""
    if current_user.role not in ["admin", "hr"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only admins and HR can update surveys"
        )
    
    survey = db.query(Survey).filter(Survey.id == survey_id).first()
    if not survey:
        raise HTTPException(status_code=404, detail="Survey not found")
    
    if survey_update.title is not None:
        survey.title = survey_update.title
    if survey_update.description is not None:
        survey.description = survey_update.description
    if survey_update.questions is not None:
        survey.questions = survey_update.questions
    if survey_update.is_active is not None:
        survey.is_active = survey_update.is_active
    if survey_update.allow_anonymous is not None:
        survey.allow_anonymous = survey_update.allow_anonymous
    
    db.commit()
    db.refresh(survey)
    
    return survey


@router.delete("/{survey_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_survey(
    survey_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Delete a survey (Admin only)."""
    if current_user.role not in ["admin", "hr"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only admins and HR can delete surveys"
        )
    
    survey = db.query(Survey).filter(Survey.id == survey_id).first()
    if not survey:
        raise HTTPException(status_code=404, detail="Survey not found")
    
    db.delete(survey)
    db.commit()
    
    return None


@router.post("/{survey_id}/respond", status_code=status.HTTP_201_CREATED)
def respond_survey(
    survey_id: UUID,
    response: SurveyRespond,
    current_user: Optional[User] = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Submit a survey response."""
    survey = db.query(Survey).filter(Survey.id == survey_id).first()
    if not survey:
        raise HTTPException(status_code=404, detail="Survey not found")
    
    if not survey.is_active:
        raise HTTPException(status_code=400, detail="Survey is no longer active")
    
    # Determine user_id and anonymous status
    user_id = None
    is_anonymous = response.anonymous
    
    if survey.allow_anonymous and is_anonymous:
        # Anonymous response allowed and requested
        user_id = None
    elif current_user:
        # Authenticated user
        user_id = current_user.id
        is_anonymous = False
    else:
        # Not authenticated and survey doesn't allow anonymous
        if not survey.allow_anonymous:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Authentication required for this survey"
            )
        # Anonymous but survey allows it
        user_id = None
        is_anonymous = True
    
    # Create response
    survey_response = SurveyResponse(
        survey_id=survey_id,
        user_id=user_id,
        responses=response.responses
    )
    
    db.add(survey_response)
    db.commit()
    db.refresh(survey_response)
    
    return {
        "id": survey_response.id,
        "status": "submitted",
        "anonymous": is_anonymous
    }


@router.get("/{survey_id}/responses")
def get_survey_responses(
    survey_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get all responses for a survey (Admin/HR only)."""
    if current_user.role not in ["admin", "hr"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only admins and HR can view survey responses"
        )
    
    survey = db.query(Survey).filter(Survey.id == survey_id).first()
    if not survey:
        raise HTTPException(status_code=404, detail="Survey not found")
    
    responses = db.query(SurveyResponse).filter(
        SurveyResponse.survey_id == survey_id
    ).all()
    
    return {
        "survey_id": survey_id,
        "survey_title": survey.title,
        "total_responses": len(responses),
        "responses": [
            {
                "id": r.id,
                "user_id": r.user_id,
                "responses": r.responses,
                "created_at": r.created_at
            }
            for r in responses
        ]
    }
