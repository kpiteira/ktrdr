-- KTRDR Research Agents Database Schema
-- PostgreSQL 15+ with pgvector extension for semantic search

-- Enable pgvector extension for vector similarity search
CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Create research schema to isolate AI agent data
CREATE SCHEMA IF NOT EXISTS research;

-- Set search path to include research schema
SET search_path TO research, public;

-- ============================================================================
-- AGENT STATES TABLE
-- ============================================================================
-- Tracks agent identity, status, and state for resumability
CREATE TABLE IF NOT EXISTS research.agent_states (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    agent_id VARCHAR(255) NOT NULL UNIQUE,
    agent_type VARCHAR(100) NOT NULL, -- 'researcher', 'assistant', 'coordinator', 'board'
    status VARCHAR(50) NOT NULL DEFAULT 'idle', -- 'idle', 'active', 'processing', 'error', 'paused'
    current_activity TEXT,
    state_data JSONB DEFAULT '{}', -- Flexible state storage for each agent type
    memory_context JSONB DEFAULT '{}', -- Agent's working memory
    last_heartbeat TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    
    -- Constraints
    CONSTRAINT valid_agent_type CHECK (agent_type IN ('researcher', 'assistant', 'coordinator', 'board', 'director')),
    CONSTRAINT valid_status CHECK (status IN ('idle', 'active', 'processing', 'error', 'paused', 'shutdown'))
);

-- Indexes for agent states
CREATE INDEX idx_agent_states_agent_id ON research.agent_states(agent_id);
CREATE INDEX idx_agent_states_type_status ON research.agent_states(agent_type, status);
CREATE INDEX idx_agent_states_heartbeat ON research.agent_states(last_heartbeat);

-- ============================================================================
-- RESEARCH SESSIONS TABLE
-- ============================================================================
-- Tracks long-term research campaigns and coordination
CREATE TABLE IF NOT EXISTS research.sessions (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    session_name VARCHAR(255) NOT NULL,
    description TEXT,
    status VARCHAR(50) NOT NULL DEFAULT 'active', -- 'active', 'paused', 'completed', 'failed'
    strategic_goals JSONB DEFAULT '[]', -- Array of strategic objectives
    resource_allocation JSONB DEFAULT '{}', -- Budget and resource constraints
    priority_areas JSONB DEFAULT '[]', -- Research focus areas
    success_metrics JSONB DEFAULT '{}', -- How to measure session success
    session_config JSONB DEFAULT '{}', -- Session-specific configuration
    coordinator_id UUID REFERENCES research.agent_states(id),
    started_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    completed_at TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    
    -- Constraints
    CONSTRAINT valid_session_status CHECK (status IN ('active', 'paused', 'completed', 'failed'))
);

-- Indexes for sessions
CREATE INDEX idx_sessions_status ON research.sessions(status);
CREATE INDEX idx_sessions_started_at ON research.sessions(started_at);
CREATE INDEX idx_sessions_coordinator ON research.sessions(coordinator_id);

