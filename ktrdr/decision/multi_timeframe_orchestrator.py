"""
Multi-timeframe decision orchestrator that coordinates decisions across multiple timeframes.

This module extends the single-timeframe DecisionOrchestrator to handle 
multi-timeframe analysis, consensus building, and integrated decision making.
"""

import yaml
import pandas as pd
import numpy as np
from dataclasses import dataclass, asdict
from typing import Dict, Any, Optional, List, Tuple
from pathlib import Path
from datetime import datetime

from .base import Signal, Position, TradingDecision
from .orchestrator import DecisionOrchestrator, DecisionContext, PositionState
from ..data.data_manager import DataManager
from ..indicators.indicator_engine import IndicatorEngine
from ..fuzzy.engine import FuzzyEngine
from ..training.multi_timeframe_model_storage import MultiTimeframeModelStorage
from ..training.multi_timeframe_label_generator import MultiTimeframeLabelGenerator
from ..neural.models.multi_timeframe_mlp import MultiTimeframeMLP
from .. import get_logger

# Set up module-level logger
logger = get_logger(__name__)


@dataclass
class TimeframeDecisionContext:
    """Decision context for a specific timeframe."""
    
    timeframe: str
    current_bar: pd.Series
    recent_bars: pd.DataFrame
    indicators: Dict[str, float]
    fuzzy_memberships: Dict[str, float]
    data_quality_score: float
    freshness_score: float
    

@dataclass
class MultiTimeframeDecisionContext:
    """Complete multi-timeframe decision context."""
    
    symbol: str
    timestamp: pd.Timestamp
    
    # Timeframe-specific contexts
    timeframe_contexts: Dict[str, TimeframeDecisionContext]
    
    # Portfolio and position state (shared across timeframes)
    current_position: Position
    position_entry_price: Optional[float]
    position_holding_period: Optional[float]
    unrealized_pnl: Optional[float]
    portfolio_value: float
    available_capital: float
    
    # Historical context
    recent_decisions: List[TradingDecision]
    last_signal_time: Optional[pd.Timestamp]
    
    # Multi-timeframe metadata
    primary_timeframe: str
    timeframe_weights: Dict[str, float]
    

@dataclass
class TimeframeDecision:
    """Decision from a specific timeframe."""
    
    timeframe: str
    signal: Signal
    confidence: float
    weight: float
    reasoning: Dict[str, Any]
    data_quality: float
    

@dataclass
class MultiTimeframeConsensus:
    """Consensus analysis across timeframes."""
    
    final_signal: Signal
    consensus_confidence: float
    timeframe_decisions: Dict[str, TimeframeDecision]
    agreement_score: float
    conflicting_timeframes: List[str]
    primary_timeframe_influence: float
    consensus_method: str
    reasoning: Dict[str, Any]


