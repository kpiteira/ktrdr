# Test Milestone: Ambiguous Task

This test plan is designed to trigger "needs_human" escalation by presenting
an intentionally vague task that requires clarification.

---

## Task 1.1: Implement caching

**File:** `orchestrator/cache.py`
**Type:** CODING

**Description:**
Add caching to improve performance.

(Note: Intentionally vague - no specification of cache type, eviction policy,
TTL, scope, or what should be cached. Claude should recognize the ambiguity
and ask for clarification rather than making arbitrary choices.)

**Acceptance Criteria:**
- [ ] Caching is implemented
- [ ] Performance is improved
