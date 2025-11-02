# Conversation Management

## Overview

Multi-turn conversation system with client-side caching, instant switching, and race condition prevention.

**Key Features:**
- Multiple concurrent conversations
- Conversation history persistence (backend in-memory)
- Instant switching between conversations
- Loading state management per conversation
- Error handling with retry

---

## Conversation Lifecycle

### 1. Create Conversation

**Trigger:** User sends first message

**Flow:**
1. Client generates UUID (`crypto.randomUUID()`)
2. Client optimistically:
   - Sets `currConversationId` to UUID
   - Adds conversation to sidebar with first message preview
3. Backend creates conversation with client-provided UUID
4. Backend saves user message
5. Backend generates response
6. Client caches conversation data

**Why client-generated UUIDs:**
- Enables optimistic updates (sidebar shows immediately)
- Avoids round-trip for UUID generation
- Backend remains stateless

### 2. Resume Conversation

**Trigger:** User clicks conversation in sidebar

**Flow:**
1. Check client-side cache
   - **Cache hit:** Show messages instantly, fetch fresh data in background
   - **Cache miss:** Show skeleton loading, fetch data
2. Update `currConversationId` and `currentConversationRef`
3. Fetch conversation from backend
4. Update cache with fresh data
5. Display messages and citations

**Cache behavior:**
- In-memory Map, cleared on page refresh
- Updated after generation and after fetching
- No TTL, no manual invalidation (always fresh from backend)

### 3. Continue Conversation

**Trigger:** User sends message in existing conversation

**Flow:**
1. Add user message optimistically to UI
2. Backend saves user message immediately
3. Backend generates response (18-60s)
4. If error: Backend rolls back user message, frontend restores input
5. If success: Client refetches conversation, updates cache
6. Display new message and any new citations

### 4. Switch During Generation

**Trigger:** User switches conversation while LLM is generating

**Flow:**
1. Update `currConversationId` and `currentConversationRef` immediately
2. Show new conversation (from cache or skeleton)
3. Original conversation continues generating in background
4. When response arrives, validate `requestConversationId === currentConversationRef.current`
5. If validation fails: Don't update UI, just update cache
6. User can switch back to see completed response

**Race condition prevention:**
- `useRef` provides synchronous conversation ID
- Responses validated before applying to UI
- Non-blocking `.then()` chains allow switching without waiting

---

## Loading States

### Per-Conversation Status Tracking

**State:** `loadingConversations: Map<string, 'loading' | 'error'>`

**Status Types:**
- `'loading'` - LLM generating response
- `'error'` - Generation failed
- `null` (not in map) - Idle

**Derived Values:**
```typescript
isLoading = currConversationId && loadingConversations.get(currConversationId) === 'loading'
hasError = currConversationId && loadingConversations.get(currConversationId) === 'error'
```

### Fetching State

**State:** `isFetchingConversation: boolean`

**Purpose:** Separate from generation loading - indicates fetching existing conversation data

**When true:**
- Cache miss in `handleResumeConversation`
- Shows skeleton loading
- Disables input

**When false:**
- Cache hit (instant display)
- Fetch complete

### UI Loading Indicators

**LLM Generating (`isLoading`):**
- "● ● ● Thinking..." with bouncing dots
- Gray assistant message bubble
- Input disabled

**Fetching Conversation (`isFetchingConversation`):**
- "● ● ● Loading conversation..." with bouncing dots
- Skeleton placeholders (2 message bubbles with shimmer)
- Input disabled

---

## Conversation Switching

### Instant Switching (Cache Hit)

**Scenario:** User switches to previously-viewed conversation

**Experience:**
1. Click conversation → Instant display (< 50ms perceived)
2. Background refresh fetches fresh data
3. Usually no visible change (data rarely stale)

**Implementation:**
```typescript
const cached = conversationCache.get(conversationId)
if (cached) {
  setMessages(cached.messages)       // Instant
  setCurrCitations(cached.citations)  // Instant
}
// Then fetch fresh data in background
```

### Loading Switch (Cache Miss)

**Scenario:** User switches to uncached conversation (first time or after refresh)

**Experience:**
1. Click conversation → Immediate feedback (ID updates)
2. Skeleton loading appears (animated shimmer)
3. Backend responds (delay due to blocking - see below)
4. Messages appear

**Backend Limitation (Phase 1):**
- Backend blocks during LLM generation (synchronous Ollama calls)
- If Conv A is generating, fetching Conv B is delayed
- Solution: Client-side caching minimizes cache misses
- Phase 2: Async backend with httpx.AsyncClient

### Switching During Generation

**Scenario:** Conv A generating, user switches to Conv B

**What happens:**
1. User in Conv A, sends message
2. Conv A marked as 'loading'
3. User switches to Conv B → Instant (cached) or skeleton (uncached)
4. Conv A continues generating in background
5. When Conv A completes:
   - Sidebar updates (message count increases)
   - Cache updates
   - UI doesn't change (user on Conv B)
6. User can switch back to Conv A to see response

