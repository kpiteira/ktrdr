-- KTRDR Research Agents - Initial Seed Data
-- This file contains initial data for development and testing

-- Set search path
SET search_path TO research, public;

-- ============================================================================
-- INITIAL AGENT STATES
-- ============================================================================

-- Create initial agent states for development
INSERT INTO research.agent_states (agent_id, agent_type, status, current_activity, state_data) VALUES
('coordinator-001', 'coordinator', 'idle', 'Waiting for research session assignment', '{"version": "1.0", "capabilities": ["workflow_orchestration", "agent_management", "resource_allocation"]}'),
('researcher-001', 'researcher', 'idle', 'Ready for hypothesis generation', '{"version": "1.0", "capabilities": ["hypothesis_generation", "experiment_design", "creative_thinking"], "specialization": "neuro_fuzzy_strategies"}'),
('assistant-001', 'assistant', 'idle', 'Ready for experiment execution', '{"version": "1.0", "capabilities": ["experiment_execution", "training_analytics", "backtest_analysis"], "specialization": "ktrdr_integration"}'),
('board-001', 'board', 'idle', 'Ready for human interaction', '{"version": "1.0", "capabilities": ["human_communication", "strategic_oversight", "progress_reporting"], "interface": "mcp"}')
ON CONFLICT (agent_id) DO NOTHING;

-- ============================================================================
-- DEFAULT RESEARCH SESSION
-- ============================================================================

-- Create default research session for initial development
INSERT INTO research.sessions (
    session_name, 
    description, 
    status,
    strategic_goals, 
    priority_areas,
    resource_allocation,
    success_metrics
) VALUES (
    'MVP Research Campaign',
    'Initial autonomous research session to validate system functionality and discover baseline trading patterns',
    'active',
    '[
        "Validate autonomous research workflow end-to-end",
        "Discover at least 3 novel neuro-fuzzy trading strategies",
        "Build initial knowledge base with 50+ insights",
        "Establish baseline fitness scoring methodology"
    ]',
    '[
        "momentum_strategies", 
        "mean_reversion", 
        "volatility_patterns", 
        "volume_analysis",
        "multi_timeframe_strategies"
    ]',
    '{
        "max_concurrent_experiments": 3,
        "max_experiment_duration_hours": 8,
        "computational_budget": 100,
        "priority_distribution": {
            "momentum_strategies": 0.3,
            "mean_reversion": 0.3,
            "volatility_patterns": 0.2,
            "volume_analysis": 0.1,
            "multi_timeframe_strategies": 0.1
        }
    }',
    '{
        "target_experiments_per_week": 20,
        "target_success_rate": 0.15,
        "target_novel_insights_per_week": 5,
        "target_fitness_threshold": 0.6
    }'
) ON CONFLICT DO NOTHING;

-- ============================================================================
-- SAMPLE KNOWLEDGE BASE ENTRIES
-- ============================================================================

-- Insert foundational knowledge entries to bootstrap the system
INSERT INTO research.knowledge_base (
    content_type,
    title,
    content,
    summary,
    keywords,
    tags,
    source_type,
    quality_score,
    relevance_score,
    confidence_level,
    validation_status
) VALUES
(
    'insight',
    'Momentum Strategies Performance in High Volatility',
    'Analysis of momentum-based trading strategies shows significantly reduced performance during high volatility periods (VIX > 25). The relationship appears to be inverse, with momentum signals becoming less reliable as market uncertainty increases. Optimal momentum strategies should incorporate volatility filters to avoid false signals during turbulent periods.',
    'Momentum strategies underperform in high volatility environments and benefit from volatility-based filters.',
    ARRAY['momentum', 'volatility', 'vix', 'strategy_performance', 'filtering'],
    ARRAY['momentum_strategies', 'volatility_patterns', 'risk_management'],
    'manual_entry',
    0.85,
    0.90,
    0.80,
    'validated'
),
(
    'pattern',
    'Volume Surge Preceding Price Breakouts',
    'Statistical analysis reveals that 73% of significant price breakouts (>2% intraday moves) are preceded by volume surges of at least 150% above the 20-day average within the previous 3 trading sessions. This pattern is most reliable in liquid stocks with market cap > $1B.',
    'Volume surges reliably predict price breakouts in liquid large-cap stocks.',
    ARRAY['volume', 'breakouts', 'price_action', 'liquidity', 'market_cap'],
    ARRAY['volume_analysis', 'breakout_strategies', 'large_cap'],
    'manual_entry',
    0.90,
    0.85,
    0.75,
    'validated'
),
(
    'failure_analysis',
    'Mean Reversion Failure in Trending Markets',
    'Mean reversion strategies consistently fail when applied during strong trending periods. Analysis shows that when the 50-day moving average slope exceeds 2 degrees for more than 10 consecutive days, mean reversion signals produce negative returns 68% of the time. The strategy requires trend strength filters to avoid counter-trend trades.',
    'Mean reversion strategies fail in strong trending markets and need trend filters.',
    ARRAY['mean_reversion', 'trend_analysis', 'moving_average', 'failure_mode'],
    ARRAY['mean_reversion', 'trend_analysis', 'risk_management'],
    'manual_entry',
    0.88,
    0.92,
    0.82,
    'validated'
),
(
    'success_factor',
    'Multi-Timeframe Confirmation Improves Signal Quality',
    'Trading signals that show confirmation across multiple timeframes (5m, 15m, 1h) demonstrate 34% higher success rates compared to single-timeframe signals. The improvement is most pronounced for momentum strategies, where multi-timeframe alignment increases win rate from 52% to 69%.',
    'Multi-timeframe signal confirmation significantly improves trading strategy performance.',
    ARRAY['multi_timeframe', 'signal_confirmation', 'momentum', 'win_rate'],
    ARRAY['multi_timeframe_strategies', 'signal_quality', 'momentum_strategies'],
    'manual_entry',
    0.92,
    0.88,
    0.85,
    'validated'
),
(
    'architecture_pattern',
    'LSTM-Fuzzy Hybrid Architecture for Regime Detection',
    'Hybrid neural architectures combining LSTM layers for temporal pattern recognition with fuzzy logic layers for regime classification show superior performance in adaptive trading systems. The LSTM component handles sequence learning while fuzzy layers provide interpretable regime boundaries. Optimal architecture: 2 LSTM layers (64, 32 units) followed by 3 fuzzy membership layers.',
    'LSTM-Fuzzy hybrid architectures excel at regime-aware trading strategy implementation.',
    ARRAY['lstm', 'fuzzy_logic', 'regime_detection', 'neural_architecture', 'hybrid_models'],
    ARRAY['neuro_fuzzy', 'architecture_patterns', 'regime_detection'],
    'manual_entry',
    0.87,
    0.89,
    0.78,
    'unvalidated'
)
ON CONFLICT DO NOTHING;

