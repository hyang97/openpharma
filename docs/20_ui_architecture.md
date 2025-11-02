# Frontend Architecture

## Overview

Next.js 15 + React + TypeScript single-page application with real-time conversational RAG interface.

**Tech Stack:**
- Next.js 15 (App Router)
- React 18 (Client Components)
- TypeScript
- Tailwind CSS
- No state management libraries (React built-in state)

---

## Component Hierarchy

```
app/page.tsx (Chat)
├── ConversationSidebar
│   └── Conversation items (map)
├── ChatHeader
│   └── Hamburger menu + Home button
├── MessageList
│   ├── Skeleton loading (cache miss)
│   ├── MessageBubble[] (actual messages)
│   └── Loading indicator (LLM generating)
├── CitationList
│   └── Citation cards (expandable)
└── ChatInput
    └── Auto-expanding textarea + Send button
```

**Component Responsibility:**
- `Chat (page.tsx)` - **State container** - Manages all conversation state, handles API calls
- `ConversationSidebar` - **Presentation** - Displays conversation list, handles selection
- `MessageList` - **Presentation + Auto-scroll** - Displays messages, loading states, auto-scrolls
- `MessageBubble` - **Presentation** - Renders individual messages (user bubbles only)
- `CitationList` - **Presentation** - Displays expandable citation cards
- `ChatInput` - **Controlled component** - Input field with disabled state

---

## State Management Strategy

### Centralized State (page.tsx)

All state lives in `Chat` component. No global state, no context providers, no state management libraries.

**Conversation State:**
```typescript
currConversationId: string | null           // Current conversation
currentConversationRef: useRef<string | null>  // Sync ref for async validation
messages: Message[]                         // Current conversation messages
currCitations: Citation[]                   // Current conversation citations
allConversationSumm: ConversationSummary[]  // Sidebar conversation list
```

**Loading State:**
```typescript
loadingConversations: Map<string, 'loading' | 'error'>  // Per-conversation status
isFetchingConversation: boolean            // Fetching conversation data (separate from generation)
isLoading: boolean (derived)               // Current conversation generating
hasError: boolean (derived)                // Current conversation has error
```

**Cache State:**
```typescript
conversationCache: Map<string, {messages, citations}>  // Client-side cache
```

**UI State:**
```typescript
input: string                              // Current input value
isSidebarOpen: boolean                     // Mobile sidebar toggle
```

### Why Centralized?

- **Simple:** Single source of truth, easy to debug
- **Phase 1 appropriate:** Limited scope, no need for complex state management
- **Refactorable:** Can extract to Context/Redux/Zustand in Phase 2 if needed

---

## Data Flow Patterns

### Props Down, Events Up

Components are **presentation-only** (except Chat). Data flows down via props, events bubble up via callbacks.

**Example:**
```
Chat (state)
  ↓ props: messages, isLoading
MessageList (presentation)
  ↓ props: message
MessageBubble (presentation)
```

```
User clicks conversation in sidebar
  ↑ event: onSelectConversation(id)
ConversationSidebar
  ↑ calls
Chat.handleResumeConversation(id)
  ↓ updates state
  ↓ props: messages, citations
MessageList re-renders
```

### Async Operations

All API calls handled in `Chat` component using **non-blocking `.then()` chains**:

**Why `.then()` instead of `async/await`:**
- Prevents blocking UI during long-running operations (18-60s LLM generation)
- Allows conversation switching without waiting
- Enables concurrent request handling

**Pattern:**
```typescript
fetch(url)
  .then(response => response.json())
  .then(data => {
    // Validate still on same conversation
    if (conversationId === currentConversationRef.current) {
      updateState(data)
    }
  })
  .catch(handleError)
```

---

## Key Architectural Patterns

### useRef for Async Validation

**Problem:** React state updates are asynchronous. During long async operations, state may be stale.

