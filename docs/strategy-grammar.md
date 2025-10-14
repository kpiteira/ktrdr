# KTRDR Strategy Configuration Grammar

## Formal Grammar Specification

This document defines the formal grammar for KTRDR strategy configuration files using Extended Backus-Naur Form (EBNF).

## Version History
- **v1.0**: Legacy format with single symbol/timeframe focus
- **v2.0**: Clean format with systematic comments, pure fuzzy logic, and AI agent optimization
- **v2.1**: Added required `feature_id` field to indicators for explicit fuzzy set mapping (2025-10-14)

## V2.0 Commenting Requirements
Every parameter in v2.0 strategies MUST include explanatory comments that:
- Explain the rationale behind each choice
- Make strategies self-documenting for both humans and AI agents
- Support automated strategy research and variation generation
- Follow consistent comment patterns for parsing by AI systems

## Design Principles
- **Self-documenting**: Every parameter requires explanatory comments
- **AI-friendly**: Clear reasoning for automated strategy research
- **Pure fuzzy**: Only fuzzy logic features, no legacy ML components
- **Clean structure**: Logical field ordering and consistent formatting
- **Hypothesis-driven**: Explicit strategy beliefs for testing

## Grammar Definition

### Root Structure
```ebnf
StrategyConfig ::= V1Strategy | V2Strategy

V1Strategy ::= MetaSection 
               DataSection? 
               IndicatorSection 
               FuzzySection 
               ModelSection 
               DecisionSection 
               TrainingSection 
               OptionalSections*

V2Strategy ::= MetaSection 
               HypothesisSection 
               ScopeSection 
               TrainingDataSection 
               DeploymentSection 
               IndicatorSection 
               FuzzySection 
               ModelSection 
               DecisionSection 
               TrainingSection 
               OptionalSections*
```

### Meta Information (Required)
```ebnf
MetaSection ::= "name:" String CommentLine
                "description:" String CommentLine
                "version:" VersionString CommentLine

HypothesisSection ::= "hypothesis:" String CommentLine

CommentLine ::= '#' [^\n]* '\n'

VersionString ::= '"' VersionNumber '"'
VersionNumber ::= [0-9]+ '.' [0-9]+ ('.' [0-9]+)? Suffix?
Suffix ::= '_v2' | '.neuro' | '-alpha' | '-beta' | '-rc' [0-9]+
```

### V1 Legacy Format
```ebnf
DataSection ::= "data:" 
                "  symbols:" SymbolList 
                "  timeframes:" TimeframeList 
                "  history_required:" Integer

SymbolList ::= '[' String (',' String)* ']'
TimeframeList ::= '[' Timeframe (',' Timeframe)* ']'
Timeframe ::= '"' ([0-9]+ ('m'|'h'|'d'|'w')) '"'
```

### V2 Multi-Scope Format
```ebnf
ScopeSection ::= "scope:" ScopeType CommentLine
ScopeType ::= '"symbol_specific"' | '"symbol_group"' | '"universal"'

TrainingDataSection ::= "training_data:" CommentLine
                        "  symbols:" SymbolConfiguration CommentLine
                        "  timeframes:" TimeframeConfiguration CommentLine
                        "  history_required:" Integer CommentLine
                        "  start_date:" Date? CommentLine
                        "  end_date:" Date? CommentLine

SymbolConfiguration ::= "mode:" SymbolMode
                        ("list:" SymbolList | "symbol:" String | "selection_criteria:" SelectionCriteria)

SymbolMode ::= '"single"' | '"multi_symbol"' | '"symbol_group"'

TimeframeConfiguration ::= "mode:" TimeframeMode
                           ("timeframe:" Timeframe | "list:" TimeframeList)
                           "base_timeframe:" Timeframe?

TimeframeMode ::= '"single"' | '"multi_timeframe"'

DeploymentSection ::= "deployment:" CommentLine
                      "  target_symbols:" TargetSymbolConfiguration CommentLine
                      "  target_timeframes:" TargetTimeframeConfiguration CommentLine

TargetSymbolConfiguration ::= "mode:" TargetSymbolMode
                              "restrictions:" Restrictions?

TargetSymbolMode ::= '"training_only"' | '"group_restricted"' | '"universal"'
```

