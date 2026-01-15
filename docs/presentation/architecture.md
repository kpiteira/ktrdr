# KTRDR Architecture Overview

## What is KTRDR?

### The Origins

**A chimeric project** - a reboot of a project I worked on in 2004, reimagined as a vehicle for learning agentic systems and agentic coding.

### The Application: Agentic Trading Strategy Researcher

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                        KTRDR: WHAT IT DOES                                  │
└─────────────────────────────────────────────────────────────────────────────┘

                         ┌─────────────────────────┐
                         │   STRATEGY DESIGNER     │
                         │        AGENT            │
                         │                         │
                         │  Designs trading        │
                         │  strategies using       │
                         │  technical indicators   │
                         │  and fuzzy logic rules  │
                         └───────────┬─────────────┘
                                     │
                                     ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                                                                             │
│   ┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐         │
│   │ TRAINING        │    │ TRAINING        │    │ TRAINING        │         │
│   │ WORKER          │    │ WORKER          │    │ WORKER (GPU)    │         │
│   │                 │    │                 │    │                 │         │
│   │ Trains Neuro-   │    │ Trains Neuro-   │    │ 10-100x faster  │         │
│   │ Fuzzy Neural    │    │ Fuzzy Neural    │    │ model training  │         │
│   │ Network models  │    │ Network models  │    │                 │         │
│   └────────┬────────┘    └────────┬────────┘    └────────┬────────┘         │
│            │                      │                      │                  │
│            └──────────────────────┼──────────────────────┘                  │
│                                   ▼                                         │
│                        ┌─────────────────────┐                              │
│                        │   TRAINED MODELS    │                              │
│                        │   (Neuro-Fuzzy NN)  │                              │
│                        └──────────┬──────────┘                              │
│                                   │                                         │
│            ┌──────────────────────┼──────────────────────┐                  │
│            │                      │                      │                  │
│   ┌────────▼────────┐    ┌────────▼────────┐    ┌────────▼────────┐         │
│   │ BACKTEST        │    │ BACKTEST        │    │ BACKTEST        │         │
│   │ WORKER          │    │ WORKER          │    │ WORKER          │         │
│   │                 │    │                 │    │                 │         │
│   │ Validates       │    │ Validates       │    │ Validates       │         │
│   │ strategies on   │    │ strategies on   │    │ strategies on   │         │
│   │ historical data │    │ historical data │    │ historical data │         │
│   └────────┬────────┘    └────────┬────────┘    └────────┬────────┘         │
│            │                      │                      │                  │
│            └──────────────────────┼──────────────────────┘                  │
│                                   ▼                                         │
└─────────────────────────────────────────────────────────────────────────────┘
                                     │
                                     ▼
                         ┌─────────────────────────┐
                         │   ASSESSMENT AGENT      │
                         │                         │
                         │  Evaluates backtest     │
                         │  results, identifies    │
                         │  promising strategies   │
                         └───────────┬─────────────┘
                                     │
                                     ▼
                         ┌─────────────────────────┐
                         │   LEARNING AGENT        │
                         │                         │
                         │  Accumulates            │
                         │  experiments and        │
                         │  learnings over time    │
                         └─────────────────────────┘


┌─────────────────────────────────────────────────────────────────────────────┐
│                              USER INTERFACES                                │
│                                                                             │
│   ┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐         │
│   │      CLI        │    │      API        │    │   MCP Server    │         │
│   │                 │    │                 │    │                 │         │
│   │  ktrdr train    │    │  REST endpoints │    │  Claude Code    │         │
│   │  ktrdr backtest │    │  for all        │    │  integration    │         │
│   │  ktrdr ops list │    │  operations     │    │  for automation │         │
│   └────────┬────────┘    └────────┬────────┘    └────────┬────────┘         │
│            │                      │                      │                  │
│            └──────────────────────┼──────────────────────┘                  │
│                                   │                                         │
│                                   ▼                                         │
│                         ┌─────────────────────┐                             │
│                         │   Backend API       │                             │
│                         │   (Orchestrator)    │                             │
│                         └─────────────────────┘                             │
│                                                                             │
│   [React Web UI - deprecated, not used]                                     │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Key Concepts

