# Handoff: M4 Individual Cancel

## Task 4.1 & 4.2 Complete: Modify cancel() and API Endpoint

### Summary

Changed `cancel()` from no-argument (cancels "the active cycle") to `cancel(operation_id: str)` (cancels a specific research). This enables individual research cancellation in multi-research scenarios.

### Gotchas

- **API endpoint path changed**: From `DELETE /agent/cancel` to `DELETE /agent/cancel/{operation_id}`. CLI will need updating in Task 4.3.

- **HTTP status codes**: The endpoint now returns:
  - 200: Success
  - 404: not_found or not_research
  - 409: not_cancellable (already completed/failed)
  - 500: Internal error

### Implementation Notes

**Service (`agent_service.py:330-380`):**
- Validates operation exists via `ops.get_operation(operation_id)`
- Checks `operation_type == OperationType.AGENT_RESEARCH`
- Checks `status in [RUNNING, PENDING]` for cancellability
- Returns structured response with reason codes: `not_found`, `not_research`, `not_cancellable`

**Endpoint (`agent.py:80-110`):**
- Path param: `operation_id: str`
- Maps reason codes to HTTP status codes
- Passes operation_id to service

### Test Coverage

Unit tests added for cancel(operation_id):
- Running research cancellation
- Pending research cancellation
- Unknown operation_id (not_found)
- Non-research operation (not_research)
- Completed research (not_cancellable)
- Failed research (not_cancellable)
- Multiple researches - cancel one, others continue

Endpoint tests updated for new path format.

### Next Task Notes (Task 4.3)

Task 4.3 updates the CLI cancel command:
- Change from `ktrdr agent cancel` (no args) to `ktrdr agent cancel <operation_id>`
- Update the httpx call to use the new endpoint path: `DELETE /agent/cancel/{operation_id}`
- Handle the new error responses (not_found, not_research, not_cancellable)
