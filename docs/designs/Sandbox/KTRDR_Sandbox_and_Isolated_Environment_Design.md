# KTRDR Sandbox and Isolated Environment Design
*Design document (not an implementation plan)*

## What this document covers
This document proposes a sandboxing approach that enables:

- 2–3 parallel feature streams (one agent per stream)
- each stream runs a fully isolated Docker Compose stack
- optional shared observability (Grafana/Jaeger, possibly Prometheus) without mixing data
- predictable lifecycle: create, start, test (incl E2E), collect evidence, teardown
- security guardrails: minimize blast radius if the agent makes mistakes

It focuses on **volumes, ports, container naming, Compose project identity, and data/secret boundaries**.

---

## Problem statement
Today, “the environment” is effectively tied to:
- one folder on your Mac
- one set of container names
- one set of host ports
- some shared host mounts (e.g., `/mnt/ktrdr_data`)
- a “single active stack” assumption

This creates friction for:
- parallel branch work (agent A and agent B collide)
- automated E2E runs (agent needs a runnable environment per branch)
- safe autonomy (agent needs broad permissions but you want minimal risk)

---

## Design principles

### 1) Isolation by default
Each feature stream must get:
- its own container set
- its own network
- its own DB state (volume)
- its own ports (if ports are published at all)
- optionally its own data root on the host (if the stack writes)

### 2) Identity is the backbone
Everything should be keyed off one stable identifier:

**`instance_id`**: derived from worktree folder name or branch slug.

This identity must be used to:
- namespace Compose resources
- select ports
- label telemetry
- name artifact outputs
- prevent cross-stream collisions

### 3) Minimize host exposure
Publishing ports is convenient but increases collision and security surface.
Prefer:
- internal docker networking
- publishing only what you need
- binding published ports to `127.0.0.1` when possible

### 4) Sandbox is “CI runner you control”
The sandbox should be able to:
- build images
- run compose up/down
- run tests and E2E
- generate evidence

But it should not:
- have broad access to your home directory
- see personal secrets
- have unrestricted LAN reach by default

---

## Core mechanism: Docker Compose project isolation

### Why Compose projects matter
Docker Compose can run multiple instances of the same compose file simultaneously as long as each instance has a unique **project name**.

The project name scopes:
- container naming (unless overridden)
- networks
- volumes (when not externally named)
- general resource separation

### The rule: never hardcode global container names
**Do not use `container_name:`** in multi-instance stacks.

If you set `container_name: ktrdr-backend`, you break project isolation: the second stack cannot start.

**Proposed solution**
- remove all `container_name:` fields
- rely on Compose naming: `<project>_<service>_<index>`

This is the single biggest unlock for parallel stacks.

---

## Ports: avoid collisions and reduce exposure

### Preferred approach: don’t publish ports unless required
For E2E that runs “inside the stack”, you often don’t need host ports at all.

- E2E container calls `http://backend:8000` via Compose DNS
- no host mapping required

### When you do publish ports: parameterize host ports
If you need host access (browser, curl from host, etc.), parameterize the host side:

```yaml
ports:
  - "${KTRDR_API_PORT:-8000}:8000"
```

Bind to localhost when possible:

```yaml
ports:
  - "127.0.0.1:${KTRDR_API_PORT:-8000}:8000"
```

---

## Volumes: isolate state cleanly

### Named volumes
Use named volumes without `external: true` so Compose namespaces them per project.

Avoid hard-coded global volume names.

### Host mounts
Decide explicitly between:
- **Shared datasets** (faster, less isolated)
- **Per-instance data roots** (safer, recommended for sandbox runs)

Parameterize data roots where possible.

---

## Worktrees and folders
Use git worktrees so each branch has its own folder.

Recommended convention:
- `../ktrdr--<branch-slug>`
- `instance_id = basename($PWD)`
- `COMPOSE_PROJECT_NAME = instance_id`

---

## Shared observability

### Identity labeling
All telemetry must include:
- `instance_id`
- environment (`local`, `sandbox`)
- service name

Telemetry without identity is considered broken.

### Modes
- Shared Grafana + Jaeger, Prometheus per instance (simplest)
- Fully shared stack with strict labeling (cleaner UX, more setup)

Sandbox telemetry should be filtered by default.

---

## E2E inside the stack
Run E2E tests in a dedicated container that:
- depends on backend
- talks via Compose DNS (`backend:8000`)
- produces per-instance artifacts

This avoids port collisions and improves reproducibility.

---

## Sandbox lifecycle

1) Create instance (worktree, env, data root)
2) Start stack
3) Startability Gate
4) Tests (unit + E2E)
5) Evidence collection
6) Teardown and cleanup

Cleanup must be reliable and complete.

---

## Security guardrails

- bind ports to localhost by default
- avoid anonymous admin dashboards
- narrow filesystem mounts
- treat sandbox secrets as ephemeral
- never mount broad host paths

---

## Summary
Parallel agent-driven development becomes smooth when combining:

- git worktrees
- Docker Compose project isolation
- no hardcoded container names
- minimal, parameterized port publishing
- namespaced volumes
- explicit data mount strategy
- E2E inside the stack
- strong cleanup discipline

This sandbox foundation enables autonomous milestones with evidence while keeping the developer machine and homelab safer.