-- ============================================================================
-- EXPERIMENTS TABLE
-- ============================================================================
-- Complete experiment lifecycle tracking with rich metadata
CREATE TABLE IF NOT EXISTS research.experiments (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    session_id UUID REFERENCES research.sessions(id) ON DELETE CASCADE,
    experiment_name VARCHAR(255) NOT NULL,
    hypothesis TEXT NOT NULL, -- The creative hypothesis being tested
    experiment_type VARCHAR(100) NOT NULL, -- 'neural_architecture', 'fuzzy_strategy', 'indicator_combo', etc.
    
    -- Experiment Configuration
    configuration JSONB NOT NULL DEFAULT '{}', -- Complete experiment parameters
    ktrdr_strategy_config JSONB, -- KTRDR-specific strategy configuration
    neural_architecture JSONB, -- Neural network architecture details
    fuzzy_configuration JSONB, -- Fuzzy logic membership functions
    training_parameters JSONB, -- Training hyperparameters
    
    -- Execution Tracking
    status VARCHAR(50) NOT NULL DEFAULT 'queued', -- 'queued', 'running', 'completed', 'failed', 'aborted'
    assigned_agent_id UUID REFERENCES research.agent_states(id),
    execution_log JSONB DEFAULT '[]', -- Detailed execution timeline
    error_details JSONB, -- Error analysis if failed
    
    -- Results and Analysis
    results JSONB, -- Raw experiment results
    fitness_score DECIMAL(10, 6), -- Quantitative fitness assessment (0.0 to 1.0)
    performance_metrics JSONB, -- Detailed performance breakdown
    training_analytics JSONB, -- Training dynamics and learning curves
    backtest_results JSONB, -- Backtesting performance data
    
    -- Research Intelligence
    insights_generated JSONB DEFAULT '[]', -- Key insights from this experiment
    failure_analysis JSONB, -- What went wrong and why (for failed experiments)
    success_factors JSONB, -- What made this experiment succeed
    recommended_followups JSONB DEFAULT '[]', -- Suggested next experiments
    
    -- Timestamps
    queued_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    started_at TIMESTAMP WITH TIME ZONE,
    completed_at TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    
    -- Constraints
    CONSTRAINT valid_experiment_status CHECK (status IN ('queued', 'running', 'completed', 'failed', 'aborted')),
    CONSTRAINT valid_fitness_score CHECK (fitness_score IS NULL OR (fitness_score >= 0.0 AND fitness_score <= 1.0))
);

-- Indexes for experiments
CREATE INDEX idx_experiments_session_id ON research.experiments(session_id);
CREATE INDEX idx_experiments_status ON research.experiments(status);
CREATE INDEX idx_experiments_type ON research.experiments(experiment_type);
CREATE INDEX idx_experiments_agent_id ON research.experiments(assigned_agent_id);
CREATE INDEX idx_experiments_fitness_score ON research.experiments(fitness_score) WHERE fitness_score IS NOT NULL;
CREATE INDEX idx_experiments_created_at ON research.experiments(created_at);

-- ============================================================================
-- KNOWLEDGE BASE TABLE
-- ============================================================================
-- Semantic content storage with vector embeddings for intelligent retrieval
CREATE TABLE IF NOT EXISTS research.knowledge_base (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    
    -- Content Identification
    content_type VARCHAR(100) NOT NULL, -- 'insight', 'pattern', 'failure_analysis', 'success_factor', 'hypothesis'
    title VARCHAR(500) NOT NULL,
    content TEXT NOT NULL, -- The actual knowledge content
    summary TEXT, -- Executive summary of the content
    
    -- Semantic Search
    embedding VECTOR(1536), -- OpenAI text-embedding-3-small dimensions
    keywords TEXT[], -- Extracted keywords for traditional search
    tags VARCHAR(100)[], -- User-defined tags for categorization
    
    -- Source and Context
    source_experiment_id UUID REFERENCES research.experiments(id) ON DELETE SET NULL,
    source_session_id UUID REFERENCES research.sessions(id) ON DELETE SET NULL,
    source_agent_id UUID REFERENCES research.agent_states(id) ON DELETE SET NULL,
    source_type VARCHAR(100), -- 'experiment_result', 'agent_insight', 'pattern_analysis', 'manual_entry'
    
    -- Quality and Relevance
    quality_score DECIMAL(5, 4), -- 0.0000 to 1.0000 quality assessment
    relevance_score DECIMAL(5, 4), -- How relevant this knowledge is currently
    confidence_level DECIMAL(5, 4), -- Confidence in this knowledge (0.0 to 1.0)
    validation_status VARCHAR(50) DEFAULT 'unvalidated', -- 'unvalidated', 'validated', 'disputed', 'deprecated'
    
    -- Usage Analytics
    access_count INTEGER DEFAULT 0, -- How often this knowledge is accessed
    last_accessed_at TIMESTAMP WITH TIME ZONE,
    effectiveness_rating DECIMAL(3, 2), -- How effective this knowledge proved to be
    
    -- Metadata
    metadata JSONB DEFAULT '{}', -- Additional flexible metadata
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    
    -- Constraints
    CONSTRAINT valid_content_type CHECK (content_type IN ('insight', 'pattern', 'failure_analysis', 'success_factor', 'hypothesis', 'strategy_template', 'architecture_pattern')),
    CONSTRAINT valid_source_type CHECK (source_type IN ('experiment_result', 'agent_insight', 'pattern_analysis', 'manual_entry', 'cross_experiment_analysis')),
    CONSTRAINT valid_validation_status CHECK (validation_status IN ('unvalidated', 'validated', 'disputed', 'deprecated')),
    CONSTRAINT valid_quality_score CHECK (quality_score IS NULL OR (quality_score >= 0.0 AND quality_score <= 1.0)),
    CONSTRAINT valid_relevance_score CHECK (relevance_score IS NULL OR (relevance_score >= 0.0 AND relevance_score <= 1.0)),
    CONSTRAINT valid_confidence_level CHECK (confidence_level IS NULL OR (confidence_level >= 0.0 AND confidence_level <= 1.0))
);

