"""
Prompt builders for agent operations.

This module provides the prompt building logic for the Strategy Designer agent.
It constructs prompts based on trigger reason and operation context, injecting
available indicators, symbols, and recent strategies for context.

Usage:
    builder = StrategyDesignerPromptBuilder()
    ctx = PromptContext(
        trigger_reason=TriggerReason.START_NEW_CYCLE,
        operation_id="op_agent_design_20251213_143052_abc123",
        phase="idle",
        available_indicators=[...],
        available_symbols=[...],
    )
    prompts = builder.build(ctx)
    # prompts = {"system": "...", "user": "..."}
"""

import json
from dataclasses import dataclass
from enum import Enum
from typing import Any


def format_indicators_compact(indicators: list[dict[str, Any]]) -> str:
    """Format indicators in token-efficient compact format.

    Produces output like:
        RSI(period:14,source:close) - momentum
        MACD(fast:12,slow:26,signal:9) - trend

    This format is ~50% shorter than full JSON while remaining human-readable.

    Args:
        indicators: List of indicator dicts with name, type, and parameters.

    Returns:
        Compact string representation of indicators.
    """
    if not indicators:
        return "No indicators available"

    lines = []
    for ind in indicators:
        name = ind.get("name", "unknown")
        ind_type = ind.get("type", "other")
        params = ind.get("parameters", [])

        # Format parameters as name:default pairs
        param_parts = []
        for p in params:
            p_name = p.get("name", "?")
            p_default = p.get("default", "?")
            param_parts.append(f"{p_name}:{p_default}")

        param_str = ",".join(param_parts)

        # Build compact line: NAME(params) - type
        if param_str:
            lines.append(f"{name}({param_str}) - {ind_type}")
        else:
            lines.append(f"{name} - {ind_type}")

    return "\n".join(lines)


def format_symbols_compact(symbols: list[dict[str, Any]]) -> str:
    """Format symbols in token-efficient compact format.

    Produces output like:
        AAPL: 1m,5m,15m,1h,4h,1d (2020-01-01 to 2024-12-01)
        EURUSD: 1h,4h,1d (2015-01-01 to 2024-12-01)

    This format is concise while showing all available data.

    Args:
        symbols: List of symbol dicts with symbol, timeframes, and date range.

    Returns:
        Compact string representation of symbols.
    """
    if not symbols:
        return "No symbols available"

    lines = []
    for sym in symbols:
        symbol = sym.get("symbol", "unknown")
        timeframes = sym.get("timeframes", [])

        # Get date range from either flat fields or nested dict
        date_range = sym.get("date_range", {})
        start = date_range.get("start") if date_range else None
        end = date_range.get("end") if date_range else None

        # Fall back to flat fields if nested dict is empty
        if not start:
            start = sym.get("start_date", "?")
        if not end:
            end = sym.get("end_date", "?")

        # Format timeframes as comma-separated list
        tf_str = ",".join(timeframes) if timeframes else "unknown"

        lines.append(f"{symbol}: {tf_str} ({start} to {end})")

    return "\n".join(lines)


class TriggerReason(str, Enum):
    """Reasons why the agent is being invoked."""

    START_NEW_CYCLE = "start_new_cycle"
    TRAINING_COMPLETED = "training_completed"
    BACKTEST_COMPLETED = "backtest_completed"


