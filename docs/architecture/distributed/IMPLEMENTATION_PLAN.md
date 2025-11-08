# Distributed Training & Backtesting Implementation Plan
## DRAFT - Subject to Architecture Review

**Version**: 0.1 DRAFT
**Status**: Preliminary - Not Yet Reviewed
**Date**: 2025-11-08

---

## ⚠️ Notice

This is a **preliminary implementation plan** extracted from the design document. It is based on the current design but **has not been finalized**.

**Next Steps:**
1. Review and approve ARCHITECTURE.md
2. Revise this implementation plan based on architecture feedback
3. Finalize phases, tasks, and timelines
4. Begin implementation

---

## Implementation Phases

### Phase 1: Development Setup (Week 1)

**Goal**: Enable local development with worker scaling

**Tasks**:
1. Create `docker-compose.dev.yml` with backend + workers
2. Implement worker registration API (`POST /workers/register`)
3. Add worker startup scripts with registration logic
4. Test local scaling: `docker-compose up --scale backtest-worker=3`
5. Validate concurrent operations (3 backtests simultaneously)

**Deliverables**:
- [ ] Docker Compose configuration
- [ ] Worker registration API implemented
- [ ] Workers self-register on startup
- [ ] Backend routes operations to registered workers
- [ ] Progress tracking works end-to-end

**Success Criteria**: Can run 3 concurrent backtests on Mac, workers visible in registry

---

### Phase 2: Worker Registry Foundation (Week 2)

**Goal**: Implement worker lifecycle management

**Tasks**:
1. Implement `WorkerRegistry` class with registration
2. Implement health checking background task (10s interval)
3. Implement cleanup task (remove dead workers after 5min)
4. Add round-robin load balancing
5. Add worker list API for monitoring

**Deliverables**:
- [ ] WorkerRegistry with push-based registration
- [ ] Health checks running every 10s
- [ ] Dead worker cleanup after 5min unavailability
- [ ] Worker re-registration working (idempotent)

**Success Criteria**: Workers auto-register, health status tracked, dead workers removed

---

### Phase 3: Production LXC Setup (Week 3)

**Goal**: Deploy to Proxmox with LXC workers

**Tasks**:
1. Create LXC template with KTRDR environment
2. Add worker startup script with registration logic
3. Clone template to create workers (3 training, 5 backtesting)
4. Configure systemd services for auto-start
5. Deploy backend to Proxmox

**Deliverables**:
- [ ] LXC template ready with registration script
- [ ] 8 LXC workers running (3 training, 5 backtesting)
- [ ] Workers self-register on startup
- [ ] Backend accepts LXC worker registrations

**Success Criteria**: Production backend routes to LXC workers, workers auto-register on start

---

### Phase 4: Integration & Testing (Week 4)

**Goal**: Validate entire system end-to-end

**Tasks**:
1. End-to-end testing (dev and prod)
2. Load testing (10 concurrent training + 20 concurrent backtesting)
3. Failure testing (worker crashes, network issues)
4. Performance tuning (cache TTL, health check intervals)
5. Documentation updates

**Deliverables**:
- [ ] All tests passing
- [ ] Load test results documented
- [ ] Failure recovery validated
- [ ] Performance baseline established

**Success Criteria**: System handles expected load, recovers from failures gracefully

---

## Timeline

**Total Estimated Duration**: 4 weeks

| Phase | Duration | Dependencies |
|-------|----------|--------------|
| Phase 1: Dev Setup | 1 week | None |
| Phase 2: Worker Registry | 1 week | Phase 1 complete |
| Phase 3: Production LXC | 1 week | Phase 2 complete |
| Phase 4: Testing | 1 week | Phase 3 complete |

**Note**: This timeline is preliminary and subject to revision after architecture review.

---

## Risk Assessment

**Medium Risk Items**:
- Worker registration reliability across network failures
- Health check tuning (false positives/negatives)
- LXC template creation and cloning automation

**Low Risk Items**:
- Docker Compose configuration (standard Docker patterns)
- Worker API implementation (existing patterns)
- Testing infrastructure (existing test framework)

---

## Open Questions

These questions should be addressed during architecture review:

1. **Backend URL Discovery**: How do workers discover backend URL?
   - Environment variable?
   - DNS-based discovery?
   - Configuration file?

2. **Worker ID Generation**: How to ensure unique worker IDs?
   - Hostname-based?
   - UUID-based?
   - Manual configuration?

3. **Security**: Should worker registration require authentication?
   - API token?
   - Mutual TLS?
   - No authentication (trusted network)?

4. **Monitoring**: What metrics should be exposed?
   - Prometheus endpoints?
   - Log aggregation?
   - Custom dashboard?

---

## Next Steps

1. ✅ Review DESIGN.md (completed)
2. ⏳ Review ARCHITECTURE.md (in progress)
3. ⏳ Finalize this implementation plan based on architecture feedback
4. ⏳ Begin Phase 1 implementation

---

**Document Status**: DRAFT - Do not use for implementation until finalized