class MultiTimeframeDecisionOrchestrator:
    """
    Enhanced decision orchestrator for multi-timeframe analysis.
    
    Coordinates decision making across multiple timeframes using:
    - Individual timeframe analysis
    - Cross-timeframe consensus building  
    - Hierarchical decision resolution
    - Risk management integration
    """
    
    def __init__(
        self,
        strategy_config_path: str,
        model_path: Optional[str] = None,
        mode: str = "backtest",
        timeframes: Optional[List[str]] = None
    ):
        """
        Initialize multi-timeframe decision orchestrator.
        
        Args:
            strategy_config_path: Path to strategy YAML file
            model_path: Path to trained multi-timeframe model
            mode: Operating mode (backtest, paper, live)
            timeframes: List of timeframes to analyze (from config if None)
        """
        self.mode = mode
        
        # Load strategy configuration
        self.strategy_config = self._load_strategy_config(strategy_config_path)
        self.strategy_name = self.strategy_config["name"]
        
        # Extract multi-timeframe configuration
        self.timeframes = timeframes or self._extract_timeframes_from_config()
        self.primary_timeframe = self._determine_primary_timeframe()
        self.timeframe_weights = self._calculate_timeframe_weights()
        
        logger.info(f"Initialized MultiTimeframeDecisionOrchestrator for {len(self.timeframes)} timeframes: {self.timeframes}")
        
        # Initialize single-timeframe orchestrators for each timeframe
        self.timeframe_orchestrators: Dict[str, DecisionOrchestrator] = {}
        for timeframe in self.timeframes:
            # Create timeframe-specific config
            tf_config_path = self._create_timeframe_config(timeframe)
            self.timeframe_orchestrators[timeframe] = DecisionOrchestrator(
                strategy_config_path=tf_config_path,
                model_path=None,  # Will load multi-timeframe model separately
                mode=mode
            )
        
        # Load multi-timeframe model if specified
        self.multi_timeframe_model = None
        self.model_metadata = None
        if model_path:
            self._load_multi_timeframe_model(model_path)
        
        # Initialize multi-timeframe components
        self.data_manager = DataManager()
        self.model_storage = MultiTimeframeModelStorage()
        
        # State management
        self.position_states: Dict[str, PositionState] = {}
        self.decision_history: List[TradingDecision] = []
        self.consensus_history: List[MultiTimeframeConsensus] = []
        self.max_history = 100
        
    def make_multi_timeframe_decision(
        self,
        symbol: str,
        timeframe_data: Dict[str, pd.DataFrame],
        portfolio_state: Dict[str, Any]
    ) -> TradingDecision:
        """
        Generate trading decision using multi-timeframe analysis.
        
        Args:
            symbol: Trading symbol
            timeframe_data: Historical data for each timeframe
            portfolio_state: Current portfolio/account state
            
        Returns:
            Final trading decision with multi-timeframe reasoning
        """
        logger.info(f"Making multi-timeframe decision for {symbol}")
        
        # Step 1: Prepare multi-timeframe context
        context = self._prepare_multi_timeframe_context(
            symbol=symbol,
            timeframe_data=timeframe_data,
            portfolio_state=portfolio_state
        )
        
        # Step 2: Generate individual timeframe decisions
        timeframe_decisions = self._generate_timeframe_decisions(context)
        
        # Step 3: Build consensus across timeframes
        consensus = self._build_multi_timeframe_consensus(timeframe_decisions, context)
        
        # Step 4: Apply multi-timeframe orchestrator logic
        final_decision = self._apply_multi_timeframe_logic(consensus, context)
        
        # Step 5: Update state and history
        self._update_multi_timeframe_state(symbol, final_decision, consensus, context)
        
        logger.info(f"Multi-timeframe decision for {symbol}: {final_decision.signal.value} "
                   f"(confidence: {final_decision.confidence:.3f})")
        
        return final_decision
    
    def _extract_timeframes_from_config(self) -> List[str]:
        """Extract timeframes from strategy configuration."""
        timeframe_configs = self.strategy_config.get("timeframe_configs", {})
        if timeframe_configs:
            return list(timeframe_configs.keys())
        
        # Fallback to default timeframes
        return ["1h", "4h", "1d"]
    
    def _determine_primary_timeframe(self) -> str:
        """Determine primary timeframe for decision hierarchy."""
        timeframe_configs = self.strategy_config.get("timeframe_configs", {})
        
        # Look for explicitly marked primary timeframe
        for tf, config in timeframe_configs.items():
            if config.get("primary", False):
                return tf
        
        # Default to middle timeframe
        if len(self.timeframes) >= 2:
            return self.timeframes[len(self.timeframes) // 2]
        
        return self.timeframes[0] if self.timeframes else "1h"
    
    def _calculate_timeframe_weights(self) -> Dict[str, float]:
        """Calculate weights for each timeframe."""
        timeframe_configs = self.strategy_config.get("timeframe_configs", {})
        weights = {}
        
        for tf in self.timeframes:
            config = timeframe_configs.get(tf, {})
            weights[tf] = config.get("weight", 1.0 / len(self.timeframes))
        
        # Normalize weights to sum to 1.0
        total_weight = sum(weights.values())
        if total_weight > 0:
            weights = {tf: w / total_weight for tf, w in weights.items()}
        
        return weights
    
    def _create_timeframe_config(self, timeframe: str) -> str:
        """Create temporary timeframe-specific configuration."""
        # For now, use the base config for all timeframes
        # In a full implementation, this would create timeframe-specific configs
        return Path(self.strategy_config.get("config_path", "strategies/multi_timeframe_config.yaml"))
    
    def _load_multi_timeframe_model(self, model_path: str):
        """Load multi-timeframe neural network model."""
        try:
            # Parse model path to extract components
            model_parts = Path(model_path).name.split("_")
            if len(model_parts) < 3:
                raise ValueError(f"Invalid multi-timeframe model path: {model_path}")
            
            symbol = model_parts[0]
            timeframes_str = "_".join(model_parts[1:-1])  # Everything except version
            timeframes = timeframes_str.split("_")
            
            # Load using multi-timeframe storage
            model_data = self.model_storage.load_multi_timeframe_model(
                strategy_name=self.strategy_name,
                symbol=symbol,
                timeframes=timeframes
            )
            
            self.multi_timeframe_model = model_data["model"]
            self.model_metadata = model_data["metadata"]
            
            logger.info(f"Loaded multi-timeframe model for {symbol} with timeframes {timeframes}")
            
        except Exception as e:
            logger.warning(f"Failed to load multi-timeframe model: {e}")
            self.multi_timeframe_model = None
            self.model_metadata = None
    
    def _prepare_multi_timeframe_context(
        self,
        symbol: str,
        timeframe_data: Dict[str, pd.DataFrame],
        portfolio_state: Dict[str, Any]
    ) -> MultiTimeframeDecisionContext:
        """Prepare comprehensive multi-timeframe context."""
        
        # Get position state
        if symbol not in self.position_states:
            self.position_states[symbol] = PositionState(symbol)
        position_state = self.position_states[symbol]
        
        # Prepare timeframe-specific contexts
        timeframe_contexts = {}
        for timeframe in self.timeframes:
            if timeframe in timeframe_data:
                tf_context = self._prepare_timeframe_context(
                    timeframe, timeframe_data[timeframe]
                )
                timeframe_contexts[timeframe] = tf_context
        
        # Get recent decisions for this symbol
        recent_decisions = [
            d for d in self.decision_history[-20:]
            if d.reasoning.get("symbol") == symbol
        ]
        
        return MultiTimeframeDecisionContext(
            symbol=symbol,
            timestamp=pd.Timestamp.now(tz="UTC"),
            timeframe_contexts=timeframe_contexts,
            current_position=position_state.position,
            position_entry_price=position_state.entry_price,
            position_holding_period=position_state.holding_period,
            unrealized_pnl=position_state.unrealized_pnl,
            portfolio_value=portfolio_state.get("total_value", 0),
            available_capital=portfolio_state.get("available_capital", 0),
            recent_decisions=recent_decisions,
            last_signal_time=position_state.last_signal_time,
            primary_timeframe=self.primary_timeframe,
            timeframe_weights=self.timeframe_weights
        )
    
    def _prepare_timeframe_context(
        self,
        timeframe: str,
        data: pd.DataFrame
    ) -> TimeframeDecisionContext:
        """Prepare context for a specific timeframe."""
        
        if data.empty:
            logger.warning(f"Empty data for timeframe {timeframe}")
            return TimeframeDecisionContext(
                timeframe=timeframe,
                current_bar=pd.Series(),
                recent_bars=pd.DataFrame(),
                indicators={},
                fuzzy_memberships={},
                data_quality_score=0.0,
                freshness_score=0.0
            )
        
        current_bar = data.iloc[-1]
        recent_bars = data.tail(20)
        
        # Calculate indicators for this timeframe
        orchestrator = self.timeframe_orchestrators[timeframe]
        indicators_df = orchestrator.indicator_engine.apply(data)
        
        # Map indicators (same logic as single-timeframe orchestrator)
        indicators = {}
        for config in self.strategy_config["indicators"]:
            original_name = config["name"]
            indicator_type = config["name"].upper()
            
            for col in indicators_df.columns:
                if col.upper().startswith(indicator_type):
                    if indicator_type in ["SMA", "EMA"]:
                        indicators[original_name] = (
                            data["close"].iloc[-1] / indicators_df[col].iloc[-1]
                        )
                    elif indicator_type == "MACD":
                        if (col.startswith("MACD_") and 
                            "_signal_" not in col and "_hist_" not in col):
                            indicators[original_name] = indicators_df[col].iloc[-1]
                            break
                    else:
                        indicators[original_name] = indicators_df[col].iloc[-1]
                        break
        
        # Generate fuzzy memberships
        fuzzy_values = {}
        for indicator_name, indicator_value in indicators.items():
            if indicator_name in self.strategy_config["fuzzy_sets"]:
                membership_result = orchestrator.fuzzy_engine.fuzzify(
                    indicator_name, indicator_value
                )
                fuzzy_values.update(membership_result)
        
        # Calculate data quality metrics
        data_quality_score = self._calculate_data_quality(data)
        freshness_score = self._calculate_freshness_score(data, timeframe)
        
        return TimeframeDecisionContext(
            timeframe=timeframe,
            current_bar=current_bar,
            recent_bars=recent_bars,
            indicators=indicators,
            fuzzy_memberships=fuzzy_values,
            data_quality_score=data_quality_score,
            freshness_score=freshness_score
        )
    
    def _calculate_data_quality(self, data: pd.DataFrame) -> float:
        """Calculate data quality score for timeframe data."""
        if data.empty:
            return 0.0
        
        quality_factors = []
        
        # Completeness: ratio of non-null values
        completeness = 1.0 - data.isnull().sum().sum() / (len(data) * len(data.columns))
        quality_factors.append(completeness)
        
        # Consistency: check for reasonable price relationships
        if "high" in data.columns and "low" in data.columns:
            valid_hl = (data["high"] >= data["low"]).mean()
            quality_factors.append(valid_hl)
        
        # Volume consistency (if available)
        if "volume" in data.columns:
            volume_validity = (data["volume"] >= 0).mean()
            quality_factors.append(volume_validity)
        
        return np.mean(quality_factors)
    
    def _calculate_freshness_score(self, data: pd.DataFrame, timeframe: str) -> float:
        """Calculate data freshness score."""
        if data.empty:
            return 0.0
        
        # Get expected interval for timeframe
        interval_map = {"1m": 1, "5m": 5, "15m": 15, "1h": 60, "4h": 240, "1d": 1440}
        expected_interval_minutes = interval_map.get(timeframe, 60)
        
        # Calculate time since last data point
        last_timestamp = data.index[-1]
        current_time = pd.Timestamp.now(tz="UTC")
        
        if last_timestamp.tz is None:
            last_timestamp = last_timestamp.tz_localize("UTC")
        
        minutes_since_last = (current_time - last_timestamp).total_seconds() / 60
        
        # Score based on how recent the data is relative to expected interval
        if minutes_since_last <= expected_interval_minutes:
            return 1.0
        elif minutes_since_last <= expected_interval_minutes * 2:
            return 0.8
        elif minutes_since_last <= expected_interval_minutes * 5:
            return 0.5
        else:
            return 0.2
    
    def _generate_timeframe_decisions(
        self,
        context: MultiTimeframeDecisionContext
    ) -> Dict[str, TimeframeDecision]:
        """Generate individual decisions for each timeframe."""
        
        timeframe_decisions = {}
        
        for timeframe in self.timeframes:
            if timeframe not in context.timeframe_contexts:
                logger.warning(f"No context available for timeframe {timeframe}")
                continue
            
            tf_context = context.timeframe_contexts[timeframe]
            
            # Generate decision using timeframe-specific orchestrator
            orchestrator = self.timeframe_orchestrators[timeframe]
            
            # Create portfolio state dict for the orchestrator
            portfolio_state = {
                "total_value": context.portfolio_value,
                "available_capital": context.available_capital
            }
            
            try:
                # Generate timeframe decision
                decision = orchestrator.make_decision(
                    symbol=context.symbol,
                    timeframe=timeframe,
                    current_bar=tf_context.current_bar,
                    historical_data=tf_context.recent_bars,
                    portfolio_state=portfolio_state
                )
                
                # Adjust confidence based on data quality
                quality_adjusted_confidence = (
                    decision.confidence * 
                    tf_context.data_quality_score * 
                    tf_context.freshness_score
                )
                
                timeframe_decision = TimeframeDecision(
                    timeframe=timeframe,
                    signal=decision.signal,
                    confidence=quality_adjusted_confidence,
                    weight=self.timeframe_weights.get(timeframe, 1.0),
                    reasoning=decision.reasoning,
                    data_quality=tf_context.data_quality_score
                )
                
                timeframe_decisions[timeframe] = timeframe_decision
                
                logger.debug(f"Timeframe {timeframe} decision: {decision.signal.value} "
                           f"(confidence: {quality_adjusted_confidence:.3f})")
                
            except Exception as e:
                logger.error(f"Failed to generate decision for timeframe {timeframe}: {e}")
                continue
        
        return timeframe_decisions
    
    def _build_multi_timeframe_consensus(
        self,
        timeframe_decisions: Dict[str, TimeframeDecision],
        context: MultiTimeframeDecisionContext
    ) -> MultiTimeframeConsensus:
        """Build consensus across timeframe decisions."""
        
        if not timeframe_decisions:
            logger.warning("No timeframe decisions available for consensus")
            return MultiTimeframeConsensus(
                final_signal=Signal.HOLD,
                consensus_confidence=0.0,
                timeframe_decisions=timeframe_decisions,
                agreement_score=0.0,
                conflicting_timeframes=[],
                primary_timeframe_influence=0.0,
                consensus_method="none",
                reasoning={"error": "No timeframe decisions available"}
            )
        
        # Get consensus method from config
        consensus_config = self.strategy_config.get("multi_timeframe", {})
        consensus_method = consensus_config.get("consensus_method", "weighted_majority")
        
        if consensus_method == "hierarchy":
            consensus = self._hierarchical_consensus(timeframe_decisions, context)
        elif consensus_method == "weighted_majority":
            consensus = self._weighted_majority_consensus(timeframe_decisions, context)
        else:  # "consensus" or default
            consensus = self._simple_consensus(timeframe_decisions, context)
        
        # Calculate agreement score
        signals = [d.signal for d in timeframe_decisions.values()]
        unique_signals = set(signals)
        agreement_score = 1.0 - (len(unique_signals) - 1) / max(len(signals), 1)
        
        # Identify conflicting timeframes
        most_common_signal = max(set(signals), key=signals.count) if signals else Signal.HOLD
        conflicting_timeframes = [
            tf for tf, decision in timeframe_decisions.items()
            if decision.signal != most_common_signal
        ]
        
        consensus.agreement_score = agreement_score
        consensus.conflicting_timeframes = conflicting_timeframes
        consensus.consensus_method = consensus_method
        
        return consensus
    
    def _weighted_majority_consensus(
        self,
        timeframe_decisions: Dict[str, TimeframeDecision],
        context: MultiTimeframeDecisionContext
    ) -> MultiTimeframeConsensus:
        """Build consensus using weighted majority voting."""
        
        # Calculate weighted votes for each signal
        signal_votes = {Signal.BUY: 0.0, Signal.HOLD: 0.0, Signal.SELL: 0.0}
        total_weight = 0.0
        weighted_confidence = 0.0
        
        for decision in timeframe_decisions.values():
            vote_weight = decision.weight * decision.confidence
            signal_votes[decision.signal] += vote_weight
            total_weight += decision.weight
            weighted_confidence += decision.confidence * decision.weight
        
        # Determine winning signal
        final_signal = max(signal_votes.items(), key=lambda x: x[1])[0]
        
        # Calculate consensus confidence
        if total_weight > 0:
            consensus_confidence = weighted_confidence / total_weight
            # Boost confidence if signal has strong majority
            winning_vote_ratio = signal_votes[final_signal] / sum(signal_votes.values())
            consensus_confidence *= (0.5 + 0.5 * winning_vote_ratio)
        else:
            consensus_confidence = 0.0
        
        # Primary timeframe influence
        primary_decision = timeframe_decisions.get(context.primary_timeframe)
        primary_influence = 0.0
        if primary_decision:
            primary_influence = (
                1.0 if primary_decision.signal == final_signal 
                else -1.0 * primary_decision.confidence
            )
        
        reasoning = {
            "method": "weighted_majority",
            "signal_votes": {s.value: v for s, v in signal_votes.items()},
            "total_weight": total_weight,
            "winning_vote_ratio": signal_votes[final_signal] / sum(signal_votes.values()),
            "primary_timeframe": context.primary_timeframe,
            "primary_alignment": primary_decision.signal == final_signal if primary_decision else None
        }
        
        return MultiTimeframeConsensus(
            final_signal=final_signal,
            consensus_confidence=consensus_confidence,
            timeframe_decisions=timeframe_decisions,
            agreement_score=0.0,  # Will be calculated later
            conflicting_timeframes=[],  # Will be calculated later
            primary_timeframe_influence=primary_influence,
            consensus_method="weighted_majority",
            reasoning=reasoning
        )
    
    def _hierarchical_consensus(
        self,
        timeframe_decisions: Dict[str, TimeframeDecision],
        context: MultiTimeframeDecisionContext
    ) -> MultiTimeframeConsensus:
        """Build consensus using hierarchical decision making."""
        
        # Primary timeframe has highest priority
        primary_decision = timeframe_decisions.get(context.primary_timeframe)
        
        if primary_decision and primary_decision.confidence > 0.7:
            # High confidence primary timeframe decision wins
            final_signal = primary_decision.signal
            consensus_confidence = primary_decision.confidence
            primary_influence = 1.0
        else:
            # Fall back to weighted majority if primary is not confident
            return self._weighted_majority_consensus(timeframe_decisions, context)
        
        reasoning = {
            "method": "hierarchical",
            "primary_timeframe": context.primary_timeframe,
            "primary_confidence": primary_decision.confidence if primary_decision else 0.0,
            "primary_signal": primary_decision.signal.value if primary_decision else "NONE",
            "fallback_used": False
        }
        
        return MultiTimeframeConsensus(
            final_signal=final_signal,
            consensus_confidence=consensus_confidence,
            timeframe_decisions=timeframe_decisions,
            agreement_score=0.0,
            conflicting_timeframes=[],
            primary_timeframe_influence=primary_influence,
            consensus_method="hierarchical",
            reasoning=reasoning
        )
    
    def _simple_consensus(
        self,
        timeframe_decisions: Dict[str, TimeframeDecision],
        context: MultiTimeframeDecisionContext
    ) -> MultiTimeframeConsensus:
        """Build consensus using simple majority voting."""
        
        # Count votes for each signal
        signal_counts = {Signal.BUY: 0, Signal.HOLD: 0, Signal.SELL: 0}
        total_confidence = 0.0
        
        for decision in timeframe_decisions.values():
            signal_counts[decision.signal] += 1
            total_confidence += decision.confidence
        
        # Determine winning signal
        final_signal = max(signal_counts.items(), key=lambda x: x[1])[0]
        
        # Calculate consensus confidence
        num_decisions = len(timeframe_decisions)
        if num_decisions > 0:
            consensus_confidence = total_confidence / num_decisions
            # Boost confidence based on unanimity
            winning_count = signal_counts[final_signal]
            unanimity_factor = winning_count / num_decisions
            consensus_confidence *= unanimity_factor
        else:
            consensus_confidence = 0.0
        
        # Primary timeframe influence
        primary_decision = timeframe_decisions.get(context.primary_timeframe)
        primary_influence = 0.0
        if primary_decision:
            primary_influence = (
                0.5 if primary_decision.signal == final_signal else -0.5
            )
        
        reasoning = {
            "method": "simple_consensus",
            "signal_counts": {s.value: c for s, c in signal_counts.items()},
            "winning_count": signal_counts[final_signal],
            "total_decisions": num_decisions,
            "unanimity_factor": signal_counts[final_signal] / num_decisions
        }
        
        return MultiTimeframeConsensus(
            final_signal=final_signal,
            consensus_confidence=consensus_confidence,
            timeframe_decisions=timeframe_decisions,
            agreement_score=0.0,
            conflicting_timeframes=[],
            primary_timeframe_influence=primary_influence,
            consensus_method="simple_consensus",
            reasoning=reasoning
        )
    
    def _apply_multi_timeframe_logic(
        self,
        consensus: MultiTimeframeConsensus,
        context: MultiTimeframeDecisionContext
    ) -> TradingDecision:
        """Apply additional multi-timeframe orchestrator logic."""
        
        original_signal = consensus.final_signal
        final_signal = original_signal
        final_confidence = consensus.consensus_confidence
        
        orchestrator_overrides = []
        
        # Multi-timeframe specific risk checks
        multi_tf_config = self.strategy_config.get("multi_timeframe", {})
        
        # Minimum agreement threshold
        min_agreement = multi_tf_config.get("min_agreement_threshold", 0.6)
        if consensus.agreement_score < min_agreement:
            final_signal = Signal.HOLD
            orchestrator_overrides.append(
                f"Low agreement score ({consensus.agreement_score:.3f} < {min_agreement})"
            )
        
        # Conflicting timeframes threshold
        max_conflicts = multi_tf_config.get("max_conflicting_timeframes", 1)
        if len(consensus.conflicting_timeframes) > max_conflicts:
            final_signal = Signal.HOLD
            orchestrator_overrides.append(
                f"Too many conflicting timeframes ({len(consensus.conflicting_timeframes)} > {max_conflicts})"
            )
        
        # Data quality threshold
        min_data_quality = multi_tf_config.get("min_data_quality", 0.8)
        data_qualities = [d.data_quality for d in consensus.timeframe_decisions.values()]
        avg_data_quality = np.mean(data_qualities) if data_qualities else 1.0
        if avg_data_quality < min_data_quality:
            final_signal = Signal.HOLD
            final_confidence *= avg_data_quality  # Penalize confidence
            orchestrator_overrides.append(
                f"Low data quality ({avg_data_quality:.3f} < {min_data_quality})"
            )
        
        # Mode-specific adjustments (same as single timeframe)
        mode_config = multi_tf_config.get("modes", {}).get(self.mode, {})
        
        # Apply mode-specific confidence threshold
        mode_confidence_threshold = mode_config.get("confidence_threshold")
        if mode_confidence_threshold and final_confidence < mode_confidence_threshold:
            final_signal = Signal.HOLD
            orchestrator_overrides.append(
                f"Confidence below {self.mode} threshold ({mode_confidence_threshold})"
            )
        
        # Enhanced reasoning with multi-timeframe details
        reasoning = {
            "consensus": asdict(consensus),
            "original_signal": original_signal.value,
            "final_signal": final_signal.value,
            "orchestrator_overrides": orchestrator_overrides,
            "multi_timeframe_metadata": {
                "timeframes": self.timeframes,
                "primary_timeframe": context.primary_timeframe,
                "timeframe_weights": context.timeframe_weights,
                "avg_data_quality": avg_data_quality,
                "decision_timestamp": context.timestamp.isoformat()
            }
        }
        
        return TradingDecision(
            signal=final_signal,
            confidence=final_confidence,
            timestamp=context.timestamp,
            reasoning=reasoning,
            current_position=context.current_position
        )
    
    def _update_multi_timeframe_state(
        self,
        symbol: str,
        decision: TradingDecision,
        consensus: MultiTimeframeConsensus,
        context: MultiTimeframeDecisionContext
    ):
        """Update state after multi-timeframe decision."""
        
        # Update position state
        if symbol not in self.position_states:
            self.position_states[symbol] = PositionState(symbol)
        
        position_state = self.position_states[symbol]
        
        # Create a dummy current bar for position update
        # Use primary timeframe data
        primary_tf_context = context.timeframe_contexts.get(context.primary_timeframe)
        if primary_tf_context and not primary_tf_context.current_bar.empty:
            position_state.update_from_decision(decision, primary_tf_context.current_bar)
        
        # Add symbol and multi-timeframe metadata to decision
        decision.reasoning["symbol"] = symbol
        decision.reasoning["multi_timeframe"] = True
        decision.reasoning["consensus_method"] = consensus.consensus_method
        
        # Update histories
        self.decision_history.append(decision)
        self.consensus_history.append(consensus)
        
        # Trim histories
        if len(self.decision_history) > self.max_history:
            self.decision_history.pop(0)
        if len(self.consensus_history) > self.max_history:
            self.consensus_history.pop(0)
        
        # Update individual timeframe orchestrators
        for timeframe, tf_decision in consensus.timeframe_decisions.items():
            if timeframe in self.timeframe_orchestrators:
                orchestrator = self.timeframe_orchestrators[timeframe]
                # Add the symbol-specific decision to their history
                tf_trading_decision = TradingDecision(
                    signal=tf_decision.signal,
                    confidence=tf_decision.confidence,
                    timestamp=context.timestamp,
                    reasoning=tf_decision.reasoning,
                    current_position=context.current_position
                )
                tf_trading_decision.reasoning["symbol"] = symbol
                orchestrator.decision_history.append(tf_trading_decision)
    
    def _load_strategy_config(self, config_path: str) -> Dict[str, Any]:
        """Load strategy configuration from YAML file."""
        config_path = Path(config_path)
        if not config_path.exists():
            raise FileNotFoundError(f"Strategy config not found: {config_path}")
        
        with open(config_path, "r") as f:
            config = yaml.safe_load(f)
        
        # Store config path for timeframe-specific configs
        config["config_path"] = str(config_path)
        
        # Validate required sections for multi-timeframe
        required_sections = ["name", "indicators", "fuzzy_sets"]
        for section in required_sections:
            if section not in config:
                raise ValueError(f"Missing required configuration section: {section}")
        
        return config
    
    # Public interface methods
    
    def get_position_state(self, symbol: str) -> PositionState:
        """Get current position state for a symbol."""
        if symbol not in self.position_states:
            self.position_states[symbol] = PositionState(symbol)
        return self.position_states[symbol]
    
    def get_decision_history(
        self, 
        symbol: Optional[str] = None, 
        limit: int = 20
    ) -> List[TradingDecision]:
        """Get recent decision history."""
        decisions = self.decision_history[-limit:]
        
        if symbol:
            decisions = [d for d in decisions if d.reasoning.get("symbol") == symbol]
        
        return decisions
    
    def get_consensus_history(
        self,
        symbol: Optional[str] = None,
        limit: int = 20
    ) -> List[MultiTimeframeConsensus]:
        """Get recent consensus history."""
        consensus_list = self.consensus_history[-limit:]
        
        if symbol:
            # Filter by decisions that contain the symbol
            filtered_consensus = []
            decision_symbols = [d.reasoning.get("symbol") for d in self.decision_history]
            for i, consensus in enumerate(consensus_list):
                if i < len(decision_symbols) and decision_symbols[-(len(consensus_list)-i)] == symbol:
                    filtered_consensus.append(consensus)
            consensus_list = filtered_consensus
        
        return consensus_list
    
    def get_timeframe_analysis(self, symbol: str) -> Dict[str, Any]:
        """Get detailed timeframe analysis for a symbol."""
        recent_decisions = self.get_decision_history(symbol, limit=10)
        recent_consensus = self.get_consensus_history(symbol, limit=10)
        
        analysis = {
            "symbol": symbol,
            "timeframes": self.timeframes,
            "primary_timeframe": self.primary_timeframe,
            "timeframe_weights": self.timeframe_weights,
            "recent_decisions_count": len(recent_decisions),
            "recent_consensus_count": len(recent_consensus)
        }
        
        if recent_consensus:
            latest_consensus = recent_consensus[-1]
            analysis["latest_consensus"] = {
                "final_signal": latest_consensus.final_signal.value,
                "consensus_confidence": latest_consensus.consensus_confidence,
                "agreement_score": latest_consensus.agreement_score,
                "conflicting_timeframes": latest_consensus.conflicting_timeframes,
                "consensus_method": latest_consensus.consensus_method
            }
            
            # Timeframe breakdown
            analysis["timeframe_breakdown"] = {}
            for tf, tf_decision in latest_consensus.timeframe_decisions.items():
                analysis["timeframe_breakdown"][tf] = {
                    "signal": tf_decision.signal.value,
                    "confidence": tf_decision.confidence,
                    "weight": tf_decision.weight,
                    "data_quality": tf_decision.data_quality
                }
        
        return analysis
    
    def reset_state(self, symbol: Optional[str] = None):
        """Reset orchestrator state."""
        if symbol:
            if symbol in self.position_states:
                self.position_states[symbol] = PositionState(symbol)
            # Also reset individual timeframe orchestrators
            for orchestrator in self.timeframe_orchestrators.values():
                orchestrator.reset_state(symbol)
        else:
            self.position_states.clear()
            self.decision_history.clear()
            self.consensus_history.clear()
            for orchestrator in self.timeframe_orchestrators.values():
                orchestrator.reset_state()


def create_multi_timeframe_decision_orchestrator(
    strategy_config_path: str,
    model_path: Optional[str] = None,
    mode: str = "backtest",
    timeframes: Optional[List[str]] = None
) -> MultiTimeframeDecisionOrchestrator:
    """
    Factory function to create multi-timeframe decision orchestrator.
    
    Args:
        strategy_config_path: Path to strategy YAML file
        model_path: Path to trained multi-timeframe model
        mode: Operating mode (backtest, paper, live)
        timeframes: List of timeframes to analyze
        
    Returns:
        Configured MultiTimeframeDecisionOrchestrator instance
    """
    return MultiTimeframeDecisionOrchestrator(
        strategy_config_path=strategy_config_path,
        model_path=model_path,
        mode=mode,
        timeframes=timeframes
    )