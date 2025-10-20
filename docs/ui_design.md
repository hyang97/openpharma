# UI Design Document

## Overview

OpenPharma's user interface is a Next.js-based React application that provides a conversational chat interface for querying pharmaceutical research literature with multi-turn conversation support and conversation-wide citation numbering.

## Visual Layout

### Empty State (Landing)
```
┌──────────────────────────────────────────────────┐
│                                                  │
│                                                  │
│              OpenPharma                          │
│     AI-powered pharma research assistant         │
│                                                  │
│  ┌──────────────────────────────────────────┐   │
│  │ Ask a question about diabetes research  │   │
│  │                                    [Send]│   │
│  └──────────────────────────────────────────┘   │
│                                                  │
└──────────────────────────────────────────────────┘
```

### Active State (With Conversation)
```
┌────────┬───────────────────────────────────────┐
│ Convos │  OpenPharma    [New Conversation]    │
├────────┼───────────────────────────────────────┤
│ > Chat1│  User: What is metformin?            │
│   Chat2│  Assistant: Metformin is... [1][2]   │
│   Chat3│  ─────────────────────────────────    │
│        │  User: What about side effects?       │
│        │  Assistant: Side effects [1][3]...    │
│        │  ═════════════════════════════════    │
│        │  Citations:                           │
│        │  [1] Paper A (PMC123)                 │
│        │  [2] Paper B (PMC456)                 │
│        │  [3] Paper C (PMC789)                 │
├────────┼───────────────────────────────────────┤
│        │  [Type your question...]      [Send] │
└────────┴───────────────────────────────────────┘
```

## Tech Stack

- **Framework**: Next.js 15.5.6 with App Router
- **Language**: TypeScript 5
- **Styling**: Tailwind CSS 3.4
- **UI Pattern**: Server Components with Client Components for interactivity

## Architecture

### Component Structure

```
src/
├── app/
│   ├── page.tsx              # Main chat page (client component)
│   ├── layout.tsx            # Root layout
│   └── globals.css           # Global Tailwind styles
├── components/
│   ├── ConversationSidebar.tsx  # Sidebar with conversation list (NEW)
│   ├── ChatHeader.tsx        # Header with new conversation button
│   ├── MessageList.tsx       # Message container with loading state
│   ├── MessageBubble.tsx     # Individual message display
│   ├── CitationList.tsx      # Citation cards (conversation-wide)
│   └── ChatInput.tsx         # Input field with send button
└── types/
    └── message.ts            # Shared TypeScript types
```

### State Management

The main `page.tsx` component manages state for multi-turn conversations:

1. **currentConversationId**: `string | null` - Active conversation UUID
2. **conversations**: `ConversationSummary[]` - List of all conversations with metadata
3. **messages**: `Message[]` - Messages in the current conversation
4. **allCitations**: `Citation[]` - All citations from current conversation (conversation-wide)
5. **input**: `string` - Current input field value
6. **isLoading**: `boolean` - Loading indicator during API calls

State flows down through props, and callbacks flow up to update parent state.

## Design System

### Color Palette

- **Background**: `slate-900` (dark charcoal)
- **User Messages**: `slate-700` (lighter grey)
- **Assistant Messages**: `slate-800` with `slate-700` border
- **Accent**: `blue-600` (cobalt) for buttons and citation numbers
- **Text**: White and various slate tones (100-500)

### Typography

- **Title**: 6xl font weight bold (empty state), xl bold (header)
- **Body**: Base size with relaxed leading
- **Labels**: Xs uppercase with wide tracking
- **Citations**: Xs with italic titles

### Layout States

#### Empty State (No Active Conversation)
- Centered layout with large title
- Tagline below title
- Input field centered in viewport
- Clean, minimal design
- **No sidebar** (keeps focus on getting started)

#### Active State (With Messages)
- **Sidebar appears on left (280px)** showing conversation list
- Current conversation highlighted in sidebar
- Fixed header at top with "New Conversation" button
- Scrollable message area in middle
- Conversation-wide citations displayed below messages
- Fixed input at bottom
- Messages aligned left (assistant) and right (user)

### Component Patterns

#### ConversationSidebar (NEW)
- **Props**: `conversations: ConversationSummary[]`, `currentId: string | null`, `onSelect: (id: string) => void`
- **Features**:
  - List of conversations with preview of first message
  - Highlight currently active conversation
  - Click to switch conversations
  - Scroll if list exceeds viewport height
  - Collapsible on mobile

#### ChatInput
- **Props**: `value`, `onChange`, `onSend`, `centered?`
- **Features**:
  - Enter key to send (Shift+Enter for newline)
  - Disabled send button when input empty
  - Different styling for centered vs. bottom position

#### MessageBubble
- **Props**: `message: Message`
- **Features**:
  - Role-based styling (user vs assistant)
  - Uppercase role labels
  - Citation display for assistant messages
  - Rounded corners (xl) with padding

#### CitationList
- **Props**: `citations: Citation[]`
- **Features**:
  - Border separator from main content
  - Card-based citation display
  - Blue numbered references
  - Journal and PMC ID metadata

#### MessageList
- **Props**: `messages: Message[]`, `isLoading: boolean`
- **Features**:
  - Loading indicator with animated dots
  - "Thinking..." message during API calls
  - Consistent spacing between messages

## User Flow

1. **Landing**: User sees centered title and input field (no sidebar)
2. **First Query**: User types question and presses Enter or clicks Send
3. **Conversation Starts**:
   - Backend creates new conversation with UUID
   - Sidebar appears on left
   - Input moves to bottom, loading indicator appears
