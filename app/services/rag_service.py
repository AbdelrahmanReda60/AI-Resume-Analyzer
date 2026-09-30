from sqlalchemy.orm import Session
from app.services.vector_store import search_vector_store

def retrieve_rag_context(db: Session, query: str, top_k: int = 4, category: str = None) -> tuple[str, list]:
    """
    Retrieves top-K knowledge base chunks for query and returns:
    (formatted_context_str, list_of_cited_sources)
    """
    chunks = search_vector_store(db, query, top_k=top_k, category=category)

    if not chunks:
        return "No specific knowledge base context found.", []

    context_lines = []
    sources = []

    for i, chunk in enumerate(chunks, 1):
        source_label = f"[{chunk['category'].upper()}: {chunk['title']}]"
        context_lines.append(f"{i}. {source_label}\n   {chunk['content']}")
        sources.append({
            "citation": source_label,
            "title": chunk["title"],
            "category": chunk["category"]
        })

    formatted_context = "\n\n".join(context_lines)
    return formatted_context, sources
