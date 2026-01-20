# M7 Handoff: Documentation & Polish

## Task 7.1 Complete: Handle Edge Cases

### Implementation

Added three new edge case handling features:

1. **Orphaned Container Detection** (`detect_orphaned_containers()`)
   - Queries Docker for running containers matching `ktrdr--*` pattern
   - Compares against registry to find containers without registered instances
   - Called during `sandbox list` to warn about orphans

2. **Duplicate Instance ID Handling** (`derive_unique_instance_id()`)
   - When creating a sandbox with a name that exists, appends `-2`, `-3`, etc.
   - Tries up to 99 suffixes before failing
   - Note: Not currently called automatically during create - use for manual deduplication

3. **Improved Slot Exhaustion Error**
   - When all 10 slots are in use, lists all instances with slot numbers
   - Shows destroy command suggestion for remediation

### Gotchas

**Container name parsing:** Container names have format `{instance_id}-{service}-{number}` (e.g., `ktrdr--my-feature-backend-1`). The parsing uses `rsplit("-", 2)` to extract the instance ID.

---

## Task 7.2 Complete: Update README

### Implementation

Added to README.md:
- Command reference tables for both local-prod and sandbox
- CLI auto-detection documentation explaining port targeting

### Pattern Used

Tables use markdown format:
```markdown
| Command | Description |
|---------|-------------|
| `ktrdr sandbox create <name>` | Create new sandbox instance |
```

---

## Task 7.3 Complete: Final Polish and Cleanup

### Implementation

- Enhanced `sandbox create` command with examples in docstring
- Improved argument help text with clearer defaults
- Verified no TODOs/FIXMEs in sandbox/local-prod code
- Verified 126 sandbox/local-prod tests pass

### Help Text Pattern

Used Typer's docstring format for examples:
```python
def create(...) -> None:
    """Create a new sandbox instance using git worktree.

    Creates a new directory ../ktrdr--<name> with its own git working
    directory and allocates a unique port slot for running in parallel.

    Examples:
        ktrdr sandbox create my-feature
        ktrdr sandbox create bugfix --branch fix/issue-123
    """
```

---

## M7 Milestone Complete

All 3 tasks completed:
- [x] Task 7.1: Edge case handling (orphans, duplicates, slot exhaustion)
- [x] Task 7.2: README updated with command tables and auto-detection docs
- [x] Task 7.3: Help text polished, no TODOs/FIXMEs

**Quality gates:** All tests pass, quality checks pass.