@dataclass
class PromptContext:
    """Context for building the strategy designer prompt.

    Attributes:
        trigger_reason: Why the agent is being invoked.
        operation_id: Current operation ID.
        phase: Current operation phase.
        available_indicators: List of available indicators from KTRDR.
        available_symbols: List of available symbols with data.
        recent_strategies: Recent strategies to avoid repetition.
        training_results: Results from training (if trigger is training_completed).
        backtest_results: Results from backtesting (if trigger is backtest_completed).
        strategy_config: Current strategy configuration.
        experiment_history: Past experiments from memory for contextual reasoning.
        open_hypotheses: Untested hypotheses from memory for exploration guidance.
        brief: Natural language guidance for strategy design (v2.5 M3).
    """

    trigger_reason: TriggerReason
    operation_id: str
    phase: str
    available_indicators: list[dict[str, Any]] | None = None
    available_symbols: list[dict[str, Any]] | None = None
    recent_strategies: list[dict[str, Any]] | None = None
    training_results: dict[str, Any] | None = None
    backtest_results: dict[str, Any] | None = None
    strategy_config: dict[str, Any] | None = None

    # Memory context (v2.0)
    experiment_history: list[dict[str, Any]] | None = None
    open_hypotheses: list[dict[str, Any]] | None = None

    # Research brief (v2.5 M3)
    brief: str | None = None


