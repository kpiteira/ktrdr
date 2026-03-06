---
design: docs/designs/forward-return-regression/DESIGN.md
architecture: docs/designs/forward-return-regression/ARCHITECTURE.md
---

# M2: Assessment + Agent Integration

The system can evaluate regression strategies and run autonomous research cycles. Requires M1 complete.

## Task 2.1: MetricsCollector Regression Metrics

**File(s):** Modify `ktrdr/training/analytics/metrics_collector.py`, add tests in `tests/unit/training/analytics/test_metrics_regression.py`
**Type:** CODING

**Description:**
Add regression-specific metrics collection: MSE, MAE, R-squared, directional accuracy, predicted return distribution stats. The existing `collect_epoch_metrics()` branches on output_format.

**Implementation Notes:**
- Current code at line ~23 has `class_names = ["BUY", "HOLD", "SELL"]` and at line ~146 uses sklearn `precision_recall_fscore_support` — both classification-specific
- Add `collect_regression_metrics(self, y_true, y_pred) -> dict` returning: mse, mae, r_squared, directional_accuracy, mean_predicted_return, std_predicted_return
- R-squared: `1 - SS_res / SS_tot` (handle edge case where SS_tot=0, return 0.0)
- Directional accuracy: `(sign(y_pred) == sign(y_true)).mean()` — same as training but on validation/test sets
- Branch `collect_epoch_metrics()` on output_format to call either classification or regression path
- sklearn `r2_score`, `mean_squared_error`, `mean_absolute_error` available for implementation

**Testing Requirements:**
- [ ] MSE calculated correctly on known data
- [ ] MAE calculated correctly on known data
- [ ] R-squared = 1.0 for perfect predictions
- [ ] R-squared = 0.0 for mean-prediction
- [ ] R-squared < 0 for worse-than-mean predictions
- [ ] Directional accuracy = 1.0 when all signs match
- [ ] Directional accuracy = 0.5 for random predictions
- [ ] Classification metrics unchanged

**Acceptance Criteria:**
- [ ] Regression metrics collected during training
- [ ] Metrics dict structure matches what gates and assessment expect

---

## Task 2.2: Gate System Regression Gates

**File(s):** Modify `ktrdr/agents/gates.py`, add tests in `tests/unit/agents/test_gates_regression.py`
**Type:** CODING

**Description:**
Add regression-specific gate checks: directional accuracy > 50%, net return > 0, minimum trade count. Gates branch on output_format.

**Implementation Notes:**
- Current gate config (line ~32-34): `min_accuracy: float = 0.10`
- Add to GateConfig: `min_directional_accuracy: float = 0.50`, `min_net_return: float = 0.0`, `min_trades: int = 5`
- Gate check (line ~86-93): branch on `output_format`
  - Regression: check directional_accuracy, net_return, trade_count from test metrics
  - Classification: existing accuracy check (unchanged)
- Return `(passed: bool, reason: str)` — same interface
- These are minimal safety nets (D5). The real evaluation is the LLM assessment agent.

**Testing Requirements:**
- [ ] Regression gate passes when directional_accuracy > 0.5 AND net_return > 0 AND trades >= 5
- [ ] Regression gate fails on low directional accuracy with clear reason
- [ ] Regression gate fails on negative net return with clear reason
- [ ] Regression gate fails on too few trades with clear reason
- [ ] Classification gate unchanged
- [ ] Default gate behavior (no output_format) is classification

**Acceptance Criteria:**
- [ ] Regression gates enforce minimal quality thresholds
- [ ] Gate reasons are human-readable
- [ ] Classification gates untouched

---

## Task 2.3: Assessment Prompt Regression Context

**File(s):** Modify `ktrdr/agents/prompts.py`, add tests
**Type:** CODING

**Description:**
Update assessment prompt to include regression context when evaluating regression strategies. The LLM assessment agent needs to know it's looking at regression metrics, not classification.

**Implementation Notes:**
- Current assessment prompt (line ~315-317) has example strategy hardcoded with zigzag labels
- Add conditional block when `output_format == "regression"`:
  - Explain what the model predicts (forward returns, not classes)
  - List key metrics: R-squared, directional accuracy, MAE
  - Explain cost threshold mechanism
  - Guide evaluation: "modest R-squared but good directional accuracy can still be profitable"
  - Consider trade count vs selectivity tradeoff
