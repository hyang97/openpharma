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

**Architecture**: Two-state FSM with lookahead buffering to prevent streaming `## References` section.

**State Machine:**
- **State 1 (Preamble)**: Buffer tokens until `## Answer` heading detected (or 100-token fallback)
- **State 2 (Streaming)**: Yield tokens with 5-token lookahead to detect `## References` before streaming it

**Key Design Decisions:**

1. **Lookahead Buffer (5 tokens)**:
   - `## References` is 2-3 tokens in Llama 3.1 (tested: `'##'` → `' References'` → `':'`)
   - 5-token lookahead provides safety margin for other tokenizers (GPT-4, Claude)
   - Trade-off: ~250ms initial latency (imperceptible) vs preventing reference section leakage

2. **Preamble Handling**:
   - State 1 accumulates tokens as a string until heading found
   - Seeds lookahead buffer with content after `## Answer` (prevents streaming gap)
   - Fallback at 100 tokens if no heading (handles non-standard LLM responses)

3. **References Detection**:
   - Search full lookahead buffer (joined string) for `REFERENCES_HEADING_PATTERN`
   - When detected: Strip pattern, yield clean text, break (discards buffered tokens)
   - When stream ends naturally: Flush remaining buffer (last 5 tokens)

4. **Pattern Reuse**:
   - Import `ANSWER_HEADING_PATTERN` and `REFERENCES_HEADING_PATTERN` from `response_processing.py`
   - Ensures consistency with non-streaming citation extraction

**Implementation**: See `app/rag/generation.py:103-192` for full generator code.

### Streaming Endpoint (`app/main.py`)

**Architecture**: SSE endpoint that coordinates retrieval, streaming generation, and post-processing.

**Event Flow:**
1. **Setup**: Create/retrieve conversation, add user message optimistically
2. **Retrieval**: Semantic search (same as non-streaming endpoint)
3. **Start Event**: Send `{"type": "start", "conversation_id": "..."}` to client
4. **Streaming**: Iterate over `generate_response_stream()`, forward token events to client
5. **Post-processing**: Extract citations, save message with metadata
6. **Done Event**: Send `{"type": "done"}` to signal completion

**Error Handling:**
- All exceptions caught in `event_generator()` → Send `{"type": "error"}` event (no HTTPException)
- Rollback: Delete user message via `conversation_manager.delete_last_message()`
- Timeout: 5 minutes (300s) via `asyncio.timeout()`

**SSE Event Types:**
- `start` - Conversation ID for client tracking
- `token` - Individual token/word with raw `[PMCxxxxxx]` citations
- `done` - Stream complete, trigger frontend refetch for formatted messages
- `error` - Generation failed, includes error message

**Key Design Choice**: Return `StreamingResponse` (not `ChatResponse`), media type `text/event-stream`

**Implementation**: See `app/main.py:119-190` for full endpoint code.

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