-- Indexes for knowledge base
CREATE INDEX idx_knowledge_content_type ON research.knowledge_base(content_type);
CREATE INDEX idx_knowledge_source_experiment ON research.knowledge_base(source_experiment_id);
CREATE INDEX idx_knowledge_source_session ON research.knowledge_base(source_session_id);
CREATE INDEX idx_knowledge_quality_score ON research.knowledge_base(quality_score) WHERE quality_score IS NOT NULL;
CREATE INDEX idx_knowledge_tags ON research.knowledge_base USING GIN(tags);
CREATE INDEX idx_knowledge_keywords ON research.knowledge_base USING GIN(keywords);
CREATE INDEX idx_knowledge_created_at ON research.knowledge_base(created_at);

-- Vector similarity search index (HNSW for fast approximate nearest neighbor)
CREATE INDEX idx_knowledge_embedding ON research.knowledge_base USING hnsw (embedding vector_cosine_ops);

-- ============================================================================
-- AGENT COMMUNICATIONS TABLE
-- ============================================================================
-- Tracks communication between agents for coordination and learning
CREATE TABLE IF NOT EXISTS research.agent_communications (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    
    -- Communication Parties
    from_agent_id UUID NOT NULL REFERENCES research.agent_states(id),
    to_agent_id UUID REFERENCES research.agent_states(id), -- NULL for broadcast messages
    communication_type VARCHAR(100) NOT NULL, -- 'experiment_assignment', 'status_update', 'insight_sharing', 'coordination', 'broadcast'
    
    -- Message Content
    subject VARCHAR(500),
    message_content TEXT NOT NULL,
    message_data JSONB DEFAULT '{}', -- Structured data payload
    priority VARCHAR(20) DEFAULT 'normal', -- 'low', 'normal', 'high', 'urgent'
    
    -- Message Status
    status VARCHAR(50) DEFAULT 'sent', -- 'sent', 'delivered', 'read', 'processed', 'failed'
    response_required BOOLEAN DEFAULT FALSE,
    response_timeout TIMESTAMP WITH TIME ZONE,
    
    -- Context
    related_experiment_id UUID REFERENCES research.experiments(id) ON DELETE SET NULL,
    related_session_id UUID REFERENCES research.sessions(id) ON DELETE SET NULL,
    correlation_id UUID, -- For tracking conversation threads
    
    -- Timestamps
    sent_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    delivered_at TIMESTAMP WITH TIME ZONE,
    read_at TIMESTAMP WITH TIME ZONE,
    processed_at TIMESTAMP WITH TIME ZONE,
    
    -- Constraints
    CONSTRAINT valid_communication_type CHECK (communication_type IN ('experiment_assignment', 'status_update', 'insight_sharing', 'coordination', 'broadcast', 'error_report', 'resource_request')),
    CONSTRAINT valid_priority CHECK (priority IN ('low', 'normal', 'high', 'urgent')),
    CONSTRAINT valid_message_status CHECK (status IN ('sent', 'delivered', 'read', 'processed', 'failed'))
);

-- Indexes for agent communications
CREATE INDEX idx_communications_from_agent ON research.agent_communications(from_agent_id);
CREATE INDEX idx_communications_to_agent ON research.agent_communications(to_agent_id);
CREATE INDEX idx_communications_type ON research.agent_communications(communication_type);
CREATE INDEX idx_communications_status ON research.agent_communications(status);
CREATE INDEX idx_communications_correlation ON research.agent_communications(correlation_id);
CREATE INDEX idx_communications_sent_at ON research.agent_communications(sent_at);