### Technical Indicators (Required)
```ebnf
IndicatorSection ::= "indicators:" CommentLine IndicatorList
IndicatorList ::= ('-' IndicatorDefinition CommentLine)+

IndicatorDefinition ::= "name:" IndicatorName CommentLine
                        "feature_id:" FeatureId CommentLine
                        IndicatorParameters*

IndicatorName ::= '"rsi"' | '"macd"' | '"sma"' | '"ema"' | '"bollinger"' |
                  '"stoch"' | '"atr"' | '"adx"' | '"williams_r"' | String

FeatureId ::= String  # Must be unique within strategy, alphanumeric/underscore/dash only, cannot be reserved word

IndicatorParameters ::= "period:" Integer CommentLine |
                        "fast_period:" Integer |
                        "slow_period:" Integer |
                        "signal_period:" Integer |
                        "source:" PriceSource |
                        "std_dev:" Number

PriceSource ::= '"open"' | '"high"' | '"low"' | '"close"' | '"volume"' | '"hl2"' | '"hlc3"' | '"ohlc4"'
```

### Fuzzy Logic Configuration (Required)
```ebnf
FuzzySection ::= "fuzzy_sets:" CommentLine FuzzySetDefinitions
FuzzySetDefinitions ::= (IndicatorName ':' CommentLine FuzzySets)+

FuzzySets ::= (FuzzySetName ':' CommentLine FuzzySetDefinition)+
FuzzySetName ::= '"oversold"' | '"neutral"' | '"overbought"' | 
                 '"negative"' | '"positive"' |
                 '"below"' | '"near"' | '"above"' |
                 '"low"' | '"medium"' | '"high"' | String

FuzzySetDefinition ::= LegacyFormat | SimplifiedFormat

LegacyFormat ::= "type:" FuzzyType
                 "parameters:" ParameterList

SimplifiedFormat ::= ParameterList

FuzzyType ::= '"triangular"' | '"trapezoidal"' | '"gaussian"'
ParameterList ::= '[' Number (',' Number)* ']'
```

### Neural Network Model (Required)
```ebnf
ModelSection ::= "model:" CommentLine ModelDefinition
ModelDefinition ::= "type:" ModelType CommentLine
                    "architecture:" ArchitectureConfig CommentLine
                    "training:" TrainingConfig CommentLine
                    "features:" FeatureConfig CommentLine

ModelType ::= '"mlp"' | '"lstm"' | '"gru"' | '"transformer"' | '"cnn"'

ArchitectureConfig ::= "hidden_layers:" LayerList
                       "activation:" ActivationFunction
                       "output_activation:" ActivationFunction
                       "dropout:" Number
                       V2ArchitectureOptions*

V2ArchitectureOptions ::= "symbol_embedding_dim:" Integer |
                          "attention_mechanism:" Boolean |
                          "residual_connections:" Boolean

LayerList ::= '[' Integer (',' Integer)* ']'
ActivationFunction ::= '"relu"' | '"tanh"' | '"sigmoid"' | '"leaky_relu"' | '"gelu"' | '"swish"'

TrainingConfig ::= "learning_rate:" Number
                   "batch_size:" Integer
                   "epochs:" Integer
                   "optimizer:" OptimizerType
                   OptimizerOptions*
                   SchedulerConfig?
                   EarlyStoppingConfig?

OptimizerType ::= '"adam"' | '"sgd"' | '"rmsprop"' | '"adamw"'

FeatureConfig ::= "include_price_context:" Boolean
                  "include_volume_context:" Boolean
                  "include_raw_indicators:" Boolean
                  "lookback_periods:" Integer
                  "scale_features:" Boolean
                  V2FeatureOptions*

V2FeatureOptions ::= "timeframe_features:" Boolean |
                     "feature_combination:" CombinationMethod

CombinationMethod ::= '"concatenation"' | '"attention"' | '"average"'
```

