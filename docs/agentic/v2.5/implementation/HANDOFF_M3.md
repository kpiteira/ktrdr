# Handoff: M3 Baby Gates + Brief

## Gotchas

### Docker Rebuild Required for E2E Test
- **Problem:** E2E test shows `brief: null` in operation metadata
- **Symptom:** API accepts brief, but running container doesn't store it
- **Solution:** Rebuild Docker images: `docker compose build --no-cache backend`

### Existing Gate Tests Updated
- **Problem:** Old tests expected 45% accuracy/win_rate thresholds
- **Symptom:** Tests fail with `assert 0.1 == 0.45`
- **Solution:** Tests updated to use Baby mode values (10% accuracy, -50% loss_decrease, 10% win_rate)

## Emergent Patterns

### Brief Propagation Path
```
API (AgentTriggerRequest.brief)
  → AgentService.trigger(brief=...)
    → OperationMetadata.parameters["brief"]
      → ResearchWorker reads from parent metadata
        → DesignWorker.run(brief=...)
          → get_strategy_designer_prompt(brief=...)
            → PromptContext.brief
              → "## Research Brief" section in prompt
```

### Empty Brief Handling
Empty string `""` is treated as `None` at the prompt level to avoid creating an empty section. This normalization happens in `get_strategy_designer_prompt()`:
```python
brief=brief if brief else None
```

## Notes for E2E Testing

After Docker rebuild, verify with:
```bash
# 1. Trigger with brief
curl -X POST http://localhost:8000/api/v1/agent/trigger \
  -H "Content-Type: application/json" \
  -d '{"brief": "Design a simple RSI strategy for EURUSD 1h only", "model": "haiku"}'

# 2. Check brief is stored
curl http://localhost:8000/api/v1/operations/<OP_ID> | jq '.data.metadata.parameters.brief'
# Expected: "Design a simple RSI strategy for EURUSD 1h only"

# 3. Verify Baby gates allow exploration (30% accuracy should pass)
# Check experiment status after cycle completes
```
