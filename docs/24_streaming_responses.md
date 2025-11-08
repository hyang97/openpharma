# Streaming Responses Design

## Overview

Add Server-Sent Events (SSE) streaming to provide progressive text display as the LLM generates tokens, improving perceived performance.

**Prerequisites:** Understanding of current architecture
- Backend: See `docs/15_rag.md` for generation pipeline, response processing, and heading patterns
- Frontend: See `docs/22_conversation_management.md` for conversation state management

**Design Principles:**
1. Single source of truth (only `/chat/stream` endpoint, no parallel requests)
2. Reuse existing loading state management and refetch patterns
3. Stream continues in background if user switches away
4. Backend filters content between `## Answer` and `## References` markers using standardized patterns
5. Always refetch after streaming for properly formatted messages

## Current Flow (Non-Streaming)

See `docs/15_rag.md` for complete pipeline details.

1. **Retrieval** (endpoint level): `semantic_search()` → top 5 reranked chunks
2. **Generation**: `generate_response()` returns text with `[PMCxxxxxx]` citations, `## Answer` and `## References` headings
3. **Post-processing**: `extract_and_store_citations()` extracts citations from answer section, `prepare_messages_for_display()` strips headings and renumbers `[PMCxxxxxx] → [1]`
4. **Response**: Return formatted text + citations via `/chat` endpoint

## State Management

**States** (reuse existing `loadingConversations` Map):

| State | Display | When |
|-------|---------|------|
| `'loading'` | "● ● ● Thinking..." (standalone) | Before first token OR user switched away |
| `'streaming'` | Streaming text only | User watching tokens arrive |
| `'updating_citations'` | Streamed text + "● ● ● Updating citations..." (at bottom) | Stream done, refetch in progress, user watching |
| `'error'` | Error banner | Generation failed |
| `null` | Final message with `[1]` citations | Complete |

**State Transitions:**

User stays: `'loading' → 'streaming' → 'updating_citations' → null`

User switches away: `'loading'/'streaming' → 'loading' → null`

**Switching Behavior:**
- Switch away during streaming → Change to `'loading'` immediately, stream continues silently
- Switch back while loading → Shows "● ● ● Thinking..."
- Switch back after complete → Instant load from cache

## Backend Implementation

### Streaming Generator (`app/rag/generation.py`)

**Note:** Use standardized heading patterns from `app/rag/response_processing.py`:
- `ANSWER_HEADING_PATTERN` - detects `## Answer` heading
- `REFERENCES_HEADING_PATTERN` - detects `## References` heading

```python
from app.rag.response_processing import ANSWER_HEADING_PATTERN, REFERENCES_HEADING_PATTERN

async def generate_response_stream(
    user_message: str,
    conversation_id: str,
    chunks: List[SearchResult],
    conversation_history: Optional[List[dict]] = None
):
    """
    Async generator that streams response tokens, filtering content between
    ## Answer and ## References markers.

    Yields:
        dict: {"type": "token", "content": "..."}
        dict: {"type": "done", "full_response": "..."}
    """
    # Build messages (reuse existing function)
    messages = build_messages(user_message, chunks, conversation_history)

    # Start Ollama streaming
    client = ollama.Client(host=os.getenv("OLLAMA_BASE_URL", "http://localhost:11434"))
    stream = client.chat(
        model=OLLAMA_MODEL,
        messages=messages,
        stream=True,
        options={'keep_alive': -1}
    )

    # State machine variables
    buffer = ""
    streaming_started = False
    answer_content = ""
    full_response = ""
    token_count = 0

    for chunk in stream:
        # Extract token from Ollama response
        if not chunk.get('message', {}).get('content'):
            continue

        token = chunk['message']['content']
        buffer += token
        full_response += token
        token_count += 1

        # State 1: Waiting for ## Answer heading
        if not streaming_started:
            # Use standardized pattern for consistency
            match = re.search(ANSWER_HEADING_PATTERN, buffer, re.IGNORECASE)
            if match:
                # Found heading, start streaming from after it
                streaming_started = True
                answer_content = buffer[match.end():]
                if answer_content:
                    yield {"type": "token", "content": answer_content}
                buffer = ""
            elif token_count > 100:
                # Fallback: No heading after 100 tokens, start streaming all tokens, yield the full buffer
                streaming_started = True
                yield {"type": "token", "content": buffer}
                answer_content = buffer
                buffer = ""

        # State 2: Streaming (between ## Answer and ## References)
        else:
            answer_content += token

            # Check last 50 chars for ## References (handles multi-token headers)
            check_window = answer_content[-50:] if len(answer_content) > 50 else answer_content
            if re.search(REFERENCES_HEADING_PATTERN, check_window, re.IGNORECASE):
                # Found References marker, stop streaming
                # Strip the ## References part from accumulated content
                answer_content = re.sub(
                    r'\s*##\s*References.*$',
                    '',
                    answer_content,
                    flags=re.IGNORECASE | re.DOTALL
                )
                break
            else:
                # Safe to stream this token
                yield {"type": "token", "content": token}

    # Stream complete, send full response for backend processing
    yield {"type": "done", "full_response": full_response.strip()}
```

