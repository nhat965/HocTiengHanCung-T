from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_session
from app.models import Textbook
from app.schemas import TextbookResponse

router = APIRouter(prefix="/textbooks", tags=["textbooks"])


@router.get("", response_model=list[TextbookResponse])
def list_textbooks(session: Session = Depends(get_session)) -> list[TextbookResponse]:
    textbooks = session.scalars(select(Textbook).order_by(Textbook.volume_number)).all()
    return [TextbookResponse(id=item.id, title=item.title, level=item.level, volume_number=item.volume_number) for item in textbooks]
