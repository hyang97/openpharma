from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import os
import ollama
from typing import Optional
from .db.database import get_db
from .logging_config import setup_logging, get_logger

# Configure logging on startup
setup_logging(
    level=os.getenv("LOG_LEVEL", "INFO"),
    log_file="logs/openpharma.log"
)

logger = get_logger(__name__)

app = FastAPI(title="OpenPharma API", version="0.1.0")

@app.on_event("startup")
async def startup_event():
    logger.info("Starting OpenPharma API")
    logger.info(f"Using local LLM: {os.getenv('USE_LOCAL_LLM', 'true')}")

@app.on_event("shutdown")
async def shutdown_event():
    logger.info("Shutting down OpenPharma API")

class QuestionRequest(BaseModel):
    question: str
    use_local: Optional[bool] = None # allows use_local (boolean type) to be optional parameter. default value is None, meaning "i don't care, use environment variable"

class QuestionResponse(BaseModel):
    answer: str
    model_used: str

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy", "message": "OpenPharma API is running"}

@app.post("/ask", response_model=QuestionResponse)
async def ask_question(request: QuestionRequest):
    """Ask a question and get an AI response"""

    # Determine which model to use
    use_local = request.use_local if request.use_local is not None else os.getenv("USE_LOCAL_LLM", default="true").lower() == "true"

    logger.info(f"Received question: {request.question[:100]}...")
    logger.debug(f"Using local model: {use_local}")

    try:
        if use_local:
            # Use local Ollama
            client = ollama.Client(host=os.getenv("OLLAMA_BASE_URL", default="http://localhost:11434"))
            response = client.chat(
                model='llama3.1:8b',
                messages=[{
                    'role': 'user',
                    'content': f"You are a research assistant specializing in pharmaceutical and medical research. Please answer this question: {request.question}"
                }]
            )
            answer = response['message']['content']
            model_used = "llama3.1:8b (local)"
            logger.info(f"Generated response using {model_used}")
        else:
            # TODO: Add OpenAI integration later
            logger.warning("OpenAI integration requested but not implemented")
            raise HTTPException(status_code=501, detail="OpenAI integration not yet implemented")

        return QuestionResponse(answer=answer, model_used=model_used)

    except Exception as e:
        logger.error(f"Error generating response: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error generating response: {str(e)}")

@app.get("/")
async def root():
    return {"message": "Welcome to OpenPharma API", "docs": "/docs"}