# Streaming Responses Design

## Overview

Add Server-Sent Events (SSE) streaming to provide progressive text display as the LLM generates tokens, improving perceived performance.

**Design Principles:**
1. Single source of truth (only `/chat/stream` endpoint, no parallel requests)
2. Reuse existing loading state management and refetch patterns
3. Stream continues in background if user switches away
4. Backend filters content between `## Answer` and `## References` markers
5. Always refetch after streaming for properly formatted messages

## Current Flow (Non-Streaming)

1. Retrieval: Semantic search → rerank
2. Generation: LLM generates with `[PMCxxxxxx]` citations, `## Answer` and `## References` headings
3. Post-processing: Extract citations, strip headings, renumber `[PMCxxxxxx] → [1]`
4. Response: Return formatted text + citations

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

### 1. Streaming Generator (`app/rag/generation.py`)

```python
async def generate_response_stream(...):
    """
    Buffers tokens until ## Answer detected, streams until ## References detected.
    Yields: {"type": "token", "content": "..."} or {"type": "done", "full_response": "..."}
    """
    buffer = ""
    streaming_started = False
    answer_content = ""
    full_response = ""

    for chunk in ollama_stream:
        token = chunk['message']['content']
        buffer += token
        full_response += token

        if not streaming_started:
            match = re.search(r'##\s*Answer\s*:?\s*\n?', buffer, re.IGNORECASE)
            if match:
                streaming_started = True
                answer_content = buffer[match.end():]
                if answer_content:
                    yield {"type": "token", "content": answer_content}
                buffer = ""
        else:
            answer_content += token
            check_window = answer_content[-50:]
            if re.search(r'##\s*References', check_window, re.IGNORECASE):
                answer_content = re.sub(r'\s*##\s*References.*$', '', answer_content, flags=re.IGNORECASE | re.DOTALL)
                break
            else:
                yield {"type": "token", "content": token}

    yield {"type": "done", "full_response": full_response.strip()}
```

**Fallback:** If no `## Answer` after 100 tokens, start streaming anyway.

### 2. Streaming Endpoint (`app/main.py`)

```python
@app.post("/chat/stream")
async def send_message_stream(request: UserRequest):
    """Streams tokens via SSE, saves message after completion."""
    conversation_id = request.conversation_id or conversation_manager.create_conversation()
    conversation_manager.add_message(conversation_id, "user", request.user_message)
    chunks = semantic_search(...)

    async def event_generator():
        full_response = ""
        try:
            yield f"data: {json.dumps({'type': 'start', 'conversation_id': conversation_id})}\n\n"

            async for chunk in generate_response_stream(...):
                if chunk["type"] == "token":
                    yield f"data: {json.dumps(chunk)}\n\n"
                elif chunk["type"] == "done":
                    full_response = chunk["full_response"]

            # Extract citations and save (same as /chat endpoint)
            citations = extract_and_store_citations(...)
            conversation_manager.add_message(conversation_id, "assistant", full_response, ...)

            yield f"data: {json.dumps({'type': 'done'})}\n\n"
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
  try {
    const response = await fetch(`${API_URL}/chat/stream`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ user_message: message, conversation_id: conversationId, use_reranker: true })
    })

    const reader = response.body.getReader()
    const decoder = new TextDecoder()
    let streamedContent = ''
    let hasStartedStreaming = false

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