- **Neuro-Fuzzy Neural Networks**: Hybrid models combining neural networks with fuzzy logic for interpretable trading decisions
- **Strategy Designer Agent**: Creates trading strategies by combining technical indicators with fuzzy rules
- **Assessment Agent**: Evaluates backtest results to identify what works
- **Learning Agent**: Builds institutional memory across experiments - what worked, what didn't, and why

### Why This Project?

1. **Learning vehicle** for agentic systems and agentic coding
2. **AI & ML Learning** - includes a lot of the components of agentic systems, meta systems for coding, + ML refresher :)
3. **Real complexity** - not a toy, requires real distributed systems
4. **Multiple agent types** coordinating on a shared goal
5. **Long-running operations** that need tracking, checkpointing, and resumption
6. **Fun** for the first time I'm able to have fun with hardware

---

## Infrastructure Architecture

The diagrams below show how the system is deployed, not what it does.

---

## Visual Diagram (ASCII reference for your drawing)

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           KTRDR ARCHITECTURE                                │
└─────────────────────────────────────────────────────────────────────────────┘


═══════════════════════════════════════════════════════════════════════════════
                              DEVELOPMENT MACHINE
═══════════════════════════════════════════════════════════════════════════════

┌─ Zellij Terminal Multiplexer ───────────────────────────────────────────────┐
│                                                                             │
│  ┌─ Claude #1 ──────┐  ┌─ Claude #2 ──────┐  ┌─ Claude #3 ──────┐           │
│  │ CLI Restructure  │  │ Sandbox Shell    │  │ Spec/Design      │           │
│  │ (feature work)   │  │ (infra work)     │  │ (planning)       │           │
│  │                  │  │                  │  │                  │           │
│  │ stream-a sandbox │  │ stream-b sandbox │  │ spec-work repo   │           │
│  └──────────────────┘  └──────────────────┘  └──────────────────┘           │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘

┌─ ktrdr CLI ─────────────────────────────────────────────────────────────────┐
│  ktrdr sandbox create <name>  - Create isolated environment                 │
│  ktrdr sandbox up             - Start complete Docker stack                 │
│  ktrdr train                  - Start training operations                   │
│  ktrdr backtest               - Run backtests                               │
│  ktrdr operations list        - Monitor running operations                  │
└─────────────────────────────────────────────────────────────────────────────┘


═══════════════════════════════════════════════════════════════════════════════
                    SANDBOX ENVIRONMENTS (Complete Isolation)
═══════════════════════════════════════════════════════════════════════════════

Each sandbox = repo clone + complete Docker stack + unique ports
(Long-lived sandboxes with 1 branch per milestone)

┌─ Main Dev (slot 0) ────────┐ ┌─ Sandbox A (slot 1) ───────┐ ┌─ Sandbox B (slot 2) ───────┐
│ ktrdr2/                    │ │ ktrdr--stream-a/           │ │ ktrdr--stream-b/           │
│                            │ │                            │ │                            │
│ Backend      :8000         │ │ Backend      :8001         │ │ Backend      :8002         │
│ Database     :5432         │ │ Database     :5433         │ │ Database     :5434         │
│ Grafana      :3000         │ │ Grafana      :3001         │ │ Grafana      :3002         │
│ Jaeger       :16686        │ │ Jaeger       :16687        │ │ Jaeger       :16688        │
│ Prometheus   :9090         │ │ Prometheus   :9091         │ │ Prometheus   :9092         │
│ Workers      :5003-5006    │ │ Workers      :5010-5013    │ │ Workers      :5020-5023    │
│                            │ │                            │ │                            │
│ branch: main               │ │ feature: cli-restructure   │ │ feature: sandbox-shell     │
└────────────────────────────┘ └────────────────────────────┘ └────────────────────────────┘
              │                             │                             │
              └─────────────────────────────┼─────────────────────────────┘
                                            │
                                            ▼
                              ┌─────────────────────────────┐
                              │    ~/.ktrdr/shared/         │
                              │    (Read-Only Mounts)       │
                              │                             │
                              │    data/      - Market data │
                              │    models/    - ML models   │
                              │    strategies/- Trading     │
                              └─────────────────────────────┘

