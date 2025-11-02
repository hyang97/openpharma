# OpenPharma Product Backlog

Last updated: 2025-10-27

## Backlog Organization

This backlog is organized by:
- **Priority**: P0 (Critical) → P3 (Nice-to-have)
- **Status**: 🔴 Not Started, 🟡 In Progress, 🟢 Done, ❌ Blocked, 🔵 On Hold
- **Effort**: S (Small, <4 hrs), M (Medium, 4-16 hrs), L (Large, 16-40 hrs), XL (Extra Large, 40+ hrs)
- **Impact**: High, Medium, Low
- **Category**: Performance, Data Quality, UX, Infrastructure, Code Quality, Security

## How to Track Completion

1. **Update status emoji** when starting/completing tasks
2. **Add completion date** in notes when marking 🟢 Done
3. **Move completed items** to `archive/BACKLOG_completed_YYYYMMDD.md` during session wrap-up
4. **Update TODO.md** for active sprint tasks (granular day-to-day tracking)
5. **Use BACKLOG.md** for strategic planning and quarterly review

### Workflow
- **Daily work**: Use TODO.md for current sprint tasks
- **Weekly review**: Update BACKLOG.md status emojis
- **Monthly review**: Archive completed items, re-prioritize remaining
- **Quarterly review**: Add new items, adjust priorities based on feedback

---

## P0 - Critical (Do First)

### Data & Infrastructure

| ID | Status | Task | Effort | Impact | Category | Notes |
|----|--------|------|--------|--------|----------|-------|
| P0-1 | 🟡 | Complete historical paper ingestion pipeline | XL | High | Data Quality | Run stages 2-4 for 58K historical papers. |
| P0-2 | 🟢 | Complete reranking evaluation | M | High | Performance | Completed: 2025-10-27. Decision: Deploy reranker (ms-marco-MiniLM-L-6-v2). |
| P0-3 | 🔴 | Add basic error handling with retries | M | High | Infrastructure | No retry logic for API failures. Production reliability issue. |
| P0-4 | 🔴 | Implement log rotation policy | S | Medium | Infrastructure | Logs at 1.1MB with no rotation. Will grow unbounded. |

### Performance

| ID | Status | Task | Effort | Impact | Category | Notes |
|----|--------|------|--------|--------|----------|-------|
| P0-5 | 🔴 | Test lighter models for faster inference | M | High | Performance | Try phi4-mini, llama3.2:3b. Target: <30s response time. |
| P0-6 | 🔴 | Implement response streaming (SSE) | M | High | UX | Improve perceived latency. 18-40s feels slow without streaming. |

---

## P1 - High Priority (Do Next)

### Monitoring & Observability

| ID | Status | Task | Effort | Impact | Category | Notes |
|----|--------|------|--------|--------|----------|-------|
| P1-1 | 🔴 | Add Prometheus metrics endpoint | M | High | Infrastructure | Track query latency, chunk similarity, citation counts |
| P1-2 | 🔴 | Create query analytics table | S | Medium | Infrastructure | Track popular topics, zero-result queries, user behavior |
| P1-3 | 🔴 | Add performance dashboard | M | Medium | Infrastructure | Simple /stats endpoint or Grafana |
| P1-4 | 🔴 | Add Ollama service health check | S | High | Infrastructure | Detect when embedding/LLM service is down |

### Security & Production Readiness

| ID | Status | Task | Effort | Impact | Category | Notes |
|----|--------|------|--------|--------|----------|-------|
| P1-5 | 🔴 | Implement API rate limiting | M | High | Security | Vulnerable to abuse without limits |
| P1-6 | 🔴 | Add input validation and sanitization | S | High | Security | Max length, XSS prevention, content filtering |
| P1-7 | 🔴 | Add request size limits | S | Medium | Security | Prevent 10MB message attacks |
| P1-8 | 🔴 | Implement conversation persistence | M | High | Infrastructure | Currently in-memory (lost on restart). Use Redis or DB. |
| P1-9 | 🔴 | Add API authentication | L | Medium | Security | Anyone can access currently. Add token-based auth. |

### Code Quality

