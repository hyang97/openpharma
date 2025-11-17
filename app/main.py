from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
import time
import os
import json
import asyncio
import logging
from typing import Optional, List

from app.models import Citation, SearchResult
from app.db.database import get_db
from app.logging_config import setup_logging, get_logger
from app.rag.generation import generate_response, generate_response_stream
from app.retrieval import semantic_search, hybrid_retrieval
from app.rag.conversation_manager import ConversationManager
from app.rag.response_processing import prepare_messages_for_display, extract_and_store_citations

# Initialize conversation manager on startup
conversation_manager = ConversationManager(max_age_seconds=3600)

# Configure logging on startup
setup_logging(
    level=os.getenv("LOG_LEVEL", "INFO"),
    log_file="logs/openpharma.log"
)
logger = get_logger(__name__)

# Configure metrics logger to separate file
metrics_logger = get_logger("metrics")
metrics_handler = logging.FileHandler("logs/streaming_metrics.log")
metrics_handler.setFormatter(logging.Formatter('%(asctime)s - %(message)s'))
metrics_logger.addHandler(metrics_handler)
metrics_logger.setLevel(logging.INFO)
metrics_logger.propagate = False  # Don't send to root logger

app = FastAPI(title="OpenPharma API", version="0.1.0")

# Configure CORS to allow requests from React frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",  # React dev server
        "https://openpharma.byhenry.me"  # Production
    ],
    allow_credentials=True,
    allow_methods=["*"],  # Allow all methods (GET, POST, etc.)
    allow_headers=["*"],  # Allow all headers
)

class UserRequest(BaseModel):
    user_message: str
    use_local: Optional[bool] = None
    conversation_id: Optional[str] = None
    use_reranker: bool = False
    additional_chunks_per_doc: int = 0
    top_k: int = 10
    top_n: int = 5

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
    display_messages = prepare_messages_for_display(c.messages, conversation_id, conversation_manager)

    # Build and return the response
    return ConversationDetailResponse(
        conversation_id=conversation_id,
        first_message=first_message[:100],
        message_count=len(c.messages),
        last_updated=c.last_accessed,
        messages=display_messages,
        citations=citations
    )

