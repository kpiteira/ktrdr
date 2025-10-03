# KTRDR Async Architecture Documentation

**Status**: Slices 1,2,3,5 Complete | Slice 4 Pending
**Last Updated**: 2025-10-03

This directory contains all documentation for KTRDR's ServiceOrchestrator-based async architecture.

---

## 📖 Start Here

### Primary Documentation (Read First)

1. **[ARCHITECTURE.md](ARCHITECTURE.md)** - Complete architectural specification (1,700+ lines)
   - ServiceOrchestrator foundation
   - Progress and cancellation architecture
   - Data and Training domain patterns
   - Host service integration
   - End-to-end flows and diagrams
   - **This is the Single Source of Truth**

2. **[IMPLEMENTATION-STATUS.md](IMPLEMENTATION-STATUS.md)** - Current progress and gaps
   - What's implemented (Slices 1,2,3,5)
   - What's pending (Slice 4)
   - Technical debt tracking
   - Performance metrics

3. **[guides/service-orchestrator-pattern.md](guides/service-orchestrator-pattern.md)** - Developer quick-start
   - How to use ServiceOrchestrator
   - Common patterns (simple delegation vs complex orchestration)
   - Code examples and recipes
   - Do's and don'ts

---

## 🚧 Current Work

### Slice 4: Host Service Integration (NOT STARTED) 🔴

**Critical Gap**: AsyncServiceAdapter infrastructure missing

**Impact**:
- ❌ No connection pooling (30%+ performance improvement missed)
- ❌ TrainingAdapter creates new HTTP client for each request
- ❌ No unified patterns between IbDataAdapter and TrainingAdapter

**See**: [slices/pending/SLICE-4-HOST-SERVICE-INTEGRATION.md](slices/pending/SLICE-4-HOST-SERVICE-INTEGRATION.md)

---

## ✅ Completed Work

All completed slice specifications: [slices/completed/](slices/completed/)

- **Slice 1**: Generic Progress Foundation
- **Slice 2**: Cancellation Enhancement
- **Slice 3**: Training System Integration
- **Slice 5**: Training Service Orchestrator Migration

---

## 📁 Directory Structure

```
docs/architecture/async/
├── README.md                          # This file - navigation hub
├── ARCHITECTURE.md                    # Complete architecture spec (Single Source of Truth)
├── IMPLEMENTATION-STATUS.md           # Current state and gaps
│
├── guides/                            # Developer guides
│   └── service-orchestrator-pattern.md  # How to use the pattern
│
├── slices/                            # Organized slice specifications
│   ├── completed/                     # Finished slices (1,2,3,5)
│   │   ├── SLICE-1-PROGRESS-FOUNDATION.md
│   │   ├── SLICE-2-CANCELLATION-ENHANCEMENT.md
│   │   ├── SLICE-3-TRAINING-INTEGRATION.md
│   │   └── SLICE-5-TRAINING-ORCHESTRATOR.md
│   └── pending/                       # Pending work
│       └── SLICE-4-HOST-SERVICE-INTEGRATION.md
│
└── archive/                           # Historical documents (preserved)
    ├── specs/                         # Superseded specifications
    ├── learnings/                     # Valuable diagnostics and insights
    └── deprecated-tasks/              # Unused task variants
```

---

## 🎯 Quick Navigation

| Looking for... | Go to... |
|----------------|----------|
| **Complete architecture** | [ARCHITECTURE.md](ARCHITECTURE.md) |
| **What's done/pending** | [IMPLEMENTATION-STATUS.md](IMPLEMENTATION-STATUS.md) |
| **How to use ServiceOrchestrator** | [guides/service-orchestrator-pattern.md](guides/service-orchestrator-pattern.md) |
| **Completed slices** | [slices/completed/](slices/completed/) |
| **Pending work (Slice 4)** | [slices/pending/SLICE-4-HOST-SERVICE-INTEGRATION.md](slices/pending/SLICE-4-HOST-SERVICE-INTEGRATION.md) |
| **Historical context** | [archive/](archive/) |

---

## 📊 Key Metrics

### Implementation Progress
- **Completed**: 4 of 5 slices (80%)
- **In Production**: Slices 1,2,3,5 fully operational
- **Pending**: Slice 4 (AsyncServiceAdapter infrastructure)

