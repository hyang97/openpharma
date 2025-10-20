from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import os
import re
from typing import Optional, List
from .db.database import get_db
from .logging_config import setup_logging, get_logger
from .rag.generation import generate_response, RAGResponse, Citation
from .rag.conversation_manager import ConversationManager

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

def renumber_and_store_citations_for_conversation(result: RAGResponse, conversation_id: str) -> RAGResponse:
    """
    Renumber citations in RAGResponse and store citations to use conversation-wide.

    Args:
        result: RAGResponse with [PMC...] format in generated_response
        conversation_id: Conversation identifier

    Returns:
        Updated generated_response text with [1], [2], etc. format
    """
    renumbered_response = result.generated_response

    # Update citation numbers and replace PMC IDs in generated response text
    for response_citation in result.response_citations:
        # Get or store citation, returning conversation-wide number
        convo_citation_num = conversation_manager.get_or_store_citation(conversation_id, citation=response_citation)

        # Update citation object
        response_citation.number = convo_citation_num

        # Replace [PMC...] with [num] in response text
        renumbered_response = renumbered_response.replace(f'PMC{response_citation.source_id}', f'{convo_citation_num}')

    result.generated_response = renumbered_response
    return result



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

    # Build and return the response
    return ConversationDetailResponse(
        conversation_id=conversation_id,
        first_message=first_message[:100],
        message_count=len(c.messages),
        last_updated=c.last_accessed,
        messages=c.messages,
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

        # Renumber citations using conversation-wide numbering and update RAGResponse
        result = renumber_and_store_citations_for_conversation(result, conversation_id)

        # Add user message and assistant response to conversation
        conversation_manager.add_message(conversation_id, "user", request.user_message)
        conversation_manager.add_message(conversation_id, "assistant", result.generated_response)

        # Get all conversation-wide citations
        conversation_citations = conversation_manager.get_all_citations(conversation_id)

        logger.info(f"Generated RAG response with {len(result.response_citations)} citations in {result.generation_time_ms:.0f}ms")

        # Return ChatResponse with both response and conversation-wide citations
        return ChatResponse(
            user_message=result.user_message,
            generated_response=result.generated_response,
            response_citations=result.response_citations,
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