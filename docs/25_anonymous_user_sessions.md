# Anonymous User Sessions

Design document for implementing anonymous user sessions to enable multi-user support without requiring authentication.

## Overview

OpenPharma currently stores all conversations in-memory with no user isolation. This design adds anonymous user tracking to enable:
- Multi-user support (each browser session gets isolated conversations)
- Persistent user identity across page refreshes (via localStorage)
- Future migration path to authenticated users (Phase 2)

## Design Goals

1. **Zero Friction**: Users can start chatting immediately without registration/login
2. **Privacy-First**: No PII collection, anonymous identifiers only
3. **Session Persistence**: Conversations survive page refreshes within same browser
4. **Security**: Users cannot access other users' conversations
5. **Phase 1 Aligned**: Minimal complexity, no database schema changes required
6. **Future-Proof**: Easy migration to authenticated users later

## Architecture

### User Identification Strategy

**Anonymous User ID Format**: `anon_{timestamp}_{random}`
- Example: `anon_1704067200_a3f9k2x7q`
- Generated client-side on first visit
- Stored in browser localStorage (key: `openpharma_user_id`)
- Sent with every API request

**Lifecycle:**
1. User opens app → Frontend checks localStorage
2. If no user_id exists → Generate new ID, store in localStorage
3. All API requests include user_id in request body
4. Backend filters conversations by user_id
5. User closes tab → ID persists in localStorage
6. User returns → Same ID retrieved, conversations restored

### Data Model Changes

**No database schema changes required** - all changes are in-memory only.

**Conversation Object** (app/models.py):
```python
class Conversation:
    conversation_id: str
    user_id: str  # NEW: anonymous user identifier
    messages: List[dict]
    citation_mapping: Dict[str, int]
    conversation_citations: Dict[str, Citation]
    last_accessed: float
```

**ConversationManager**:
- Add `user_id` parameter to all conversation methods
- Filter conversations by user_id in `get_conversation_summaries()`
- Add ownership validation in `get_conversation()`, `add_message()`

### API Changes

**Request Model** (app/main.py):
```python
class UserRequest(BaseModel):
    user_message: str
    user_id: str  # NEW: required anonymous user ID
    conversation_id: Optional[str]
    # ... existing fields
```

**Endpoint Changes:**
- `POST /chat/stream`: Accept user_id, validate ownership
- `POST /chat`: Accept user_id, validate ownership
- `GET /conversations`: Filter by user_id query param
- `GET /conversations/{id}`: Validate user owns conversation

**Security Validation:**
```python
# Before accessing any conversation
conv = conversation_manager.get_conversation(conversation_id)
if conv and conv.user_id != request.user_id:
    raise HTTPException(status_code=403, detail="Access denied")
```

### Frontend Changes

**New Hook** (ui/src/hooks/useAnonymousUser.ts):
```typescript
export function useAnonymousUser(): string | null {
  const [userId, setUserId] = useState<string | null>(null);

  useEffect(() => {
    let storedUserId = localStorage.getItem('openpharma_user_id');

    if (!storedUserId) {
      storedUserId = `anon_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;
      localStorage.setItem('openpharma_user_id', storedUserId);
    }

    setUserId(storedUserId);
  }, []);

  return userId;
}
```

**Integration Points:**
- Call `useAnonymousUser()` in main page component
- Pass `userId` to all API calls (chat, conversations)
- Block UI until userId is ready (prevent race conditions)

## Security Considerations

### Input Validation

**user_id Format**:
- Regex: `^[a-zA-Z0-9_-]+$` (alphanumeric + underscore/hyphen only)
- Max length: 100 characters
- Prevents injection attacks (SQL, XSS, command injection)

**Conversation Ownership**:
- Always validate `conv.user_id == request.user_id` before access
- Return 403 Forbidden if ownership check fails
- Prevents horizontal privilege escalation

### Rate Limiting (Future)

Not implemented in Phase 1, but recommended for production:
- Track requests per user_id (in-memory counter)
- Limit: 100 requests/hour per user_id
- Returns 429 Too Many Requests when exceeded

### Privacy Guarantees

- No PII stored (no email, IP address logging)
- User IDs are random, non-sequential (no enumeration attacks)
- Conversations auto-expire after 1 hour inactivity (existing cleanup)
- No server-side tracking across sessions

## Migration Path to Authenticated Users

**Phase 2 Enhancement** (optional):

1. Add `users` table with email/password
2. Add `user_id` column to database-backed conversations table
3. Implement `/auth/register` and `/auth/login` endpoints
4. Allow "Link Anonymous Session" flow:
   - User signs in → Backend merges `anon_123` conversations into authenticated user
   - Frontend updates localStorage to use authenticated user_id
5. Enable cross-device sync (conversations stored in database)

**Backwards Compatibility:**
- Existing anonymous users continue working
- No breaking changes to API (user_id already required)
- Frontend checks if user is authenticated, shows "Sign In to Sync" banner

## Implementation Status

✅ **Completed (December 2025)**

All backend and frontend changes implemented and tested:
- User ID generation and localStorage persistence
- API integration with user_id on all endpoints
- Conversation isolation and ownership validation
- Multi-user testing with 403 error enforcement
- Fixed SSR compatibility and "Backend Offline" false indicator

See `archive/25_anonymous_user_sessions_implementation_20251207.md` for detailed implementation steps.

## Alternatives Considered

### Option 1: Server-Side Session Cookies
**Rejected**: Requires session storage backend (Redis), adds complexity, cookie issues with CORS

### Option 2: IP-Based Identification
**Rejected**: NAT/VPN users share IPs, privacy concerns, not persistent across network changes

### Option 3: Database-Backed Anonymous Users
**Rejected**: Overkill for Phase 1, requires migration scripts, adds latency

### Option 4: No User Isolation (Status Quo)
**Rejected**: Multi-user deployment impossible, conversations leak between users

## Open Questions

1. **Should we show user_id in UI for debugging?**
   - Recommendation: Add hidden debug panel (Ctrl+Shift+D) showing user_id

2. **How long should conversations persist?**
   - Current: 1 hour inactivity timeout (existing cleanup)
   - Alternative: 24 hours for better UX?

3. **Should we support "Clear All Data" button?**
   - Recommendation: Yes, add to settings panel (localStorage.clear())

## References

- Existing conversation management: `docs/22_conversation_management.md`
- Frontend architecture: `docs/20_ui_architecture.md`
- API endpoints: `app/main.py:161-190` (conversation endpoints)
