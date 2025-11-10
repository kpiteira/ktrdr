# Design Document: Documentation System Refactoring

## Document Information

- **Date**: 2025-01-10
- **Status**: PROPOSED
- **Supersedes**: Current scattered documentation structure
- **Related**: Task 5.4 (distributed workers docs), Task 6.6 (Proxmox docs)

---

## Executive Summary

This document describes a comprehensive refactoring of KTRDR's documentation system to address 5-6 months of accumulated technical debt, establish clear documentation taxonomy, and implement guardrails for maintaining documentation quality going forward.

**The Core Problem**: Documentation scattered across multiple locations (`docs/`, `specification/`, `docs/architecture/`, root-level files) with unclear status, stale content, and no quality enforcement.

**The Result**: Single unified documentation structure with clear taxonomy, automated quality checks, and enforced documentation practices integrated into development workflow.

---

## Table of Contents

1. [The Design](#the-design)
2. [Documentation Taxonomy](#documentation-taxonomy)
3. [Core Principles](#core-principles)
4. [Migration Strategy](#migration-strategy)
5. [Quality Guardrails](#quality-guardrails)
6. [Design Rationale](#design-rationale)
7. [Success Criteria](#success-criteria)

---

## 1. The Design

### The Big Picture

Imagine a documentation system where:

1. **One location for everything**: All documentation lives in `docs/`, organized by purpose and audience
2. **Clear taxonomy**: 5 document types, each with clear purpose and audience
3. **Status transparency**: Every document clearly indicates if it's current, obsolete, or future work
4. **Quality enforcement**: Automated checks ensure docs stay current and complete
5. **Integrated workflow**: Documentation is part of the development process, not an afterthought

That's it. That's the whole design.

### The Key Innovation

**Taxonomy-Driven Organization**: Documents are organized by PURPOSE and AUDIENCE, not by when they were created or which feature they document.

```
Current (CONFUSED):
docs/
├── architecture/  (specs from Oct-Nov 2025)
├── developer/  (some guides, some stale)
├── user-guides/  (some exist, many broken links)
├── 40+ root-level files (mix of everything)
specification/
├── current/  (6 months stale)
├── implemented/  (6 months stale)
├── future/  (good)
└── Archive/  (good)

Proposed (CLEAR):
docs/
├── specifications/  (how we DESIGNED and BUILT)
│   └── [initiatives]/
│       ├── 01-design.md
│       ├── 02-architecture.md
│       ├── 03-implementation-plan.md
│       └── README.md
├── architecture/  (high-level WHAT and HOW of current system)
│   ├── system-overview.md
│   ├── data-flow.md
│   └── distributed-workers.md
├── developer/  (HOW TO develop, extend, debug)
│   ├── testing-guide.md
│   ├── distributed-workers-guide.md
│   └── adding-indicators.md
├── user-guides/  (USING and OPERATING the system)
│   ├── cli-reference.md
│   ├── deployment.md
│   └── deployment-proxmox.md
├── api/  (API contract reference)
│   └── [auto-generated + examples]
└── _archive/  (historical docs)
    └── [organized by date]

**Note**: During transition (before refactoring), there's also:
├── architecture/  (CURRENTLY contains specifications - will be renamed)
└── architecture-overviews/  (TEMPORARY - will become architecture/)
```

### Why This Works

**For Developers**:
- Clear where to find information based on what they need
- Specifications show the evolution of thinking and design decisions
- Developer guides show HOW to work with the current system
- No confusion between "how we built it" and "how to use it"

**For Operators**:
- User guides focused on deployment and operation
- Clear distinction between Docker (dev) and Proxmox (prod)
- Troubleshooting guides in the right place

**For Maintainers** (including AI):
- Chronological specifications show architectural evolution
- Quality checks ensure docs stay current
- Slash commands enforce documentation as part of workflow

**The Beauty**: Same successful pattern from Oct-Nov 2025 (docs/architecture/), extended to ALL documentation with clear taxonomy.

---

## 2. Documentation Taxonomy

### Type 1: Specifications (Design → Architecture → Implementation)

**Purpose**: Historical record of HOW we designed and built features

**Location**: `docs/specifications/[initiative]/`

**Structure**:
```
docs/specifications/
├── operations/
│   ├── 01-problem-statement-producer-consumer-antipattern.md
│   ├── 02-proposal-pull-based-operations-architecture.md
│   ├── 03-deep-architectural-analysis-operations-service.md
│   ├── 04-design-pull-based-operations.md
│   ├── 05-architecture-pull-based-operations.md
│   ├── 06-implementation-plan-pull-based-operations.md
│   └── 00-index.md
├── data/
│   ├── 01-design-data-separation.md
│   ├── 02-architecture-data-separation.md
│   ├── 03-implementation-plan-v2-revised.md
│   └── OBSOLETE-03-implementation-plan-data-separation.md
├── distributed/
│   ├── DESIGN.md
│   ├── ARCHITECTURE.md
│   ├── IMPLEMENTATION_PLAN_PHASES_1-4.md
│   └── IMPLEMENTATION_PLAN_PHASES_5-6.md
└── [other initiatives...]
```

**Content**:
- Design rationale and trade-offs
- Architecture diagrams and component interaction
- Implementation plans with task tracking (checkboxes)
- Status updates as work progresses

**Audience**: Developers, future maintainers, AI assistants

**Key Characteristic**: **Living documents** - updated during implementation to reflect reality

**Winning Pattern** (Oct-Nov 2025):
- ✅ Write design BEFORE implementing
- ✅ Track tasks in implementation plan with checkboxes
- ✅ Update status as work completes
- ✅ Clearly mark obsolete versions

---

### Type 2: Architecture Overviews (Current System Understanding)

**Purpose**: High-level understanding of WHAT the system is and HOW it works NOW

**Location**: `docs/architecture/`

**Structure**:
```
docs/architecture/
├── system-overview.md           (30,000 ft view)
├── data-flow.md                 (data pipeline explanation)
├── async-infrastructure.md      (async patterns in KTRDR)
├── distributed-workers.md       (workers architecture)
├── service-orchestrator.md      (ServiceOrchestrator pattern)
├── host-services.md             (IB + GPU host services)
└── component-interaction.md     (how modules interact)
```

**Content**:
- High-level architectural diagrams
- Component interaction explanations
- Key patterns and principles
- Links to detailed specifications for deep dives

**Audience**: New developers, architects, technical stakeholders

**Key Characteristic**: **Extracted from specifications** - distilled, high-level view of current state

**Source Material**: Specifications from `docs/specifications/`, but simplified and current-state-focused

---

### Type 3: Developer Guides (Working WITH the System)

**Purpose**: HOW TO develop, extend, debug, and test

**Location**: `docs/developer/`

**Structure**:
```
docs/developer/
├── setup.md                        (development environment)
├── testing-guide.md                (how to test)
├── distributed-workers-guide.md    (creating/debugging workers)
├── adding-indicators.md            (extending indicators)
├── architecture-guidelines.md      (code patterns)
├── debugging-guide.md              (common issues)
└── contributing.md                 (PR process)
```

**Content**:
- Step-by-step how-to guides
- Code examples and patterns
- Testing strategies
- Debugging procedures
- Common pitfalls and solutions

**Audience**: Active developers extending or debugging the system

**Key Characteristic**: **Actionable** - focused on concrete tasks developers need to do

---

### Type 4: User Guides (USING and OPERATING the System)

**Purpose**: Operating and using KTRDR

**Location**: `docs/user-guides/`

**Structure**:
```
docs/user-guides/
├── cli-reference.md            (all CLI commands)
├── deployment.md               (Docker deployment)
├── deployment-proxmox.md       (Proxmox LXC deployment)
├── strategy-management.md      (working with strategies)
├── data-management.md          (loading and managing data)
├── monitoring.md               (health checks, metrics)
└── troubleshooting.md          (common operational issues)
```

**Content**:
- Deployment procedures
- Operational guides
- CLI command reference
- Configuration guides
- Troubleshooting

**Audience**: End users, operators, traders, DevOps

**Key Characteristic**: **Operational** - focused on running and using the system

---

### Type 5: API Reference (Endpoint Documentation)

**Purpose**: API contract reference

**Location**: `docs/api/`

**Structure**:
```
docs/api/
├── README.md                    (API overview)
├── ENDPOINT_REFERENCE.md        (all endpoints)
├── ARCHITECTURE.md              (API architecture)
├── CLIENT_INTEGRATION.md        (how to integrate)
├── TROUBLESHOOTING.md           (API debugging)
└── examples/
    ├── data-loading.md
    ├── training.md
    └── backtesting.md
```

**Content**:
- Endpoint reference (auto-generated from OpenAPI)
- Request/response examples
- Authentication and authorization
- Error codes and handling
- Rate limiting and pagination
- Integration examples

**Audience**: API consumers, frontend developers, integrators

**Key Characteristic**: **Reference** - comprehensive API contract documentation

---

## 3. Core Principles

### Principle 1: Single Source of Truth

**Rule**: All documentation lives in `docs/`. No exceptions.

**Rationale**: Scattered documentation leads to confusion, duplication, and staleness.

**Implementation**:
- Delete `specification/` folder entirely
- Move all valuable content from `specification/` to `docs/`
- All new docs go in `docs/`

---

### Principle 2: Purpose-Driven Organization

**Rule**: Documents are organized by purpose and audience, not by feature or date.

**Rationale**: Users come to documentation with questions like "How do I deploy?" not "What was built in October?"

**Implementation**:
- Specifications: organized by initiative (operations, data, distributed, etc.)
- Architecture: organized by topic (data-flow, workers, async, etc.)
- Developer: organized by task (testing, debugging, extending, etc.)
- User guides: organized by operation (deployment, monitoring, troubleshooting, etc.)

---

### Principle 3: Status Transparency

**Rule**: Every document clearly indicates its status: CURRENT, OBSOLETE, PROPOSED, HISTORICAL.

**Rationale**: Readers need to know if information is accurate or outdated.

**Implementation**:
- All specifications have "Status" header (PROPOSED → IN PROGRESS → IMPLEMENTED)
- Obsolete files prefixed with `OBSOLETE-` or moved to `_archive/`
- README.md in each folder summarizes current vs historical docs

---

### Principle 4: Quality Enforcement

**Rule**: Documentation is part of the development process, enforced by tooling.

**Rationale**: Without enforcement, documentation falls behind and becomes technical debt.

**Implementation**:
- Slash commands require documentation step
- Quality checks verify documentation completeness
- PR templates include documentation checklist
- Automated checks for broken links, stale dates

---

### Principle 5: Chronological Specifications

**Rule**: Specifications are kept chronologically to show architectural evolution.

**Rationale**: Understanding WHY decisions were made requires seeing the evolution of thinking.

**Implementation**:
- Old specifications are NOT deleted, they're marked as historical
- New specifications reference or supersede old ones
- Chronological reading shows evolution (e.g., pull-based ops superseded push-based)

---

## 4. Migration Strategy

### Phase 1: Establish New Structure (No Migration Yet)

**Goal**: Create the new taxonomy structure WITHOUT moving anything yet

**Actions**:
1. Rename `docs/architecture/` → `docs/specifications/`
2. Rename `docs/architecture-overviews/` → `docs/architecture/` (if exists - from Tasks 5.4/6.6)
3. If `docs/architecture-overviews/` doesn't exist, create empty `docs/architecture/` (for overviews)
4. Verify `docs/developer/`, `docs/user-guides/`, `docs/api/` exist
5. Create `docs/_archive/` for historical docs

**Rationale**: Establish the target structure before migrating content.

**Note**: `docs/architecture-overviews/` is a temporary folder created by Tasks 5.4 and 6.6 (distributed workers documentation) to avoid confusion. It contains architecture overview documents that will become `docs/architecture/` after the specifications are moved.

---

### Phase 2: Delete Root-Level Cruft

**Goal**: Remove temporary and obsolete docs from `docs/` root

**Actions**:
1. Delete completion reports (feature-engineering-removal-completion.md, etc.)
2. Delete obsolete plans (IB_CONNECTION_REFACTOR_PLAN.md, etc.)
3. Delete phase0 docs (all phase0-*.md files)
4. Delete one-off fixes (CRITICAL_CHART_JUMPING_FIX.md, etc.)

**Rationale**: These are temporary documents that served their purpose and clutter the structure.

**List**: See Phase 2 in Implementation Plan for complete inventory.

---

### Phase 3: Audit and Categorize Remaining Docs

**Goal**: Evaluate every remaining doc and decide: Keep (which type?), Archive, or Delete

**Actions**:
1. Create inventory spreadsheet of all docs
2. For each doc, decide:
   - **Keep as Specification**: Move to `docs/specifications/`
   - **Keep as Architecture**: Move/extract to `docs/architecture/`
   - **Keep as Developer Guide**: Verify/update in `docs/developer/`
   - **Keep as User Guide**: Verify/update in `docs/user-guides/`
   - **Archive**: Move to `docs/_archive/[year]/`
   - **Delete**: Remove entirely
3. Mark status of each doc (CURRENT, OBSOLETE, etc.)

**Rationale**: Every doc must have a clear purpose or be removed.

---

### Phase 4: Extract Architecture Overviews

**Goal**: Create high-level architecture docs from specifications

**Actions**:
1. Extract `docs/architecture/distributed-workers.md` from `specifications/distributed/`
2. Extract `docs/architecture/async-infrastructure.md` from `specifications/operations/`
3. Extract `docs/architecture/data-flow.md` from `specifications/data/`
4. Create `docs/architecture/system-overview.md` (new, comprehensive)
5. Create `docs/architecture/service-orchestrator.md` (pattern explanation)

**Rationale**: Specifications are detailed and historical. Architecture docs are high-level and current.

---

### Phase 5: Migrate specification/ Folder

**Goal**: Eliminate `specification/` folder entirely

**Actions**:
1. Review `specification/current/` → Decide which are truly current
   - ADR-008: Move to `docs/architecture/` (current state assessment)
   - GPU acceleration: Move to `docs/specifications/future/`
   - Multi-symbol: Move to `docs/specifications/future/`
2. Review `specification/implemented/` → Delete (6 months stale, superseded by specs)
3. Review `specification/future/` → Move to `docs/specifications/future/`
4. Review `specification/research/` → Move to `docs/specifications/research/`
5. Keep `specification/Archive/` → Move to `docs/_archive/historical/`
6. Delete `specification/` folder

**Rationale**: All documentation should live in `docs/`.

---

### Phase 6: Fix docs/index.md and Create READMEs

**Goal**: Create accurate navigation and documentation index

**Actions**:
1. Rewrite `docs/index.md` with accurate links
2. Create `docs/specifications/README.md` (index of all specifications)
3. Create `docs/architecture/README.md` (guide to architecture docs)
4. Create `docs/developer/README.md` (guide to developer docs)
5. Create `docs/user-guides/README.md` (guide to user docs)
6. Update root `README.md` to link to `docs/`

**Rationale**: Users need clear entry points to find documentation.

---

## 5. Quality Guardrails

### Guardrail 1: Documentation Slash Command

**Goal**: Ensure every project/initiative has proper documentation

**Implementation**: New slash command `/document` or integrate into existing `/task`

**Behavior**:
- Checks if initiative has `docs/specifications/[name]/` folder
- Verifies 01-design.md, 02-architecture.md, 03-implementation-plan.md exist
- Checks if implementation plan has documentation tasks
- Warns if documentation is missing or incomplete

**Usage**:
```bash
# Check documentation for current work
/document distributed

# Output:
✅ Design document: docs/specifications/distributed/DESIGN.md
✅ Architecture document: docs/specifications/distributed/ARCHITECTURE.md
✅ Implementation plan: docs/specifications/distributed/IMPLEMENTATION_PLAN_PHASES_5-6.md
✅ Task 5.4: Documentation task exists (8 hours allocated)
✅ Task 6.6: Proxmox documentation task exists (6 hours allocated)

# Or if missing:
❌ No architecture overview in docs/architecture/
⚠️  Implementation plan missing documentation task
```

---

### Guardrail 2: Quality Check Slash Command

**Goal**: Verify specification quality and completeness

**Implementation**: New slash command `/check-spec [initiative]`

**Checks**:
1. **Structure**: Required files present (design, architecture, implementation plan)
2. **Status**: Status header present and valid (PROPOSED, IN PROGRESS, IMPLEMENTED)
3. **Links**: No broken internal links
4. **Tasks**: Implementation plan has task checkboxes for tracking
5. **Documentation**: Implementation plan includes documentation tasks
6. **Dates**: Documents have "Last Updated" or "Date" field
7. **Supersedes**: If obsolete version exists, new one declares it supersedes

**Usage**:
```bash
/check-spec distributed

# Output:
✅ Structure: All required documents present
✅ Status: IMPLEMENTATION_PLAN marked IN PROGRESS
✅ Links: No broken links found
✅ Tasks: 14 tasks tracked with checkboxes (6 complete, 8 pending)
✅ Documentation: 2 documentation tasks (5.4, 6.6)
✅ Dates: All documents have date headers
⚠️  Note: DESIGN.md last updated 2025-11-09 (1 day ago)
```

---

### Guardrail 3: PR Template with Documentation Checklist

**Goal**: Ensure PRs include necessary documentation updates

**Implementation**: Update `.github/pull_request_template.md`

**Checklist Items**:
- [ ] If new feature: Specification created in `docs/specifications/`
- [ ] If architectural change: Architecture overview updated
- [ ] If new pattern: Developer guide created/updated
- [ ] If deployment change: User guide updated
- [ ] If API change: API docs updated
- [ ] CLAUDE.md updated if architectural patterns changed
- [ ] No broken links (verified with link checker)

---

### Guardrail 4: Automated Link Checker

**Goal**: Prevent broken links in documentation

**Implementation**: GitHub Action or pre-commit hook

**Behavior**:
- Scans all markdown files in `docs/`
- Checks internal links (relative paths)
- Checks external links (with caching to avoid rate limits)
- Fails if broken links found
- Reports in CI/PR

---

### Guardrail 5: Documentation Freshness Checker

**Goal**: Identify stale documentation

**Implementation**: Script run monthly or on-demand

**Behavior**:
- Scans all docs for "Last Updated" or "Date" headers
- Reports docs not updated in >3 months
- Compares specification status with git history
  - If spec says "IN PROGRESS" but no commits in 3 months → flag as stale
  - If spec says "PROPOSED" but feature is implemented → flag for status update

---

## 6. Design Rationale

### Why 5 Document Types?

**Decision**: Separate specifications, architecture overviews, developer guides, user guides, and API docs

**Rationale**:
- **Different audiences**: Developers read differently than operators
- **Different purposes**: Learning architecture vs doing a task vs operating system
- **Different update cadence**: Specifications are historical, guides are living
- **Clear mental model**: "I need to deploy" → user-guides/deployment.md

**Alternative Considered**: Single flat structure or feature-based organization

**Why Rejected**: Feature-based doesn't answer "how do I...?" questions naturally

---

### Why Keep Old Specifications?

**Decision**: Don't delete old specs, mark them as obsolete or superseded

**Rationale**:
- **Architectural evolution**: Understanding WHY decisions were made
- **Context for future changes**: "Why did we choose pull-based? Read specs."
- **Learning resource**: Shows iteration and improvement over time
- **Historical debugging**: "When did we change from X to Y?"

**Example**:
- `data/03-implementation-plan-v2-revised.md` (current)
- `data/OBSOLETE-03-implementation-plan-data-separation.md` (superseded)

Seeing both shows the evolution of thinking and why v2 was needed.

---

### Why Enforce Documentation in Workflow?

**Decision**: Slash commands and PR templates require documentation

**Rationale**:
- **Without enforcement, docs lag**: Documentation is always "later" without forcing function
- **Cost of updating later is high**: Context is lost, requires re-learning
- **Quality compounds**: Good docs enable better future work
- **AI assistants need it**: Without current docs, AI makes wrong assumptions

**Alternative Considered**: Trust developers to document voluntarily

**Why Rejected**: 5-6 months of documentation debt proves this doesn't work

---

### Why Delete Temporary Docs Instead of Archive?

**Decision**: Delete completion reports, one-off fixes, phase0 docs

**Rationale**:
- **Git preserves history**: Can always recover if needed
- **Archive implies future value**: These docs have none
- **Reduces clutter**: Makes navigation easier
- **Clear signal**: Deletion says "this is done, move on"

**Alternative Considered**: Archive everything

**Why Rejected**: Archive becomes a dumping ground, still clutters navigation

---

## 7. Success Criteria

### Immediate Success (Post-Implementation)

- ✅ All documentation lives in `docs/` (nothing in `specification/`)
- ✅ Clear 5-type taxonomy with folders for each type
- ✅ Zero root-level cruft docs (all either categorized or deleted)
- ✅ `docs/index.md` has accurate links (no 404s)
- ✅ Every specification has clear status (PROPOSED, IMPLEMENTED, OBSOLETE)
- ✅ READMEs in each folder guide navigation

---

### Quality Success (Post-Implementation)

- ✅ Zero broken internal links (verified by automated checker)
- ✅ All specifications have date headers
- ✅ Architecture overviews extracted from specifications
- ✅ Developer guides are actionable (with examples)
- ✅ User guides cover Docker AND Proxmox deployment

---

### Process Success (Ongoing)

- ✅ `/check-spec` command verifies quality
- ✅ PR template enforces documentation checklist
- ✅ No specification created without documentation task in implementation plan
- ✅ New developers can find what they need within 5 minutes
- ✅ AI assistants have accurate context (no 6-month-stale docs)

---

### Cultural Success (Long-term)

- ✅ Documentation is part of "done" definition
- ✅ Specifications are written BEFORE implementation
- ✅ Implementation plans track documentation tasks
- ✅ Documentation debt is visible and addressed
- ✅ Team refers to documentation regularly (proves it's useful)

---

## Appendices

### Appendix A: Document Inventory (Current State)

**docs/**: 160 markdown files
- `docs/architecture/`: 70 files (all Oct-Nov 2025 specs - KEEP)
- `docs/developer/`: 15 files (mixed quality)
- `docs/user-guides/`: 7 files (some good, some stale)
- `docs/api/`: 8 files (good)
- Root level: ~40 files (MOSTLY DELETE)
- Other folders: ~20 files (mixed)

**specification/**: 94 markdown files
- `specification/Archive/`: ~40 files (historical - keep archived)
- `specification/implemented/`: 4 files (6 months stale - DELETE)
- `specification/current/`: 10 files (mixed - evaluate)
- `specification/future/`: 3 files (keep - move to docs/specifications/future/)
- `specification/research/`: ~15 files (keep - move to docs/specifications/research/)

**Total**: ~254 markdown files

**Post-Refactor Target**: ~150-180 markdown files (30% reduction through deletion and consolidation)

---

### Appendix B: Winning Pattern (Oct-Nov 2025)

**What Worked**:
1. Write design document FIRST
2. Write architecture document NEXT
3. Write implementation plan with detailed tasks
4. Track tasks with checkboxes as work progresses
5. Update status in the documents as work completes
6. Keep all documents in same folder (operations/, data/, distributed/, etc.)

**Evidence of Success**:
- 6 major initiatives specified and implemented (operations, data, backtesting, distributed, etc.)
- Clear architectural decisions documented
- Trade-offs explained
- Implementation tracked
- Quality remained high

**Key Insight**: This pattern worked because documents were LIVING - updated during implementation, not abandoned after writing.

---

### Appendix C: Temporary Folder Strategy (docs/architecture-overviews/)

**Problem**: Tasks 5.4 and 6.6 need to create architecture overview documents, but:
- Current `docs/architecture/` contains specifications (to be renamed to `docs/specifications/`)
- Writing to `docs/architecture/` now would cause confusion during refactoring
- These documents belong in the FUTURE `docs/architecture/` (after rename)

**Solution**: Create temporary folder `docs/architecture-overviews/`

**Timeline**:

1. **Now** (Tasks 5.4, 6.6): Write to `docs/architecture-overviews/`
   - `docs/architecture-overviews/distributed-workers.md`
   - (Future architecture overviews go here too)

2. **During Refactoring Phase 1**:
   - Rename `docs/architecture/` → `docs/specifications/`
   - Rename `docs/architecture-overviews/` → `docs/architecture/`
   - Result: Architecture overviews are in their final location!

**Benefits**:
- ✅ Zero risk of confusion during refactoring
- ✅ Clear separation: specs vs overviews
- ✅ Simple migration: one rename command
- ✅ Self-documenting: folder name indicates temporary purpose

**README**: `docs/architecture-overviews/README.md` explains the temporary nature and future rename.

---

### Appendix D: Migration Risks and Mitigations

**Risk 1**: Breaking existing links in code or external systems

**Mitigation**:
- Create redirects for moved files
- Search codebase for hardcoded doc paths
- Update all links in batch

**Risk 2**: Losing valuable content during migration

**Mitigation**:
- Complete inventory BEFORE deleting anything
- Use git for safety (can always recover)
- Review with stakeholder before deleting

**Risk 3**: Team confusion during transition

**Mitigation**:
- Document migration in CHANGELOG
- Update CLAUDE.md with new doc structure
- Create announcement/guide for team

**Risk 4**: Incomplete migration (gets abandoned)

**Mitigation**:
- Break into phases (each phase delivers value)
- Automate what can be automated
- Make Phase 1 non-disruptive (just rename)

---

**Document Version**: 1.0
**Last Updated**: 2025-01-10
**Next Review**: After Phase 1 implementation
