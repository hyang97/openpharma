"""
LLM-based generation for OpenPharma RAG system.

Takes search results and generates synthesized answers with citations.
"""
from fastapi import HTTPException
from typing import List, Optional
import time, os, re, asyncio
import ollama, anthropic

from app.models import SearchResult
from app.logging_config import get_logger
from app.rag.response_processing import ANSWER_HEADING_PATTERN, REFERENCES_HEADING_PATTERN

logger = get_logger(__name__)

# Model configuration
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "llama3.1:8b")
ANTHROPIC_MODEL = os.getenv("ANTHROPIC_MODEL", "claude-3-haiku-20240307")

# Gemini fallback model chain
GEMINI_MODEL_CHAIN = [
    os.getenv("GEMINI_MODEL", "gemini-3.7-flash"),
    "gemini-3.5-flash-lite",
    "gemini-3.1-flash-lite-preview",
]
# Deduplicate while preserving order
GEMINI_MODEL_CHAIN = list(dict.fromkeys(GEMINI_MODEL_CHAIN))

# Number of tokens to lookahead for ## References
LOOKAHEAD_LENGTH = 5

# System prompt for RAG generation
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

def _extract_system_message(messages: List[dict]) -> tuple[str, List[dict]]:
    """For Anthropic API, extract system messages from message list"""
    system_message = ""
    chat_messages = []
    for msg in messages:
        if msg['role'] == 'system':
            system_message = msg['content']
        else:
            chat_messages.append(msg)
    return system_message, chat_messages


def _format_gemini_contents(messages: List[dict]) -> tuple[str, list]:
    """For Gemini API, extract system instruction and format chat contents."""
    system_instruction = SYSTEM_PROMPT
    contents = []
    for msg in messages:
        if msg['role'] == 'system':
            system_instruction = msg['content']
        else:
            role = "user" if msg['role'] == 'user' else "model"
            contents.append({"role": role, "parts": [{"text": msg['content']}]})
    return system_instruction, contents