### Code Statistics
- Async infrastructure: ~2,000 lines
- ServiceOrchestrator: ~500 lines
- Progress/Cancellation: ~800 lines
- Adapters: ~700 lines

### Performance
- ✅ Cancellation response: <1 second
- ✅ Progress overhead: Minimal
- ⏳ Connection pooling: Not yet implemented (30%+ improvement pending)

---

## 🔑 Key Concepts

### ServiceOrchestrator Pattern
All async operations inherit from `ServiceOrchestrator` providing:
- Unified progress reporting with domain-specific renderers
- Consistent cancellation across all operations
- Environment-based local vs host service routing
- Operations service integration

### Domain-Specific Enhancement
Each domain (Data, Training) extends the foundation:
- **Data**: Complex job orchestration with DataJobManager
- **Training**: Simple delegation with progress bridging

### Progress Architecture
Structured progress context eliminates CLI string parsing:
```python
{
    "symbol": "AAPL",
    "timeframe": "1h",
    "mode": "backfill",
    "segment": 3,
    "total_segments": 5
}
```

### Cancellation Flow
Unified cancellation propagates through:
1. ServiceOrchestrator
2. Domain managers (DataManager, TrainingManager)
3. Job managers or adapters
4. Host services (when applicable)

---

## 🎓 For New Developers

### Onboarding Path

1. **Read** [ARCHITECTURE.md](ARCHITECTURE.md) (30-45 minutes)
   - Focus on sections relevant to your domain (Data or Training)
   - Understand ServiceOrchestrator foundation
   - Review domain-specific patterns

2. **Study** [guides/service-orchestrator-pattern.md](guides/service-orchestrator-pattern.md) (15 minutes)
   - Quick-start guide with code examples
   - Common patterns and recipes

3. **Check** [IMPLEMENTATION-STATUS.md](IMPLEMENTATION-STATUS.md) (5 minutes)
   - Current state and gaps
   - Known technical debt

4. **Explore** Reference Implementations
   - Simple delegation: [TrainingService](../../ktrdr/api/services/training_service.py)
   - Complex orchestration: [DataManager](../../ktrdr/data/data_manager.py)

**Total time**: ~1 hour to full understanding

---

## 🗄️ Archive

Historical documents preserved in [archive/](archive/):

- `archive/specs/` - Superseded specifications (unified spec, training design doc)
- `archive/learnings/` - Valuable diagnostics (slice-3 learnings, dummy service reference)
- `archive/deprecated-tasks/` - Unused task variants

**Note**: Nothing is deleted - all historical context preserved for reference.

---

## 🔄 Document Lifecycle

| Document | Status | Update Frequency |
|----------|--------|------------------|
| ARCHITECTURE.md | Living | Updated when architecture changes |
| IMPLEMENTATION-STATUS.md | Living | Updated when slices complete |
| guides/ | Stable | Updated when patterns evolve |
| slices/completed/ | Stable | Historical reference |
| slices/pending/ | Active | Updated during implementation |
| archive/ | Frozen | Preserved for history |

---

## ❓ Common Questions

**Q: Which spec should I read first?**
A: Start with [ARCHITECTURE.md](ARCHITECTURE.md) - it's the single authoritative source.

**Q: What's the difference between DataManager and TrainingManager?**
A: Data uses complex job orchestration (multi-step), Training uses simple delegation (single-block). See [ARCHITECTURE.md § Architectural Patterns Comparison](ARCHITECTURE.md#architectural-patterns--comparisons).

**Q: Why isn't Slice 4 implemented?**
A: Slice 4 is a performance optimization (connection pooling), not a functional requirement. The system works correctly without it. See [IMPLEMENTATION-STATUS.md § Slice 4](IMPLEMENTATION-STATUS.md#slice-4-host-service-integration-not-started--critical-gap).

**Q: How do I add a new async service?**
A: Follow the [ServiceOrchestrator Pattern Guide](guides/service-orchestrator-pattern.md) with examples from existing services.

**Q: Where can I find the old specs?**
A: All superseded documents are in [archive/specs/](archive/specs/).

---

**For questions or clarifications**, refer to the specific sections in [ARCHITECTURE.md](ARCHITECTURE.md) or [IMPLEMENTATION-STATUS.md](IMPLEMENTATION-STATUS.md).