4. **Response**: Assistant message appears with citations
5. **Multi-Turn**: User can ask follow-up questions
   - Citations maintain consistent numbering across turns
   - Same conversation_id sent with each request
6. **New Conversation**: Click "New Conversation" button in header
   - Clears current messages
   - Starts fresh conversation with new UUID
   - Previous conversation remains in sidebar
7. **Resume Old Conversation**: Click conversation in sidebar
   - Loads that conversation's message history
   - Shows that conversation's citations
   - Continues using that conversation_id

## API Integration

### Endpoint: POST /chat
- **URL**: `http://localhost:8000/chat`
- **Method**: POST
- **Request Body**:
  ```json
  {
    "user_message": "user query string",
    "use_local": true,
    "conversation_id": "uuid-string-or-null"
  }
  ```
  - `conversation_id`: Optional. If `null`, backend creates new conversation. If provided, continues existing conversation.

- **Response** (ChatResponse):
  ```json
  {
    "user_message": "original question",
    "generated_response": "synthesized response with [1], [2] citations",
    "response_citations": [
      {
        "number": 1,
        "title": "Paper title",
        "journal": "Journal name",
        "source_id": "1234567"
      }
    ],
    "conversation_citations": [
      {
        "number": 1,
        "title": "Paper title",
        "journal": "Journal name",
        "source_id": "1234567"
      },
      {
        "number": 2,
        "title": "Another paper",
        "journal": "Journal B",
        "source_id": "7654321"
      }
    ],
    "conversation_id": "uuid-of-conversation",
    "llm_provider": "ollama",
    "generation_time_ms": 1234.5
  }
  ```
  - **response_citations**: Citations used in current response only
  - **conversation_citations**: All citations from entire conversation (conversation-wide)
  - **Note**: Citation numbers are conversation-wide. If [1] was PMC12345 in turn 1, it remains [1] in turn 2.

### Endpoint: GET /conversations
- **URL**: `http://localhost:8000/conversations`
- **Method**: GET
- **Response**:
  ```json
  [
    {
      "conversation_id": "uuid-string",
      "first_message": "What is metformin?",
      "message_count": 4,
      "last_updated": 1234567890.123
    }
  ]
  ```
  - Returns array of conversation summaries sorted by last_updated (newest first)

### Endpoint: GET /conversations/{conversation_id}
- **URL**: `http://localhost:8000/conversations/{conversation_id}`
- **Method**: GET
- **Response**:
  ```json
  {
    "conversation_id": "uuid-string",
    "first_message": "What is metformin?",
    "message_count": 4,
    "last_updated": 1234567890.123,
    "messages": [
      {"role": "user", "content": "What is metformin?"},
      {"role": "assistant", "content": "Metformin is... [1][2]"}
    ],
    "citations": [
      {
        "number": 1,
        "title": "Paper title",
        "journal": "Journal name",
        "source_id": "1234567"
      }
    ]
  }
  ```

### Error Handling
- Network errors show: "Sorry, there was an error. Please try again."
- Error messages styled as assistant messages

## TypeScript Types

### Message
```typescript
type Message = {
  role: string              // 'user' | 'assistant'
  content: string           // Message text with inline citation numbers [1], [2]
}
```

### Citation
```typescript
type Citation = {
  number: number            // Conversation-wide sequential number
  title: string             // Paper title
  journal: string           // Journal name
  source_id: string         // PMC ID (without prefix)
}
```

### ConversationSummary (NEW)
```typescript
type ConversationSummary = {
  conversation_id: string   // UUID
  first_message: string     // Preview text for sidebar
  message_count: number     // Total messages in conversation
  last_updated: string      // ISO timestamp
}
```

## Development

### Running Locally
```bash
cd ui
npm install
npm run dev
```

### Build for Production
```bash
npm run build
npm start
```

### Environment
- Development: `http://localhost:3000`
- Backend API: `http://localhost:8000`

## Phase 1 Features (Current)

### Implemented (Backend)
- ✅ Multi-turn conversations with conversation-wide citation numbering
- ✅ ConversationManager tracks messages and citations per conversation
- ✅ Citation numbers persist across turns ([1] always means same paper)
- ✅ `/ask` endpoint accepts and returns `conversation_id`
- ✅ Comprehensive tests (21 unit + 8 integration tests)

### Implemented (Frontend)
- ✅ Update React UI to send/receive `conversation_id`
- ✅ Track `currentConversationId` in React state
- ✅ Build collapsible ConversationSidebar component
- ✅ "New Conversation" button in header
- ✅ Click to resume previous conversations from sidebar
- ✅ Show conversation-wide citations (expandable, below messages)
- ✅ Sidebar updates dynamically when conversations are created/updated
- ✅ `/chat` endpoint (renamed from `/ask`) with `ChatResponse` model
- ✅ `GET /conversations` endpoint for conversation summaries
- ✅ `GET /conversations/{id}` endpoint for conversation details

### Planned for Later in Phase 1
- Query rewriting for follow-up questions ("side effects" → "side effects of metformin")
- Inline citation links to PubMed Central
- Copy message to clipboard
- Delete conversation from sidebar

## Phase 2 Enhancements
- Conversation persistence (database instead of in-memory)
- User authentication and multi-user support
- Export conversation as PDF/Markdown
- Dark/light mode toggle
- Citation hover previews with abstract
- Streaming LLM responses for better UX
- Edit conversation titles
- Search within conversation history