### Decision Logic (Required)
```ebnf
DecisionSection ::= "decisions:" CommentLine DecisionConfig
DecisionConfig ::= "output_format:" OutputFormat CommentLine
                   "confidence_threshold:" Number CommentLine
                   "position_awareness:" Boolean CommentLine
                   "filters:" FilterConfig? CommentLine
                   V2DecisionOptions*

OutputFormat ::= '"classification"' | '"regression"' | '"probability"'

V2DecisionOptions ::= "symbol_aware_decisions:" Boolean |
                      "cross_symbol_consistency:" Boolean

FilterConfig ::= "min_signal_separation:" Integer
                 "volume_filter:" Boolean
                 "momentum_filter:" Boolean?
```

### Training Configuration (Required)
```ebnf
TrainingSection ::= "training:" CommentLine TrainingDefinition
TrainingDefinition ::= "method:" TrainingMethod CommentLine
                       "labels:" LabelConfig CommentLine
                       "data_split:" DataSplitConfig CommentLine
                       "fitness_metrics:" MetricsConfig CommentLine
                       V2TrainingOptions*

TrainingMethod ::= '"supervised"' | '"reinforcement"' | '"self_supervised"'

LabelConfig ::= "source:" LabelSource
                "zigzag_threshold:" Number
                "label_lookahead:" Integer
                LabelOptions*

LabelSource ::= '"zigzag"' | '"forward_returns"' | '"volatility"' | '"manual"'

DataSplitConfig ::= "train:" Number
                    "validation:" Number
                    "test:" Number

V2TrainingOptions ::= "split_strategy:" SplitStrategy |
                      "cross_symbol_evaluation:" Boolean |
                      "balanced_sampling:" Boolean

SplitStrategy ::= '"temporal"' | '"random"' | '"stratified"'

MetricsConfig ::= "primary:" PrimaryMetric
                  "secondary:" '[' SecondaryMetric (',' SecondaryMetric)* ']'

PrimaryMetric ::= '"accuracy"' | '"f1_score"' | '"precision"' | '"recall"' | '"cross_symbol_accuracy"'
SecondaryMetric ::= '"accuracy"' | '"precision"' | '"recall"' | '"f1_score"' | 
                    '"per_symbol_accuracy"' | '"generalization_score"' | '"attention_diversity"'
```

### Optional Sections
```ebnf
OptionalSections ::= OrchestratorSection | RiskManagementSection | BacktestingSection

OrchestratorSection ::= "orchestrator:" OrchestratorConfig
OrchestratorConfig ::= "max_position_size:" Number
                       "signal_cooldown:" Integer
                       "modes:" ModeConfig

RiskManagementSection ::= "risk_management:" RiskConfig
RiskConfig ::= "position_sizing:" PositioningMethod
               "risk_per_trade:" Number
               "max_portfolio_risk:" Number

BacktestingSection ::= "backtesting:" BacktestConfig
BacktestConfig ::= "start_date:" Date
                   "end_date:" Date
                   "initial_capital:" Number
                   "transaction_costs:" Number
                   "slippage:" Number
```

### Common Types
```ebnf
String ::= '"' [^"]* '"'
Integer ::= [0-9]+
Number ::= [0-9]+ ('.' [0-9]+)?
Boolean ::= 'true' | 'false'
Date ::= '"' [0-9]{4} '-' [0-9]{2} '-' [0-9]{2} '"'
```

## Validation Rules

### Version-Specific Constraints
1. **V1 Strategies MUST have**:
   - `data` section with `symbols` and `timeframes`
   - No `scope`, `training_data`, or `deployment` sections

2. **V2 Strategies MUST have**:
   - `scope` field
   - `training_data` section with symbol/timeframe configurations  
   - `deployment` section with target configurations
   - No legacy `data` section

### Cross-Section Validation
1. **Symbol/Timeframe Consistency**:
   - V2 deployment targets must be subset of training data
   - Timeframe lists must contain valid timeframe strings

2. **Model/Feature Compatibility**:
   - Multi-timeframe features require `timeframe_features: true`
   - Symbol embeddings require multi-symbol training data

