"""
Strategy Designer prompt builder for the research agent.

This module provides the prompt building logic for the Strategy Designer agent.
It constructs prompts based on trigger reason and session context, injecting
available indicators, symbols, and recent strategies for context.

Usage:
    builder = StrategyDesignerPromptBuilder()
    ctx = PromptContext(
        trigger_reason=TriggerReason.START_NEW_CYCLE,
        session_id=1,
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
        session_id: Current session ID.
        phase: Current session phase.
        available_indicators: List of available indicators from KTRDR.
        available_symbols: List of available symbols with data.
        recent_strategies: Recent strategies to avoid repetition.
        training_results: Results from training (if trigger is training_completed).
        backtest_results: Results from backtesting (if trigger is backtest_completed).
        strategy_config: Current strategy configuration.
    """

    trigger_reason: TriggerReason
    session_id: int
    phase: str
    available_indicators: list[dict[str, Any]] | None = None
    available_symbols: list[dict[str, Any]] | None = None
    recent_strategies: list[dict[str, Any]] | None = None
    training_results: dict[str, Any] | None = None
    backtest_results: dict[str, Any] | None = None
    strategy_config: dict[str, Any] | None = None


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

## Strategy YAML Template

Use this format when creating strategies:

```yaml
name: "strategy_name_timestamp"
description: "One-line description"
version: "1.0"
hypothesis: "What market behavior are you trying to capture?"

scope: "universal"

training_data:
  symbols:
    mode: "multi_symbol"  # or "single"
    list: ["EURUSD"]
  timeframes:
    mode: "single"  # or "multi_timeframe"
    list: ["1h"]
    base_timeframe: "1h"
  history_required: 200

deployment:
  target_symbols:
    mode: "universal"  # or "training_only" or "group_restricted"
  target_timeframes:
    mode: "single"  # or "multi_timeframe"
    supported: ["1h"]

indicators:
  - name: "rsi"
    feature_id: rsi_14
    period: 14
    source: "close"

fuzzy_sets:
  rsi_14:
    oversold:
      type: "triangular"
      parameters: [0, 20, 35]
    neutral:
      type: "triangular"
      parameters: [30, 50, 70]
    overbought:
      type: "triangular"
      parameters: [65, 80, 100]

model:
  type: "mlp"
  architecture:
    hidden_layers: [32, 16]
    activation: "relu"
    output_activation: "softmax"
    dropout: 0.2
  features:
    include_price_context: false
    lookback_periods: 2
    scale_features: true
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
  position_awareness: true

training:
  method: "supervised"
  labels:
    source: "zigzag"
    zigzag_threshold: 0.03
    label_lookahead: 20
  data_split:
    train: 0.7
    validation: 0.15
    test: 0.15
```

## CRITICAL: Valid Enum Values

You MUST use ONLY these exact values. Using any other value will cause validation failure.

### training_data.symbols.mode
- `"single"` - Train on one symbol only (legacy mode)
- `"multi_symbol"` - Train on multiple symbols

### training_data.timeframes.mode
- `"single"` - Use one timeframe only (legacy mode)
- `"multi_timeframe"` - Use multiple timeframes

### deployment.target_symbols.mode
- `"universal"` - No symbol restrictions (recommended for new strategies)
- `"group_restricted"` - Restricted to specific symbol groups
- `"training_only"` - Only deploy to symbols used in training

### deployment.target_timeframes.mode
- `"single"` - Deploy to single timeframe
- `"multi_timeframe"` - Deploy to multiple timeframes

### fuzzy_sets type (with required parameter counts)
- `"triangular"` - Requires exactly 3 parameters: [left, center, right]
- `"trapezoidal"` - Requires exactly 4 parameters: [left_bottom, left_top, right_top, right_bottom]
- `"gaussian"` - Requires exactly 2 parameters: [mean, sigma]
- `"sigmoid"` - Requires exactly 2 parameters: [center, slope]

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

1. **Missing feature_id**: Every indicator MUST have a `feature_id` field. This is REQUIRED.
   - WRONG: `- name: "RSI", period: 14`
   - CORRECT: `- name: "RSI", feature_id: "rsi_14", period: 14`

2. **fuzzy_sets keys must match feature_id exactly**: The keys in `fuzzy_sets` must match the `feature_id` of the corresponding indicator.
   - If indicator has `feature_id: "rsi_14"`, then fuzzy_sets must have key `rsi_14:`

