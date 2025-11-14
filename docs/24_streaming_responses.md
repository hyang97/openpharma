# Streaming Responses

## Overview

Server-Sent Events (SSE) streaming implementation for progressive token display during LLM generation.

**Status**: ✅ Complete (implemented Nov 13, 2025)

---

## Architecture

### Backend (FastAPI + SSE)

**Endpoint**: `POST /chat/stream`

**Flow**:
1. Receives user message, performs retrieval
2. Calls `generate_response_stream()` generator
3. Yields SSE events: `data: {json}\n\n`
4. Event types: `token`, `complete`, `error`

**Token Filtering** (`app/rag/generation.py:103-202`):
- State machine with lookahead buffering
- Waits 3 tokens after matching `## Answer` heading before streaming (captures `: \n` tokens)
- 5-token lookahead to detect `## References` heading and stop streaming
- Fallback: starts streaming after 100 tokens if no heading found

### Frontend (React + SSE)

**Implementation**: `ui/src/hooks/useChat.ts:37-175`

**State Flow**:
```
Send message → 'loading' → First token → 'streaming' →
Complete → 'updating_citations' → Refetch → null (done)
```

**Key Features**:
1. **Progressive Display** - `streamResponse()` parses SSE, updates last assistant message on each token
2. **Background Streaming** - Stream continues if user switches away, resumes display if switched back
3. **Metrics Tracking** - Time to first token, tokens/sec, avg inter-token time
4. **Error Handling** - 2-min timeout, rolls back user + assistant messages, restores input
5. **Refetch** - Always refetches after streaming for proper citation formatting (`[PMCxxxxx]` → `[1]`)

---

## UX Enhancements

### Visual Indicators

**Blinking Cursor** (`ui/src/components/MessageBubble.tsx:91-93`):
- Shows at end of assistant message during streaming
- Uses `animate-pulse` for blink effect

**Formatting Citations Indicator** (`ui/src/components/MessageList.tsx:85-96`):
- Animated dots + "Formatting citations..." text
- Shows after streaming completes, before refetch finishes

**Dimmed PMC Citations** (`ui/src/components/MessageBubble.tsx:14-26`):
- Raw `[PMCxxxxxx]` citations shown with `opacity-50` during streaming
- Become clickable numbered `[1]`, `[2]` after refetch

### Auto-Scroll Behavior (`ui/src/components/MessageList.tsx:16-22`)

**During streaming**: No auto-scroll (user can freely scroll to read)
**After streaming**: Resumes auto-scroll for next message

---

## Performance Metrics

**Logged to**: `logs/streaming_metrics.log`

**Tracked Metrics**:
- Time to first token (ms) - Request to first token received
- Total tokens
- Average time per token (ms)
- Total stream time (ms)
- Tokens per second

**Implementation**:
- Frontend tracks timing (`ui/src/hooks/useChat.ts:42-46, 95-103, 142-167`)
- POST to `/metrics/streaming` when complete
- Backend logs to dedicated file (`app/main.py:294-309`)

---

## Design Decisions

### Why SSE over WebSockets?
- Simpler: HTTP-based, no connection management
- Sufficient: One-way streaming (server → client)
- Compatible: Works with existing FastAPI patterns

### Why Refetch After Streaming?
- Backend response processing formats citations for display
- Streaming sends raw `[PMCxxxxxx]`, backend converts to numbered `[1]`, `[2]`
- Ensures consistency with non-streaming mode

### Why No Auto-Scroll During Streaming?
- Matches standard chat UX (ChatGPT, Claude, etc.)
- Allows user to scroll up to read citations mid-generation
- Prevents jarring scroll interruptions

### Why Empty Assistant Message?
- Needed as placeholder for streaming updates (`setMessages` updates last message)
- Filtered from render (MessageList skips empty assistant messages)
- Only added to display state, not cache (cache only has user message until stream completes)

---

## Edge Cases Handled

1. **User switches away during streaming** → Stream continues silently, state set to 'loading'
2. **User switches back during streaming** → Adds empty assistant message, resumes display
3. **Stream timeout (2 min)** → Rolls back both messages, restores input
4. **Network error** → Same rollback flow
5. **LLM doesn't generate headings** → Starts streaming after 100 tokens

---

## Files Changed

**Backend**:
- `app/main.py` - `/chat/stream` endpoint, `/metrics/streaming` endpoint
- `app/rag/generation.py` - `generate_response_stream()` generator with lookahead buffering

**Frontend**:
- `ui/src/hooks/useChat.ts` - `streamResponse()` helper, metrics tracking
- `ui/src/components/MessageBubble.tsx` - Blinking cursor, dimmed PMC citations
- `ui/src/components/MessageList.tsx` - Formatting indicator, auto-scroll behavior
- `ui/src/app/page.tsx` - Pass streaming state props

---

## Configuration

**Enable/Disable**: `ui/src/app/page.tsx:18`
```typescript
const chat = useChat(API_URL, true)  // true = streaming, false = standard
```

**Timeout**: `ui/src/hooks/useChat.ts:64`
```typescript
if (Date.now() - lastTokenTime > 2 * 60 * 1000)  // 2 minutes
```