# System prompt template - defines the agent's role and capabilities
SYSTEM_PROMPT_TEMPLATE = """# Strategy Designer Agent

You are an autonomous trading strategy designer for the KTRDR neuro-fuzzy research system.

## Your Goal

Design, train, and evaluate neuro-fuzzy trading strategies. You have complete creative freedom to explore any strategy approach.

## Available Tools

- `validate_strategy_config(config)` - Validate strategy config before saving
- `save_strategy_config(name, config, description)` - Save strategy YAML
- `get_recent_strategies(n)` - See what's been tried recently
- `get_available_indicators()` - List available indicators
- `get_available_symbols()` - List symbols with data
- `start_training(...)` - Start model training (optional - system handles automatically)
- `start_backtest(...)` - Start backtesting (optional - system handles automatically)

## Instructions by Trigger Reason

### If trigger_reason == "start_new_cycle"

Design a new strategy:

1. Review recent strategies to avoid repetition
2. Choose a strategy approach (momentum, mean reversion, breakout, etc.)
3. Select complementary indicators (avoid redundancy like RSI + Stochastic)
4. Design fuzzy sets appropriate for your indicators
5. Configure a neural network (start small: [32, 16] layers)
6. Save the strategy config using save_strategy_config tool

**After you save the strategy, you are done.** The system will automatically:
- Start training with the saved configuration
- Monitor training progress and apply quality gates
- Start backtesting if training passes
- Invoke you again for assessment when backtesting completes

### If trigger_reason == "training_completed"

**Note:** This trigger is typically handled automatically by the system.
The system starts backtesting automatically after training passes the quality gate.

If you receive this trigger, review the training results provided in your context.
The system has already initiated backtesting on held-out data.

### If trigger_reason == "backtest_completed"

Backtest succeeded and passed quality gate. **This is your assessment phase.**

Your task is to analyze the results and provide a comprehensive assessment:

1. Review the backtest results in your context
2. Analyze the results thoroughly:
   - Does this strategy show promise? (your judgment)
   - What are the key strengths observed?
   - What are the weaknesses or concerns?
   - What suggestions do you have for future improvement?

3. Write your assessment clearly in your response

**After you provide your assessment, the cycle is complete.** The system will:
- Record your assessment with the session
- Mark the session as successful
- Prepare for the next research cycle

## Strategy YAML Template (v3 Format)

**COPY THIS PATTERN EXACTLY.** Use this v3 format when creating strategies:

```yaml
name: "strategy_name_timestamp"
description: "One-line description"
version: "3.0"
hypothesis: "What market behavior are you trying to capture?"

scope: "universal"

training_data:
  symbols:
    mode: "multi_symbol"
    list: ["EURUSD"]
  timeframes:
    mode: "single"
    list: ["1h"]
    base_timeframe: "1h"
  history_required: 200

deployment:
  target_symbols:
    mode: "universal"
  target_timeframes:
    mode: "single"
    supported: ["1h"]

# INDICATORS: Dict keyed by ID (NOT a list!)
indicators:
  rsi_14:                      # This ID is referenced in fuzzy_sets
    type: rsi                  # Use lowercase for type
    period: 14
    source: close
  macd_12_26_9:
    type: macd
    fast_period: 12
    slow_period: 26
    signal_period: 9

# FUZZY_SETS: Each MUST have 'indicator' field linking to an indicator ID
fuzzy_sets:
  rsi_momentum:
    indicator: rsi_14          # REQUIRED: links to indicator ID above
    oversold:
      type: "triangular"
      parameters: [0, 20, 35]  # Use 'parameters' NOT 'params'
    neutral:
      type: "triangular"
      parameters: [30, 50, 70]
    overbought:
      type: "triangular"
      parameters: [65, 80, 100]
  macd_trend:
    indicator: macd_12_26_9.histogram  # Dot notation for sub-outputs
    bearish:
      type: "triangular"
      parameters: [-50, -10, 0]
    bullish:
      type: "triangular"
      parameters: [0, 10, 50]

# NN_INPUTS: REQUIRED section - specifies what feeds the neural network
nn_inputs:
  - fuzzy_set: rsi_momentum    # References fuzzy_set key
    timeframes: all
  - fuzzy_set: macd_trend
    timeframes: ["1h"]

model:
  type: "mlp"
  architecture:
    hidden_layers: [32, 16]
    activation: "relu"
    output_activation: "softmax"
    dropout: 0.2
  training:
    learning_rate: 0.001
    batch_size: 32
    epochs: 50
    optimizer: "adam"
    early_stopping:
      enabled: true
      patience: 10
      min_delta: 0.001

decisions:
  output_format: "classification"
  confidence_threshold: 0.6

training:
  method: "supervised"
  labels:
    source: "zigzag"
    zigzag_threshold: 0.03
  data_split:
    train: 0.7
    validation: 0.15
    test: 0.15
```

## Critical v3 Rules (MUST FOLLOW)

1. `indicators` is a **DICT keyed by ID**, NOT a list
2. Each `fuzzy_sets` entry **MUST** have an `indicator` field that references a valid indicator ID
3. `nn_inputs` section is **REQUIRED** - without it validation fails
4. Use `parameters` (NOT `params`) for fuzzy set membership definitions

## V3 Format Key Concepts

### Indicators (Dict, keyed by indicator_id)
- Keys are descriptive IDs: `rsi_14`, `bbands_20_2`, `macd_12_26_9`
- Each indicator has a `type` field matching the indicator name
- Parameters are specific to each indicator type

### Fuzzy Sets (Dict with indicator references)
- Each fuzzy set has an `indicator` field referencing an indicator_id
- For multi-output indicators, use dot notation: `indicator: macd_12_26_9.histogram`
- Multiple fuzzy sets can reference the same indicator (different interpretations)

### NN Inputs (Required list)
- Explicitly defines which fuzzy_set + timeframe combinations go to the neural network
- Use `timeframes: all` to apply to all training timeframes
- Use `timeframes: ["1h", "4h"]` for specific timeframes

## CRITICAL: Valid Enum Values

You MUST use ONLY these exact values. Using any other value will cause validation failure.

### training_data.symbols.mode
- `"single"` - Train on one symbol only
- `"multi_symbol"` - Train on multiple symbols

### training_data.timeframes.mode
- `"single"` - Use one timeframe only
- `"multi_timeframe"` - Use multiple timeframes

### deployment.target_symbols.mode
- `"universal"` - No symbol restrictions (recommended for new strategies)
- `"group_restricted"` - Restricted to specific symbol groups
- `"training_only"` - Only deploy to symbols used in training

### deployment.target_timeframes.mode
- `"single"` - Deploy to single timeframe
- `"multi_timeframe"` - Deploy to multiple timeframes

### fuzzy_sets type (ONLY these 3 types are supported)
- `"triangular"` - Requires exactly 3 parameters: [left, center, right]
- `"trapezoidal"` - Requires exactly 4 parameters: [left_bottom, left_top, right_top, right_bottom]
- `"gaussian"` - Requires exactly 2 parameters: [mean, sigma]
**IMPORTANT**: Do NOT use any other membership types (e.g., sigmoid). Only triangular, trapezoidal, and gaussian are supported.

### model.type
- `"mlp"` - Multi-layer perceptron (currently the only supported type)

### model.architecture.activation
- `"relu"` - ReLU activation
- `"tanh"` - Hyperbolic tangent
- `"sigmoid"` - Sigmoid activation

### model.architecture.output_activation
- `"softmax"` - For classification (3-class: buy/hold/sell)
- `"sigmoid"` - For binary classification

### model.training.optimizer
- `"adam"` - Adam optimizer (recommended)
- `"sgd"` - Stochastic gradient descent

## CRITICAL: Common Validation Errors (AVOID THESE)

1. **indicators must be a dict**: In v3, indicators is a dict keyed by indicator_id, NOT a list.
   - WRONG: `indicators: [{ name: rsi, period: 14 }]`
   - CORRECT: `indicators: { rsi_14: { type: rsi, period: 14 } }`

2. **fuzzy_sets must have indicator field**: Each fuzzy set must reference an indicator.
   - WRONG: `rsi_momentum: { oversold: ... }` (missing indicator reference)
   - CORRECT: `rsi_momentum: { indicator: rsi_14, oversold: ... }`

3. **nn_inputs is required**: You must explicitly list which fuzzy_set + timeframe combinations to use.
   - Every strategy MUST have an `nn_inputs` section

4. **Use `parameters` not `params`**: The field name is `parameters` (not `params`) for fuzzy set definitions.
   - WRONG: `params: [0, 30, 50]`
   - CORRECT: `parameters: [0, 30, 50]`

5. **Indicator names are case-sensitive**: Use the exact name as shown in the Available Indicators list (with backticks).

6. **DO NOT invent enum values**: Only use values listed above. Never use values like `mode: "adaptive"` or `type: "lstm"`.

## Design Guidelines

1. **Be creative**: Try different approaches, don't just vary parameters
2. **Avoid redundancy**: RSI and Stochastic measure similar things - pick one
3. **Start conservative**: Small networks, fewer epochs - can always scale up
4. **Clear hypothesis**: Know what market behavior you're trying to capture
5. **Data integrity**: Never use training data for backtesting

## Output Format

End your response with a status summary:

```
## Status

Phase: {new_phase}
Strategy: {strategy_name}
Action Taken: {what you did}
Next: {what happens next}
```
"""