-- ============================================================================
-- RESEARCH INSIGHTS TABLE
-- ============================================================================
-- Cross-experiment patterns and meta-insights discovered by the system
CREATE TABLE IF NOT EXISTS research.insights (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    
    -- Insight Classification
    insight_type VARCHAR(100) NOT NULL, -- 'pattern', 'correlation', 'failure_mode', 'success_factor', 'meta_learning'
    insight_category VARCHAR(100), -- 'market_regime', 'architecture', 'hyperparameter', 'indicator', 'timing'
    title VARCHAR(500) NOT NULL,
    description TEXT NOT NULL,
    
    -- Supporting Evidence
    supporting_experiments UUID[] DEFAULT '{}', -- Array of experiment IDs that support this insight
    confidence_score DECIMAL(5, 4) NOT NULL, -- Statistical confidence in this insight
    statistical_significance DECIMAL(10, 8), -- P-value or other significance measure
    sample_size INTEGER, -- Number of experiments this insight is based on
    
    -- Actionable Intelligence
    actionable_recommendations JSONB DEFAULT '[]', -- Specific actions based on this insight
    impact_assessment JSONB, -- Expected impact of applying this insight
    implementation_complexity VARCHAR(50), -- 'low', 'medium', 'high', 'very_high'
    
    -- Validation and Evolution
    validation_experiments UUID[] DEFAULT '{}', -- Experiments that validate this insight
    contradicting_experiments UUID[] DEFAULT '{}', -- Experiments that contradict this insight
    evolution_history JSONB DEFAULT '[]', -- How this insight has evolved over time
    
    -- Discovery Context
    discovered_by_agent_id UUID REFERENCES research.agent_states(id),
    discovery_method VARCHAR(100), -- 'pattern_analysis', 'correlation_analysis', 'failure_clustering', 'manual_observation'
    discovery_session_id UUID REFERENCES research.sessions(id),
    
    -- Usage and Impact
    times_applied INTEGER DEFAULT 0,
    success_rate DECIMAL(5, 4), -- Success rate when this insight is applied
    last_applied_at TIMESTAMP WITH TIME ZONE,
    
    -- Timestamps
    discovered_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    last_validated_at TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    
    -- Constraints
    CONSTRAINT valid_insight_type CHECK (insight_type IN ('pattern', 'correlation', 'failure_mode', 'success_factor', 'meta_learning', 'regime_dependency', 'architecture_preference')),
    CONSTRAINT valid_implementation_complexity CHECK (implementation_complexity IN ('low', 'medium', 'high', 'very_high')),
    CONSTRAINT valid_confidence_score CHECK (confidence_score >= 0.0 AND confidence_score <= 1.0),
    CONSTRAINT valid_success_rate CHECK (success_rate IS NULL OR (success_rate >= 0.0 AND success_rate <= 1.0))
);

-- Indexes for insights
CREATE INDEX idx_insights_type ON research.insights(insight_type);
CREATE INDEX idx_insights_category ON research.insights(insight_category);
CREATE INDEX idx_insights_confidence ON research.insights(confidence_score);
CREATE INDEX idx_insights_discovered_by ON research.insights(discovered_by_agent_id);
CREATE INDEX idx_insights_session ON research.insights(discovery_session_id);
CREATE INDEX idx_insights_discovered_at ON research.insights(discovered_at);

