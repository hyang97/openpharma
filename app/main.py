from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import os
import re
from typing import Optional, List

from app.models import Citation, RAGResponse
from app.db.database import get_db
from app.logging_config import setup_logging, get_logger
from app.rag.generation import generate_response
from app.rag.conversation_manager import ConversationManager

# Initialize conversation manager on startup
conversation_manager = ConversationManager(max_age_seconds=3600)

# Configure logging on startup
setup_logging(
    level=os.getenv("LOG_LEVEL", "INFO"),
    log_file="logs/openpharma.log"
)
logger = get_logger(__name__)

app = FastAPI(title="OpenPharma API", version="0.1.0")

# Configure CORS to allow requests from React frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],  # React dev server
    allow_credentials=True,
    allow_methods=["*"],  # Allow all methods (GET, POST, etc.)
    allow_headers=["*"],  # Allow all headers
)

class UserRequest(BaseModel):
    user_message: str
    use_local: Optional[bool] = None
    conversation_id: Optional[str] = None

class ConversationSummaryResponse(BaseModel):
    conversation_id: str 
    first_message: str 
    message_count: int 
    last_updated: float

class ConversationDetailResponse(BaseModel):
    conversation_id: str
    first_message: str
    message_count: int
    last_updated: float
    messages: List[dict]
    citations: List[Citation]

class ChatResponse(BaseModel):
    user_message: str
    generated_response: str
    response_citations: List[Citation]
    conversation_citations: List[Citation]
    llm_provider: str
    generation_time_ms: float
    conversation_id: str

def prepare_messages_for_display(messages: List[dict], conversation_id: str) -> List[dict]:
    """
    Prepare messages for frontend: strip headings, renumber citations [PMCxxxx] -> [1].
    """
    # Fetch citation mapping once for efficiency
    all_citations = conversation_manager.get_all_citations(conversation_id)
    pmc_to_number = {cit.source_id: cit.number for cit in all_citations}

    prepared_messages = []
    for msg in messages:
        if msg['role'] == 'assistant':
            content = msg['content']

            # Strip "## Answer" heading if present (case-insensitive)
            # Matches: "## Answer", "##Answer", "## Answer:", "## Answer :", etc.
            # \s* allows any whitespace between ## and Answer
            # :? allows optional colon after Answer
            # [\s:]* captures any trailing whitespace or colons
            # Must be at start of line (^) or start of string (\A)
            content = re.sub(r'^##\s*Answer\s*:?\s*\n?', '', content.strip(), flags=re.IGNORECASE | re.MULTILINE)

            # Strip leading colons and whitespace (artifact from heading removal)
            content = content.lstrip(': \t\n')

            # Strip "## References" section and everything after it (case-insensitive)
            # Matches multiple formats:
            # - "## References"
            # - "##References"
            # - "## References:"
            # - "References:"
            # - "**References**" (bold markdown)
            # .*$ captures everything from the heading to end of text
            content = re.sub(
                r'(?:^|\n)\s*(?:##\s*References|References\s*:|[\*]{2}References[\*]{2})\s*:?\s*.*$',
                '',
                content,
                flags=re.IGNORECASE | re.DOTALL | re.MULTILINE
            )

            # Strip trailing whitespace
            content = content.rstrip()

            # Replace all [PMCxxxx] with [number]
            # Supports both single citations [PMC123] and comma-separated [PMC123, PMC456]
            for source_id, number in pmc_to_number.items():
                # Pattern matches:
                # - [PMC123] -> [1]
                # - [PMC123, PMC456] -> [1, 2] (when both are replaced)
                # - [ PMC123 ] -> [1] (with whitespace)
                # - [PMC123,PMC456] -> [1,2] (no space after comma)
                # Uses lookahead to match PMC ID followed by comma, space, or closing bracket
                pattern = r'PMC' + source_id + r'(?=\s*[,\]])'
                content = re.sub(pattern, str(number), content)

            prepared_messages.append({
                'role': msg['role'],
                'content': content
            })
        else:
            # User messages pass through unchanged
            prepared_messages.append(msg)

    return prepared_messages


