"""
LLM-based generation for OpenPharma RAG system.

Takes search results and generates synthesized answers with citations.
"""
from fastapi import HTTPException
from dataclasses import dataclass
from typing import List, Optional
import time

from app.retrieval import semantic_search, SearchResult
import os, re
import ollama

from app.logging_config import get_logger

logger = get_logger(__name__)

@dataclass
class Citation:
    """A single citation reference."""
    number: int
    title: str
    journal: str
    source_id: str  # PMC ID
    authors: Optional[List[str]] = None
    publication_date: Optional[str] = None
    chunk_id: int = None


@dataclass
class RAGResponse:
    """Complete answer with citations and metadata."""
    user_message: str
    generated_response: str
    response_citations: List[Citation]  # Citations that appear in this specific response
    chunks_used: List[SearchResult]
    llm_provider: str
    generation_time_ms: float
    conversation_id: str

def extract_citations_with_pmc_ids(answer_text: str, chunks: List[SearchResult]) -> tuple[str, List[Citation]]:
    """
    Extract PMC citations from LLM response, keeping [PMC...] citation format at this stage.

    Returns:
        Tuple of (answer_text with [PMC...], citations_list with number=0 as placeholder)
    """
    # Find all PMC IDs in order of appearance
    cited_pmcs = []
    bracket_contents = re.findall(r'\[([^\]]+)\]', answer_text)
    for content in bracket_contents:
        pmcs = re.findall(r'PMC(\d+)', content)
        cited_pmcs.extend(pmcs)

    # Get unique PMC IDs, preserving order
    seen = set()
    unique_pmcs = []
    for pmc_id in cited_pmcs:
        if pmc_id not in seen:
            seen.add(pmc_id)
            unique_pmcs.append(pmc_id)

    # Build chunk lookup
    chunk_map = {chunk.source_id: chunk for chunk in chunks}

    # Build citation objects (number will be assigned later in endpoint)
    citations = []
    for pmc_id in unique_pmcs:
        chunk = chunk_map.get(pmc_id)
        if chunk:
            citations.append(Citation(
                number=0,  # Placeholder, will be assigned by conversation manager
                title=chunk.title,
                journal=chunk.journal,
                source_id=pmc_id,
                authors=chunk.authors,
                publication_date=chunk.publication_date,
                chunk_id=chunk.chunk_id
            ))

    # Return answer text unchanged (still has [PMC...] format)
    return answer_text, citations

def build_messages(user_message: str, chunks: list[SearchResult], top_n: int, conversation_history: Optional[List[dict]]) -> List[dict]:
    """Build RAG prompt with user message, context, and literature chunks."""

    SYSTEM_PROMPT = """
<Task Context>
This is the generation step of a retrieval-augmented generation (RAG) workflow that powers OpenPharma, an AI-powered research & insights product. 
Users can ask questions in natural language and receive instant answers, transforming a multi-day research process into a matter of minutes in a chat-based interface.
Users may be competitive intelligence analysts, commercial strategists, brand managers, pharma consultants, etc. to inform business decisions.
</Task Context>

<Role Context>
You are an expert pharmaceutical researcher. 
Your role is to synthesize findings from scientific literature for life sciences companies & consultants, providing answers that are backed by credible evidence and verifiable citations.
</Role Context>

<Task Description>
Query and Synthesize Scientific Literature: Users may ask questions about drug efficacy, safety, mechanisms of action, key opinion leaders, etc.
You will review scientific literature passages in <Literature> in order to answer the user's query. 
You will think through step-by-step to pull in relevant details from <Literature> to support the answer. Reflect on your confidence in your answer based on the relevance, completeness, and consistency of the provided <Literature>.
You will respond concisely, summarizing the main answer, and providing supporting details from <Literature> with citations.
</Task Description>

<Constraints>
If there is insufficient information, your response must be **No sufficient evidence**
Your response must include only the response to the user's message.
Your answer must be based exclusively on the content provided in <Literature>.
CRITICAL: You MUST cite sources using their EXACT [PMC...] identifiers from <Literature> inline in your answer text.
CRITICAL: Do NOT use numbered citations like [1], [2], [3]. ONLY use [PMCxxxxxx] format.
CRITICAL: Do NOT include a separate references section or bibliography.

<Correct Examples>
"GLP-1 agonists improve glycemic control [PMC12345678] and reduce cardiovascular risk [PMC87654321]."
</Correct Examples>

<Incorrect Examples>
"GLP-1 agonists improve glycemic control [1] and reduce cardiovascular risk [2]."
"GLP-1 agonists improve glycemic control [PMC12345678] and reduce cardiovascular risk [PMC12345678].
References:
[PMC12345678] ...
[PMC12345678] ..."
</Incorrect Examples>"
"""
    messages = []
    messages.append({'role': 'system', 'content': SYSTEM_PROMPT})
    if conversation_history:
        messages.extend(conversation_history)

    current_message = f"<Literature>\nBelow are the top {top_n} most relevant literature passages to the user's query. Each passage starts with a unique [source_id].\n"
    # Use top n chunks in context, no re-ranking
    # Add to prompt with numbered chunks, formatted for inline citations [x]
    
    for idx, chunk in enumerate(chunks[:top_n], 1):
        # Strip citation markers [1], [2, 3], etc. from original paper text
        cleaned_content = re.sub(r'\[\d+(?:,\s*\d+)*\]', '', chunk.content)
        current_message += f"[PMC{chunk.source_id}] Title: {chunk.title} | {cleaned_content} | Journal: {chunk.journal}\n"

    current_message += f"</Literature>\nUser Query: {user_message}"

    messages.append({'role': 'user', 'content': current_message})

    return messages
    