class StrategyDesignerPromptBuilder:
    """Builds prompts for the Strategy Designer agent.

    The builder constructs prompts based on trigger reason and operation context,
    injecting available indicators, symbols, and recent strategies.
    """

    def __init__(self):
        """Initialize the prompt builder."""
        self._system_template = SYSTEM_PROMPT_TEMPLATE

    def build(self, context: PromptContext) -> dict[str, str]:
        """Build the prompt for the given context.

        Args:
            context: The prompt context with trigger reason and operation data.

        Returns:
            Dict with 'system' and 'user' keys containing the respective prompts.
        """
        system_prompt = self._build_system_prompt(context)
        user_prompt = self._build_user_prompt(context)

        return {
            "system": system_prompt,
            "user": user_prompt,
        }

    def _build_system_prompt(self, context: PromptContext) -> str:
        """Build the system prompt with static instructions.

        The system prompt defines the agent's role, available tools,
        instructions by trigger reason, and output format.

        Args:
            context: The prompt context (used for any dynamic system elements).

        Returns:
            The system prompt string.
        """
        return self._system_template

    def _build_user_prompt(self, context: PromptContext) -> str:
        """Build the user prompt with dynamic context.

        The user prompt includes:
        - Trigger reason
        - Operation ID and phase
        - Available indicators and symbols
        - Recent strategies (for novelty)
        - Results from training/backtest (if applicable)

        Args:
            context: The prompt context with all dynamic data.

        Returns:
            The user prompt string.
        """
        sections = []

        # Header with trigger reason and operation info
        sections.append(self._format_header(context))

        # Context data based on trigger reason
        sections.append(self._format_context_data(context))

        return "\n\n".join(sections)

    def _format_header(self, context: PromptContext) -> str:
        """Format the header with trigger reason and operation info."""
        return f"""## Current Context

You are being invoked because: {context.trigger_reason.value}
Operation ID: {context.operation_id}
Current Phase: {context.phase}"""

    def _format_context_data(self, context: PromptContext) -> str:
        """Format the context data based on trigger reason."""
        parts = []

        # Trigger-specific context
        if context.trigger_reason == TriggerReason.START_NEW_CYCLE:
            parts.append(self._format_new_cycle_context(context))
        elif context.trigger_reason == TriggerReason.TRAINING_COMPLETED:
            parts.append(self._format_training_completed_context(context))
        elif context.trigger_reason == TriggerReason.BACKTEST_COMPLETED:
            parts.append(self._format_backtest_completed_context(context))

        return "\n\n".join(parts)

    def _format_new_cycle_context(self, context: PromptContext) -> str:
        """Format context for starting a new design cycle."""
        sections = []

        # Research Brief (v2.5 M3) - shown first if provided
        if context.brief:
            sections.append(
                f"""## Research Brief

{context.brief}

**Follow this brief carefully when designing your strategy.** The brief provides specific guidance for this research cycle.

---"""
            )

        sections.append("## Available Resources")

        # Available indicators
        if context.available_indicators:
            indicators_text = self._format_indicators(context.available_indicators)
            sections.append(f"### Available Indicators\n\n{indicators_text}")

        # Available symbols
        if context.available_symbols:
            symbols_text = self._format_symbols(context.available_symbols)
            sections.append(f"### Available Symbols\n\n{symbols_text}")

        # Recent strategies to avoid repetition
        if context.recent_strategies:
            recent_text = self._format_recent_strategies(context.recent_strategies)
            sections.append(
                f"### Recent Strategies (avoid repetition)\n\n{recent_text}"
            )

        # Memory sections (v2.0)
        if context.experiment_history:
            experiment_text = self._format_experiment_history(
                context.experiment_history
            )
            if experiment_text:
                sections.append(experiment_text)

        if context.open_hypotheses:
            hypotheses_text = self._format_hypotheses(context.open_hypotheses)
            if hypotheses_text:
                sections.append(hypotheses_text)

        sections.append(
            """## Your Task

Design a new neuro-fuzzy trading strategy. Be creative - try a different approach than recent strategies. Use the save_strategy_config tool to save your design, then start training."""
        )

        return "\n\n".join(sections)

    def _format_training_completed_context(self, context: PromptContext) -> str:
        """Format context for training completion."""
        sections = ["## Training Results"]

        if context.training_results:
            results_json = json.dumps(context.training_results, indent=2)
            sections.append(f"```json\n{results_json}\n```")

        if context.strategy_config:
            sections.append("### Strategy Configuration")
            config_json = json.dumps(context.strategy_config, indent=2)
            sections.append(f"```json\n{config_json}\n```")

        sections.append(
            """## Your Task

Training is complete. Review the results above and start backtesting on held-out data. Remember to use different data than was used for training."""
        )

        return "\n\n".join(sections)

    def _format_backtest_completed_context(self, context: PromptContext) -> str:
        """Format context for backtest completion."""
        sections = ["## Backtest Results"]

        if context.backtest_results:
            results_json = json.dumps(context.backtest_results, indent=2)
            sections.append(f"```json\n{results_json}\n```")

        if context.training_results:
            sections.append("### Training Results (for reference)")
            training_json = json.dumps(context.training_results, indent=2)
            sections.append(f"```json\n{training_json}\n```")

        if context.strategy_config:
            sections.append("### Strategy Configuration")
            config_json = json.dumps(context.strategy_config, indent=2)
            sections.append(f"```json\n{config_json}\n```")

        sections.append(
            """## Your Task

Backtesting is complete. Analyze the results and write a comprehensive assessment:
- Does this strategy show promise?
- What are its key strengths?
- What are its weaknesses or concerns?
- Suggestions for future improvement

Then update your state with the assessment and mark the cycle as complete."""
        )

        return "\n\n".join(sections)

    def _format_indicators(self, indicators: list[dict[str, Any]]) -> str:
        """Format indicators list in compact token-efficient format.

        Uses backticks around indicator names to emphasize exact case.
        Format: `NAME`(param:default,...) - type

        This compact format saves ~50% tokens compared to verbose JSON.
        """
        if not indicators:
            return "No indicators available"

        lines = []
        # Add case sensitivity warning at the top
        lines.append(
            "**Warning: Indicator names are case-sensitive. Use exact names below.**\n"
        )

        for ind in indicators:
            name = ind.get("name", "unknown")
            ind_type = ind.get("type", "other")
            params = ind.get("parameters", [])

            # Format parameters as name:default pairs
            param_parts = []
            for p in params:
                p_name = p.get("name", "?")
                p_default = p.get("default", "?")
                param_parts.append(f"{p_name}:{p_default}")

            param_str = ",".join(param_parts)

            # Build compact line with backticks for code formatting
            if param_str:
                lines.append(f"- `{name}`({param_str}) - {ind_type}")
            else:
                lines.append(f"- `{name}` - {ind_type}")

        return "\n".join(lines)

    def _format_symbols(self, symbols: list[dict[str, Any]]) -> str:
        """Format symbols list in compact token-efficient format.

        Format: SYMBOL: tf1,tf2,tf3 (start to end)

        This compact format is concise while showing all available data.
        """
        if not symbols:
            return "No symbols available"

        lines = []
        for sym in symbols:
            symbol = sym.get("symbol", "unknown")
            timeframes = sym.get("timeframes", [])
            date_range = sym.get("date_range", {})

            # Get date range
            start = date_range.get("start", "?") if date_range else "?"
            end = date_range.get("end", "?") if date_range else "?"

            # Format timeframes as comma-separated list (no spaces for compactness)
            tf_str = ",".join(timeframes) if timeframes else "unknown"

            lines.append(f"- **{symbol}**: {tf_str} ({start} to {end})")

        return "\n".join(lines)

    def _format_recent_strategies(self, strategies: list[dict[str, Any]]) -> str:
        """Format recent strategies for display."""
        lines = []
        for strat in strategies:
            name = strat.get("name", "unknown")
            strat_type = strat.get("type", "unknown")
            outcome = strat.get("outcome", "unknown")
            sharpe = strat.get("sharpe")
            sharpe_str = f", sharpe={sharpe:.2f}" if sharpe is not None else ""
            lines.append(f"- **{name}** ({strat_type}): {outcome}{sharpe_str}")
        return "\n".join(lines) if lines else "No recent strategies"

    def _format_experiment_history(self, experiments: list[dict[str, Any]]) -> str:
        """Format experiments as contextual observations for reasoning.

        Produces markdown like:
            ## Experiment History

            ### Recent Experiments

            **exp_v15_rsi_di** (2025-12-27)
            - Context: RSI + DI | 1h | EURUSD | zigzag 1.5%
            - Results: 64.8% test
            - Verdict: strong_signal
            - Observations:
              - Combining RSI with DI improved by 0.6pp vs RSI solo

        Args:
            experiments: List of experiment records from memory.

        Returns:
            Formatted markdown string, or empty string if no experiments.
        """
        if not experiments:
            return ""

        lines = ["## Experiment History\n", "### Recent Experiments\n"]

        for exp in experiments:
            lines.append(self._format_single_experiment(exp))

        return "\n".join(lines)

    def _format_single_experiment(self, exp: dict[str, Any]) -> str:
        """Format one experiment with full context.

        Args:
            exp: Single experiment record dict.

        Returns:
            Formatted markdown for one experiment.
        """
        exp_id = exp.get("id", "unknown")
        timestamp = exp.get("timestamp", "")[:10] if exp.get("timestamp") else ""
        ctx = exp.get("context", {})
        res = exp.get("results", {})
        assess = exp.get("assessment", {})

        # Build context string
        indicators = ctx.get("indicators", ["unknown"])
        indicators_str = " + ".join(indicators) if indicators else "unknown"
        timeframe = ctx.get("timeframe", "?")
        symbol = ctx.get("symbol", "?")
        # Format zigzag threshold as percentage for consistency with accuracy display
        zigzag = ctx.get("zigzag_threshold")
        zigzag_str = ""
        if isinstance(zigzag, (int, float)) and zigzag != 0:
            # Values <= 1 are fractional (0.015 = 1.5%), convert to percentage
            zigzag_pct = zigzag * 100 if zigzag <= 1 else zigzag
            zigzag_str = f" | zigzag {zigzag_pct:.1f}%"
        elif zigzag:
            # Preserve non-numeric representations as-is
            zigzag_str = f" | zigzag {zigzag}"
        context_str = f"{indicators_str} | {timeframe} | {symbol}{zigzag_str}"

        # Build results string - convert to percentage if needed
        test_acc = res.get("test_accuracy", 0)
        if isinstance(test_acc, float) and test_acc <= 1:
            test_acc = test_acc * 100
        test_str = f"{test_acc:.1f}%"

        # Build header
        header = f"**{exp_id}**"
        if timestamp:
            header += f" ({timestamp})"

        lines = [
            header,
            f"- Context: {context_str}",
            f"- Results: {test_str} test",
            f"- Verdict: {assess.get('verdict', 'unknown')}",
        ]

        # Add observations (limited to 3)
        observations = assess.get("observations", [])
        if observations:
            lines.append("- Observations:")
            for obs in observations[:3]:
                lines.append(f"  - {obs}")

        return "\n".join(lines) + "\n"

    def _format_hypotheses(self, hypotheses: list[dict[str, Any]]) -> str:
        """Format open hypotheses for the agent to consider.

        Produces markdown like:
            ## Open Hypotheses

            Consider testing one of these hypotheses:

            - **H_001**: Multi-timeframe might break the plateau
              - Source: exp_v15_rsi_di
              - Rationale: Best result so far, but hitting accuracy ceiling

        Args:
            hypotheses: List of hypothesis records from memory.

        Returns:
            Formatted markdown string, or empty string if no hypotheses.
        """
        if not hypotheses:
            return ""

        lines = ["## Open Hypotheses\n"]
        lines.append("Consider testing one of these hypotheses:\n")

        for h in hypotheses:
            h_id = h.get("id", "?")
            text = h.get("text", "")
            source = h.get("source_experiment", "")
            rationale = h.get("rationale", "")

            lines.append(f"- **{h_id}**: {text}")
            if source:
                lines.append(f"  - Source: {source}")
            if rationale:
                lines.append(f"  - Rationale: {rationale}")

        return "\n".join(lines)