-- ============================================================================
-- SAMPLE INSIGHTS
-- ============================================================================

-- Insert sample insights to demonstrate the insights system
INSERT INTO research.insights (
    insight_type,
    insight_category,
    title,
    description,
    confidence_score,
    statistical_significance,
    sample_size,
    actionable_recommendations,
    impact_assessment,
    implementation_complexity,
    discovery_method
) VALUES
(
    'correlation',
    'market_regime',
    'VIX-Strategy Performance Correlation',
    'Strong negative correlation (-0.67) between VIX levels and momentum strategy performance. As market fear increases, momentum signals become less reliable. This correlation is stable across different market conditions and time periods.',
    0.87,
    0.001,
    156,
    '[
        "Implement VIX-based position sizing for momentum strategies",
        "Reduce momentum allocation when VIX > 25",
        "Consider regime-switching models based on volatility levels"
    ]',
    '{
        "expected_performance_improvement": 0.15,
        "risk_reduction": 0.22,
        "implementation_effort": "medium"
    }',
    'medium',
    'correlation_analysis'
),
(
    'pattern',
    'timing',
    'First Hour Trading Volume Pattern',
    'Trading volume in the first hour consistently shows 2.3x average daily volume, with 78% of daily price range established within first 90 minutes. This pattern creates opportunities for early momentum capture and volatility-based strategies.',
    0.91,
    0.0001,
    287,
    '[
        "Focus momentum strategies on first 90 minutes of trading",
        "Implement time-of-day filters for volatility strategies",
        "Use first-hour volume as signal strength indicator"
    ]',
    '{
        "expected_performance_improvement": 0.18,
        "signal_quality_improvement": 0.25,
        "implementation_effort": "low"
    }',
    'low',
    'pattern_analysis'
),
(
    'success_factor',
    'architecture',
    'Dropout Regularization in Financial Neural Networks',
    'Dropout rates between 0.3-0.4 significantly improve generalization in financial neural networks. Lower dropout (<0.2) leads to overfitting, while higher dropout (>0.5) reduces learning capacity. Optimal performance achieved with layer-specific dropout: 0.3 for input, 0.4 for hidden layers.',
    0.84,
    0.002,
    45,
    '[
        "Standardize dropout rates: 0.3 input, 0.4 hidden layers",
        "Implement adaptive dropout based on validation performance",
        "Monitor overfitting indicators during training"
    ]',
    '{
        "generalization_improvement": 0.12,
        "overfitting_reduction": 0.28,
        "implementation_effort": "low"
    }',
    'low',
    'manual_observation'
)
ON CONFLICT DO NOTHING;

-- ============================================================================
-- INITIAL WORKFLOW CHECKPOINT
-- ============================================================================

-- Create a sample workflow checkpoint for testing
INSERT INTO research.workflow_checkpoints (
    workflow_id,
    checkpoint_name,
    workflow_type,
    workflow_state,
    current_node,
    completed_nodes,
    status
) VALUES (
    'initial-system-validation',
    'system_startup_checkpoint',
    'research_session',
    '{
        "session_id": "initial_session",
        "agents_initialized": true,
        "knowledge_base_loaded": true,
        "coordinator_ready": true,
        "next_action": "await_experiment_queue"
    }',
    'system_ready',
    ARRAY['initialize_agents', 'load_knowledge_base', 'start_coordinator'],
    'active'
) ON CONFLICT DO NOTHING;

-- ============================================================================
-- ANALYTICS AND REPORTING SETUP
-- ============================================================================

-- Update agent heartbeats to current time
UPDATE research.agent_states 
SET last_heartbeat = NOW()
WHERE agent_id IN ('coordinator-001', 'researcher-001', 'assistant-001', 'board-001');

-- Assign coordinator to the default session
UPDATE research.sessions 
SET coordinator_id = (SELECT id FROM research.agent_states WHERE agent_id = 'coordinator-001')
WHERE session_name = 'MVP Research Campaign';

-- ============================================================================
-- DEVELOPMENT UTILITIES
-- ============================================================================

-- Create some sample experiment templates for quick testing
-- (These would normally be generated by the Researcher agent)

-- Note: These are placeholder experiment configurations for development
-- In production, these will be generated dynamically by AI agents

-- End of seed data file