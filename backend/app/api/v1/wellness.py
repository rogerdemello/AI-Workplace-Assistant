from typing import List, Optional

from fastapi import APIRouter, HTTPException, Query, status, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ...database import get_db
from ...models.wellness_tip import WellnessTip, WellnessTipType

router = APIRouter(prefix="/wellness", tags=["wellness"])


class WellnessTipResponse(BaseModel):
    id: str
    tip_type: str
    title: str
    content: str
    emoji: str
    is_active: bool


class WellnessTipsListResponse(BaseModel):
    tips: List[WellnessTipResponse]
    total: int


def _to_response(tip: WellnessTip) -> WellnessTipResponse:
    return WellnessTipResponse(
        id=str(tip.id),
        tip_type=tip.tip_type.value,
        title=tip.title,
        content=tip.content,
        emoji=tip.emoji,
        is_active=tip.is_active,
    )


@router.get("/tips", response_model=WellnessTipsListResponse)
def list_wellness_tips(
    active_only: bool = Query(default=True, description="Filter to active tips only"),
    db: Session = Depends(get_db),
):
    query = db.query(WellnessTip)
    if active_only:
        query = query.filter(WellnessTip.is_active == True)
    tips = query.order_by(WellnessTip.created_at.desc()).all()
    return WellnessTipsListResponse(
        tips=[_to_response(t) for t in tips],
        total=len(tips),
    )


@router.get("/tips/{tip_type}", response_model=WellnessTipsListResponse)
def get_wellness_tips_by_type(
    tip_type: str,
    active_only: bool = Query(default=True, description="Filter to active tips only"),
    db: Session = Depends(get_db),
):
    try:
        tip_enum = WellnessTipType(tip_type)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid tip_type. Must be one of: {', '.join(t.value for t in WellnessTipType)}",
        )

    query = db.query(WellnessTip).filter(WellnessTip.tip_type == tip_enum)
    if active_only:
        query = query.filter(WellnessTip.is_active == True)
    tips = query.order_by(WellnessTip.created_at.desc()).all()
    return WellnessTipsListResponse(
        tips=[_to_response(t) for t in tips],
        total=len(tips),
    )