-- ============================================================================
-- WORKFLOW CHECKPOINTS TABLE
-- ============================================================================
-- LangGraph workflow state management for resumability
CREATE TABLE IF NOT EXISTS research.workflow_checkpoints (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    
    -- Workflow Identification
    workflow_id VARCHAR(255) NOT NULL, -- LangGraph workflow identifier
    checkpoint_name VARCHAR(255) NOT NULL,
    workflow_type VARCHAR(100) NOT NULL, -- 'experiment_execution', 'research_session', 'insight_analysis'
    
    -- State Management
    workflow_state JSONB NOT NULL, -- Complete workflow state for resumption
    current_node VARCHAR(255), -- Current node in the workflow graph
    completed_nodes VARCHAR(255)[] DEFAULT '{}', -- Array of completed workflow nodes
    failed_nodes VARCHAR(255)[] DEFAULT '{}', -- Array of failed workflow nodes
    
    -- Context and Metadata
    related_experiment_id UUID REFERENCES research.experiments(id) ON DELETE CASCADE,
    related_session_id UUID REFERENCES research.sessions(id) ON DELETE CASCADE,
    agent_context JSONB DEFAULT '{}', -- Agent-specific context for the workflow
    
    -- Execution Tracking
    status VARCHAR(50) DEFAULT 'active', -- 'active', 'paused', 'completed', 'failed'
    execution_metadata JSONB DEFAULT '{}',
    error_context JSONB, -- Error information if workflow failed
    
    -- Timestamps
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    
    -- Constraints
    CONSTRAINT valid_workflow_status CHECK (status IN ('active', 'paused', 'completed', 'failed')),
    CONSTRAINT valid_workflow_type CHECK (workflow_type IN ('experiment_execution', 'research_session', 'insight_analysis', 'agent_coordination', 'knowledge_synthesis'))
);

-- Indexes for workflow checkpoints
CREATE INDEX idx_workflow_checkpoints_workflow_id ON research.workflow_checkpoints(workflow_id);
CREATE INDEX idx_workflow_checkpoints_type ON research.workflow_checkpoints(workflow_type);
CREATE INDEX idx_workflow_checkpoints_status ON research.workflow_checkpoints(status);
CREATE INDEX idx_workflow_checkpoints_experiment ON research.workflow_checkpoints(related_experiment_id);
CREATE INDEX idx_workflow_checkpoints_session ON research.workflow_checkpoints(related_session_id);

-- ============================================================================
-- AUTOMATIC UPDATE TRIGGERS
-- ============================================================================

-- Function to update the updated_at timestamp
CREATE OR REPLACE FUNCTION research.update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ language 'plpgsql';

-- Apply update triggers to all tables with updated_at columns
CREATE TRIGGER update_agent_states_updated_at BEFORE UPDATE ON research.agent_states 
    FOR EACH ROW EXECUTE FUNCTION research.update_updated_at_column();

CREATE TRIGGER update_sessions_updated_at BEFORE UPDATE ON research.sessions 
    FOR EACH ROW EXECUTE FUNCTION research.update_updated_at_column();

CREATE TRIGGER update_experiments_updated_at BEFORE UPDATE ON research.experiments 
    FOR EACH ROW EXECUTE FUNCTION research.update_updated_at_column();

CREATE TRIGGER update_knowledge_base_updated_at BEFORE UPDATE ON research.knowledge_base 
    FOR EACH ROW EXECUTE FUNCTION research.update_updated_at_column();

CREATE TRIGGER update_insights_updated_at BEFORE UPDATE ON research.insights 
    FOR EACH ROW EXECUTE FUNCTION research.update_updated_at_column();

CREATE TRIGGER update_workflow_checkpoints_updated_at BEFORE UPDATE ON research.workflow_checkpoints 
    FOR EACH ROW EXECUTE FUNCTION research.update_updated_at_column();

-- ============================================================================
-- UTILITY FUNCTIONS
-- ============================================================================

-- Function to find similar knowledge based on vector embeddings
CREATE OR REPLACE FUNCTION research.find_similar_knowledge(
    query_embedding VECTOR(1536),
    content_type_filter VARCHAR(100) DEFAULT NULL,
    limit_count INTEGER DEFAULT 10,
    similarity_threshold DECIMAL DEFAULT 0.7
)
RETURNS TABLE (
    id UUID,
    title VARCHAR(500),
    content TEXT,
    content_type VARCHAR(100),
    similarity_score DECIMAL
) AS $$
BEGIN
    RETURN QUERY
    SELECT 
        kb.id,
        kb.title,
        kb.content,
        kb.content_type,
        (1 - (kb.embedding <=> query_embedding))::DECIMAL as similarity_score
    FROM research.knowledge_base kb
    WHERE 
        (content_type_filter IS NULL OR kb.content_type = content_type_filter)
        AND kb.embedding IS NOT NULL
        AND (1 - (kb.embedding <=> query_embedding)) >= similarity_threshold
    ORDER BY kb.embedding <=> query_embedding
    LIMIT limit_count;