def get_strategy_designer_prompt(
    trigger_reason: TriggerReason | str,
    operation_id: str,
    phase: str,
    available_indicators: list[dict[str, Any]] | None = None,
    available_symbols: list[dict[str, Any]] | None = None,
    recent_strategies: list[dict[str, Any]] | None = None,
    training_results: dict[str, Any] | None = None,
    backtest_results: dict[str, Any] | None = None,
    strategy_config: dict[str, Any] | None = None,
    experiment_history: list[dict[str, Any]] | None = None,
    open_hypotheses: list[dict[str, Any]] | None = None,
    brief: str | None = None,
) -> dict[str, str]:
    """Convenience function to build the strategy designer prompt.

    This is the main entry point for getting a prompt. It creates the
    context and builds the prompt in one call.

    Args:
        trigger_reason: Why the agent is being invoked.
        operation_id: Current operation ID.
        phase: Current operation phase.
        available_indicators: List of available indicators.
        available_symbols: List of available symbols.
        recent_strategies: Recent strategies to avoid.
        training_results: Training results (if applicable).
        backtest_results: Backtest results (if applicable).
        strategy_config: Current strategy config.
        experiment_history: Past experiments from memory for contextual reasoning.
        open_hypotheses: Untested hypotheses from memory for exploration guidance.
        brief: Natural language guidance for strategy design (v2.5 M3).

    Returns:
        Dict with 'system' and 'user' keys containing the prompts.
    """
    # Convert string to enum if needed
    if isinstance(trigger_reason, str):
        trigger_reason = TriggerReason(trigger_reason)

    context = PromptContext(
        trigger_reason=trigger_reason,
        operation_id=operation_id,
        phase=phase,
        available_indicators=available_indicators,
        available_symbols=available_symbols,
        recent_strategies=recent_strategies,
        training_results=training_results,
        backtest_results=backtest_results,
        strategy_config=strategy_config,
        experiment_history=experiment_history,
        open_hypotheses=open_hypotheses,
        brief=brief if brief else None,  # Treat empty string as None
    )

    builder = StrategyDesignerPromptBuilder()
    return builder.build(context)


