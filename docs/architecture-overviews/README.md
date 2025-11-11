# Architecture Overviews (Temporary Folder)

## Purpose

This folder contains **architecture overview documents** - high-level explanations of KTRDR's architecture for technical stakeholders.

## Why "architecture-overviews" and Not "architecture"?

This is a **temporary folder** created to avoid confusion during the transition period.

### Current State (2025-01)

- `docs/architecture/` contains **specifications** (how we designed and built features)
- `docs/architecture-overviews/` contains **architecture overviews** (high-level system understanding)

### Future State (After Documentation Refactoring)

When we execute the documentation refactoring (see `docs/architecture/docs-updates/`):

1. `docs/architecture/` will be renamed to `docs/specifications/`
2. `docs/architecture-overviews/` will be renamed to `docs/architecture/`

At that point, this folder will disappear and its contents will live in `docs/architecture/`.

## What Goes Here?

**Architecture overviews** extracted from detailed specifications:

- High-level system architecture explanations
- Component interaction diagrams
- Key patterns and principles
- Links to detailed specifications for deep dives

**Examples**:
- `distributed-workers.md` - Overview of distributed workers architecture
- (Future) `async-infrastructure.md` - Overview of async patterns
- (Future) `data-flow.md` - Overview of data pipeline

## What Does NOT Go Here?

- **Specifications**: Go in `docs/architecture/` (currently) or `docs/specifications/` (after refactoring)
- **Developer guides**: Go in `docs/developer/`
- **User guides**: Go in `docs/user-guides/`
- **API docs**: Go in `docs/api/`

## Documents in This Folder

### distributed-workers.md

**Created**: 2025-01-10 (Task 5.4)
**Purpose**: High-level overview of distributed workers architecture
**Audience**: Technical stakeholders, architects, senior developers
**Source**: Extracted from `docs/architecture/distributed/DESIGN.md` and `ARCHITECTURE.md`

---

**Last Updated**: 2025-01-10
**Next Action**: Rename to `docs/architecture/` during documentation refactoring