END;
$$ LANGUAGE plpgsql;

-- Function to get experiment success rate by type
CREATE OR REPLACE FUNCTION research.get_experiment_success_rate(
    experiment_type_filter VARCHAR(100) DEFAULT NULL,
    session_id_filter UUID DEFAULT NULL
)
RETURNS TABLE (
    experiment_type VARCHAR(100),
    total_experiments BIGINT,
    successful_experiments BIGINT,
    success_rate DECIMAL
) AS $$
BEGIN
    RETURN QUERY
    SELECT 
        e.experiment_type,
        COUNT(*) as total_experiments,
        COUNT(CASE WHEN e.status = 'completed' AND e.fitness_score > 0.5 THEN 1 END) as successful_experiments,
        ROUND(
            COUNT(CASE WHEN e.status = 'completed' AND e.fitness_score > 0.5 THEN 1 END)::DECIMAL / 
            NULLIF(COUNT(*), 0) * 100, 2
        ) as success_rate
    FROM research.experiments e
    WHERE 
        (experiment_type_filter IS NULL OR e.experiment_type = experiment_type_filter)
        AND (session_id_filter IS NULL OR e.session_id = session_id_filter)
        AND e.status IN ('completed', 'failed')
    GROUP BY e.experiment_type
    ORDER BY success_rate DESC;
END;
$$ LANGUAGE plpgsql;

-- ============================================================================
-- INITIAL DATA
-- ============================================================================

-- Create default research session
INSERT INTO research.sessions (
    session_name, 
    description, 
    strategic_goals, 
    priority_areas
) VALUES (
    'Initial Research Campaign',
    'First autonomous research session to establish baseline patterns and validate system functionality',
    '["Discover novel neuro-fuzzy trading strategies", "Validate autonomous research workflows", "Build initial knowledge base"]',
    '["momentum_strategies", "mean_reversion", "volatility_patterns", "volume_analysis"]'
) ON CONFLICT DO NOTHING;

-- ============================================================================
-- VIEWS FOR COMMON QUERIES
-- ============================================================================

-- Active experiments overview
CREATE OR REPLACE VIEW research.active_experiments_overview AS
SELECT 
    e.id,
    e.experiment_name,
    e.hypothesis,
    e.status,
    e.assigned_agent_id,
    a.agent_id as agent_name,
    e.fitness_score,
    s.session_name,
    e.created_at,
    e.started_at,
    EXTRACT(EPOCH FROM (NOW() - e.started_at))/3600 as hours_running
FROM research.experiments e
LEFT JOIN research.agent_states a ON e.assigned_agent_id = a.id
LEFT JOIN research.sessions s ON e.session_id = s.id
WHERE e.status IN ('queued', 'running')
ORDER BY e.created_at DESC;

-- Knowledge base summary
CREATE OR REPLACE VIEW research.knowledge_summary AS
SELECT 
    content_type,
    COUNT(*) as count,
    AVG(quality_score) as avg_quality,
    AVG(relevance_score) as avg_relevance,
    MAX(created_at) as latest_entry
FROM research.knowledge_base
GROUP BY content_type
ORDER BY count DESC;

-- Agent status overview
CREATE OR REPLACE VIEW research.agent_status_overview AS
SELECT 
    agent_id,
    agent_type,
    status,
    current_activity,
    last_heartbeat,
    EXTRACT(EPOCH FROM (NOW() - last_heartbeat))/60 as minutes_since_heartbeat
FROM research.agent_states
ORDER BY agent_type, last_heartbeat DESC;

-- Set permissions (adjust based on your authentication setup)
-- GRANT USAGE ON SCHEMA research TO research_user;
-- GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA research TO research_user;
-- GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA research TO research_user;
-- GRANT EXECUTE ON ALL FUNCTIONS IN SCHEMA research TO research_user;