**Solution:** Maintain both state and ref, update synchronously:
```typescript
const [currConversationId, setCurrConversationId] = useState(null)
const currentConversationRef = useRef(null)

// Always update both together
setCurrConversationId(id)
currentConversationRef.current = id

// Validate in async callbacks
.then(data => {
  if (conversationId === currentConversationRef.current) {
    // Safe to update UI
  }
})
```

### Client-Side Caching

**Strategy:** In-memory Map cache, cleared on page refresh.

**Cache policy:**
- Update on fetch (conversation loaded)
- Update on generation (new message added)
- No TTL, no invalidation (data always fresh from backend)

**Benefits:**
- Instant switching for previously-viewed conversations
- Reduces backend load
- Smooth UX during backend blocking (Phase 1 limitation)

### Optimistic Updates

**Pattern:** Update UI immediately, validate later.

**Examples:**
- User message appears immediately in message list
- New conversations appear in sidebar immediately
- Loading indicators show immediately

**Rollback:** Backend deletes user message on error, frontend restores input.

---

## Navigation & Routing

**Single-page application** - No routing, no navigation between pages.

**State-based views:**
- Landing page: `messages.length === 0 && !currConversationId`
- Conversation view: `currConversationId !== null`

**Future (Phase 2):** Consider Next.js App Router for:
- `/` - Landing page
- `/conversation/:id` - Conversation view
- `/settings` - Settings page

---

## Performance Considerations

### Current Optimizations
- Client-side caching for instant switching
- Auto-scroll uses `scrollIntoView({ behavior: 'smooth' })`
- Tailwind CSS (no runtime CSS-in-JS overhead)
- No heavy libraries (keeps bundle small)

### Known Limitations (Phase 1)
- No virtualization (all messages render)
- No pagination (all conversations in sidebar)
- No debouncing on input
- No request deduplication

### Phase 2 Improvements
- Virtualized message list for long conversations
- Infinite scroll for conversation list
- React Query for advanced caching
- Streaming responses from LLM

---

## Error Handling Strategy

### Backend Errors
- Rollback user message via `delete_last_message()`
- Mark conversation as 'error' in `loadingConversations` Map
- Show error banner (dismissible)
- Restore input for retry

### Network Errors
- Handled by `.catch()` in fetch chains
- Same flow as backend errors

### Validation Errors
- Input disabled when empty (`disabled={!value.trim()}`)
- Input disabled when loading/fetching (`disabled={isLoading || isFetchingConversation}`)

---

## Mobile Responsiveness

**Approach:** Mobile-first design with Tailwind breakpoints.

**Breakpoints:**
- `< 768px` - Mobile (stacked layout, collapsible sidebar)
- `≥ 768px` - Desktop (side-by-side layout, persistent sidebar)

**Mobile-specific features:**
- Fixed header with hamburger menu
- Collapsible sidebar overlay
- Auto-scroll on first message send
- Touch-friendly button sizes

---

## Testing Strategy (Phase 1)

**Current:** Manual testing only.

**Test scenarios:**
- Conversation switching during loading
- Cache hit (instant) vs cache miss (skeleton)
- Error handling and retry
- Mobile responsive layout

**Phase 2:** Add automated tests:
- Unit tests (Jest + React Testing Library)
- E2E tests (Playwright)
- Visual regression tests (Chromatic/Percy)

---

## Future Considerations (Phase 2)

### Component Extraction
Extract conversation management to custom hooks:
- `useConversations()` - Conversation list and selection
- `useConversationCache()` - Caching logic
- `useMessages()` - Message state and updates

### State Management
Consider Redux/Zustand/Jotai if:
- Multiple pages need shared state
- Complex state transitions
- Time-travel debugging needed

### Code Splitting
- Route-based splitting with Next.js dynamic imports
- Component-level splitting for heavy features

### Type Safety
- Stricter TypeScript config (`strict: true`)
- Zod for runtime validation
- Type-safe API client (tRPC/GraphQL)