| ID | Status | Task | Effort | Impact | Category | Notes |
|----|--------|------|--------|--------|----------|-------|
| P1-10 | 🔴 | Refactor app/main.py (292 lines) | M | Medium | Code Quality | Split into api/, utils/ modules. Extract text processing. |
| P1-11 | 🔴 | Remove commented-out code | S | Low | Code Quality | generation.py lines 130-136, others |
| P1-12 | 🔴 | Add centralized configuration management | S | Medium | Code Quality | Consolidate env vars, validate on startup |
| P1-13 | 🔴 | Enforce Ollama version check on startup | S | Medium | Infrastructure | Critical requirement (0.11.x) not validated |

### User Experience

| ID | Status | Task | Effort | Impact | Category | Notes |
|----|--------|------|--------|--------|----------|-------|
| P1-14 | 🔴 | Add React error boundaries | S | High | UX | Crashes break entire app currently |
| P1-15 | 🔴 | Add retry button for failed API calls | S | Medium | UX | Users stuck when API fails |
| P1-16 | 🔴 | Add request timeout on frontend | S | Medium | UX | No timeout currently (line 93 page.tsx) |
| P1-17 | 🔴 | Add loading state for citations | S | Low | UX | Users don't know if citations are loading |

---

## P2 - Medium Priority (Do Soon)

### Performance Optimization

| ID | Status | Task | Effort | Impact | Category | Notes |
|----|--------|------|--------|--------|----------|-------|
| P2-1 | 🔴 | Optimize prompt length | S | Medium | Performance | Current: 71 lines. Target: 30-40 lines. |
| P2-2 | 🔴 | Test reduced context window | S | Medium | Performance | Try top_n=3-4 instead of 5 |
| P2-3 | 🔴 | Explore model quantization (Q4/Q5) | M | Medium | Performance | Faster inference, minimal quality loss |
| P2-4 | 🔴 | Optimize database queries | M | Medium | Performance | Add indexes on fetch_status, pmc_id |
| P2-5 | 🔴 | Optimize SQLAlchemy connection pooling | S | Low | Performance | Verify pool settings are optimized |

### Evaluation & Quality

| ID | Status | Task | Effort | Impact | Category | Notes |
|----|--------|------|--------|--------|----------|-------|
| P2-6 | 🔴 | Implement RAGAS evaluation framework | L | High | Data Quality | Critical for ongoing quality monitoring. 95%+ citation accuracy target. |
| P2-7 | 🔴 | Add systematic response quality testing | M | Medium | Data Quality | Automated test suite for answer quality |
| P2-8 | 🔴 | Measure and track citation accuracy | M | High | Data Quality | Verify claims match source chunks |

### User Experience

| ID | Status | Task | Effort | Impact | Category | Notes |
|----|--------|------|--------|--------|----------|-------|
| P2-9 | 🔴 | Add conversation age indicators | S | Low | UX | Show last_updated in sidebar |
| P2-10 | 🔴 | Add search within conversation history | M | Medium | UX | Find past conversations |
| P2-11 | 🔴 | Add export/download conversation | M | Low | UX | PDF or markdown export |
| P2-12 | 🔴 | Show retrieval confidence scores | S | Medium | UX | Help users understand answer quality |
| P2-13 | 🔴 | Add "related questions" suggestions | M | Medium | UX | Guide users to explore topics |
| P2-14 | 🔴 | Add query suggestions/autocomplete | L | Low | UX | Requires query history analysis |

### Advanced RAG Features

| ID | Status | Task | Effort | Impact | Category | Notes |
|----|--------|------|--------|--------|----------|-------|
| P2-15 | 🔴 | Implement query rewriting | M | Medium | Performance | Improve multi-turn retrieval (documented but not implemented) |
| P2-16 | 🔴 | Re-evaluate hybrid retrieval | M | Medium | Performance | Currently commented out. Test with better models. |
| P2-17 | 🔴 | Add metadata filtering | M | Medium | UX | Filter by journal, date range, author |
| P2-18 | 🔴 | Add explanation for chunk selection | M | Low | UX | Show why certain chunks were retrieved |

---

## P3 - Low Priority (Future)

### Data Quality

