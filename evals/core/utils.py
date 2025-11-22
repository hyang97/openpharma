"""Shared utility functions: database queries, formatting, I/O."""
import json
import random
from pathlib import Path
from typing import Dict, List
from sqlalchemy import text
from sqlalchemy.orm import Session
from app.db.database import engine


def fetch_chunk_content_and_pmid(chunk_ids: List[int]) -> Dict[int, Dict[str, str]]:
    """Fetch chunk content and PMID from database."""
    if not chunk_ids:
        return {}

    stmt = text("""
        SELECT
            dc.document_chunk_id,
            dc.content,
            p.pmid
        FROM document_chunks dc
        JOIN documents d ON dc.document_id = d.document_id
        LEFT JOIN pubmed_papers p ON d.source_id = p.pmc_id
        WHERE dc.document_chunk_id = ANY(:chunk_ids)
    """)

    with Session(engine) as session:
        results = session.execute(stmt, {'chunk_ids': chunk_ids}).fetchall()

    return {
        row.document_chunk_id: {
            'content': row.content,
            'pmid': row.pmid if row.pmid else 'Unknown'
        }
        for row in results
    }


def enrich_citations_with_content(citations: List[Dict]) -> List[Dict]:
    """Enrich citations with chunk content and PMID from database."""
    chunk_ids = [cit["chunk_id"] for cit in citations]
    chunk_data_map = fetch_chunk_content_and_pmid(chunk_ids)

    enriched_citations = []
    for cit in citations:
        cit_copy = cit.copy()
        chunk_data = chunk_data_map.get(cit["chunk_id"], {})
        cit_copy["chunk_content"] = chunk_data.get('content', 'Content not available')
        cit_copy["pmid"] = chunk_data.get('pmid', 'Unknown')
        enriched_citations.append(cit_copy)

    return enriched_citations


def load_json(file_path: str) -> Dict:
    """Load JSON file."""
    with open(file_path, 'r') as f:
        return json.load(f)


def save_json(data: Dict, file_path: str):
    """Save data to JSON file."""
    path = Path(file_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, 'w') as f:
        json.dump(data, f, indent=2)


def save_text(content: str, file_path: str):
    """Save text content to file."""
    path = Path(file_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, 'w') as f:
        f.write(content)


def format_citations_minimal(citations: List[Dict]) -> str:
    """Format citations with minimal info - just chunk content."""
    if not citations:
        return "No citations"

    output = ""
    for i, cit in enumerate(citations, 1):
        chunk_content = cit.get('chunk_content', 'Content not available')
        output += f"[{i}] {chunk_content}\n\n"

    return output


def format_question_for_llm_judge(result: Dict, enriched_citations: List[Dict]) -> str:
    """Format question as markdown for LLM-as-judge review."""
    template_path = Path(__file__).parent / "llm_judge_qa_template.md"
    with open(template_path, 'r') as f:
        template = f.read()

    return template.format(
        question_id=result['question_id'],
        question=result['question'],
        expected_answer=result.get('expected_answer', 'N/A'),
        long_answer=result.get('long_answer', 'N/A'),
        rag_answer=result.get('rag_answer', 'N/A'),
        num_chunks=len(enriched_citations),
        chunks=format_citations_minimal(enriched_citations)
    )


def get_llm_judge_prompt() -> str:
    """LLM-as-judge evaluation prompt."""
    prompt_path = Path(__file__).parent / "llm_judge_prompt.md"
    with open(prompt_path, 'r') as f:
        return f.read()
