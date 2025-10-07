from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import os
import ollama
from typing import Optional

app = FastAPI(title="OpenPharma API", version="0.1.0")

class QuestionRequest(BaseModel):
    question: str
    use_local: Optional[bool] = None

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
    use_local = request.use_local if request.use_local is not None else os.getenv("USE_LOCAL_LLM", "true").lower() == "true"

    try:
        if use_local:
            # Use local Ollama
            client = ollama.Client(host=os.getenv("OLLAMA_BASE_URL", "http://localhost:11434"))
            response = client.chat(
                model='llama3.1:8b',
                messages=[{
                    'role': 'user',
                    'content': f"You are a research assistant specializing in pharmaceutical and medical research. Please answer this question: {request.question}"
                }]
            )
            answer = response['message']['content']
            model_used = "llama3.1:8b (local)"
        else:
            # TODO: Add OpenAI integration later
            raise HTTPException(status_code=501, detail="OpenAI integration not yet implemented")

        return QuestionResponse(answer=answer, model_used=model_used)

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error generating response: {str(e)}")

@app.get("/")
async def root():
    return {"message": "Welcome to OpenPharma API", "docs": "/docs"}