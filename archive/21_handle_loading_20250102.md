# Conversation Switching and Loading State Design

## Overview

Solves the race condition bug where switching conversations during an API request causes response contamination.

**Problem:** User sends message in Conv A, switches to Conv B while Conv A is generating (18-60s), sees Conv A's response in Conv B.

**Solution:** Non-blocking async operations with client-side caching and synchronous state checks.

---

## Architecture Decisions

### Backend Concurrency Limitation (Phase 1)
The `/chat` endpoint blocks during LLM generation due to synchronous Ollama calls, preventing concurrent request processing. This is acceptable for Phase 1 and will be addressed in Phase 2 with async implementation (httpx.AsyncClient or ThreadPoolExecutor).

### Frontend Strategy
- **Non-blocking operations:** `.then()` chains instead of `async/await` to allow conversation switching during generation
- **Client-side caching:** Instant switching for previously-viewed conversations
- **Synchronous state checks:** `useRef` to validate conversation ID in async callbacks
- **Optimistic updates:** User messages and sidebar updates appear immediately

---

## Implementation

### Backend Changes

**File:** `app/main.py`
- Save user message immediately before RAG generation
- Rollback on error using `delete_last_message()` in ConversationManager
- Accept optional client-provided conversation IDs

**File:** `app/rag/conversation_manager.py`
- `delete_last_message()` method for error rollback
- `create_conversation()` accepts optional UUID from client

### Frontend Changes

**File:** `ui/src/app/page.tsx`

**State Management:**
- `loadingConversations: Map<string, 'loading' | 'error'>` - Per-conversation status tracking
- `currConversationId` + `currentConversationRef` - State and ref kept synchronized for async validation
- `conversationCache: Map<string, {messages, citations}>` - Client-side cache for instant switching
- `isFetchingConversation: boolean` - Indicates conversation data fetch in progress (separate from LLM generation)

**Key Functions:**

1. **handleSend()** - Non-blocking message sending
   - Uses `.then()` chains instead of `await`
   - Validates `requestConversationId === currentConversationRef.current` before applying response
   - Updates cache after successful generation
   - Generates client-side UUIDs for new conversations

2. **handleResumeConversation()** - Instant conversation switching
   - Updates `currConversationId` and `currentConversationRef` immediately
   - Shows cached data if available (instant)
   - Shows skeleton loading if not cached
   - Fetches fresh data in background and updates cache
   - Only updates UI if `conversationId === currentConversationRef.current`

3. **handleReturnHome()** - Returns to landing page
   - Clears both state and ref

**File:** `ui/src/components/MessageList.tsx`
- Skeleton loading placeholders for cache misses (2 animated bubbles with shimmer)
- Bouncing dots indicator: "● ● ● Loading conversation..."
- Auto-scroll to bottom on message updates (`useEffect` with `scrollIntoView`)

**File:** `ui/src/components/ChatInput.tsx`
- Disabled when `isLoading || isFetchingConversation`

**File:** `ui/src/app/page.tsx` (render logic)
- Landing page shown when: `messages.length === 0 && !currConversationId`
- Message view shown when: conversation selected (even if empty/loading)

---

## Key Behaviors

### Race Condition Prevention
- `currentConversationRef` provides immediate (synchronous) access to latest conversation ID
- Async responses validated against ref before updating UI
- `.then()` chains allow non-blocking conversation switching

### Client-Side Caching
- **Cache hit:** Instant display, background refresh for accuracy
- **Cache miss:** Skeleton loading with bouncing dots, disabled input
- Cache cleared on page refresh
- Cache updated after generation and after fetching conversations

### Per-Conversation Status Tracking
- Independent status per conversation: 'loading', 'error', or null (idle)
- Status persists across switches
- Error banner shown when switching back to errored conversation

### Error Handling
- Backend rolls back user message on error
- Frontend marks conversation as 'error' and restores input
- Error banner dismissible, allows retry

### UX Enhancements
- Input disabled during fetch or generation
- Auto-scroll to bottom on message updates
- Skeleton loading for cache misses (animated shimmer)
- Optimistic sidebar updates for new conversations

---

## Edge Cases Handled

1. **First message:** `null → uuid` transition, optimistic sidebar update
2. **Rapid switching:** Ref validation prevents out-of-order updates
3. **Error during generation:** Rollback on backend, restore input on frontend
4. **Switch during fetch:** Fetch completes but doesn't update UI (ID check fails)
5. **Browser refresh:** Cache cleared, returns to landing page
6. **Multiple concurrent generations:** Independent status tracking per conversation
7. **Cache miss during backend blocking:** Shows skeleton loading, user can switch back to loading conversation

---

## Testing Scenarios

1. **Main bug fix:** Send in Conv A, switch to Conv B during generation → Conv B shows correct messages
2. **Cache hit:** Switch between previously-viewed conversations → Instant switching
3. **Cache miss:** Switch to uncached conversation → Skeleton loading, then messages appear
4. **Error handling:** Backend error during generation → Error banner, input restored
5. **Auto-scroll:** Long conversations scroll to bottom on updates
6. **Input disabled:** Cannot send while fetching or generating

---

## Phase 2 Improvements

- Implement async backend with httpx.AsyncClient or ThreadPoolExecutor
- Consider React Query for advanced caching and invalidation
- Refactor page.tsx to extract conversation management logic
- Add cache invalidation strategy (TTL, manual refresh)
- Implement optimistic cache updates for real-time collaboration
