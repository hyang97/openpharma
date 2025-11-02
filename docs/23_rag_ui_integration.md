# RAG-Specific UI Integration

## Overview

Documents how the React frontend integrates with the RAG backend, including citation management, message handling, and RAG-specific display patterns.

**Key Features:**
- Conversation-wide citation numbering
- Expandable citation cards with metadata
- Message role display (user vs assistant)
- Loading states specific to LLM generation
- Error handling for RAG failures

---

## RAG Response Structure

### Backend Response Format

**Endpoint:** `POST /chat`

**Request:**
```typescript
{
  user_message: string
  use_local: boolean
  conversation_id?: string
  use_reranker: boolean
}
```

**Response:**
```typescript
{
  conversation_id: string
  assistant_message: string
  citations: Citation[]
}
```

**Citation Format:**
```typescript
{
  citation_number: number         // Conversation-wide sequential numbering
  pmcid: string                  // PMC ID (e.g., "PMC1234567")
  title: string                  // Paper title
  authors: string                // Comma-separated author list
  journal: string                // Journal name
  publication_date: string       // ISO date
  doi?: string                   // Optional DOI
  pmid?: string                  // Optional PubMed ID
}
```

### Multi-Turn Conversation Format

**Endpoint:** `GET /conversations/{conversation_id}`

**Response:**
```typescript
{
  conversation_id: string
  messages: Message[]
  citations: Citation[]          // Deduplicated, conversation-wide
}
```

**Message Format:**
```typescript
{
  role: 'user' | 'assistant'
  content: string
}
```

---

## Citation Management

### Conversation-Wide Numbering

**Behavior:**
- Citations numbered sequentially across entire conversation (not per message)
- New citations get next available number
- Duplicate PMCIDs reuse existing citation number
- Citation list accumulates across all messages

**Example:**
```
Message 1: "...diabetes treatment [1][2]"
Citations: [1] Smith et al., [2] Jones et al.

Message 2: "...insulin resistance [2][3]"
Citations: [1] Smith et al., [2] Jones et al., [3] Brown et al.
```

**Implementation:**
- Backend maintains citation map in ConversationManager
- Frontend displays full citation list below all messages
- Citations never reset or renumber during conversation

### Citation Display

**Location:** Below message list, above input

**Layout:**
- Card-based design (slate-800 background, slate-700 border)
- Stacked vertically with space-y-4 spacing
- Max width: `max-w-4xl` (same as message area)

**Content per card:**
- Citation number (blue-500, bold) - e.g., "[1]"
- Title (white, italic, text-sm)
- Authors (slate-400, text-xs) - truncated if long
- Journal (slate-400, text-xs)
- Publication date (slate-400, text-xs)
- DOI link (blue-500, text-xs, underline on hover) - if available
- PMID link (blue-500, text-xs, underline on hover) - if available

**Expandable behavior:** Not implemented in Phase 1

**Future (Phase 2):**
- Collapse/expand citation cards
- Show abstract on expand
- Inline citation highlighting in message text
- Citation filtering (show only citations for specific message)

---

## Message Display Patterns

### User Messages

**Visual:**
- Aligned right (justify-end)
- Background: slate-700
- Border radius: rounded-xl
- Padding: px-5 py-4
- Max width: max-w-2xl
- No role label (clean bubble design)

**Content:**
- Plain text only (no markdown in Phase 1)
- Preserves line breaks
- No special formatting

### Assistant Messages

**Visual:**
- Aligned left (justify-start)
- Background: slate-800 with border-slate-700
- Border radius: rounded-xl
- Padding: px-5 py-4
- Max width: max-w-3xl (wider than user)
- Role label: "OPENPHARMA" (uppercase, text-xs, slate-400)

**Content:**
- Plain text with inline citation numbers (e.g., "[1]")
- Citation numbers in assistant messages correspond to citation list below
- No markdown rendering in Phase 1

**Future (Phase 2):**
- Markdown rendering (bold, italic, lists, code blocks)
- Syntax highlighting for code
- Inline citation tooltips (hover to preview)
- Streaming text animation

---

## Loading States

### LLM Generation Loading

**Trigger:** User sends message, backend generating response

**Indicator:**
- Container: slate-800 with border-slate-700
- Label: "OPENPHARMA" (same as assistant)
- Animated bouncing dots: ● ● ● with staggered delay
- Text: "Thinking..." (text-sm, slate-300)

**Behavior:**
- Appears at bottom of message list
- Input disabled during generation
- Send button disabled (slate-700 background)
- User can switch conversations (loading continues in background)

**Duration:** 18-40 seconds typical (97% LLM generation, 3% retrieval)

