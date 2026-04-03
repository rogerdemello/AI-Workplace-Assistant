from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from typing import Optional, List
from uuid import UUID

from ...auth import get_current_user
from ...models.user import User
from ...services.intent_classifier import (
    IntentClassifier,
    get_intent_classifier,
    INTENT_LIST
)

router = APIRouter(prefix="/ai", tags=["ai"])


class IntentClassificationRequest(BaseModel):
    message: str


class IntentClassificationResponse(BaseModel):
    intent: str
    confidence: float
    reasoning: Optional[str] = None
    fallback: bool = False
    suggestion: Optional[str] = None
    escalate: bool = False


class IntentHistoryResponse(BaseModel):
    entries: List[dict]
    total: int


def get_classifier(
    confidence_threshold: float = Query(default=0.7, ge=0.0, le=1.0),
    use_mock: bool = Query(default=False)
) -> IntentClassifier:
    return get_intent_classifier(
        confidence_threshold=confidence_threshold,
        use_mock=use_mock
    )


@router.post("/classify-intent", response_model=IntentClassificationResponse)
def classify_intent(
    request: IntentClassificationRequest,
    current_user: User = Depends(get_current_user),
    classifier: IntentClassifier = Depends(get_classifier)
):
    result = classifier.classify_with_fallback(
        message=request.message,
        user_id=str(current_user.id)
    )
    return IntentClassificationResponse(**result)


@router.get("/intents", response_model=List[str])
def list_intents(current_user: User = Depends(get_current_user)):
    return INTENT_LIST


@router.get("/classify-intent/history", response_model=IntentHistoryResponse)
def get_intent_history(
    limit: int = Query(default=50, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    classifier: IntentClassifier = Depends(get_classifier)
):
    entries = classifier.get_history(
        user_id=str(current_user.id),
        limit=limit
    )
    return IntentHistoryResponse(entries=entries, total=len(entries))