def extract_and_store_citations(result: RAGResponse, conversation_id: str) -> List[Citation]:
    """
    Extracts [PMCxxxxx] citations from generated_response text, builds Citation
    objects, assigns conversation-wide numbers and store in conversation manager.
    """
    # Extract all PMC IDs from brackets in response text
    cited_pmc_ids = []
    bracket_contents = re.findall(r'\[([^\]]+)\]', result.generated_response)
    for content in bracket_contents:
        # Extract PMC IDs, handling formats [PMC123], [PMC123, PMC456], [ PMC123 ], [PMC123,PMC456]
        pmcs = re.findall(r'PMC(\d+)', content)
        cited_pmc_ids.extend(pmcs)

    # Get unique PMC IDs, preserving order of first appearance
    seen = set()
    unique_pmc_ids = []
    for pmc_id in cited_pmc_ids:
        if pmc_id not in seen:
            seen.add(pmc_id)
            unique_pmc_ids.append(pmc_id)

    # Build lookup map: source_id -> SearchResult
    chunk_map = {chunk.source_id: chunk for chunk in result.prompt_literature_chunks}

    # Build Citation objects via ConversationManager
    numbered_citations = []
    for pmc_id in unique_pmc_ids:
        chunk = chunk_map.get(pmc_id)
        if chunk:
            # Let ConversationManager create/retrieve Citation with proper number
            citation = conversation_manager.get_or_create_citation(
                conversation_id=conversation_id,
                chunk=chunk
            )
            numbered_citations.append(citation)

    return numbered_citations



@app.on_event("startup")
async def startup_event():
    logger.info("Starting OpenPharma API")
    logger.info(f"Using local LLM: {os.getenv('USE_LOCAL_LLM', 'true')}")

@app.on_event("shutdown")
async def shutdown_event():
    logger.info("Shutting down OpenPharma API")

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy", "message": "OpenPharma API is running"}

@app.get("/conversations", response_model=List[ConversationSummaryResponse])
async def get_all_conversation_summaries():
    summaries = conversation_manager.get_conversation_summaries()
    return summaries

@app.get("/conversations/{conversation_id}", response_model=ConversationDetailResponse)
async def get_conversation_detail(conversation_id: str):
    """Get full details for a specific conversation"""
    c = conversation_manager.get_conversation(conversation_id)
    if not c:
        raise HTTPException(status_code=404, detail="Conversation not found")

    # Get all citations for this conversation
    citations = conversation_manager.get_all_citations(conversation_id)

    # Get first user message
    first_message = next((m["content"] for m in c.messages if m["role"] == "user"), "")

    # Prepare messages for frontend display
    display_messages = prepare_messages_for_display(c.messages, conversation_id)

    # Build and return the response
    return ConversationDetailResponse(
        conversation_id=conversation_id,
        first_message=first_message[:100],
        message_count=len(c.messages),
        last_updated=c.last_accessed,
        messages=display_messages,
        citations=citations
    )




@app.post("/chat", response_model=ChatResponse)
async def send_message(request: UserRequest):
    """Send a message and get an AI response with citations"""

    # Determine which model to use
    use_local = request.use_local if request.use_local is not None else os.getenv("USE_LOCAL_LLM", default="true").lower() == "true"

    logger.info(f"Received question: {request.user_message[:100]}...")
    logger.debug(f"Using local model: {use_local}")

    # Get or create conversation object
    conversation_id = request.conversation_id
    if not conversation_id:
        conversation_id = conversation_manager.create_conversation()
    conversation = conversation_manager.get_conversation(conversation_id)
    if not conversation:
        raise HTTPException(status_code=404, detail="Conversation not found")

    # Get conversation history for multi-turn support
    conversation_history = conversation_manager.get_messages(conversation_id)

    try:
        # Use RAG pipeline - returns RAGResponse with [PMC...] format
        result = generate_response(user_message=request.user_message, conversation_id=conversation_id, use_local=use_local, conversation_history=conversation_history)

        # Extract and store citations from response (assigns conversation-wide numbers)
        numbered_response_citations = extract_and_store_citations(result, conversation_id)

        # Store messages with ORIGINAL [PMC...] format for LLM context
        conversation_manager.add_message(conversation_id, "user", request.user_message)
        conversation_manager.add_message(
            conversation_id,
            "assistant",
            result.generated_response,
            cited_source_ids=[cit.source_id for cit in numbered_response_citations], 
            cited_chunk_ids=[cit.chunk_id for cit in numbered_response_citations]
        )

        # Get all conversation-wide citations
        conversation_citations = conversation_manager.get_all_citations(conversation_id)

        # Prepare response text for frontend display only (wrap in list for single message)
        display_response = prepare_messages_for_display(
            [{'role': 'assistant', 'content': result.generated_response}],
            conversation_id
        )[0]['content']

        logger.info(f"Generated RAG response with {len(numbered_response_citations)} citations in {result.generation_time_ms:.0f}ms")

        # Return ChatResponse with renumbered text for display
        return ChatResponse(
            user_message=result.user_message,
            generated_response=display_response,
            response_citations=numbered_response_citations,  # Use numbered citations
            conversation_citations=conversation_citations,
            llm_provider=result.llm_provider,
            generation_time_ms=result.generation_time_ms,
            conversation_id=result.conversation_id
        )

    except Exception as e:
        logger.error(f"Error generating response: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error generating response: {str(e)}")

@app.get("/")
async def root():
    return {"message": "Welcome to OpenPharma API", "docs": "/docs"}