### Streaming Endpoint (`app/main.py`)

```python
import asyncio

@app.post("/chat/stream")
async def send_message_stream(request: UserRequest):
    """Streams tokens via SSE, saves message after completion."""
    conversation_id = request.conversation_id or conversation_manager.create_conversation()
    conversation_manager.add_message(conversation_id, "user", request.user_message)

    # Retrieval at endpoint level (same as /chat)
    chunks = semantic_search(
        request.user_message,
        top_k=20,
        top_n=5,
        use_reranker=request.use_reranker
    )

    async def event_generator():
        full_response = ""
        try:
            yield f"data: {json.dumps({'type': 'start', 'conversation_id': conversation_id})}\n\n"

            # Add 3-minute timeout
            async with asyncio.timeout(180):
                async for chunk in generate_response_stream(...):
                    if chunk["type"] == "token":
                        yield f"data: {json.dumps(chunk)}\n\n"
                    elif chunk["type"] == "done":
                        full_response = chunk["full_response"]

            # Extract citations and save (same as /chat endpoint)
            citations = extract_and_store_citations(full_response, chunks, conversation_id)
            conversation_manager.add_message(
                conversation_id,
                "assistant",
                full_response,
                cited_source_ids=[c.source_id for c in citations],
                cited_chunk_ids=[c.chunk_id for c in citations]
            )

            yield f"data: {json.dumps({'type': 'done'})}\n\n"
        except asyncio.TimeoutError:
            conversation_manager.delete_last_message(conversation_id)
            yield f"data: {json.dumps({'type': 'error', 'message': 'Generation timeout'})}\n\n"
        except Exception as e:
            conversation_manager.delete_last_message(conversation_id)
            yield f"data: {json.dumps({'type': 'error', 'message': str(e)})}\n\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream")
```

## Frontend Implementation

### 1. Update `handleSend()` (`ui/src/app/page.tsx`)

**Changes:**
- Add empty assistant message optimistically: `setMessages([...messages, userMsg, { role: 'assistant', content: '' }])`
- Call `startStreaming(conversationId, message)` instead of `/chat` endpoint
- Keep all existing logic (conversation ID, sidebar updates, etc.)

### 2. New `startStreaming()` Function