3. **Use `parameters` not `params`**: The field name is `parameters` (not `params`) for fuzzy set definitions.
   - WRONG: `params: [0, 30, 50]`
   - CORRECT: `parameters: [0, 30, 50]`

4. **Indicator names are case-sensitive**: Use the exact name as shown in the Available Indicators list (with backticks).

5. **DO NOT invent enum values**: Only use values listed above. Never use values like `mode: "adaptive"` or `type: "lstm"`.

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

    The builder constructs prompts based on trigger reason and session context,
    injecting available indicators, symbols, and recent strategies.
    """

    def __init__(self):
        """Initialize the prompt builder."""
        self._system_template = SYSTEM_PROMPT_TEMPLATE

    def build(self, context: PromptContext) -> dict[str, str]:
        """Build the prompt for the given context.

        Args:
            context: The prompt context with trigger reason and session data.

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
        - Session ID and phase
        - Available indicators and symbols
        - Recent strategies (for novelty)
        - Results from training/backtest (if applicable)

        Args:
            context: The prompt context with all dynamic data.

        Returns:
            The user prompt string.
        """
        sections = []

        # Header with trigger reason and session info
        sections.append(self._format_header(context))

        # Context data based on trigger reason
        sections.append(self._format_context_data(context))

        return "\n\n".join(sections)

    def _format_header(self, context: PromptContext) -> str:
        """Format the header with trigger reason and session info."""
        return f"""## Current Context

You are being invoked because: {context.trigger_reason.value}
Session ID: {context.session_id}
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
        sections = ["## Available Resources"]

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
        """Format indicators list for display.

        Uses backticks around indicator names to emphasize exact case and
        adds a case-sensitivity warning.
        """
        lines = []
        # Add case sensitivity warning at the top
        lines.append(
            "**⚠️ Indicator names are case-sensitive. You must use the exact name below.**\n"
        )
        for ind in indicators:
            name = ind.get("name", "unknown")
            desc = ind.get("description", "")
            params = ind.get("parameters", [])
            param_str = ", ".join(p.get("name", "") for p in params) if params else ""
            # Use backticks around indicator name for code formatting
            lines.append(
                f"- `{name}`: {desc}"
                + (f" (params: {param_str})" if param_str else "")
            )
        return "\n".join(lines) if lines else "No indicators available"

    def _format_symbols(self, symbols: list[dict[str, Any]]) -> str:
        """Format symbols list for display."""
        lines = []
        for sym in symbols:
            symbol = sym.get("symbol", "unknown")
            timeframes = sym.get("timeframes", [])
            date_range = sym.get("date_range", {})
            tf_str = ", ".join(timeframes) if timeframes else "unknown"
            start = date_range.get("start", "?")
            end = date_range.get("end", "?")
            lines.append(
                f"- **{symbol}**: timeframes [{tf_str}], data range {start} to {end}"
            )
        return "\n".join(lines) if lines else "No symbols available"

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


def get_strategy_designer_prompt(
    trigger_reason: TriggerReason | str,
    session_id: int,
    phase: str,
    available_indicators: list[dict[str, Any]] | None = None,
    available_symbols: list[dict[str, Any]] | None = None,
    recent_strategies: list[dict[str, Any]] | None = None,
    training_results: dict[str, Any] | None = None,
    backtest_results: dict[str, Any] | None = None,
    strategy_config: dict[str, Any] | None = None,
) -> dict[str, str]:
    """Convenience function to build the strategy designer prompt.

    This is the main entry point for getting a prompt. It creates the
    context and builds the prompt in one call.

    Args:
        trigger_reason: Why the agent is being invoked.
        session_id: Current session ID.
        phase: Current session phase.
        available_indicators: List of available indicators.
        available_symbols: List of available symbols.
        recent_strategies: Recent strategies to avoid.
        training_results: Training results (if applicable).
        backtest_results: Backtest results (if applicable).
        strategy_config: Current strategy config.

    Returns:
        Dict with 'system' and 'user' keys containing the prompts.
    """
    # Convert string to enum if needed
    if isinstance(trigger_reason, str):
        trigger_reason = TriggerReason(trigger_reason)

    context = PromptContext(
        trigger_reason=trigger_reason,
        session_id=session_id,
        phase=phase,
        available_indicators=available_indicators,
        available_symbols=available_symbols,
        recent_strategies=recent_strategies,
        training_results=training_results,
        backtest_results=backtest_results,
        strategy_config=strategy_config,
    )

    builder = StrategyDesignerPromptBuilder()
    return builder.build(context)
