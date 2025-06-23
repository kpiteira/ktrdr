# 📋 KTRDR Documentation Cleanup Plan
*Comprehensive audit and reorganization strategy*

## 🎯 Executive Summary

**Current State**: Documentation scattered across 3 locations (~40 files) with mixed relevance
**Target State**: Professional, organized documentation system reflecting the mature trading platform
**System Maturity**: 85-90% implemented neuro-fuzzy trading platform (7.5/10 architecture score per ADR-008)

## 📊 Audit Results Summary

| Location | Total Files | Keep Current | Move/Reorganize | Archive | Delete |
|----------|-------------|--------------|-----------------|---------|--------|
| **Root Level** | 15 | 2 | 6 | 6 | 1 |
| **Specification/** | 25+ | 8 | 5 | 0 | 2 |
| **docs/** | Well-organized | ✅ Keep as-is | - | - | - |

## 🔍 Key Findings

### ✅ What's Working Well
- **docs/ folder structure is excellent** - well-organized with user-guides/, developer/, api/
- **CLAUDE.md is critical** - development constitution that should remain at root
- **claude-knowledge/ folder** - most up-to-date high-level documentation
- **ADR-008** - excellent current architecture assessment (December 2024)

### ⚠️ Critical Issues Identified
1. **Implementation-Spec Gap**: ADRs 2,3,4,5 are 85-90% implemented but specs may be outdated
2. **Technical Debt**: ADR-008 identifies 83 files with TODO/FIXME markers
3. **Scattered Documentation**: 15 root-level files that belong in docs/
4. **Broken ADR Index**: ADR-000 has duplicates and inconsistent status tracking

### 🎯 System Reality vs Documentation
- **Neural Network System**: FULLY IMPLEMENTED (70+ trained models in /models/)
- **Decision Engine**: COMPLETE with orchestrator, position tracking, confidence filtering
- **Training Pipeline**: COMPLETE with ZigZag labeling, feature engineering, model versioning
- **Strategy Configuration**: COMPLETE YAML-based system exactly as specified

## 📁 Proposed Final Organization Structure

```
📁 PROJECT ROOT
├── 📄 README.md                    (Keep - essential)
├── 📄 CLAUDE.md                    (Keep - development constitution)
│
├── 📁 docs/                        (EXCELLENT - keep structure)
│   ├── 📁 user-guides/
│   │   ├── 📄 cli-reference.md     (← UNIFIED_CLI_GUIDE.md)
│   │   └── 📄 strategy-management.md (← STRATEGY_CLI_GUIDE.md)
│   ├── 📁 developer/
│   │   ├── 📄 testing-guide.md     (← TESTING_GUIDE.md)
│   │   ├── 📄 indicator-architecture.md (← ARCHITECTURE_INDICATORS.md)
│   │   ├── 📄 backtesting-issues.md (← BACKTESTING_EXECUTION_AUDIT.md)
│   │   └── 📄 test-recovery-plan.md (← UNIT_TEST_RECOVERY_PLAN.md)
│   └── 📁 archive/
│       ├── 📄 data-loading-improvements-complete.md
│       ├── 📄 head-timestamp-fix-complete.md
│       ├── 📄 pace-limiting-fix-complete.md
│       ├── 📄 volume-handling-analysis-complete.md
│       └── 📄 progress-tracking-implementation-complete.md
│
└── 📁 specification/
    ├── 📁 current/                 (NEW - active specs)
    │   ├── 📄 adr-000-index.md     (Fix duplicates/inconsistencies)
    │   ├── 📄 adr-008-architecture-assessment.md ⭐ (Most current)
    │   └── 📁 claude-knowledge/    (Keep - high-level docs)
    ├── 📁 implemented/             (NEW - needs reality sync)
    │   ├── 📄 adr-002-decision-engine.md (Verify vs /ktrdr/decision/)
    │   ├── 📄 adr-003-neuro-fuzzy-framework.md (85% implemented)
    │   ├── 📄 adr-004-training-system.md (90% implemented)
    │   └── 📄 adr-005-backtesting-system.md (Needs verification)
    ├── 📁 future/                  (NEW - unimplemented specs)
    │   ├── 📄 adr-006-deployment-evolution.md
    │   ├── 📄 adr-007-paper-trading.md
    │   └── 📄 adr-010-train-mode-ui.md
    ├── 📁 research/                (NEW - research & MCP)
    │   ├── 📄 All MCP-related files
    │   ├── 📄 multi-symbol-model-design.md
    │   └── 📄 Research documents
    └── 📁 Archive/                 (Keep as-is - historical)
```

## 🚀 Implementation Plan

### Phase 1: Root Level Cleanup & Content Validation (Priority: HIGH)

**⚠️ CRITICAL: Each file must be updated for accuracy BEFORE moving to final location**

#### Step 1A: Content Accuracy Analysis Required

**Files Moving to docs/user-guides/ (CHECK ACCURACY FIRST):**

1. **STRATEGY_CLI_GUIDE.md** → `docs/user-guides/strategy-management.md`
   - 🔍 **Accuracy Check**: Do CLI commands match current implementation?
   - 🔍 **Completeness**: Does it cover neuro-fuzzy strategy commands?
   - 🔧 **Update Required**: Verify all command examples work with current code

2. **UNIFIED_CLI_GUIDE.md** → `docs/user-guides/cli-reference.md`
   - 🔍 **Accuracy Check**: Are all CLI commands current and functional?
   - 🔍 **Completeness**: Missing any new commands from recent development?
   - 🔧 **Update Required**: Test all examples, add missing commands

**Files Moving to docs/developer/ (CHECK ACCURACY FIRST):**

3. **TESTING_GUIDE.md** → `docs/developer/testing-guide.md`
   - 🔍 **Accuracy Check**: Do test commands work with current setup?
   - 🔍 **Completeness**: Covers neuro-fuzzy system testing?
   - 🔧 **Update Required**: Verify pytest commands, add neural network testing

4. **ARCHITECTURE_INDICATORS.md** → `docs/developer/indicator-architecture.md`
   - 🔍 **Accuracy Check**: Does architecture match current indicator implementation?
   - 🔍 **Completeness**: Covers fuzzy integration?
   - 🔧 **Update Required**: Verify against /ktrdr/indicators/ structure

5. **BACKTESTING_EXECUTION_AUDIT.md** → `docs/developer/backtesting-issues.md`
   - 🔍 **Accuracy Check**: Are identified issues still present?
   - 🔍 **Relevance**: Do recommendations match current backtesting system?
   - 🔧 **Update Required**: Check if issues have been resolved

6. **UNIT_TEST_RECOVERY_PLAN.md** → `docs/developer/test-recovery-plan.md`
   - 🔍 **Accuracy Check**: Is test recovery plan still relevant?
   - 🔍 **Progress**: Which parts have been completed?
   - 🔧 **Update Required**: Mark completed items, update remaining tasks

#### Step 1B: Move and Update Process

```bash
# DO NOT run these commands until content accuracy is verified!

# Step 1: Analyze and update content accuracy (manual process)
# Step 2: Then move files to proper locations
mv STRATEGY_CLI_GUIDE.md docs/user-guides/strategy-management.md
mv UNIFIED_CLI_GUIDE.md docs/user-guides/cli-reference.md
mv TESTING_GUIDE.md docs/developer/testing-guide.md
mv ARCHITECTURE_INDICATORS.md docs/developer/indicator-architecture.md
mv BACKTESTING_EXECUTION_AUDIT.md docs/developer/backtesting-issues.md
mv UNIT_TEST_RECOVERY_PLAN.md docs/developer/test-recovery-plan.md
```

#### Files to Archive (Completed Projects)
```bash
mkdir -p docs/archive
mv DATA_LOADING_IMPROVEMENTS.md docs/archive/data-loading-improvements-complete.md
mv HEAD_TIMESTAMP_FIX_SUMMARY.md docs/archive/head-timestamp-fix-complete.md
mv PACE_LIMITING_FIX_SUMMARY.md docs/archive/pace-limiting-fix-complete.md
mv VOLUME_HANDLING_ANALYSIS.md docs/archive/volume-handling-analysis-complete.md
mv PROGRESS_TRACKING_IMPLEMENTATION.md docs/archive/progress-tracking-implementation-complete.md
mv CLAUDE-training-fix-plan.md docs/archive/training-indicator-coupling-fix-plan.md
```

#### Files to Delete (Obsolete)
```bash
rm NEURAL_ARCHITECTURE_FIXES.md
```

#### Files to Keep at Root
- ✅ README.md (Essential project overview)
- ✅ CLAUDE.md (Development constitution)

### Phase 2: Specification Critical Analysis & Reorganization (Priority: HIGH)

**⚠️ CRITICAL: Each specification file MUST be analyzed against current codebase reality before reorganization**

#### Step 2A: Audit Each Specification File for Accuracy

**Files Requiring Immediate Reality Check:**

1. **adr-000-index.md** 
   - ❌ BROKEN: Contains duplicate ADR-002 entries
   - ❌ INCONSISTENT: Status tracking doesn't match reality
   - 🔧 **Action**: Complete rewrite based on actual ADR status

2. **ADR-001-current-architecture-assessment.md** vs **ADR-008-current-architecture-assessment.md**
   - ❓ **DUPLICATE CONCERN**: Two architecture assessments?
   - 🔍 **Action**: Compare both, determine which is current, archive the other
   - 📅 **Check dates**: Which reflects actual 2024 architecture?

3. **adr-002-decision-engine.md**
   - ✅ **IMPLEMENTED**: /ktrdr/decision/ exists with orchestrator
   - ❓ **ACCURACY**: Does spec match actual implementation?
   - 🔧 **Action**: Line-by-line comparison with /ktrdr/decision/orchestrator.py

4. **ADR-003-neuro-fuzzy-strategy-framework.md**
   - ✅ **85% IMPLEMENTED**: Neural networks, decision engine exist
   - ❓ **ACCURACY**: 1000+ line spec vs actual /ktrdr/neural/ implementation
   - 🔧 **Action**: Update spec to match actual features (model collapse detection, etc.)

5. **adr-004-training-system.md**
   - ✅ **90% IMPLEMENTED**: Training pipeline exists, 70+ trained models
   - ❓ **ACCURACY**: Does ZigZag labeler match spec? Feature engineering?
   - 🔧 **Action**: Verify against /ktrdr/training/ implementation

6. **adr-005-backtesting-system.md**
   - ❓ **UNKNOWN STATUS**: Need to verify implementation
   - 🔍 **Action**: Check if backtesting engine exists and matches spec

7. **adr-006-deployment-evolution.md**
   - ❓ **RELEVANCE**: 4-phase deployment plan - still valid for current system?
   - 🔍 **Action**: Review against current Docker setup and production needs

8. **adr-007-paper-trading.md**
   - ❓ **PREMATURE**: System ready for paper trading?
   - 🔍 **Action**: Verify prerequisites are met before keeping as active spec

9. **adr-010-train-mode-ui.md**
   - ❓ **UI COMPLEXITY**: ADR-008 mentions frontend state issues
   - 🔍 **Action**: Check if this addresses current UI problems or adds complexity

#### Step 2B: Files Requiring Deep Accuracy Analysis

**Research & Design Documents:**
- **multi-symbol-model-design.md**: Does this match current model capabilities?
- **neural-training-api-endpoints.md**: Are these endpoints implemented?
- **neuro-fuzzy-strategies-research.md**: Still relevant research or outdated?
- **phase5-multi-timeframe-neuro-fuzzy-enhancement.md**: Ready for phase 5?
- **ib-connection-system-redesign.md**: Does this address current IB issues?
- **ib-gap-analysis-improvements.md**: Are these gaps still present?

**MCP Documents:**
- **All ktrdr-mcp-*.md files**: Are these current for active MCP development?
- **mcp-end-to-end-business-tests.md**: Does this match current testing approach?

**Standalone Documents:**
- **getting-started-guide.md**: Accurate for current system state?
- **TIMEZONE_ANALYSIS.md**: Still relevant or analysis complete?
- **New docs.md**: What is this file? Useful or placeholder?

#### Step 2C: Reorganization Based on Analysis Results

**Only after accuracy analysis, reorganize into:**

```bash
cd specification/

# Create new structure
mkdir -p verified-current verified-implemented outdated-needs-update research-current archive-obsolete

# Move files based on ANALYSIS RESULTS, not assumptions
# (Commands will be updated after each file is analyzed)
```

### Phase 3: Critical Updates (Priority: HIGH)

#### 1. Fix ADR-000 Index
- Remove duplicate ADR-002 entries
- Update status tracking for all ADRs
- Ensure consistency with actual implementation state

#### 2. Sync Implemented ADRs with Reality
**ADR-003 (Neuro-Fuzzy Framework)**:
- ✅ Neural network models: COMPLETE (/ktrdr/neural/)
- ✅ Decision engine: COMPLETE (/ktrdr/decision/)
- ✅ Strategy YAML config: COMPLETE
- ❓ Update spec to match current implementation details

**ADR-004 (Training System)**:
- ✅ Training pipeline: COMPLETE (/ktrdr/training/)
- ✅ ZigZag labeler: COMPLETE with enhancements
- ✅ Feature engineering: COMPLETE
- ✅ Model storage: COMPLETE with versioning
- ❓ Update spec to match current feature set

**ADR-005 (Backtesting System)**:
- ❓ Verify integration with DecisionOrchestrator
- ❓ Check if backtesting matches current specification

#### 3. Address Technical Debt (From ADR-008)
Priority areas identified:
- 83 files with TODO/FIXME markers
- Coupling issues between modules
- Production readiness gaps
- State management complexity

## 📋 Detailed File Analysis

### Root Level Files Analysis

| File | Status | Action | Reason |
|------|--------|--------|---------|
| README.md | ✅ Current | Keep | Essential project overview |
| CLAUDE.md | ✅ Current | Keep | Development constitution |
| STRATEGY_CLI_GUIDE.md | 🔄 Current | Move to docs/user-guides/ | User documentation |
| TESTING_GUIDE.md | 🔄 Current | Move to docs/developer/ | Developer documentation |
| UNIFIED_CLI_GUIDE.md | 🔄 Current | Move to docs/user-guides/ | User reference |
| ARCHITECTURE_INDICATORS.md | 🔄 Current | Move to docs/developer/ | Architecture documentation |
| BACKTESTING_EXECUTION_AUDIT.md | 🔄 Current | Move to docs/developer/ | Technical analysis |
| UNIT_TEST_RECOVERY_PLAN.md | 🔄 Current | Move to docs/developer/ | Development process |
| DATA_LOADING_IMPROVEMENTS.md | 📦 Complete | Archive | Completed project |
| HEAD_TIMESTAMP_FIX_SUMMARY.md | 📦 Complete | Archive | Completed fix |
| PACE_LIMITING_FIX_SUMMARY.md | 📦 Complete | Archive | Completed fix |
| VOLUME_HANDLING_ANALYSIS.md | 📦 Complete | Archive | Completed analysis |
| PROGRESS_TRACKING_IMPLEMENTATION.md | 📦 Complete | Archive | Completed feature |
| CLAUDE-training-fix-plan.md | 📦 Complete | Archive | Completed fix plan |
| NEURAL_ARCHITECTURE_FIXES.md | 🗑️ Obsolete | Delete | Temporary notes |

### Specification Files Analysis

| File | Category | Status | Action |
|------|----------|--------|--------|
| adr-000-index.md | Current | ⚠️ Broken | Fix duplicates & inconsistencies |
| ADR-001-current-architecture-assessment.md | Reference | 🔄 Outdated | Keep as reference, ADR-008 supersedes |
| adr-002-decision-engine.md | Implemented | 🔄 Needs Sync | Verify vs /ktrdr/decision/ |
| ADR-003-neuro-fuzzy-strategy-framework.md | Implemented | 🔄 Needs Sync | 85% implemented, update spec |
| adr-004-training-system.md | Implemented | 🔄 Needs Sync | 90% implemented, update spec |
| adr-005-backtesting-system.md | Implemented | ❓ Unknown | Verify implementation status |
| adr-006-deployment-evolution.md | Future | ✅ Current | Keep for future work |
| adr-007-paper-trading.md | Future | ✅ Current | Keep for future work |
| adr-008-architecture-assessment.md | Current | ⭐ Most Current | Primary architecture reference |
| adr-010-train-mode-ui.md | Future | ✅ Current | Keep for future UI work |
| claude-knowledge/ | Current | ⭐ Most Current | High-level documentation |
| All MCP files | Research | ✅ Current | Active MCP development |
| Archive/ | Historical | ✅ Correct | Keep as-is |
| tasks-archive/ | Historical | ✅ Correct | Keep as-is |

## 🎯 Success Metrics

### Immediate Benefits
- ✅ Clean root directory (only 2 essential files)
- ✅ Logical categorization (current/implemented/future/research)
- ✅ Professional appearance matching project maturity
- ✅ All historical work preserved but organized

### Long-term Benefits
- 📈 Easy maintenance with clear categorization
- 📈 Better decision-making (clear what's real vs planned)
- 📈 Reduced onboarding time for new developers
- 📈 Documentation lifecycle process established

## ⚠️ Critical Next Steps - UPDATED APPROACH

**🚨 CHANGED METHODOLOGY: Analysis-First Approach (Not Blind Reorganization)**

### Immediate Priority (Week 1):
1. **ACCURACY AUDIT**: Systematically check each document against current codebase
2. **CONTENT UPDATES**: Fix inaccuracies BEFORE moving files
3. **REALITY SYNC**: Update specs to match implemented features
4. **BROKEN FIXES**: Fix ADR-000 index duplicates and inconsistencies

### Implementation Priority (Week 2):
1. **VERIFIED MOVES**: Only move files after content verification
2. **UPDATED DOCS**: Ensure all moved files reflect current system state
3. **CROSS-REFERENCES**: Update internal links and navigation
4. **VALIDATION**: Test that all CLI examples and procedures work

### Ongoing (Monthly):
1. **TECHNICAL DEBT**: Address ADR-008's 83 TODO/FIXME findings
2. **SPEC MAINTENANCE**: Keep implemented ADRs synchronized with code evolution
3. **DOCUMENTATION LIFECYCLE**: Follow new placement guidelines for future docs

## 🎯 **Key Methodology Change**

**OLD APPROACH (TOO SIMPLE):**
```
Find scattered docs → Move to organized folders → Done
```

**NEW APPROACH (THOROUGH & RESPONSIBLE):**
```
Audit content accuracy → Update outdated information → Verify with codebase → Then organize
```

This ensures documentation cleanup actually improves accuracy, not just appearance.

## 💡 Document Lifecycle Process

Going forward, establish this process:
1. **NEW IDEAS** → research/
2. **ACTIVE DEVELOPMENT** → current/
3. **COMPLETED FEATURES** → implemented/ (with reality sync)
4. **FUTURE PLANNING** → future/
5. **COMPLETED PROJECTS** → archive/

## 🔗 Cross-Reference Updates Needed

After reorganization:
- Update internal links in all documents
- Update docs/index.md navigation structure
- Ensure CLAUDE.md references remain valid
- Add redirect notes for moved files if needed
- Update any CI/CD references to documentation paths

## 🤖 Claude Documentation Guidelines

To maintain this organized structure in future Claude interactions, the following guidelines should be added to `CLAUDE.md`:

### Documentation Placement Rules for Claude
```markdown
## 📁 DOCUMENTATION PLACEMENT GUIDELINES

When creating or updating documentation, Claude should follow these rules:

### Root Level (RESTRICTED)
- ❌ NO new files except in emergencies
- ✅ Only README.md and CLAUDE.md belong here
- 🚨 If you must create a temporary file, move it immediately after completion

### docs/ Structure
- **docs/user-guides/**: CLI references, how-to guides, tutorials
- **docs/developer/**: Architecture, testing, development process, plans
- **docs/api/**: API documentation and references  
- **docs/archive/**: Completed projects and historical documentation

### specification/ Structure  
- **specification/current/**: Active ADRs and current specifications
- **specification/implemented/**: ADRs that are implemented (may need sync)
- **specification/future/**: Planned features and unimplemented specs
- **specification/research/**: Research documents, MCP specs, analysis
- **specification/claude-knowledge/**: High-level system documentation
- **specification/Archive/**: Historical specifications (don't modify)

### Decision Matrix for New Documents
1. **Is it a user guide or CLI reference?** → docs/user-guides/
2. **Is it development process or architecture?** → docs/developer/
3. **Is it an API specification?** → docs/api/
4. **Is it a new ADR or active spec?** → specification/current/
5. **Is it research or analysis?** → specification/research/
6. **Is it a completed project summary?** → docs/archive/

### File Naming Conventions
- Use lowercase with hyphens: `file-name.md`
- Be descriptive: `backtesting-issues.md` not `issues.md`  
- Include dates for time-sensitive docs: `2024-performance-analysis.md`

### When in Doubt
- Ask the user where they want documentation placed
- Default to docs/developer/ for development-related content
- NEVER default to root directory
```

### Update Required in CLAUDE.md
This section should be added to CLAUDE.md under a new heading like "## 📁 DOCUMENTATION ORGANIZATION" to ensure future Claude interactions follow the organized structure.

---

**Final Assessment**: Your system has evolved from research tool to production-capable trading platform, but documentation organization hasn't kept pace. This plan aligns documentation structure with the sophisticated system you've built.