### Fetching Conversation Loading

**Trigger:** User switches to uncached conversation

**Indicator:**
- Skeleton placeholders (2 message bubbles with shimmer)
- User skeleton: slate-700/50 with border-slate-600/50
- Assistant skeleton: slate-800/50 with border-slate-700/50
- Animated pulse effect
- Text: "● ● ● Loading conversation..." with bouncing dots

**Behavior:**
- Replaces message list during fetch
- Input disabled during fetch
- Usually < 1 second (instant if cached)

**Cache behavior:**
- Cache hit: Instant display, no skeleton
- Cache miss: Skeleton until backend responds

---

## Error Handling

### RAG Generation Error

**Trigger:** Backend fails during LLM generation

**Backend behavior:**
- User message saved before generation
- Rollback on error (delete last message)
- Return 500 error

**Frontend behavior:**
- Error banner appears below header
- Background: red-900
- Text: "Previous message failed to send. Please try again." (red-200)
- Dismiss button: × (times symbol)
- Input restored with original message
- Conversation marked as 'error' until dismissed

**Recovery:**
- User can edit message and retry
- User can dismiss error and continue with new message
- Error persists if user switches away and back

### Network Error

**Trigger:** Fetch fails (network down, timeout)

**Same behavior as RAG generation error**

### Empty Input Validation

**Trigger:** User tries to send empty/whitespace-only message

**Behavior:**
- Send button disabled when `input.trim() === ''`
- No error shown (preventative validation)

---

## RAG-Specific Interactions

### Send Message Flow

1. User types message in ChatInput
2. User clicks send or presses Enter
3. Frontend:
   - Adds user message to UI immediately (optimistic)
   - Clears input field
   - Disables input and send button
   - Shows "Thinking..." loading indicator
4. Backend:
   - Saves user message
   - Retrieves relevant chunks via hybrid search
   - Reranks chunks (if enabled)
   - Generates response with LLM
   - Extracts citations from generated text
   - Returns response with citations
5. Frontend:
   - Removes loading indicator
   - Adds assistant message to UI
   - Updates citation list (appends new citations)
   - Re-enables input
   - Auto-scrolls to bottom

**Timing:**
- User message appears: Instant
- Loading indicator: Instant
- Assistant response: 18-40s (typical)

### Resume Conversation Flow

1. User clicks conversation in sidebar
2. Frontend:
   - Updates `currConversationId` immediately
   - Checks cache for conversation data
   - If cached: Shows messages instantly
   - If not cached: Shows skeleton loading
3. Backend:
   - Fetches conversation messages
   - Fetches conversation-wide citations
   - Returns full conversation data
4. Frontend:
   - Displays messages (if not already shown from cache)
   - Displays citations
   - Updates cache
   - Re-enables input

**Timing:**
- Conversation switch: Instant (ID update)
- Message display: Instant (if cached) or ~500ms (if not cached)

---

## Input Validation

### Client-Side Validation

**Empty input:**
- Send button disabled when `input.trim() === ''`
- No error message (preventative)

**During loading:**
- Input disabled when `isLoading === true`
- Input disabled when `isFetchingConversation === true`
- Textarea grayed out (slate-700 background)

**Max length:** No limit in Phase 1

**Future (Phase 2):**
- Character count indicator
- Token count estimation
- Max token limit warning
- Query complexity analysis

### Backend Validation

**Phase 1:** No backend validation on user input

**Future (Phase 2):**
- Input sanitization
- Query complexity limits
- Rate limiting per user
- Profanity filtering

---

## Response Streaming (Future)

**Phase 1:** No streaming - full response returned at once

**Phase 2 Design:**
- Server-Sent Events (SSE) for token streaming
- Word-by-word display in assistant message
- Smooth typing animation
- Citations appear at end of stream
- Cancel generation button

**Benefits:**
- Reduces perceived latency (first tokens in 2-3s)
- User sees progress during long generation
- Better UX for 18-40s response time

---

## Citation Accuracy (Future)

**Phase 1:** No accuracy measurement

**Phase 2 Design:**
- Track citation accuracy per conversation
- Compare cited papers to retrieved papers
- Measure hallucinated citations
- Display accuracy score in UI
- Warn user if accuracy drops below threshold

**Metrics:**
- Citation precision (% of citations that are valid)
- Citation recall (% of retrieved papers that are cited)
- Hallucination rate (% of citations not in retrieval)

---

## Feedback Mechanisms (Future)

**Phase 1:** No feedback collection

**Phase 2 Design:**
- Thumbs up/down on assistant messages
- Report incorrect citations
- Rate conversation overall
- Flag inappropriate content
- Export conversation for sharing