```typescript
const startStreaming = async (conversationId: string, message: string) => {
  let reader = null
  let timeoutId = null
  try {
    const response = await fetch(`${API_URL}/chat/stream`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ user_message: message, conversation_id: conversationId, use_reranker: true })
    })

    reader = response.body.getReader()
    const decoder = new TextDecoder()
    let streamedContent = ''
    let hasStartedStreaming = false
    let lastTokenTime = Date.now()

    // Timeout if no data received for 60s
    timeoutId = setInterval(() => {
      if (Date.now() - lastTokenTime > 60000) {
        reader?.cancel()
        throw new Error('Stream timeout')
      }
    }, 5000)

    while (true) {
      const { done, value } = await reader.read()
      if (done) break

      const chunk = decoder.decode(value)
      const lines = chunk.split('\n')

      for (const line of lines) {
        if (!line.startsWith('data: ')) continue
        const data = JSON.parse(line.slice(6))

        if (data.type === 'token') {
          streamedContent += data.content
          lastTokenTime = Date.now()

          if (conversationId === currentConversationRef.current) {
            // User watching - switch to streaming, update UI
            if (!hasStartedStreaming) {
              setLoadingConversations(prev => new Map(prev).set(conversationId, 'streaming'))
              hasStartedStreaming = true
            }
            setMessages(prev => {
              const updated = [...prev]
              updated[updated.length - 1] = { role: 'assistant', content: streamedContent }
              return updated
            })
          } else {
            // User switched away - change to loading, continue silently
            if (hasStartedStreaming) {
              setLoadingConversations(prev => new Map(prev).set(conversationId, 'loading'))
              hasStartedStreaming = false
            }
          }
        }

        if (data.type === 'done') {
          // Show "updating citations" if user watching
          if (conversationId === currentConversationRef.current && hasStartedStreaming) {
            setLoadingConversations(prev => new Map(prev).set(conversationId, 'updating_citations'))
          } else {
            setLoadingConversations(prev => new Map(prev).set(conversationId, 'loading'))
          }

          // Refetch conversation (existing pattern)
          const convResponse = await fetch(`${API_URL}/conversations/${conversationId}`)
          const convData = await convResponse.json()

          setConversationCache(prev => new Map(prev).set(conversationId, {
            messages: convData.messages,
            citations: convData.citations
          }))

          if (conversationId === currentConversationRef.current) {
            setMessages(convData.messages)
            setCurrCitations(convData.citations)
          }

          setLoadingConversations(prev => {
            const updated = new Map(prev)
            updated.delete(conversationId)
            return updated
          })

          fetchConversations()
        }

        if (data.type === 'error') {
          throw new Error(data.message)
        }
      }
    }
  } catch (error) {
    console.error('Streaming error:', error)
    setLoadingConversations(prev => new Map(prev).set(conversationId, 'error'))
    setInput(message)  // Restore for retry
  } finally {
    if (timeoutId) clearInterval(timeoutId)
    if (reader) reader.cancel()
  }
}
```

### 3. Update MessageBubble Component

```typescript
// In MessageBubble.tsx
const status = loadingConversations.get(conversationId)

return (
  <div className="message assistant">
    {message.content && <div className="content">{message.content}</div>}

    {status === 'loading' && !message.content && (
      <div className="loading-indicator">
        <span className="dots">●</span>
        <span className="dots">●</span>
        <span className="dots">●</span>
        <span className="ml-2">Thinking...</span>
      </div>
    )}

    {status === 'updating_citations' && message.content && (
      <div className="loading-indicator mt-2">
        <span className="dots">●</span>
        <span className="dots">●</span>
        <span className="dots">●</span>
        <span className="ml-2">Updating citations...</span>
      </div>
    )}
  </div>
)
```

## Edge Cases

1. **LLM doesn't generate headings**: Fallback after 100 tokens, start streaming anyway
2. **Partial header detection**: Sliding window (50 chars) detects `## References` across multiple tokens
3. **Network interruption**: Set to `'error'` state, restore input for retry
4. **False positive `## References`**: Rare, user can retry. Can add newline requirement: `\n\s*##\s*References`

## Implementation Plan

**Phase 1: Backend (2h)**
1. Implement `generate_response_stream()` with buffering state machine
2. Create `/chat/stream` endpoint, reuse existing conversation/chunk logic
3. Test: `curl -N http://localhost:8000/chat/stream -d '{"user_message":"What is diabetes?"}'`

**Phase 2: Frontend (2h)**
1. Extract `startStreaming()` function
2. Update `handleSend()` to call `startStreaming()`
3. Update MessageBubble to handle new states

**Phase 3: Testing (1h)**
1. Query types (short, long, multi-citation)
2. Conversation switching during streaming
3. Error cases (network, timeout)
4. Multi-turn conversations

## Testing Checklist

- [ ] "● ● ● Thinking..." before first token
- [ ] Text streams progressively (no indicator during streaming)
- [ ] "● ● ● Updating citations..." at bottom after stream completes
- [ ] Citations numbered `[1]`, `[2]` after refetch
- [ ] Switch away during streaming → changes to 'loading'
- [ ] Switch back during loading → shows "Thinking..."
- [ ] Switch back after complete → instant from cache
- [ ] Error state + input restoration
- [ ] Sidebar updates preserved
- [ ] Mobile responsive

## Summary

**New Code:**
- Backend: ~100 lines (streaming generator + endpoint)
- Frontend: ~80 lines (streaming handler + MessageBubble updates)
- **Total: ~180 lines**

**Reused:** All existing conversation management, caching, error handling, validation, sidebar updates

**Backward Compatibility:** Keep `/chat` endpoint for fallback during Phase 1, deprecate after confidence
