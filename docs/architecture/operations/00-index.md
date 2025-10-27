# Operations Architecture Documentation Index

## Overview

This directory contains the complete architectural documentation for the KTRDR Operations Service refactoring from push-based to pull-based architecture.

## Document Reading Order

### Phase 1: Understanding the Problem
1. **[01-problem-statement-producer-consumer-antipattern.md](./01-problem-statement-producer-consumer-antipattern.md)**
   - Identifies the push-based anti-pattern
   - Documents runtime failures (M2 metrics not flowing)
   - Explains threading boundary violations

2. **[03-deep-architectural-analysis-operations-service.md](./03-deep-architectural-analysis-operations-service.md)**
   - Exhaustive analysis of current architecture
   - Code traces through entire stack
   - Performance analysis and root cause investigation

### Phase 2: The Solution
3. **[04-design-pull-based-operations.md](./04-design-pull-based-operations.md)** ⭐ **START HERE**
   - **The core design document**
   - Explains the elegant pull-based architecture
   - Component responsibilities and interactions
   - Design rationale and trade-offs

4. **[05-architecture-pull-based-operations.md](./05-architecture-pull-based-operations.md)**
   - Detailed technical specifications
   - Component interfaces and data models
   - API contracts and sequence diagrams
   - Deployment architecture

### Phase 3: Implementation
5. **[06-implementation-plan-pull-based-operations.md](./06-implementation-plan-pull-based-operations.md)**
   - 5-phase implementation roadmap (4-5 weeks)
   - Detailed tasks with estimates
   - Testing strategy and rollback procedures
   - Risk assessment and success metrics

6. **[02-proposal-pull-based-operations-architecture.md](./02-proposal-pull-based-operations-architecture.md)**
   - Early proposal document (superseded by 04-design)
   - Historical reference

## Quick Reference

### The Core Insight
**State lives where it's produced. Consumers read on-demand, when they need it.**

Workers write to fast local memory (<1μs), clients pull fresh data when needed, and the same simple architecture works everywhere—whether operations run locally in Docker or remotely in host services.

### Key Components

```
Client Layer
    ↓ HTTP Query
OperationsService (Smart Cache)
    ├─ Cache hit → Return immediately
    └─ Cache miss → Refresh via adapter
        ↓
Service Adapter (Service-Specific)
    ├─ Domain methods (start_training, fetch_data)
    └─ OperationServiceProxy (Shared, Generic)
        └─ HTTP GET /operations/{id}
            ↓
Host Service OperationsService
    └─ ProgressBridge (Local State)
        ↑
Worker (fast writes, <1μs)
```

### Architecture Principles

1. **Locality of Reference**: State lives where it's produced
2. **Lazy Evaluation**: Don't compute until needed
3. **Cache as Contract**: Explicit TTL-based caching
4. **Uniform Interfaces**: Same API everywhere
5. **Explicit Over Implicit**: No background magic
6. **Separation of Concerns**: Each component has one job

### Component Responsibilities

| Component | Responsibility | Location |
|-----------|---------------|----------|
| **ProgressBridge** | Fast state storage | With worker (local or host) |
| **OperationsService** | CRUD + caching | Backend + host services |
| **ServiceAdapter** | Service-specific logic | Backend only |
| **OperationServiceProxy** | Generic HTTP client | Shared across adapters |
| **HealthService** | Monitoring + timeouts | Backend only |

## Current Status

**Status**: PROPOSED
**Date**: 2025-01-20
**Next Step**: Team review and approval

## Related Documents

- **Problem Analysis**: [01-problem-statement](./01-problem-statement-producer-consumer-antipattern.md), [03-deep-analysis](./03-deep-architectural-analysis-operations-service.md)
- **Architecture**: Training metrics exposure at `docs/architecture/training/metrics-exposure/`
- **Project Guidelines**: `CLAUDE.md` (will be updated after implementation)

## Questions?

For questions about:
- **Design rationale**: See [04-design-pull-based-operations.md](./04-design-pull-based-operations.md) Section 6
- **Component details**: See [05-architecture-pull-based-operations.md](./05-architecture-pull-based-operations.md) Section 2
- **Implementation timeline**: See [06-implementation-plan-pull-based-operations.md](./06-implementation-plan-pull-based-operations.md) Phase Overview

---

**Document Version**: 1.0
**Last Updated**: 2025-01-20