Why sandboxes?
• AI agents can run destructive E2E tests safely
• Multiple features developed in parallel
• Each has full observability for debugging
• Complete isolation - no cross-contamination


═══════════════════════════════════════════════════════════════════════════════
                     SINGLE ENVIRONMENT DETAIL (Any Sandbox)
═══════════════════════════════════════════════════════════════════════════════

┌─ Docker Compose Stack ──────────────────────────────────────────────────────┐
│                                                                             │
│   ┌──────────────────────────────────────────────────────────────────────┐  │
│   │                         BACKEND (FastAPI)                            │  │
│   │                                                                      │  │
│   │   • Orchestrator only - NEVER executes operations                    │  │
│   │   • Worker registry (push-based discovery)                           │  │
│   │   • Operations tracking & progress caching                           │  │
│   │   • REST API for CLI and MCP                                         │  │
│   └───────────────────────────────┬──────────────────────────────────────┘  │
│                                   │                                         │
│         ┌─────────────────────────┼─────────────────────────┐               │
│         │                         │                         │               │
│         ▼                         ▼                         ▼               │
│   ┌───────────┐            ┌───────────┐            ┌───────────┐           │
│   │ Backtest  │            │ Backtest  │            │ Training  │           │
│   │ Worker 1  │            │ Worker 2  │            │ Worker    │           │
│   │           │            │           │            │           │           │
│   │ CPU only  │            │ CPU only  │            │ CPU only  │           │
│   └───────────┘            └───────────┘            └───────────┘           │
│                                                                             │
│   ┌─ OBSERVABILITY ──────────────────────────────────────────────────────┐  │
│   │                                                                      │  │
│   │   Jaeger              Prometheus           Grafana                   │  │
│   │   └─ Distributed      └─ Metrics           └─ Dashboards             │  │
│   │      tracing (OTLP)      collection           visualization          │  │
│   └──────────────────────────────────────────────────────────────────────┘  │
│                                                                             │
│   ┌─ DATA ───────────────────────────────────────────────────────────────┐  │
│   │   TimescaleDB - Time-series optimized PostgreSQL                     │  │
│   └──────────────────────────────────────────────────────────────────────┘  │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘

═══════════════════════════════════════════════════════════════════════════════
                    HOMELAB PRODUCTION (Proxmox Cluster)
═══════════════════════════════════════════════════════════════════════════════

┌─────────────────────────────────────────────────────────────────────────────┐
│                           PROXMOX CLUSTER (4 NODES)                         │
│                                                                             │
│  ┌─ Node 1: Core ─────────────────────────────────────────────────────────┐ │
│  │ backend.ktrdr.home.mynerd.place                                        │ │
│  │                                                                        │ │
│  │   Backend (FastAPI)  •  TimescaleDB  •  Jaeger  •  Prometheus          │ │
│  │   Grafana  •  MCP Server                                               │ │
│  └────────────────────────────────────────────────────────────────────────┘ │
│                                                                             │
│  ┌─ Node 2: Workers-B ─────────────┐  ┌─ Node 3: Workers-C ─────────────┐   │
│  │workers-b.ktrdr.home.mynerd.place│  │workers-c.ktrdr.home.mynerd.place│   │
│  │                                 │  │                                 │   │
│  │  backtest-worker-1   :5003      │  │  backtest-worker-4   :5003      │   │
│  │  backtest-worker-2   :5004      │  │  backtest-worker-5   :5004      │   │
│  │  backtest-worker-3   :5007      │  │  backtest-worker-6   :5007      │   │
│  │  training-worker-1   :5005      │  │  training-worker-4   :5005      │   │
│  │  training-worker-2   :5006      │  │  training-worker-5   :5006      │   │
│  │  training-worker-3   :5008      │  │  training-worker-6   :5008      │   │
│  └─────────────────────────────────┘  └─────────────────────────────────┘   │
│                                                                             │
│  ┌─ Node 4: GPU Worker ───────────────────────────────────────────────────┐ │
│  │ ktrdr-gpuworker.ktrdr.home.mynerd.place                                │ │
│  │                                                                        │ │
│  │   training-worker-gpu  :5005                                           │ │
│  │   • NVIDIA GPU with CUDA  • 16GB+ GPU memory                           │ │
│  │   • Priority for all training (10-100x faster)                         │ │
│  │   • Registers with gpu: true capability                                │ │
│  └────────────────────────────────────────────────────────────────────────┘ │
│                                                                             │
│                                    │                                        │
│                                    ▼                                        │
│                    ┌───────────────────────────────────┐                    │
│                    │         NFS SHARED STORAGE        │                    │
│                    │        /mnt/ktrdr_data/           │                    │
│                    │                                   │                    │
│                    │   data/         - Market data     │                    │
│                    │   models/       - Trained models  │                    │
│                    │   strategies/   - Trading strats  │                    │
│                    │   checkpoints/  - Operation state │                    │
│                    └───────────────────────────────────┘                    │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘

Production Features:
• Workers self-register with backend over network
• GPU worker prioritized for training (WORKER_HAS_GPU=true)
• CPU workers provide fallback capacity
• All workers share NFS storage for models/data
• OTLP traces sent to central Jaeger
• Container images pulled from GHCR
• Secrets injected from 1Password at deploy time
```

---

## Key Points to Highlight

### 1. Sandbox = Complete Environment (Not Just Port Mapping)

Each sandbox gets:

- Its own **repo clone** (long-lived, 1 branch per milestone)
- Its own **Docker Compose project** (separate containers)
- Its own **complete observability stack** (Jaeger, Prometheus, Grafana)
- Its own **database** (separate PostgreSQL instance)
- Its own **workers** (separate backtest/training containers)
- **Shared data directories** (read-only mount)

This means AI agents can:

- Run E2E tests that modify database state
- Train models without affecting other environments
- Debug with full tracing in their own Jaeger
- Break things without impacting other work

### 2. Homelab = Real Production Cluster

4 physical/virtual nodes:

- **Core node**: Backend orchestrator, database, observability
- **Workers-B node**: CPU backtest and training workers (scalable 1-6)
- **Workers-C node**: Additional CPU workers for horizontal scaling
- **GPU node**: NVIDIA GPU for accelerated training

All connected via:

- DNS (`*.ktrdr.home.mynerd.place`)
- NFS shared storage (`/mnt/ktrdr_data`)
- OTLP tracing to central Jaeger

### 3. Worker Architecture

```
Backend receives request
    │
    ├─> WorkerRegistry selects worker
    │   ├─> GPU worker available? → Use it (10-100x faster)
    │   └─> Fallback to CPU workers
    │
    ├─> Dispatch to selected worker
    │   └─> Worker executes operation
    │
    └─> Track progress (cached, 1s TTL)
        └─> User polls for status
```

Workers self-register on startup:

```
Worker starts → POST /workers/register → Backend adds to registry → Ready
```

### 4. Observability Throughout

Every environment (local, sandbox, production) has:

- **Jaeger**: Distributed tracing (every operation traced)
- **Prometheus**: Metrics collection
- **Grafana**: Pre-built dashboards

Debug workflow: "Check Jaeger first, not logs"

---

## Services Summary Table

| Service | Local Port | Sandbox 1 | Sandbox 2 | Purpose |
|---------|-----------|-----------|-----------|---------|
| Backend | 8000 | 8001 | 8002 | FastAPI orchestrator |
| TimescaleDB | 5432 | 5433 | 5434 | Time-series database |
| Jaeger UI | 16686 | 16687 | 16688 | Distributed tracing |
| Prometheus | 9090 | 9091 | 9092 | Metrics |
| Grafana | 3000 | 3001 | 3002 | Dashboards |
| Workers | 5003-5006 | 5010-5013 | 5020-5023 | Operation execution |

---

## Suggested Talking Points

1. **"This is what I'm working on"** - A distributed trading system across multiple nodes
2. **"Each sandbox is a complete copy"** - Not just port mapping, full stack isolation
3. **"The AI agents can break things safely"** - Destructive E2E tests in sandbox
4. **"I can see everything"** - Each environment has full observability
5. **"Production runs on my homelab"** - 4 nodes, GPU acceleration, NFS storage
6. **"Workers register themselves"** - Push-based, cloud-native pattern
7. **"GPU when available, CPU always works"** - Graceful degradation