| ID | Status | Task | Effort | Impact | Category | Notes |
|----|--------|------|--------|--------|----------|-------|
| P3-1 | 🔴 | Add paper quality scoring | M | Medium | Data Quality | Journal impact factor, citation count |
| P3-2 | 🔴 | Detect and filter predatory journals | L | Low | Data Quality | Requires external journal database |
| P3-3 | 🔴 | Add paper version tracking | L | Low | Data Quality | Many papers get updated |
| P3-4 | 🔴 | Enhanced metadata extraction | L | Low | Data Quality | Author affiliations, MeSH terms |
| P3-5 | 🔴 | Clean up 418K chunks without embeddings | S | Low | Data Quality | After P0-2 completes, remove orphaned chunks |

### Advanced Features

| ID | Status | Task | Effort | Impact | Category | Notes |
|----|--------|------|--------|--------|----------|-------|
| P3-6 | 🔴 | Multi-modal support (tables, figures) | XL | Medium | UX | Extract and reason over tables/figures from papers |
| P3-7 | 🔴 | Cross-document reasoning | L | Medium | Performance | Compare findings across multiple studies |
| P3-8 | 🔴 | Citation network visualization | L | Low | UX | Graph view of paper relationships |
| P3-9 | 🔴 | Add KOL identification | M | Medium | UX | Most-cited authors, co-citation analysis |

### Deployment & Scalability

| ID | Status | Task | Effort | Impact | Category | Notes |
|----|--------|------|--------|--------|----------|-------|
| P3-10 | 🔴 | Migrate to GCP Cloud Run | L | Medium | Infrastructure | Currently Cloudflare Tunnel + laptop |
| P3-11 | 🔴 | Add Redis for conversation caching | M | Medium | Infrastructure | Replace in-memory storage |
| P3-12 | 🔴 | Implement horizontal API scaling | L | Low | Infrastructure | Currently single instance |
| P3-13 | 🔴 | Add CDN for UI assets | S | Low | Infrastructure | Vercel already handles this well |

### Documentation

| ID | Status | Task | Effort | Impact | Category | Notes |
|----|--------|------|--------|--------|----------|-------|
| P3-14 | 🔴 | Create API documentation | M | Low | Code Quality | OpenAPI/Swagger docs |
| P3-15 | 🔴 | Add contributing guidelines | S | Low | Code Quality | If open-sourcing |
| P3-16 | 🔴 | Create video demo/walkthrough | M | Low | UX | Marketing/user onboarding |

---

## Quick Wins (High Impact, Low Effort)

These tasks provide immediate value with minimal time investment:

1. **P0-5**: Add log rotation policy (2 hrs)
2. **P1-4**: Add Ollama service health check (2 hrs)
3. **P1-6**: Add input validation and sanitization (3 hrs)
4. **P1-7**: Add request size limits (1 hr)
5. **P1-11**: Remove commented-out code (1 hr)
6. **P1-13**: Enforce Ollama version check (2 hrs)
7. **P1-14**: Add React error boundaries (2 hrs)
8. **P1-15**: Add retry button for failed requests (2 hrs)
9. **P1-16**: Add request timeout on frontend (1 hr)
10. **P2-1**: Optimize prompt length (2 hrs)

**Total Quick Wins Time: ~18 hours** → Can complete in 2-3 focused work sessions

---

## Metrics & Success Criteria

### Performance
- Response time: <30s (current: 18-40s)
- P95 latency: <45s
- Retrieval time: <300ms
- Uptime: 99%+

### Quality
- Citation accuracy: 95%+ (RAGAS)
- RAGAS faithfulness score: >0.8
- RAGAS answer relevance: >0.8
- Zero-result queries: <5%

### User Experience
- Error rate: <1%
- API timeout rate: <0.5%
- Average conversation length: 3+ turns

### Infrastructure
- API response time P95: <45s
- Database query time P95: <200ms
- Log storage: <100MB/week

---

## Notes

- This backlog assumes continued Phase 1 focus (research literature RAG MVP)
- Phase 2 items (ClinicalTrials.gov, FDA integration, agents) not included
- Phase 3 items (self-hosted vLLM, fine-tuning) not included
- Estimated efforts are rough guidelines, not commitments
- Re-prioritize based on user feedback after deployment

---

## Change Log

- 2025-10-27: Initial backlog created from codebase analysis
- 2025-10-27: Deleted sprint planning
- 2025-10-27: P0-2 marked complete - reranker deployment decision made (using ms-marco-MiniLM-L-6-v2)
- 2025-10-27: Removed P0-2 (redundant with P0-1), renumbered P0-3→P0-6 accordingly