- Include `cost_model` config in assessment context so LLM can reason about cost-awareness
- Follow existing prompt construction patterns in the file

**Testing Requirements:**
- [ ] Assessment prompt includes regression guidance when output_format is regression
- [ ] Assessment prompt unchanged for classification
- [ ] cost_model config included in regression assessment context
- [ ] Regression metrics names match what MetricsCollector produces

**Acceptance Criteria:**
- [ ] Assessment agent receives enough context to evaluate regression strategies
- [ ] Prompt is clear about what regression metrics mean

---

## Task 2.4: Design Prompt Regression Guidance

**File(s):** Modify `ktrdr/agents/design_sdk_prompt.py`
**Type:** CODING

**Description:**
Update design agent prompt to know about regression mode. The design agent needs to be able to create regression strategies.

**Implementation Notes:**
- Add regression mode documentation: `output_format: regression` option, `labels.source: forward_return` with horizon, `cost_model` configuration, `loss: huber` option
- Add example regression strategy snippet (based on `strategies/regression_example_v3.yaml`)
- Guidance: "Use [64, 32] or larger architectures for regression — regression needs more capacity than classification"
- Guidance: "Set horizon based on trading frequency intent — shorter horizon (5-10) for scalping, longer (20-50) for swing"
- Guidance: "min_edge_multiplier controls selectivity — higher means fewer but more confident trades"
- Keep classification documentation intact (D7: classification preserved)

**Testing Requirements:**
- [ ] Design prompt includes regression mode documentation
- [ ] Regression example strategy is valid YAML
- [ ] Classification documentation unchanged

**Acceptance Criteria:**
- [ ] Design agent can create valid regression strategies
- [ ] Regression guidance covers all required config fields

---

## Task 2.5: Research Worker Regression Metadata

**File(s):** Modify `ktrdr/agents/workers/research_worker.py`, modify `ktrdr/agents/workers/assessment_agent_worker.py`
**Type:** CODING

**Description:**
Ensure research worker and assessment worker handle regression-specific metadata in the research cycle.

**Implementation Notes:**

Research worker:
- When extracting training results, include regression metrics (directional_accuracy, r_squared, mse) in result metadata
- Pass `output_format` through the research cycle so assessment knows the mode
- No change to flow control — just metadata passthrough

Assessment worker (line ~62-66):
- Include output_format in metrics context sent to assessment LLM
- Include cost_model config if present
- Ensure regression metric names are included in the metrics documentation

**Testing Requirements:**
- [ ] Research worker passes output_format through to assessment
- [ ] Assessment worker includes regression context in LLM prompt
- [ ] Classification research cycle unchanged

**Acceptance Criteria:**
- [ ] Regression metadata flows through full research cycle
- [ ] Assessment agent receives complete regression context

---

## Task 2.6: E2E Validation

**File(s):** No new files — validation against running infrastructure
**Type:** VALIDATION

**Description:**
Validate M2 end-to-end: trigger a full autonomous research cycle using regression mode. Design agent creates a regression strategy, training runs, assessment evaluates with regression context.

**Validation Steps:**
1. Load the `ke2e` skill before designing any validation
2. Invoke ke2e-test-scout with M2 validation requirements:
   - Trigger autonomous research with regression hint: `ktrdr research start --brief "Design a regression strategy for EURUSD 1h predicting 20-bar forward returns"`
   - Verify design agent produces a strategy with `output_format: regression`
   - Verify training completes with regression metrics in results
   - Verify assessment agent evaluates using regression context (check assessment text for regression-specific language)
   - Verify gate check uses regression thresholds
3. Invoke ke2e-test-runner with identified test recipes
4. Tests must exercise real running infrastructure (design worker, training worker, assessment worker)

**Acceptance Criteria:**
- [ ] Autonomous research cycle completes with regression strategy
- [ ] Assessment agent produces meaningful regression evaluation
- [ ] Gate system applies regression-specific checks
- [ ] No regression in classification research cycles