**Race condition prevention:**
```typescript
// In handleSend's .then() chain
if (requestConversationId !== currentConversationRef.current) {
  // User switched away, don't update UI
  fetchConversations()  // Update sidebar only
  return
}
// Safe to update UI
setMessages(convData.messages)
```

---

## Error Handling

### Generation Error

**Trigger:** Backend error during LLM generation

**Backend behavior:**
1. Save user message immediately (before generation)
2. Try to generate response
3. If error: Delete last message (`delete_last_message()`)
4. Return 500 error

**Frontend behavior:**
1. Mark conversation as 'error' in Map
2. Restore user's input (for retry)
3. Show error banner (dismissible)
4. Keep error status until dismissed or retry succeeds

**Error banner:**
- Fixed position below header
- Red background (`red-900`)
- Message: "Previous message failed to send. Please try again."
- Dismiss button (×)

### Network Error

**Same as generation error** - handled by `.catch()` in fetch chain

### Error in Background Conversation

**Scenario:** Error occurs in Conv A while user is on Conv B

**Behavior:**
1. Conv A marked as 'error' (persists)
2. User continues using Conv B normally
3. When user switches to Conv A: Error banner appears
4. User can dismiss or retry

---

## Conversation Persistence

### Session Persistence (In-Memory)

**Backend:** In-memory Map in ConversationManager
- Conversations persist across requests
- Auto-cleanup after 1 hour of inactivity
- Survives container restart: No (memory only)

**Frontend:** In-memory Map cache
- Conversations cached during session
- Cleared on page refresh
- No localStorage (design choice: refresh = fresh start)

### Cross-Tab Behavior

**Current (Phase 1):** No synchronization
- Each tab has independent cache
- Backend state shared (in-memory Map)
- No real-time updates between tabs

**Phase 2:** Consider WebSocket for real-time sync

---

## Optimistic Updates

### New Conversation

**Optimistic:**
- User message appears immediately
- Conversation added to sidebar immediately
- UUID generated client-side

**Validation:**
- Backend creates conversation with client UUID
- Backend saves message
- If error: Rollback (delete message, restore input)

### New Message

**Optimistic:**
- User message appears immediately in message list
- Input cleared immediately

**Validation:**
- Backend saves message
- Backend generates response
- If error: Rollback message, restore input

### Sidebar Updates

**Optimistic:**
- New conversation shows in sidebar immediately
- Message count and preview update immediately

**Validation:**
- `fetchConversations()` called after generation
- Replaces optimistic data with accurate data from backend

---

## Non-Blocking Implementation

### Why .then() Chains Instead of async/await

**Problem with async/await:**
```typescript
const response = await fetch(url)  // Blocks for 18-60s
const data = await response.json()
// User can't switch conversations during this time
```

**Solution with .then() chains:**
```typescript
fetch(url)
  .then(response => response.json())
  .then(data => {
    // Validate before updating
    if (conversationId === currentConversationRef.current) {
      updateState(data)
    }
  })
// Function returns immediately, user can switch
```

**Benefits:**
- Conversation switching doesn't wait for generation
- Multiple conversations can be loading simultaneously
- UI remains responsive during long operations

### useRef for Validation

**Problem:** React state updates are asynchronous

**Scenario:**
1. `setCurrConversationId('conv-b')` called
2. State update scheduled (not immediate)
3. Conv A's response arrives
4. Checks `if (requestId !== currConversationId)` → Uses OLD value
5. Race condition: Conv A response overwrites Conv B

**Solution:**
```typescript
const currentConversationRef = useRef(null)

// Always update both together
setCurrConversationId(id)
currentConversationRef.current = id  // Synchronous

// Validate in async callbacks
if (conversationId === currentConversationRef.current) {
  // Safe
}
```

---

## Cache Management

### Cache Update Points

1. **After fetching conversation** (`handleResumeConversation`)
2. **After generating response** (`handleSend`)

**Always updates cache:**
- Even if user switched away
- Data is fresh, might as well cache it

### Cache Invalidation

**Phase 1:** None
- No TTL
- No manual invalidation
- Always fetches fresh data in background

**Phase 2:** Consider
- TTL-based expiration
- Manual refresh button
- Real-time invalidation via WebSocket

### Memory Management

**Current:** Unbounded cache
- All viewed conversations cached until page refresh
- Acceptable for Phase 1 (limited users, limited conversations)

**Phase 2:** Consider
- LRU cache (limit to N conversations)
- Clear cache after X minutes
- Monitor memory usage

---

## Future Enhancements (Phase 2)

### Real-Time Features
- WebSocket for streaming responses
- Live conversation updates across tabs
- Typing indicators

### Conversation Management
- Delete conversations
- Archive conversations
- Search conversation history
- Export conversation as PDF/Markdown

### Advanced Caching
- React Query for server state management
- Background refetching
- Optimistic mutations
- Automatic retry with exponential backoff

### Offline Support
- Service Worker for offline access
- IndexedDB for persistent storage
- Sync when connection restored
