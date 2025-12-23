---
design: docs/architecture/autonomous-coding/info-command/DESIGN.md
architecture: docs/architecture/autonomous-coding/info-command/ARCHITECTURE.md
---

# Milestone 1: Info Command

**Branch:** `feature/orchestrator-info-command`
**Estimated Tasks:** 2

---

## Capability

Users can quickly view metadata about a milestone plan.

---

## Tasks

### Task 1.1: Create Plan Info Extractor

**File:** `orchestrator/plan_info.py`
**Type:** CODING

**Description:**
Extract metadata from milestone plans including name, task count, and file references.

**Implementation Notes:**

```python
from dataclasses import dataclass
from pathlib import Path
import re

@dataclass
class PlanInfo:
    name: str
    task_count: int
    has_e2e: bool
    files: list[str]

def get_plan_info(path: Path) -> PlanInfo:
    """Extract metadata from a milestone plan."""
    content = path.read_text()

    # Extract name from first heading
    name_match = re.search(r'^#\s+(.+)$', content, re.MULTILINE)
    name = name_match.group(1) if name_match else path.stem

    # Count tasks
    tasks = re.findall(r'^###\s+Task\s+\d+\.\d+', content, re.MULTILINE)

    # Check for E2E
    has_e2e = bool(re.search(r'^##\s+E2E', content, re.MULTILINE | re.IGNORECASE))

    # Extract file references
    files = re.findall(r'\*\*File:\*\*\s*`([^`]+)`', content)

    return PlanInfo(
        name=name,
        task_count=len(tasks),
        has_e2e=has_e2e,
        files=files,
    )
```

**Acceptance Criteria:**

- [ ] Extracts milestone name from heading
- [ ] Counts tasks correctly
- [ ] Detects E2E section presence
- [ ] Extracts file references from tasks

---

### Task 1.2: Add Info CLI Command

**File:** `orchestrator/cli.py`
**Type:** CODING

**Description:**
Add `orchestrator info <plan.md>` command.

**Acceptance Criteria:**

- [ ] `orchestrator info <path>` shows plan metadata
- [ ] Displays milestone name
- [ ] Displays task count
- [ ] Shows E2E status (Yes/No)
- [ ] Lists files from tasks