# ==============================================================================
# Assessment Prompt (M5: Assessment Worker)
# ==============================================================================


@dataclass
class AssessmentContext:
    """Context for building the assessment prompt.

    Attributes:
        operation_id: Current assessment operation ID.
        strategy_name: Name of the strategy being assessed.
        strategy_path: Path to the strategy configuration file.
        training_metrics: Results from training phase.
        backtest_metrics: Results from backtest phase.
    """

    operation_id: str
    strategy_name: str
    strategy_path: str
    training_metrics: dict[str, Any]
    backtest_metrics: dict[str, Any]


ASSESSMENT_SYSTEM_PROMPT = """You are an expert trading strategy evaluator. Your role is to:

1. Analyze the training and backtest results objectively
2. Identify strengths and weaknesses of the strategy
3. Provide actionable suggestions for improvement
4. Give an overall verdict on the strategy's potential

Be honest and specific. Reference actual numbers from the results.
Use the save_assessment tool to record your evaluation."""


def _calc_loss_improvement(metrics: dict[str, Any]) -> float:
    """Calculate loss improvement percentage.

    Args:
        metrics: Training metrics dict with initial_loss and final_loss.

    Returns:
        Improvement as a decimal (0.5 = 50% improvement).
    """
    initial = metrics.get("initial_loss", 0)
    final = metrics.get("final_loss", 0)
    if initial > 0:
        return (initial - final) / initial
    return 0.0


