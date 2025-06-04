# ADR-000: Architecture Decision Records Index

## Status
**Active** - December 2024

## Overview
This document serves as the central index for all Architecture Decision Records (ADRs) in the KTRDR project. It provides a roadmap of documentation for building the neuro-fuzzy trading system.

## Document Structure

### ✅ Completed ADRs

#### ADR-001: Current Architecture Assessment
**Status**: Completed  
**Purpose**: Detailed analysis of the current KTRDR architecture, identifying strengths, extension points, and areas for evolution.  
**Key Content**:
- System architecture overview (Backend, Frontend, Data Layer, IB Integration)
- API layer documentation with endpoints and schemas
- Core modules analysis (Data Management, Indicator Engine, Fuzzy Logic, Frontend)
- Infrastructure and deployment patterns
- Ready integration points for Decision Engine

#### ADR-002: Core Decision Engine Architecture
**Status**: Draft Completed - December 2024  
**Purpose**: Overall architecture for how trading decisions flow through the system.  
**Key Content**:
- Decision orchestrator that coordinates all components
- Integration points with ADR-003, ADR-004, and ADR-005
- Position and state management
- Mode-specific behavior (backtest/paper/live)
- Clear implementation roadmap for Claude Code

#### ADR-003: Neuro-Fuzzy Strategy Framework
**Status**: Completed  
**Purpose**: Design for the neural network layer that consumes fuzzy membership values to generate trading decisions.  
**Key Content**:
- Neuro-fuzzy pipeline architecture (Data → Indicators → Fuzzy → Neural Network → Decisions)
- Enhanced YAML configuration schema for strategies
- Neural network engine design with MLP implementation
- Decision engine with position awareness
- ZigZag label generation for supervised learning
- Integration points with existing systems

#### ADR-004: Training System Design
**Status**: Draft Completed - December 2024  
**Purpose**: Architecture for training neural networks using historical data and ZigZag labels.  
**Key Content**:
- Complete training pipeline leveraging existing infrastructure
- Feature engineering from fuzzy memberships
- Model versioning with organized directory structure
- Feature importance analysis
- CLI interface for single-instrument training
- Integration with existing data/indicator/fuzzy modules

#### ADR-005: Backtesting System Design  
**Status**: Draft Completed - December 2024  
**Purpose**: Historical simulation engine for evaluating trained strategies.  
**Key Content**:
- Event-driven architecture with comprehensive position tracking
- API-first design with FastAPI endpoints
- Detailed performance metrics and trade analysis
- Model version management (latest by default, CLI override)
- CLI interface using the API
- Architecture ready for future intrabar/multi-timeframe evolution

### ✅ Recently Completed ADRs

#### ADR-002: Core Decision Engine Architecture
**Status**: Draft Completed - December 2024  
**Purpose**: Overall architecture for how trading decisions flow through the system.  
**Key Content**:
- Decision orchestrator that coordinates all components
- Integration points with ADR-003, ADR-004, and ADR-005
- Position and state management
- Mode-specific behavior (backtest/paper/live)
- Clear implementation roadmap for Claude Code

### ✅ Recently Completed ADRs

### ✅ Recently Completed ADRs

#### ADR-002: Core Decision Engine Architecture
**Status**: Draft Completed - December 2024  
**Purpose**: Overall architecture for how trading decisions flow through the system.  
**Key Content**:
- Decision orchestrator that coordinates all components
- Integration points with ADR-003, ADR-004, and ADR-005
- Position and state management
- Mode-specific behavior (backtest/paper/live)
- Clear implementation roadmap for Claude Code

#### ADR-004: Training System Design
**Status**: Draft Completed - December 2024  
**Purpose**: Architecture for training neural networks using historical data and ZigZag labels.  
**Key Content**:
- Complete training pipeline leveraging existing infrastructure
- Feature engineering from fuzzy memberships
- Model versioning with organized directory structure
- Feature importance analysis
- CLI interface for single-instrument training
- Integration with existing data/indicator/fuzzy modules

#### ADR-005: Backtesting System Design  
**Status**: Draft Completed - December 2024  
**Purpose**: Historical simulation engine for evaluating trained strategies.  
**Key Content**:
- Event-driven architecture with comprehensive position tracking
- API-first design with FastAPI endpoints
- Detailed performance metrics and trade analysis
- Model version management (latest by default, CLI override)
- CLI interface using the API
- Architecture ready for future intrabar/multi-timeframe evolution

### 🎯 Future ADRs

#### ADR-006: Deployment Evolution Plan
**Status**: Future  
**Purpose**: Path from Docker development to distributed deployment.  
**Key Content**:
- Current Docker architecture analysis
- GitHub Actions integration
- AI Agent deployment patterns
- Distributed work strategies

#### ADR-007: Paper Trading Integration
**Status**: Future  
**Purpose**: Architecture for paper trading with Interactive Brokers.  
**Key Content**:
- IB paper trading API integration
- Order lifecycle management
- Real-time data feed handling
- Transition from backtest to paper trading

#### ADR-008: Risk Management System
**Status**: Future  
**Purpose**: Position sizing, stop losses, and portfolio risk controls.  
**Key Content**:
- Money management algorithms
- Stop loss implementation
- Portfolio exposure limits
- Emergency stop mechanisms

#### ADR-009: Live Trading System
**Status**: Future (Post-MVP)  
**Purpose**: Production-grade live trading with real capital.  
**Key Content**:
- Safety mechanisms and circuit breakers
- Error recovery and resilience
- Audit logging and compliance
- Monitoring and alerting

## MVP Scope

Based on the product roadmap, the MVP focuses on:
1. **ADR-001** ✅ - Understanding current system
2. **ADR-003** ✅ - Neuro-fuzzy strategy framework  
3. **ADR-004** 🔄 - Training system (needed for creating models)
4. **ADR-005** 🔄 - Backtesting system (needed for strategy validation)

Post-MVP priorities:
- **ADR-002** - Complete decision engine architecture
- **ADR-007** - Paper trading for live validation
- **ADR-008** - Risk management for capital protection

## Document Principles

All ADRs follow these principles:
- **Audience**: Developer (user) and LLMs (Claude, Claude Code)
- **Structure**: Context, Decision, Consequences, Implementation examples
- **Detail Level**: Include code examples, schemas, and clear integration points
- **Modularity**: Each ADR is self-contained but references related documents
- **Evolution**: Documents can be updated as implementation provides new insights

## Notes

- This index will be updated as new ADRs are created or existing ones are modified
- Each ADR should reference this index (ADR-000) for context
- Priority and status will be adjusted based on project progress and learnings