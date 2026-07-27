from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import List, Literal, Optional
import logging
from sqlalchemy.orm import Session

from ...auth import get_current_user
from ...database import get_db
from ...models.user import User
from ...services.sentiment import SentimentService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/sentiment", tags=["sentiment"])


class SentimentRequest(BaseModel):
    """Request model for single text sentiment analysis."""
    text: str


class SentimentBatchRequest(BaseModel):
    """Request model for batch sentiment analysis."""
    texts: List[str]


class SentimentResponse(BaseModel):
    """Response model for sentiment analysis."""
    sentiment: str
    score: float
    text: str
    source: Optional[Literal["lexicon", "llm", "hybrid", "enhanced"]] = None


class EmotionTagResponse(BaseModel):
    emotion: str
    secondary_emotions: List[str]
    confidence: float
    sentiment: str
    score: float


class SentimentTrendResponse(BaseModel):
    """Response model for sentiment trend analysis."""
    average_sentiment: float
    trend: str
    positive_percentage: float
    negative_percentage: float
    neutral_percentage: float
    total_analyses: int
    period_days: int = 7


class AlertResponse(BaseModel):
    """Response model for negative pattern alerts."""
    alert: bool
    message: str
    negative_count: int
    total_count: int
    negative_percentage: float


@router.post("/analyze", response_model=SentimentResponse)
def analyze_sentiment(
    request: SentimentRequest,
    current_user: User = Depends(get_current_user)
):
    """
    Analyze sentiment of a single text.
    
    Returns:
        SentimentResponse with label (positive/neutral/negative) and score (-1 to 1)
    """
    service = SentimentService()
    result = service.analyze(request.text)
    
    # Check if alert should be triggered
    if service.should_trigger_alert(result["sentiment"], result["score"]):
        logger.warning(
            f"Negative sentiment alert triggered for user {current_user.id}: "
            f"{result['sentiment']} ({result['score']})"
        )
    
    return SentimentResponse(**result)


@router.post("/emotion-tag", response_model=EmotionTagResponse)
def tag_emotion(
    request: SentimentRequest,
    current_user: User = Depends(get_current_user),
):
    """
    Tag emotional tone for a text, useful for proactive nudges and dashboard signals.
    """
    service = SentimentService()
    result = service.detect_emotion(request.text)
    logger.info(f"Emotion tag for user {current_user.id}: {result['emotion']}")
    return EmotionTagResponse(**result)


@router.post("/analyze/batch")
def analyze_batch(
    request: SentimentBatchRequest,
    current_user: User = Depends(get_current_user)
):
    """
    Analyze sentiment for multiple texts in batch.
    
    Returns:
        Dict with list of sentiment analysis results
    """
    service = SentimentService()
    results = service.analyze_batch(request.texts)
    return {"results": results}


@router.get("/trend", response_model=SentimentTrendResponse)
def get_sentiment_trend(
    days: int = 7,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Get sentiment trend analysis for the specified period.
    
    Args:
        days: Number of days to analyze (default: 7)
        
    Returns:
        SentimentTrendResponse with trend statistics
    """
    service = SentimentService(db=db)
    result = service.get_trend(user_id=current_user.id, days=days)
    return SentimentTrendResponse(**result)


@router.post("/check-pattern", response_model=AlertResponse)
def check_negative_pattern(
    sentiments: List[SentimentResponse],
    current_user: User = Depends(get_current_user)
):
    """
    Check for patterns of negative sentiment in recent analyses.
    
    Args:
        sentiments: List of recent sentiment results to analyze
        
    Returns:
        AlertResponse if negative pattern detected, otherwise null
    """
    service = SentimentService()
    
    # Convert to dict format for the service
    sentiment_dicts = [s.dict() for s in sentiments]
    pattern_result = service.check_negative_patterns(sentiment_dicts)
    
    if pattern_result:
        logger.warning(
            f"Negative pattern detected for user {current_user.id}: "
            f"{pattern_result['negative_percentage']}% negative"
        )
        return AlertResponse(**pattern_result)
    
    return AlertResponse(
        alert=False,
        message="No negative pattern detected",
        negative_count=0,
        total_count=len(sentiments),
        negative_percentage=0.0
    )