def generate_response(
    user_message: str,
    conversation_id: str,
    top_k: int = 20,
    top_n: int = 5,
    use_local: bool = True,
    conversation_history: Optional[List[dict]] = None
) -> RAGResponse:
    """
    Generate a response using RAG (retrieval + LLM generation).

    Args:
        user_message: Natural language question from user
        conversation_id: Unique conversation identifier
        top_k: Number of chunks to retrieve (default: 20)
        top_n: Number of chunks to use in generation (default: 5)
        use_local: Use Ollama if True, OpenAI if False (default: True)
        conversation_history: Previous messages for multi-turn conversations

    Returns:
        RAGResponse with synthesized response and citations
    """
    start_time = time.time()

    # Fetch top k chunks and build prompt
    chunks = semantic_search(user_message, top_k=top_k)

    # Build messages array for multi-turn chat
    messages = build_messages(user_message, chunks, top_n=top_n, conversation_history=conversation_history)
    logger.debug(f"Messages:\n{messages}\n")

    # Call LLM
    try:
        if use_local:
            client = ollama.Client(host=os.getenv("OLLAMA_BASE_URL", default="http://localhost:11434"))
            response = client.chat(
                model='llama3.1:8b',
                messages=messages,
                options={'keep_alive': -1}
            )
            generated_response, citations = extract_citations_with_pmc_ids(response['message']['content'], chunks=chunks[:top_n])
        else:
            # TODO: Add OpenAI integration later
            logger.warning("OpenAI integration requested but not implemented")
            raise HTTPException(status_code=501, detail="OpenAI integration not yet implemented")
    except Exception as e:
        logger.error(f"Error generating response: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error generating response: {str(e)}")


    return RAGResponse(
        user_message=user_message,
        generated_response=generated_response,
        response_citations=citations,
        chunks_used=chunks[:top_n],
        llm_provider="ollama" if use_local else "openai",
        generation_time_ms=(time.time() - start_time) * 1000,
        conversation_id=conversation_id
    )

if __name__ == "__main__":
    # Configure logging for standalone execution
    from app.logging_config import setup_logging
    setup_logging(
        level=os.getenv("LOG_LEVEL", "INFO"),
        log_file="logs/openpharma.log"
    )

    # Simple test (note: requires conversation_id parameter now)
    # result = generate_response("What are amylins used for in diabetes treatment?", conversation_id="test-123")
    # print(f"User message: {result.user_message}\n")
    # print(f"Generated response:\n{result.generated_response}\n")
    # print(f"Citations:")
    # for citation in result.citations:
    #     print(f"  [{citation.number}] {citation.title} (PMC{citation.source_id})")
    # print(f"\nGeneration time: {result.generation_time_ms:.0f}ms")
    # print(f"LLM provider: {result.llm_provider}")

    print("Note: Run tests via /ask endpoint or update this test code with conversation_id")
