# Milestone 5 Handoff: Shared Data + Init-Shared

## Gotchas

### Shared Data Environment Variables

The docker-compose.sandbox.yml uses individual environment variables for volume mounts:
- `KTRDR_DATA_DIR`
- `KTRDR_MODELS_DIR`
- `KTRDR_STRATEGIES_DIR`

Not just `KTRDR_SHARED_DIR`. The `generate_env_file` function must output all four variables.

**Symptom:** Containers start but `/app/data` is empty despite `~/.ktrdr/shared/data/` having files.

**Solution:** Fixed in d629a916 - added individual path variables to env file generation.

## Emergent Patterns

### E2E Test Covers End-to-End Flow

The M5 E2E test validates the complete workflow:
1. Clean slate → init-shared --from → verify structure
2. Create sandbox → start → verify container data access
3. Minimal init test
4. Cleanup

This caught the env var mismatch that unit tests missed.
