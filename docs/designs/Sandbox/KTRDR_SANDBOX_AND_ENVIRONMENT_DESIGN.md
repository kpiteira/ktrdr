KTRDR Isolated Development & Sandbox Design

Purpose of this document

This document defines the intended development model for KTRDR when using AI coding agents.

It exists to communicate design intent, constraints, and expectations so that an agent can:
 • work autonomously
 • operate safely
 • run full test loops (including E2E)
 • escalate appropriately
 • deliver PRs that are reviewable and trustworthy

This is not an implementation plan.
This is not an architecture spec.
This is not a security policy.

It is a working agreement about how development environments and sandboxes should behave.

⸻

Core philosophy

1. Design is human-led, implementation is agent-led
 • Humans define intent, constraints, and acceptance criteria.
 • Agents implement, test, validate, and report.
 • Humans review outcomes, not raw execution.

No human-written code is expected.

⸻

1. Autonomy requires safety

Agents are trusted to act independently only within clearly bounded environments.

Isolation, sandboxing, and explicit gates are what make autonomy safe.

⸻

1. “Don’t please, prove”

An agent is not expected to guess or bluff.
An agent is expected to:
 • test
 • validate
 • surface uncertainty early
 • escalate when appropriate

“I don’t know” is a valid and respected state.

⸻

Parallel development model

Multiple concurrent workstreams

At any time, there may be:
 • 2–3 active feature streams
 • each running independently
 • each producing its own PR

Therefore:
 • Environments must never collide
 • State must never bleed between streams
 • One stream must not destabilize another

⸻

Instance identity

Every development environment must have a stable identity, referred to as:

instance_id

This identity is used consistently across:
 • container stacks
 • sandboxes
 • test artifacts
 • telemetry
 • logs
 • reports

Example (illustrative only):

ktrdr--feat-operation-metrics

The exact naming mechanism is flexible, but identity must be explicit and propagated.

⸻

Environment types

1. Interactive local environment (human-facing)

Used for:
 • manual testing
 • exploratory debugging
 • reproducing agent findings
 • reviewing behavior before merge

Characteristics:
 • persistent
 • slower iteration is acceptable
 • may reuse shared datasets/models intentionally
 • still isolated per instance

⸻

1. Agent sandbox environment (autonomous)

Used by coding agents to execute entire milestones with minimal human intervention.

Characteristics:
 • disposable
 • isolated
 • reproducible
 • safe to destroy entirely
 • capable of running full build + test + E2E loops

The sandbox is conceptually similar to a self-hosted CI runner, but under direct project control.

⸻

Sandbox design intent

What the sandbox is allowed to do

Within its boundaries, the sandbox may:
 • run arbitrary build commands
 • run Docker / Compose
 • start and stop full stacks
 • run migrations
 • execute unit tests and E2E tests
 • generate logs and artifacts
 • commit code and push branches
 • open pull requests

⸻

What the sandbox must protect

The sandbox must not expose:
 • the developer’s home directory
 • SSH keys
 • password managers
 • unrelated repositories
 • the broader homelab or LAN by default
 • long-lived secrets

Isolation is a feature, not an inconvenience.

⸻

Filesystem boundaries

Design intent:
 • sandbox sees only what it needs
 • no broad mounts like /Users, /home, or /mnt by default
 • project workspace is narrow and explicit
 • shared data (if any) is intentionally mounted and clearly scoped

If an agent requires broader access, that is an escalation.

⸻

Network boundaries

Design intent:
 • outbound access only to what is required (e.g. GitHub, registries)
 • no implicit access to LAN services
 • no implicit access to infrastructure management endpoints

Network expansion requires explicit justification and escalation.

⸻

Secrets model

Design intent:
 • secrets are ephemeral, scoped, and replaceable
 • no human personal secrets are ever injected
 • sandbox secrets may be assumed compromised after each run
 • sandbox secrets should not enable lateral movement

If an agent requires additional secrets, it must escalate with:
 • reason
 • scope
 • duration

⸻

Startability as a first-class gate

The “Startability Gate”

The single most important automated gate is:

Does the system start cleanly from scratch?

An agent must not produce a PR unless the Startability Gate passes.

The gate validates (conceptually):
 • environment configuration is valid
 • containers build successfully
 • services start
 • health checks pass
 • API responds to basic requests
 • database is reachable
 • system can be cleanly torn down

This gate exists specifically to prevent:

“The first run doesn’t even start.”

⸻

Testing philosophy

Layered testing

Agents are expected to run:

 1. static checks (lint, type checks if applicable)
 2. unit tests
 3. API smoke tests
 4. limited E2E tests

⸻

E2E tests: “obvious stuff only”

E2E tests should:
 • validate core happy paths
 • focus on regressions that are embarrassing if broken
 • avoid brittle UI or timing-dependent checks
 • run in a reproducible way inside the environment

E2E tests are not for exhaustiveness; they are for confidence.

⸻

Observability expectations

Shared observability, isolated meaning

It is acceptable (and desirable) to share observability infrastructure across instances if and only if:
 • all telemetry is clearly labeled with instance_id
 • sandbox data is distinguishable from interactive/dev data
 • dashboards default to showing one instance at a time
 • sandbox noise does not pollute normal views

Telemetry without identity is considered broken.

⸻

Security posture (design intent, not policy)

This project acknowledges that early development often prioritizes speed.
However, unsafe shortcuts tend to persist.

Design intent moving forward:
 • prefer least privilege over convenience
 • reduce exposed ports
 • avoid anonymous admin access
 • narrow filesystem mounts
 • treat env vars with secrets as a transitional state
 • pin dependencies where feasible

Security improvements should not block development, but they should not be ignored.

⸻

Escalation model

When to escalate

An agent must escalate when encountering:
 • ambiguous spec requirements
 • architectural boundary changes
 • permission or security boundary crossings
 • inability to satisfy the Startability Gate
 • tests that cannot be stabilized
 • scope expansion beyond the intended slice

⸻

Escalation packet

When escalating, the agent provides:

 1. What is unclear or blocked
 2. Why it matters
 3. Options considered
 4. Recommended path
 5. What decision or input is needed
 6. Evidence gathered so far

Escalation is a success state, not a failure.

⸻

Expected agent deliverables

When work completes without escalation, the agent produces:
 • a clean branch
 • a pull request
 • a summary of implementation choices
 • confirmation that Startability Gate passed
 • test results or links to artifacts
 • notes mapping implementation back to the spec

The PR should be reviewable without rerunning everything manually.

⸻

Definition of success

This system is successful when:
 • 2–3 feature streams can run in parallel safely
 • agents can complete entire milestones autonomously
 • first-run failures are rare
 • escalations are meaningful, not noisy
 • human review focuses on intent and quality, not debugging
 • the developer machine and homelab remain safe

⸻

Explicit non-goals
 • Perfect isolation at the cost of usability
 • Zero human involvement
 • Treating agents as infallible
 • Treating security as an afterthought
