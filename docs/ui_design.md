# UI Design Document

## Overview

OpenPharma's user interface is a Next.js-based React application that provides a conversational chat interface for querying pharmaceutical research literature.

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
│   ├── ChatHeader.tsx        # Header with home button
│   ├── MessageList.tsx       # Message container with loading state
│   ├── MessageBubble.tsx     # Individual message display
│   ├── CitationList.tsx      # Citation cards
│   └── ChatInput.tsx         # Input field with send button
└── types/
    └── message.ts            # Shared TypeScript types
```

### State Management

The main `page.tsx` component manages three pieces of state:

1. **messages**: `Message[]` - Array of user/assistant messages
2. **input**: `string` - Current input field value
3. **isLoading**: `boolean` - Loading indicator during API calls

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

#### Empty State (No Messages)
- Centered layout with large title
- Tagline below title
- Input field centered in viewport
- Clean, minimal design

#### Active State (With Messages)
- Fixed header at top (clickable to return home)
- Scrollable message area in middle
- Fixed input at bottom
- Messages aligned left (assistant) and right (user)

### Component Patterns

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

1. **Landing**: User sees centered title and input field
2. **Query**: User types question and presses Enter or clicks Send
3. **Loading**: Input moves to bottom, loading indicator appears
4. **Response**: Assistant message appears with citations
5. **Continue**: User can ask follow-up questions
6. **Reset**: Click "OpenPharma" header to return to empty state

## API Integration

### Endpoint
- **URL**: `http://localhost:8000/ask`
- **Method**: POST
- **Request Body**:
  ```json
  {
    "question": "user query string",
    "use_local": true
  }
  ```
- **Response**:
  ```json
  {
    "answer": "synthesized response with [1], [2] citations",
    "citations": [
      {
        "number": 1,
        "title": "Paper title",
        "journal": "Journal name",
        "source_id": "1234567"
      }
    ],
    "query": "original question",
    "llm_provider": "ollama",
    "generation_time_ms": 1234.5
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
  content: string           // Message text
  citations?: Citation[]    // Only for assistant messages
}
```

### Citation
```typescript
type Citation = {
  number: number            // Sequential citation number
  title: string             // Paper title
  journal: string           // Journal name
  source_id: string         // PMC ID (without prefix)
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

## Future Enhancements

### Phase 1 (Current MVP)
- Multi-turn conversation history
- Query rewriting for better retrieval
- Inline citation links to PubMed
- Copy message to clipboard
- Regenerate response button

### Phase 2
- Conversation persistence (database)
- User authentication
- Export conversation feature
- Dark/light mode toggle
- Citation hover previews
- Streaming LLM responses