def get_assessment_prompt(context: AssessmentContext) -> str:
    """Build prompt for Claude to assess strategy results.

    Args:
        context: Assessment context with metrics.

    Returns:
        Formatted prompt string.
    """
    training = context.training_metrics
    backtest = context.backtest_metrics
    loss_improvement = _calc_loss_improvement(training)

    return f"""# Strategy Assessment Request

## Strategy Information
- **Name**: {context.strategy_name}
- **Operation ID**: {context.operation_id}
- **Configuration**: {context.strategy_path}

## Training Results
- **Accuracy**: {training.get("accuracy", 0):.1%}
- **Final Loss**: {training.get("final_loss", 0):.4f}
- **Initial Loss**: {training.get("initial_loss", 0):.4f}
- **Loss Improvement**: {loss_improvement:.1%}

## Backtest Results
- **Sharpe Ratio**: {backtest.get("sharpe_ratio", 0):.2f}
- **Win Rate**: {backtest.get("win_rate", 0):.1%}
- **Max Drawdown**: {backtest.get("max_drawdown", 0):.1%}
- **Total Return**: {backtest.get("total_return", 0):.1%}
- **Total Trades**: {backtest.get("total_trades", 0)}

## Your Task

Analyze these results and provide your assessment:

1. **Verdict**: Is this strategy "promising", "mediocre", or "poor"?
2. **Strengths**: What aspects performed well? (list 2-4 points)
3. **Weaknesses**: What aspects need improvement? (list 2-4 points)
4. **Suggestions**: How could the strategy be improved? (list 2-4 points)

Use the `save_assessment` tool to record your evaluation.
"""