@app.post("/chat/stream")
async def send_message_stream(request: UserRequest):
    """Streams tokens via SSE (Server Sent Events), saves message after completion"""

    # Determine which model to use
    use_local = request.use_local if request.use_local is not None else os.getenv("USE_LOCAL_LLM", default="true").lower() == "true"

    logger.info(f"Received question: {request.user_message[:100]}...")
    logger.debug(f"Using local model: {use_local}")

    # Get or create conversation object
    conversation_id = request.conversation_id
    if not conversation_id:
        # No ID provided
        conversation_id = conversation_manager.create_conversation()
    elif not conversation_manager.get_conversation(conversation_id):
        # ID provided, need to create new conversation
        _ = conversation_manager.create_conversation(conversation_id)

    # Get conversation history for multi-turn support
    conversation_history = conversation_manager.get_messages(conversation_id)

    # Save user message immediately, optimistic
    conversation_manager.add_message(conversation_id, "user", request.user_message)

    async def event_generator():
        generated_response = ""
        try:
            # Fetch top k chunks
            retrieval_start = time.time()
            chunks = semantic_search(request.user_message, request.top_k, request.top_n, request.use_reranker, request.additional_chunks_per_doc)
            # chunks = hybrid_retrieval(request.user_message, conversation_history, request.top_k, request.top_n, request.use_reranker, request.additional_chunks_per_doc)
            retrieval_time = (time.time() - retrieval_start) * 1000
            logger.info(f"Retrieval time: {retrieval_time:.0f}ms")

            yield f"data: {json.dumps({'type': 'start', 'conversation_id': conversation_id})}\n\n"

            # Use 5-minute timeout
            async with asyncio.timeout(300):
                async for chunk in generate_response_stream(request.user_message, chunks, use_local, conversation_history):
                    if chunk["type"] == "token":
                        yield f"data: {json.dumps(chunk)}\n\n"
                    elif chunk["type"] == "end_of_response":
                        generated_response = chunk["full_response"]
                    elif chunk["type"] == "error":
                        raise Exception(chunk["message"])
            
            # Extract and store citations from response (assigns conversation-wide numbers)
            numbered_response_citations = extract_and_store_citations(generated_response, chunks, conversation_id, conversation_manager)

            # Store messages with ORIGINAL [PMC...] format for LLM context
            conversation_manager.add_message(
                conversation_id,
                "assistant",
                generated_response,
                cited_source_ids=[cit.source_id for cit in numbered_response_citations], 
                cited_chunk_ids=[cit.chunk_id for cit in numbered_response_citations]
            )

            yield f"data: {json.dumps({'type': 'complete'})}\n\n"
        
        except asyncio.TimeoutError:
            # Rollback: delete the user message 
            deleted_message = conversation_manager.delete_last_message(conversation_id)
            logger.error(f"Removing latest message: {str(deleted_message)}")
            yield f"data: {json.dumps({'type': 'error', 'message': 'Generation timeout'})}\n\n"
        
        except Exception as e:
            # Rollback: delete the user message 
            deleted_message = conversation_manager.delete_last_message(conversation_id)
            logger.error(f"Removing latest message: {str(deleted_message)}")
            yield f"data: {json.dumps({'type': 'error', 'message': str(e)})}\n\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream")

    


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
        # No ID provided
        conversation_id = conversation_manager.create_conversation()
    elif not conversation_manager.get_conversation(conversation_id):
        # ID provided, need to create new conversation
        _ = conversation_manager.create_conversation(conversation_id)
    
    # Get conversation history for multi-turn support
    conversation_history = conversation_manager.get_messages(conversation_id)

    # Save user message immediately, optimistic
    conversation_manager.add_message(conversation_id, "user", request.user_message)

    try:
        # Fetch top k chunks
        retrieval_start = time.time()
        chunks = semantic_search(request.user_message, request.top_k, request.top_n, request.use_reranker, request.additional_chunks_per_doc)
        # chunks = hybrid_retrieval(request.user_message, conversation_history, request.top_k, request.top_n, request.use_reranker, request.additional_chunks_per_doc)
        retrieval_time = (time.time() - retrieval_start) * 1000
        logger.info(f"Retrieval time: {retrieval_time:.0f}ms")

        # Use RAG pipeline - returns RAGResponse with [PMC...] format
        generation_start = time.time()
        generated_response = generate_response(request.user_message, chunks, use_local, conversation_history)
        generation_time_ms = (time.time() - generation_start) * 1000

        # Extract and store citations from response (assigns conversation-wide numbers)
        numbered_response_citations = extract_and_store_citations(generated_response, chunks, conversation_id, conversation_manager)

        # Store messages with ORIGINAL [PMC...] format for LLM context
        conversation_manager.add_message(
            conversation_id,
            "assistant",
            generated_response,
            cited_source_ids=[cit.source_id for cit in numbered_response_citations], 
            cited_chunk_ids=[cit.chunk_id for cit in numbered_response_citations]
        )

        # Get all conversation-wide citations
        conversation_citations = conversation_manager.get_all_citations(conversation_id)

        # Prepare response text for frontend display only (wrap in list for single message)
        display_response = prepare_messages_for_display(
            [{'role': 'assistant', 'content': generated_response}],
            conversation_id,
            conversation_manager
        )[0]['content']

        logger.info(f"Generated RAG response with {len(numbered_response_citations)} citations in {generation_time_ms:.0f}ms")

        # Return ChatResponse with renumbered text for display
        return ChatResponse(
            user_message=request.user_message,
            generated_response=display_response,
            response_citations=numbered_response_citations,  # Use numbered citations
            conversation_citations=conversation_citations,
            llm_provider="ollama" if use_local else "openai",
            generation_time_ms=generation_time_ms,
            conversation_id=conversation_id
        )

    except Exception as e:
        # Rollback: delete the user message 
        deleted_message = conversation_manager.delete_last_message(conversation_id)
        logger.error(f"Error generating response: {str(e)}", exc_info=True)
        logger.error(f"Removing latest message: {str(deleted_message)}")
        raise HTTPException(status_code=500, detail=f"Error generating response: {str(e)}")

class StreamingMetricsRequest(BaseModel):
    conversation_id: str
    time_to_first_token: int  # milliseconds
    total_tokens: int
    avg_time_per_token: float  # milliseconds
    total_stream_time: int  # milliseconds
    tokens_per_second: float

@app.post("/metrics/streaming")
async def log_streaming_metrics(request: StreamingMetricsRequest):
    """Log streaming performance metrics to separate metrics file"""
    try:
        metrics_logger.info(
            f"conversation_id={request.conversation_id} "
            f"time_to_first_token={request.time_to_first_token}ms "
            f"total_tokens={request.total_tokens} "
            f"avg_time_per_token={request.avg_time_per_token:.1f}ms "
            f"total_stream_time={request.total_stream_time}ms "
            f"tokens_per_second={request.tokens_per_second:.1f}"
        )
        return {"status": "logged"}
    except Exception as e:
        logger.error(f"Error logging streaming metrics: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error logging metrics: {str(e)}")

@app.get("/")
async def root():
    return {"message": "Welcome to OpenPharma API", "docs": "/docs"}