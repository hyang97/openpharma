# UI Design System

## Design Principles

1. **Content-first** - Minimize chrome, maximize focus on research content
2. **Dark by default** - Reduce eye strain for extended research sessions
3. **Mobile-responsive** - Functional on all devices, mobile-first design
4. **Fast and minimal** - No unnecessary animations, instant feedback
5. **Professional** - Clean, modern aesthetic appropriate for pharma industry

---

## Color Palette

### Base Colors
- **Background**: `slate-900` (#0f172a) - Primary dark background
- **Surface**: `slate-800` (#1e293b) - Cards, elevated surfaces
- **Border**: `slate-700` (#334155) - Dividers, borders
- **Border Light**: `slate-600` (#475569) - Subtle borders

### Text Colors
- **Primary**: `white` (#ffffff) - Main text
- **Secondary**: `slate-300` (#cbd5e1) - Body text, secondary content
- **Tertiary**: `slate-400` (#94a3b8) - Labels, metadata
- **Muted**: `slate-500` (#64748b) - Placeholder text

### Accent Colors
- **Primary Accent**: `blue-500` (#3b82f6) - Buttons, links, interactive elements
- **Primary Accent Hover**: `blue-600` (#2563eb)
- **Error**: `red-900` (#7f1d1d) - Error backgrounds
- **Error Text**: `red-200` (#fecaca) - Error text

### Message Colors
- **User Bubble**: `slate-700` (#334155) - User message background
- **Assistant Background**: Transparent (inherits slate-900)
- **Loading Bubble**: `slate-800` (#1e293b) - Loading indicator background

---

## Typography

### Font Family
- **Base**: System font stack (native to each platform)
- **Monospace**: For code snippets (future)

### Font Sizes
- **6xl**: Landing page title (3.75rem / 60px)
- **5xl**: Mobile landing title (3rem / 48px)
- **4xl**: Section headers (future) (2.25rem / 36px)
- **xl**: Component headers (1.25rem / 20px)
- **base**: Body text (1rem / 16px)
- **sm**: Secondary text (0.875rem / 14px)
- **xs**: Labels, metadata (0.75rem / 12px)

### Font Weights
- **bold**: Titles, headers (700)
- **semibold**: Labels, role indicators (600)
- **normal**: Body text (400)

### Line Height
- **Tight**: Headings (1.25)
- **Normal**: Body text (1.5)
- **Relaxed**: Readable paragraphs (1.625)

### Letter Spacing
- **Wide**: Uppercase labels (`tracking-wide`)
- **Normal**: Body text

---

## Layout System

### Responsive Breakpoints
```css
mobile: < 768px
desktop: ≥ 768px (md: prefix in Tailwind)
```

### Grid Structure

**Desktop (≥ 768px):**
```
┌─────────┬──────────────────────────┐
│ Sidebar │  Main Content Area       │
│ 280px   │  flex-1                  │
│         │  ┌────────────────────┐  │
│         │  │ ChatHeader         │  │
│         │  ├────────────────────┤  │
│         │  │ MessageList        │  │
│         │  │ (scrollable)       │  │
│         │  ├────────────────────┤  │
│         │  │ CitationList       │  │
│         │  ├────────────────────┤  │
│         │  │ ChatInput (fixed)  │  │
│         │  └────────────────────┘  │
└─────────┴──────────────────────────┘
```

**Mobile (< 768px):**
```
┌──────────────────────────┐
│ ☰ ChatHeader             │ ← Fixed top
├──────────────────────────┤
│                          │
│ MessageList              │ ← Scrollable
│                          │
├──────────────────────────┤
│ CitationList             │
├──────────────────────────┤
│ ChatInput                │ ← Fixed bottom
└──────────────────────────┘

Sidebar overlay (when open):
┌──────────────────────────┐
│█████████████████│        │
│█ Conversations █│        │
│█████████████████│        │
│█████████████████│        │
└──────────────────────────┘
```

### Spacing Scale
- `p-2`: 0.5rem (8px)
- `p-3`: 0.75rem (12px)
- `p-4`: 1rem (16px)
- `p-6`: 1.5rem (24px)
- `space-y-6`: 1.5rem vertical spacing between messages

### Max Widths
- Message area: `max-w-4xl` (56rem / 896px)
- User bubbles: `max-w-2xl` (42rem / 672px)
- Assistant bubbles: `max-w-3xl` (48rem / 768px)
- Input field: `max-w-3xl` (48rem / 768px)

---

## Component Specs

### ChatHeader
**Fixed position, sticky to top**
- Background: `slate-900` with `border-b border-slate-700`
- Height: 60px (3.75rem)
- Padding: `p-3 sm:p-4`
- Contains: Hamburger (mobile), Title (clickable), New Conversation button

### ConversationSidebar
**Desktop:** Fixed left, 280px width
- Background: `slate-900` with `border-r border-slate-700`
- Scrollable conversation list

**Mobile:** Overlay drawer
- Full screen overlay with backdrop
- Background: `slate-900`
- Slide-in animation from left
- Close on backdrop click or conversation selection

### MessageBubble

**User Messages:**
- Alignment: Right (`justify-end`)
- Background: `slate-700`
- Padding: `px-5 py-4` (20px horizontal, 16px vertical)
- Border radius: `rounded-xl`
- Max width: `max-w-2xl`
- No label (clean bubble)

**Assistant Messages:**
- Alignment: Left (`justify-start`)
- Background: `slate-800` with `border border-slate-700`
- Padding: `px-5 py-4`
- Border radius: `rounded-xl`
- Max width: `max-w-3xl`
- Label: "OpenPharma" (uppercase, `text-xs text-slate-400`)

### Loading Indicator
- Container: `slate-800` with `border border-slate-700`
- Label: "OpenPharma" (same as assistant)
- Animated bouncing dots: `●` with staggered delay (0ms, 150ms, 300ms)
- Text: "Thinking..." (`text-sm text-slate-300`)

### Skeleton Loading (Cache Miss)
- User skeleton: `slate-700/50` with `border-slate-600/50`, `animate-pulse`
- Assistant skeleton: `slate-800/50` with `border-slate-700/50`, `animate-pulse`
- Gray bars with shimmer animation
- Text: "● ● ● Loading conversation..." with bouncing dots

### ChatInput

**Centered (Landing Page):**
- Max width: `max-w-3xl`
- Border: `border-slate-600`
- Background: `slate-800`
- No sticky positioning

**Bottom (Conversation View):**
- Sticky bottom: `sticky bottom-0 z-20`
- Background: `slate-900` with `border-t border-slate-700`
- Padding: `p-3 sm:p-4`
- Max width: `max-w-3xl mx-auto`

**Textarea:**
- Background: `slate-800`
- Border: `border-slate-600`
- Border radius: `rounded-xl`
- Padding: `px-4 py-3 sm:px-5 sm:py-4`
- Min height: 52px
- Max height: 200px (auto-expanding)
- Placeholder: "Ask a research question..." (`text-slate-500`)
- Font size: `text-base` (16px to prevent iOS zoom)

**Send Button:**
- Position: Absolute right inside input
- Background: `blue-500`, hover: `blue-600`
- Size: 36px × 36px (mobile), 40px × 40px (desktop)
- Border radius: `rounded-full`
- Icon: › (right chevron, `text-xl`)
- Disabled: `slate-700` when input empty or loading

**Disclaimer:**
- Text: "This is currently a personal learning project, use information at personal and professional risk. Enjoy and have fun!"
- Font size: `text-[10px] sm:text-xs` (10px mobile, 12px desktop)
- Color: `text-slate-500 italic`
- Centered below input

### CitationList

**Container:**
- Border top: `border-t border-slate-700`
- Padding: `p-6`
- Max width: `max-w-4xl mx-auto`

**Citation Cards:**
- Background: `slate-800`
- Border: `border-slate-700`
- Border radius: `rounded-lg`
- Padding: `p-4`
- Spacing: `space-y-4` between cards

**Citation Number:**
- Color: `text-blue-500`
- Font weight: `font-bold`

**Title:**
- Color: `text-white`
- Font size: `text-sm`
- Style: `italic`

**Metadata:**
- Color: `text-slate-400`
- Font size: `text-xs`

### Error Banner
- Position: Fixed below header, above messages
- Background: `red-900`
- Text color: `red-200`
- Padding: `p-3`
- Border radius: `rounded`
- Margin: `mx-4 sm:mx-6 mt-2`
- Dismiss button: × (times symbol, `hover:text-white`)

---

## Animation & Transitions

### Bounce Animation (Loading Dots)
- Built-in Tailwind `animate-bounce`
- Staggered delays: 0ms, 150ms, 300ms
- Used for: "Thinking...", "Loading conversation..."

### Pulse Animation (Skeleton Loading)
- Built-in Tailwind `animate-pulse`
- Used for: Skeleton placeholders during fetch

### Smooth Scroll
- Auto-scroll to bottom: `scrollIntoView({ behavior: 'smooth' })`
- Applied on message updates

### Input Expansion
- Textarea auto-expands from 52px to 200px max
- Smooth height transition via inline style updates

### No Other Animations
- Instant state changes (no fade-in/fade-out)
- Fast, responsive feel

---

## Accessibility

### Keyboard Navigation
- Enter to send message
- Shift+Enter for newline in textarea
- Tab navigation through interactive elements

### Screen Readers
- `aria-label` on buttons ("Toggle sidebar", "Send message")
- Semantic HTML (header, main, nav)

### Touch Targets
- Minimum 44px × 44px for all interactive elements
- Larger buttons on mobile

### Color Contrast
- Meets WCAG AA standards
- White text on slate-900: 15.3:1 contrast ratio
- Blue-500 on slate-900: 8.6:1 contrast ratio

---

## Mobile-Specific Design

### Fixed Elements
- Header fixed to top (z-30)
- Input fixed to bottom (z-20)
- Sidebar overlay (z-40)

### Scroll Behavior
- Header: `sticky top-0`
- Input: `sticky bottom-0`
- Messages: Natural scroll between fixed elements
- Auto-scroll to header height on first message send

### Touch Gestures
- Tap conversation to switch
- Tap backdrop to close sidebar
- No swipe gestures (keep simple)

### Font Sizes
- Minimum 16px for inputs (prevents iOS zoom)
- Larger touch targets (44px minimum)

---

## Future Enhancements (Phase 2)

### Visual
- Syntax highlighting for code blocks
- Markdown rendering for formatted text
- Inline images for figures/charts
- Dark/light theme toggle

### Animations
- Streaming text animation for LLM responses
- Smooth transitions between states
- Loading skeletons for citations

### Components
- Toast notifications
- Modal dialogs
- Dropdown menus
- Tabs for multi-domain data

### Accessibility
- Keyboard shortcuts
- Focus management
- High contrast mode
- Font size controls