**Data collection:**
- Feedback stored in database
- Used for RAGAS evaluation
- Informs model fine-tuning
- Improves retrieval pipeline

---

## Mobile-Specific RAG Patterns

### Citation Display on Mobile

**Layout:**
- Same card-based design as desktop
- Full width (minus padding)
- Stacked vertically
- Touch-friendly card height (min 80px)

**Truncation:**
- Long titles truncated with ellipsis (2 lines max)
- Long author lists truncated ("Smith et al., +5 authors")
- Tap to expand (future)

### Message Display on Mobile

**User bubbles:**
- Max width: 90% of screen width
- Right-aligned with margin-left: auto

**Assistant bubbles:**
- Max width: 95% of screen width
- Left-aligned

**Auto-scroll behavior:**
- Scroll to header height on first message
- Scroll to bottom on new message
- Smooth scroll animation

### Input on Mobile

**Special handling:**
- Fixed to bottom (sticky bottom-0)
- Font size: 16px minimum (prevents iOS zoom)
- Auto-expand up to 200px
- Send button: 36px × 36px (larger touch target)

---

## Performance Considerations

### Current Bottlenecks

**LLM Generation:** 18-40s (97% of total response time)
- Ollama Llama 3.1 8B on M1 Mac
- No streaming in Phase 1

**Retrieval:** < 1s (3% of total response time)
- Hybrid search via pgvector: ~300ms
- Reranking (if enabled): ~0.8s (ms-marco-MiniLM-L-6-v2)

**Frontend Rendering:** < 50ms
- React re-renders on message updates
- Citation list re-renders on new citations

### Optimization Strategies

**Phase 1:**
- Client-side caching (instant conversation switching)
- Non-blocking async operations (UI remains responsive)
- Optimistic updates (immediate feedback)

**Phase 2:**
- Response streaming (reduce perceived latency)
- Lazy loading for long citation lists
- Virtual scrolling for long conversations
- Debounced input (prevent rapid API calls)

---

## API Configuration

### Environment Variables

**Frontend (`ui/.env.local`):**
```
NEXT_PUBLIC_API_URL=http://localhost:8000
```

**Backend (`docker-compose.yml`):**
```
USE_LOCAL=true                    # true: Ollama, false: OpenAI
RERANKER_MODEL=cross-encoder/ms-marco-MiniLM-L-6-v2
OPENAI_API_KEY=sk-...             # Required if USE_LOCAL=false
```

### API Endpoints

**Chat:**
- `POST /chat` - Send message, get response with citations

**Conversations:**
- `GET /conversations` - List all conversations (summary)
- `GET /conversations/{id}` - Get full conversation (messages + citations)

**Health:**
- `GET /health` - API health check

**Future (Phase 2):**
- `DELETE /conversations/{id}` - Delete conversation
- `POST /conversations/{id}/feedback` - Submit feedback
- `GET /conversations/{id}/export` - Export as PDF/Markdown

---

## Testing RAG Integration

### Manual Testing Scenarios

1. **Citation numbering:** Send 3 messages, verify sequential citation numbers
2. **Citation deduplication:** Ask related questions, verify duplicate PMCIDs reuse numbers
3. **Loading states:** Send message, verify "Thinking..." appears
4. **Error handling:** Stop backend mid-generation, verify error banner
5. **Citation display:** Verify all metadata fields render correctly
6. **Mobile responsive:** Test on mobile, verify citation cards and messages layout correctly

### Automated Testing (Future)

**Unit tests:**
- Citation number extraction from message text
- Citation deduplication logic
- Message role display logic

**E2E tests:**
- Send message, wait for response, verify citation count
- Switch conversation during generation, verify no contamination
- Trigger error, verify error banner appears

**RAGAS evaluation:**
- Citation accuracy measurement
- Response relevance scoring
- Context precision/recall

---

## Future Enhancements (Phase 2)

### Advanced Citation Features
- Inline citation highlighting in message text
- Citation preview on hover
- Citation filtering by date, journal, author
- Citation export (BibTeX, RIS, EndNote)
- Full-text PDF viewer

### Response Quality
- Streaming responses with token-by-token display
- Query rewriting for better retrieval
- Multi-step reasoning display (show intermediate steps)
- Confidence scores for citations
- Alternative answers (multiple perspectives)

### User Experience
- Dark/light theme toggle
- Conversation search
- Conversation export
- Share conversation via link
- Conversation branching (fork at any message)

### Analytics
- Response time tracking
- Citation usage heatmap
- Query complexity analysis
- User satisfaction metrics
- A/B testing framework
