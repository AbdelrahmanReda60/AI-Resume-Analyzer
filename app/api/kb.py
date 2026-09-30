from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from app.database import get_db
from app.api.deps import get_current_user
from app.models.user import User
from app.services.vector_store import search_vector_store
from app.schemas.kb import KBSearchResponse, KBSearchItem

router = APIRouter(prefix="/kb", tags=["Knowledge Base"])

@router.get("/search", response_model=KBSearchResponse)
def search_kb(
    q: str = Query(..., min_length=1),
    category: str = Query(None),
    limit: int = Query(5, ge=1, le=20),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    results = search_vector_store(db, query=q, top_k=limit, category=category)
    items = []
    for r in results:
        items.append(KBSearchItem(
            chunk_id=r["chunk_id"],
            title=r["title"],
            category=r["category"],
            content_snippet=r["content"][:200],
            similarity_score=r["similarity_score"]
        ))

    return KBSearchResponse(
        query=q,
        total_results=len(items),
        results=items
    )