3. **Scope Validation**:
   - `universal` scope requires multi-symbol AND multi-timeframe training
   - `symbol_group` scope requires multi-symbol training
   - `symbol_specific` scope allows single symbol training

## V2.0 Strategy Example with Comments

```yaml
# === STRATEGY IDENTITY ===
name: "mean_reversion_rsi_macd"  # Descriptive name indicating core methodology
description: "RSI oversold signals with MACD confirmation for mean reversion"  # One-line summary
version: "2.0"  # Strategy format version for compatibility tracking
hypothesis: "RSI oversold conditions create profitable mean reversion opportunities when confirmed by MACD divergence in trending markets"  # Core belief being tested

# === STRATEGY SCOPE ===
scope: "symbol_group"  # Multi-symbol strategy for portfolio diversification

# === TRAINING APPROACH ===
training_data:
  symbols:
    mode: "multi_symbol"  # Train across multiple assets for generalization
    list: ["EURUSD", "GBPUSD", "USDJPY"]  # Major forex pairs chosen for high liquidity
  timeframes:
    mode: "multi_timeframe"  # Multi-timeframe: 1h for signals, 4h for trend context
    list: ["1h", "4h"]
    base_timeframe: "1h"  # Primary signal generation timeframe
  history_required: 500  # Extended history for robust statistical learning

# === DEPLOYMENT TARGETS ===
deployment:
  target_symbols:
    mode: "group_restricted"  # Deploy only on trained symbol group
  target_timeframes:
    mode: "multi_timeframe"  # Support both training timeframes
    supported: ["1h", "4h"]

# === TECHNICAL INDICATORS ===
indicators:  # Core indicators for mean reversion detection
- name: "rsi"  # RSI for oversold/overbought identification
  period: 14  # Standard period for reliable signals
  source: "close"  # Close price for consistency
- name: "macd"  # MACD for momentum confirmation
  fast_period: 12  # Fast EMA for responsiveness
  slow_period: 26  # Slow EMA for stability
  signal_period: 9  # Signal line for entry timing
```

## Migration Rules

### V1 → V2 Clean Migration
```yaml
# V1 Input:
data:
  symbols: ["AAPL", "MSFT"]
  timeframes: ["1h", "4h"]

# V2 Output with Comments:
scope: "symbol_group"  # Inferred from multi-symbol training
training_data:
  symbols:
    mode: "multi_symbol"  # Multiple symbols for cross-asset learning
    list: ["AAPL", "MSFT"]  # Technology stocks with correlated behavior
  timeframes:
    mode: "multi_timeframe"  # Multiple timeframes for context
    list: ["1h", "4h"]  # Short-term signals with medium-term confirmation
    base_timeframe: "1h"  # Primary trading timeframe
deployment:
  target_symbols:
    mode: "group_restricted"  # Deploy only on trained assets
  target_timeframes:
    mode: "multi_timeframe"  # Support all training timeframes
    supported: ["1h", "4h"]
```

## Reserved Keywords
- `name`, `description`, `version`, `scope`
- `training_data`, `deployment`, `data`
- `indicators`, `fuzzy_sets`, `model`, `decisions`, `training`
- `orchestrator`, `risk_management`, `backtesting`
- All indicator names, fuzzy set names, activation functions
- All enum values for modes, types, sources

## Best Practices
1. **Always include version field**: `version: "2.0"`
2. **Use quoted strings** for all string values
3. **Follow naming conventions**: snake_case for keys, lowercase for values
4. **Comment every parameter** with rationale for AI agent understanding
5. **Maintain logical section order** as defined in grammar
6. **Use hypothesis section** to clearly state strategy beliefs
7. **Validate before deployment** using `ktrdr strategies validate`

## Comment Standards for V2.0

### Section Headers
```yaml
# === SECTION NAME ===  # Clear visual separation
```

### Parameter Comments
```yaml
parameter: value  # Explanation of why this value was chosen
```

### List Comments
```yaml
list_field:  # Purpose of the list
- item1  # Reason for including this item
- item2  # Reason for including this item
```

### Complex Structure Comments
```yaml
section:  # Overall purpose of this configuration
  subsection:
    parameter: value  # Specific rationale for this parameter
```