def build_messages(user_message: str, chunks: list[SearchResult], conversation_history: Optional[List[dict]]) -> List[dict]:
    """Build RAG prompt with user message, context, and literature chunks."""
    messages = []
    messages.append({'role': 'system', 'content': SYSTEM_PROMPT})

    # Add conversation history, filtering out cited_source_ids (not part of Ollama API)
    if conversation_history:
        for msg in conversation_history:
            messages.append({
                'role': msg['role'],
                'content': msg['content']
            })

    # Old prompt (when using hybrid_retrieval with historical citations)
    # current_message = f"<Literature>\nBelow are the top {len(chunks)} most relevant literature passages to the user's query, as well as recently cited literature. Each passage starts with a unique [source_id].\n"
    
    current_message = f"<Literature>\nBelow are the top {len(chunks)} most relevant literature passages to the user's query. Each passage starts with a unique [source_id].\n"
    
    # Use top n chunks in context, no re-ranking
    # Add to prompt with numbered chunks, formatted for inline citations [x]
    for idx, chunk in enumerate(chunks, 1):
        # Strip paper reference numbers to prevent LLM from copying them into response
        # Matches: [1], [2,3], [3-5], [6-11], [1,3-5,8]
        cleaned_content = re.sub(r'\[[\d,\s\-]+\]', '', chunk.content)
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
    """
    Response text generator that streams response tokens, filtering content by ## Answer and ## References
    
    Yields:
        dict: {"type": "token", "content": "..."}
        dict: {"type": "end_of_response", "full_response": "..."}
    """

    # Build messages
    messages = build_messages(user_message, chunks, conversation_history)

    # Async token stream generator
    async def token_iter():
        if use_local:
            client = ollama.Client(host=os.getenv("OLLAMA_BASE_URL", "http://localhost:11434"))
            raw_stream = client.chat(model=OLLAMA_MODEL, messages=messages, stream=True, options={'keep_alive': -1})
            for chunk in raw_stream:
                token = chunk.message.content
                if token:
                    yield token
            return

        # Remote LLM streaming: Gemini -> Anthropic -> Ollama fallback
        gemini_api_key = os.getenv("GEMINI_API_KEY")
        if gemini_api_key:
            try:
                from google import genai
                from google.genai import types

                client = genai.Client(api_key=gemini_api_key)
                system_instruction, contents = _format_gemini_contents(messages)
                config = types.GenerateContentConfig(
                    system_instruction=system_instruction,
                    max_output_tokens=4096,
                )

                for model_name in GEMINI_MODEL_CHAIN:
                    try:
                        logger.info(f"Streaming with Gemini model: {model_name}")
                        stream = await client.aio.models.generate_content_stream(
                            model=model_name,
                            contents=contents,
                            config=config,
                        )
                        # 8-second fail-fast check on first token to accommodate cold connection while preventing server queue hangs
                        first_chunk = await asyncio.wait_for(stream.__anext__(), timeout=8.0)
                        if first_chunk.text:
                            yield first_chunk.text
                        async for chunk in stream:
                            if chunk.text:
                                yield chunk.text
                        return
                    except Exception as model_err:
                        logger.warning(f"Gemini model {model_name} streaming failed or timed out: {model_err}")
            except Exception as e:
                logger.warning(f"Gemini client initialization failed: {e}")

        # Anthropic fallback
        anthropic_key = os.getenv("ANTHROPIC_API_KEY")
        if anthropic_key:
            try:
                client = anthropic.Anthropic(api_key=anthropic_key)
                system_prompt, chat_messages = _extract_system_message(messages)
                with client.messages.stream(
                    model=ANTHROPIC_MODEL,
                    max_tokens=4096,
                    system=system_prompt,
                    messages=chat_messages
                ) as stream:
                    for text in stream.text_stream:
                        yield text
                return
            except Exception as e:
                logger.warning(f"Anthropic API failed, falling back to Ollama: {e}")

        # Local Ollama fallback
        client = ollama.Client(host=os.getenv("OLLAMA_BASE_URL", "http://localhost:11434"))
        raw_stream = client.chat(model=OLLAMA_MODEL, messages=messages, stream=True, options={'keep_alive': -1})
        for chunk in raw_stream:
            token = chunk.message.content
            if token:
                yield token

    # Stores initial tokens in string, waiting to hit ## Answer
    preamble_buffer = ""

    # Stores tokens in list to look ahead for ## References
    lookahead_buffer = []
    
    streaming_started = False 
    references_in_buffer = False
    answer_content = ""
    full_response = ""
    token_count = 0

    async for token in token_iter():
        
        preamble_buffer += token 
        full_response += token 
        token_count += 1

        # State 1: Not streaming yet, add to preamble, waiting for ## Answer heading
        if not streaming_started:
            match = re.search(ANSWER_HEADING_PATTERN, preamble_buffer, re.IGNORECASE)

            if match:
                # Found ## Answer, wait for 3 more tokens after match to capture colon/newline
                tokens_after_match = len(preamble_buffer) - match.end()
                if tokens_after_match >= 3:
                    streaming_started = True
                    answer_content = preamble_buffer[match.end():].lstrip(': \n')  # Strip leading colon, space, newline
                    if answer_content:
                        lookahead_buffer.append(answer_content)

            elif token_count > 100:
                # No header found, but it's been 100 tokens, yield full preamble and start streaming anyway
                streaming_started = True 
                answer_content = preamble_buffer 
                lookahead_buffer.append(answer_content)
        
        # State 2: Currently streaming, keep a 5-token lookahead to detect ## References to stop
        else:
            answer_content += token 
            lookahead_buffer.append(token)

            # Check if ## References is in the lookahead buffer
            lookahead_text = ''.join(lookahead_buffer)
            if re.search(REFERENCES_HEADING_PATTERN, lookahead_text, re.IGNORECASE):
                references_in_buffer = True

                # Yield text before ## References
                text_before_references = re.sub(
                    REFERENCES_HEADING_PATTERN + r'.*$', # Match ## References and everything after 
                    '', # Replace with empty string 
                    lookahead_text,
                    flags=re.IGNORECASE | re.DOTALL
                ).rstrip()

                if text_before_references:
                    yield {"type": "token", "content": text_before_references}
                break

            while len(lookahead_buffer) > LOOKAHEAD_LENGTH:
                safe_token = lookahead_buffer.pop(0)
                yield {"type": "token", "content": safe_token}
        
    
    # If we ended without references, flush remaining tokens in lookahead buffer. Need to do this to avoid losing last 5 tokens
    if not references_in_buffer:
        for token in lookahead_buffer:
            yield {"type": "token", "content": token}

    # Stream complete, send full response for backend processing 
    yield {"type": "end_of_response", "full_response": full_response.strip()}



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

    # Call LLM (try Gemini first, then Anthropic, then fall back to Ollama)
    if not use_local:
        gemini_api_key = os.getenv("GEMINI_API_KEY")
        if gemini_api_key:
            try:
                from google import genai
                from google.genai import types

                client = genai.Client(
                    api_key=gemini_api_key,
                    http_options=types.HttpOptions(
                        retry_options=types.HttpRetryOptions(attempts=1),
                    ),
                )
                system_instruction, contents = _format_gemini_contents(messages)
                config = types.GenerateContentConfig(
                    system_instruction=system_instruction,
                    max_output_tokens=4096,
                )

                for model_name in GEMINI_MODEL_CHAIN:
                    try:
                        llm_start = time.time()
                        logger.info(f"Using Gemini model: {model_name}")
                        response = client.models.generate_content(
                            model=model_name,
                            contents=contents,
                            config=config,
                        )
                        llm_time = (time.time() - llm_start) * 1000
                        logger.info(f"Gemini LLM generation time ({model_name}): {llm_time:.0f}ms")
                        if response.text:
                            return response.text
                    except Exception as model_err:
                        logger.warning(f"Gemini model {model_name} failed: {model_err}")
            except Exception as e:
                logger.warning(f"Gemini client initialization failed: {e}")

        anthropic_key = os.getenv("ANTHROPIC_API_KEY")
        if anthropic_key:
            try:
                llm_start = time.time()
                logger.info(f"Using Anthropic model: {ANTHROPIC_MODEL}")
                client = anthropic.Anthropic(api_key=anthropic_key)
                system_prompt, chat_messages = _extract_system_message(messages)
                response = client.messages.create(
                    model=ANTHROPIC_MODEL,
                    max_tokens=4096,
                    system=system_prompt,
                    messages=chat_messages,
                )
                llm_time = (time.time() - llm_start) * 1000
                logger.info(f"LLM generation time: {llm_time:.0f}ms")
                return response.content[0].text
            except Exception as e:
                logger.warning(f"Anthropic API failed, falling back to Ollama: {e}")

    try:
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
        return response.message.content
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
