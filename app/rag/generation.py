"""
LLM-based generation for OpenPharma RAG system.

Takes search results and generates synthesized answers with citations.
"""
from fastapi import HTTPException
from typing import List, Optional
import time
import os
import re
import ollama

from app.models import SearchResult
from app.logging_config import get_logger

logger = get_logger(__name__)

# Model configuration - change this to experiment with different models
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "llama3.1:8b")


def build_messages(user_message: str, chunks: list[SearchResult], conversation_history: Optional[List[dict]]) -> List[dict]:
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
Your answer must start with ## Answer
Your references section must start with ## References
CRITICAL: You MUST cite sources using their EXACT [PMC...] identifiers from <Literature> inline in your answer text.
CRITICAL: Do NOT use numbered citations like [1], [2], [3]. ONLY use [PMCxxxxxx] format.
</Constraints>

<Correct Examples>
"
## Answer:
GLP-1 agonists improve glycemic control [PMC12345678] and reduce cardiovascular risk [PMC87654321].
## References:
[PMC12345678] ...
[PMC12345678] ...
"
</Correct Examples>

<Incorrect Examples>
"GLP-1 agonists improve glycemic control [1] and reduce cardiovascular risk [2].
Notes:
[1] ...
[2] ..."
</Incorrect Examples>"
"""
    messages = []
    messages.append({'role': 'system', 'content': SYSTEM_PROMPT})

    # Add conversation history, filtering out cited_source_ids (not part of Ollama API)
    if conversation_history:
        for msg in conversation_history:
            messages.append({
                'role': msg['role'],
                'content': msg['content']
            })

    # current_message = f"<Literature>\nBelow are the top {len(chunks)} most relevant literature passages to the user's query, as well as recently cited literature. Each passage starts with a unique [source_id].\n"
    current_message = f"<Literature>\nBelow are the top {len(chunks)} most relevant literature passages to the user's query. Each passage starts with a unique [source_id].\n"
    # Use top n chunks in context, no re-ranking
    # Add to prompt with numbered chunks, formatted for inline citations [x]
    
    for idx, chunk in enumerate(chunks, 1):
        # Strip citation markers [1], [2, 3], etc. from original paper text
        cleaned_content = re.sub(r'\[\d+(?:,\s*\d+)*\]', '', chunk.content)
        current_message += f"[PMC{chunk.source_id}] Title: {chunk.title} | {cleaned_content} | Journal: {chunk.journal}\n"

    current_message += f"</Literature>\nUser Query: {user_message}"

    messages.append({'role': 'user', 'content': current_message})

    return messages
    

async def generate_response_stream(
    user_message: str, 
    chunks: List[SearchResult], 
    use_local: bool = True,
    conversation_history: Optional[List[dict]] = None
):
    pass


def generate_response(
    user_message: str,
    chunks: List[SearchResult],
    use_local: bool = True,
    conversation_history: Optional[List[dict]] = None
) -> str:
    """Generate response text using provided chunks (retrieval done by caller)"""
    
    # Build messages array for multi-turn chat
    messages = build_messages(user_message, chunks, conversation_history)
    logger.debug(f"Messages:\n{messages}\n")

    # Call LLM
    try:
        if use_local:
            llm_start = time.time()
            logger.info(f"Using model: {OLLAMA_MODEL}")
            client = ollama.Client(host=os.getenv("OLLAMA_BASE_URL", default="http://localhost:11434"))
            response = client.chat(
                model=OLLAMA_MODEL,
                messages=messages,
                options={'keep_alive': -1}
            )
            llm_time = (time.time() - llm_start) * 1000
            logger.info(f"LLM generation time: {llm_time:.0f}ms")
            return response['message']['content']
        else:
            # TODO: Add OpenAI integration later
            logger.warning("OpenAI integration requested but not implemented")
            raise HTTPException(status_code=501, detail="OpenAI integration not yet implemented")
    except Exception as e:
        logger.error(f"Error generating response: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error generating response: {str(e)}")



if __name__ == "__main__":
    from app.logging_config import setup_logging
    setup_logging(
        level=os.getenv("LOG_LEVEL", "INFO"),
        log_file="logs/openpharma.log"
    )

    print("Run tests via /ask endpoint or use tests/test_refactored_flow.py")
