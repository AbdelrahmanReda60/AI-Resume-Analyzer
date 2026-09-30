from pydantic import BaseModel
from typing import List, Optional

class KBSearchItem(BaseModel):
    chunk_id: int
    title: str
    category: str
    content_snippet: str
    similarity_score: float

class KBSearchResponse(BaseModel):
    query: str
    total_results: int
    results: List[KBSearchItem]
