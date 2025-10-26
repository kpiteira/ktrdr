# Feature Specification: Component Versioning System

**Feature Branch**: `001-component-versioning-system`
**Created**: 2025-10-25
**Status**: Draft
**Input**: User description: "version management - our project supports overall versioning but there are a number of problems with it that I want to explore:
(1) I believe it only supports overall versioning, not discrete for various elements. For example we should have an overall version (e.g ktrdr v 1.2), an API version which changes every time we make a breaking change to the API (additions are ok I think but I'd welcome advice/input on that), a per-compoment version - e.g training, data loading, host services, backtesting, frontend, cli, ...
(2) I NEVER remember to change version numbers :(. for example we've been on the current version for many month, even though it has changed very significantly
(3) I have no concept of dependencies versioning. For example the backtesting is broken because it cannot even compute indicators. Likely because we changed indicators recently but backtesting has not been touched for at least 4 or 5 month... and I'm sure many other things are broken with it. We should have a system to be able to specify dependencies for each component of our system so that if a dependency version changes (likely indicating a breaking change)  it knows it needs to change."

## User Scenarios & Testing

### Priority & Dependency Overview

The user stories are prioritized based on their dependencies and the value they deliver:

**P1 - Story 3 (Multi-Level Version Hierarchy)**: Foundation layer - establishes the version infrastructure that all other stories depend on. Without versions existing, you cannot detect version changes or automate version increments.

**P2 - Story 1 (Detect Breaking Component Changes)**: Safety layer - builds the dependency graph that prevents months-long breakages. Requires versions to exist (Story 3) but provides critical safety even with manual version management. The dependency graph also enables smarter automation in Story 2.

**P3 - Story 2 (Auto Version Management)** & **Story 4 (API Compatibility)**: Automation/specialization layer - these can be developed in parallel once the foundation (Story 3) and dependency graph (Story 1) are in place. Both enhance the system but are not required for basic functionality.

**Dependency Chain**: Story 3 → Story 1 → Stories 2 & 4 (parallel)

---

### User Story 1 - Component Dependency Management & Change Detection (Priority: P2)

**Part A - Defining Dependencies (Static Phase)**: A developer needs to document that the backtesting component depends on the indicators and data components. They define this relationship in a dependency configuration file (or through code annotations). The system stores this dependency graph and makes it queryable. Other developers can query "what does backtesting depend on?" and see [indicators, data], or query "what depends on indicators?" and see [backtesting, training]. The dependency graph covers ALL system components - training, data loading, host services, CLI, API, frontend, backtesting, indicators, etc.

**Part B - Detecting Changes (Dynamic Phase)**: A developer makes changes to any component in the system. When they commit their changes, the system uses the dependency graph to automatically detect which other components depend on the modified component and notifies the developer that those dependents may be affected. The developer can see the complete list of impacted components and understand what needs attention before breaking changes are deployed. For example: if a developer modifies the indicators module, the system queries the dependency graph, finds that backtesting and training depend on it, and warns the developer to review those dependent components.

**Why this priority**: This builds the critical dependency graph infrastructure and provides the safety net to prevent broken dependencies from going unnoticed. DEPENDS ON Story 3 (version infrastructure must exist first). This story establishes the dependency tracking that enables both breaking change detection AND smarter version management in Story 2. Even with manual versions, detecting "you modified indicators which backtesting depends on" prevents months-long breakages like the backtesting/indicators example. The graph must be defined (Part A) before it can be used for change detection (Part B).

**Independent Test**: Can be fully tested by (1) defining component dependencies and querying the graph, then (2) modifying components with dependents and verifying the system correctly identifies all affected components. Delivers immediate value by preventing silent breakage across the entire codebase.

**Acceptance Scenarios**:

**Static Phase - Dependency Definition**:
1. **Given** a developer needs to declare dependencies for a component, **When** they define dependencies (e.g., "backtesting depends on [indicators v1.5+, data v2.0+]"), **Then** the system stores this in the dependency graph and makes it queryable
2. **Given** the dependency graph exists, **When** a developer queries "what does [component X] depend on", **Then** they see all direct dependencies with version requirements (e.g., "backtesting depends on: indicators >=1.5.0, data >=2.0.0")
3. **Given** the dependency graph exists, **When** a developer queries "what depends on [component X]", **Then** they see all components that list it as a dependency (e.g., "indicators is depended on by: backtesting, training, data_loading")
4. **Given** a dependency graph is defined, **When** a developer views it, **Then** they can see the complete graph structure showing all component relationships across the entire system

**Dynamic Phase - Change Detection**:
5. **Given** any component has dependent components in the graph, **When** a developer modifies that component's code, **Then** the system identifies and displays ALL components that depend on it using the dependency graph
6. **Given** a complete component dependency graph exists for all system components, **When** a developer commits changes to any component, **Then** the system validates version compatibility for all dependent components and warns of any issues
7. **Given** a developer is about to commit changes to any component, **When** the commit would create a breaking change in a component that has dependents, **Then** the system prompts the developer to acknowledge the impact on ALL affected dependent components
8. **Given** multiple components depend on a modified component, **When** the developer reviews the impact, **Then** they see the complete dependency chain (e.g., "indicators → [backtesting, training, data_loading]")

---

### User Story 2 - Automatic Component Version Management (Priority: P3)

A developer makes significant changes to any component over several commits. The system tracks these changes and automatically suggests version bumps based on the nature of changes (major for breaking changes, minor for new features, patch for bug fixes). The developer can review and approve version changes without having to remember to manually update version numbers. For example: if a developer makes several commits to the training module adding new features and fixing bugs, the system analyzes the changes and suggests "training: 1.4.2 → 1.5.0 (2 features added, 3 bugs fixed)".

**Why this priority**: Solves the "forgetting to update versions" problem by automating detection and suggesting appropriate version changes. DEPENDS ON Stories 3 (version infrastructure) AND Story 1 (dependency graph). The dependency graph from Story 1 enables smarter version suggestions - for example, suggesting a major version bump when changes affect components with dependents. This is an automation layer on top of the foundational infrastructure.

**Independent Test**: Can be tested by making various types of changes to a component and verifying the system correctly categorizes them and suggests appropriate version increments. Delivers value by removing the manual burden of version management.

**Acceptance Scenarios**:

1. **Given** a developer has made changes to a component, **When** they prepare to commit, **Then** the system analyzes the changes and suggests an appropriate version increment (major/minor/patch)
2. **Given** multiple commits have been made to a component, **When** the developer reviews pending version changes, **Then** the system shows a summary of changes and the recommended version bump
3. **Given** a developer explicitly marks a change as breaking, **When** they commit, **Then** the system automatically increments the major version number
4. **Given** the system suggests a version bump, **When** the developer reviews it, **Then** they can accept, modify, or reject the suggestion before finalizing

---

### User Story 3 - Multi-Level Version Hierarchy (Priority: P1)

A project manager reviews the system versions and sees a clear hierarchy: overall project version (ktrdr v1.2), API version (v2.1), and individual component versions for ALL system components. Each component version changes independently based on its own change history. When querying version information, they can see at a glance which components are actively developed (high version numbers with recent changes) versus stagnant (low version numbers, old dates). For example: the hierarchy might show training v1.5, data v2.0, backtesting v0.8, indicators v1.3, host_services v1.1, frontend v2.2, CLI v1.0, etc.

**Why this priority**: This is the FOUNDATION - nothing else can work without it. Stories 1 and 2 both depend on versions existing before they can detect changes or suggest increments. This story establishes the version infrastructure (FR-001: maintain component versions, FR-002: maintain project version, FR-014: persist version info). Delivers immediate standalone value: developers can query versions and see the hierarchy even before automation is added.

**Independent Test**: Can be tested by setting component versions and querying the version hierarchy through various interfaces. Delivers value by providing clear version visibility across all system levels.

**Acceptance Scenarios**:

1. **Given** the system has multiple versioned components, **When** a developer queries version information, **Then** they see overall project version, API version, and all component versions in a hierarchical view
2. **Given** each component has its own version, **When** a component version changes, **Then** the overall project version reflects that a change occurred but does not necessarily increment at the same rate
3. **Given** the API has breaking changes, **When** the API version increments, **Then** the overall project version increments but component versions remain independent unless they were modified
4. **Given** a developer asks "what version is [any component]", **When** they query the version system, **Then** they receive that component's version, last change date, and a summary of what changed (e.g., "training v1.5.0, updated 2024-10-15, added GPU support")

---

### User Story 4 - API Version Compatibility Contract (Priority: P3)

An API consumer uses version 2.0 of the KTRDR API. When the development team adds new optional endpoints or fields, the API remains at version 2.x (minor increment). When they make a breaking change (remove an endpoint, change a required field), the version increments to 3.0. The API consumer can see clear documentation about what changed between versions and make informed decisions about when to upgrade.

**Why this priority**: API stability is critical for consumers, and clear versioning prevents breaking client integrations. DEPENDS ON Story 3 (version infrastructure). This is a specialized application of the core versioning system with API-specific rules for what constitutes breaking vs non-breaking changes. Can be developed in parallel with Story 2 once the foundation is in place.

**Independent Test**: Can be tested by simulating various API changes and verifying the system correctly categorizes them as major vs minor changes. Delivers value by establishing clear API compatibility guarantees.

**Acceptance Scenarios**:

1. **Given** the API is at version 2.5, **When** developers add new optional endpoints or optional fields to existing endpoints, **Then** the API version increments to 2.6 (minor)
2. **Given** the API is at version 2.5, **When** developers remove an endpoint, change a required field's type, or remove a required field, **Then** the API version increments to 3.0 (major)
3. **Given** an API version change occurs, **When** an API consumer queries version information, **Then** they see a changelog describing what changed and whether it's a breaking change
4. **Given** the API has multiple active major versions (e.g., 2.x and 3.x), **When** a consumer makes a request, **Then** the system routes to the appropriate version based on the consumer's specified API version

---

### Edge Cases

**Dependency Graph Management**:
- What happens when a component dependency forms a circular reference (A depends on B, B depends on A)?
- How does the system handle a component that has never been versioned being integrated into the dependency tracking system?
- What if a developer forgets to declare a dependency - can the system detect missing dependencies through import analysis?
- What if dependencies are defined inconsistently (config file says one thing, code imports say another)?
- How are transitive dependencies handled (A depends on B, B depends on C - does A need to know about C)?
- What if a dependency is removed from a component - how is the graph updated?

**Version Management**:
- What if a developer makes a breaking change but doesn't realize it (no explicit marking)?
- What if the same code change affects multiple components simultaneously (e.g., a shared utility module)?
- How are hotfix branches handled - do they affect component versions differently than feature branches?
- What if a component is deprecated - how is that reflected in the version system?
- How does the system handle version conflicts during merges (two branches both incrementing the same component version)?

**External Dependencies**:
- What if external dependencies (npm packages, Python packages) change in breaking ways - how is that tracked?

## Requirements

### Functional Requirements

- **FR-001**: System MUST maintain separate version numbers for each defined component (training, data loading, indicators, host services, backtesting, frontend, CLI, API, and any other components defined in the system)
- **FR-002**: System MUST maintain an overall project version that reflects the aggregate state of all component changes
- **FR-003**: System MUST provide a mechanism for developers to declare/define dependencies between components (e.g., declaring "backtesting depends on indicators >=1.5.0")
- **FR-003a**: System MUST store the component dependency graph in a configuration file within the repository
- **FR-003b**: System MUST validate the dependency graph for circular dependencies and warn developers if detected
- **FR-003c**: System MUST track dependencies between components with version compatibility requirements (e.g., backtesting depends on indicators >=1.5.0 <2.0.0)
- **FR-004**: System MUST detect when a change to a component affects its dependent components
- **FR-005**: System MUST notify developers when they modify a component that other components depend on
- **FR-006**: System MUST automatically analyze code changes to suggest version increments (major/minor/patch)
- **FR-007**: System MUST allow developers to explicitly mark changes as breaking, feature additions, or fixes
- **FR-008**: System MUST prevent commits that would break dependent components without developer acknowledgment
- **FR-009**: System MUST provide a command to query current version of any component
- **FR-010**: System MUST provide a command to view the version hierarchy (project → API → components)
- **FR-011**: System MUST track API version separately with semantic versioning focused on backwards compatibility
- **FR-012**: System MUST distinguish between breaking API changes (remove/modify) and non-breaking changes (add optional features)
- **FR-013**: System MUST maintain a changelog for each component showing what changed in each version
- **FR-014**: System MUST persist version information in configuration file(s) within the repository, extending the existing version config file approach
- **FR-015**: System MUST allow querying which components depend on a given component
- **FR-016**: System MUST allow querying which components a given component depends on
- **FR-017**: System MUST support version compatibility rules (e.g., training v2.x requires indicators v1.5+)
- **FR-018**: System MUST validate dependency versions are compatible during build/test
- **FR-019**: System MUST provide tooling to help developers update dependent components when breaking changes occur
- **FR-020**: System MUST distinguish between development versions (on branches) and released versions (on main/tags)

### Key Entities

- **Component**: A logical module of the system with independent versioning (examples: training, data_loading, indicators, backtesting, frontend, cli, api, host_services). Has a semantic version number (major.minor.patch), changelog, and dependency list.

- **Component Version**: A specific version of a component (e.g., indicators v1.5.2). Includes version number, release date, changelog entry, and compatibility requirements.

- **Dependency Graph**: The complete structure of component dependencies across the entire system. Stored in a configuration file (separate from version state). Defines which components depend on which other components with version compatibility requirements. Queryable to answer "what does X depend on" and "what depends on X". Must be defined by developers (static phase) before it can be used for change detection (dynamic phase).

- **Dependency Relationship**: Links between components where one component relies on another. Includes the dependent component, the dependency component, and version compatibility rules (e.g., "requires v1.5 or higher"). Multiple relationships together form the Dependency Graph.

- **Project Version**: The overall version of the KTRDR system (e.g., v1.2.0). Reflects aggregate state of all components but increments independently based on release criteria.

- **API Version**: A special component version tracking API backwards compatibility. Follows semantic versioning with strict rules: major version for breaking changes, minor for additions, patch for fixes.

- **Change Classification**: Categorization of code changes (breaking, feature, fix) used to determine appropriate version increments. Can be explicitly set by developer or inferred from commit analysis.

- **Version Compatibility Rule**: Defines which versions of a dependency are compatible with a component version (e.g., "backtesting v2.0 requires indicators >=v1.5.0 <v2.0.0").

- **Changelog Entry**: Documents what changed in a specific version of a component. Includes version number, date, change description, and breaking change indicators.

## Success Criteria

### Measurable Outcomes

- **SC-001**: Zero instances of broken component dependencies making it to main branch undetected
- **SC-002**: 100% of commits to components with dependents trigger dependency validation
- **SC-003**: Developers can identify the current version of any component in under 10 seconds
- **SC-004**: Version numbers are updated automatically for 80% of commits without manual developer intervention
- **SC-005**: When a breaking change is made to a component with dependents, all affected components are identified and reported to the developer
- **SC-006**: API version changes follow semantic versioning rules with 100% accuracy (breaking changes → major, additions → minor)
- **SC-007**: Developers can view the complete dependency graph for the project in under 5 seconds
- **SC-007a**: All components have their dependencies explicitly declared in the dependency graph (100% coverage)
- **SC-007b**: Dependency graph queries ("what does X depend on" / "what depends on X") return results in under 2 seconds
- **SC-008**: Time to identify why a component is broken due to dependency changes is reduced by 90% (from discovering manually to automatic detection)
- **SC-009**: 95% of suggested version increments are accepted by developers without modification
- **SC-010**: All components have up-to-date version information and changelogs

## Assumptions

- **Semantic Versioning**: The system will follow semantic versioning principles (major.minor.patch) where major = breaking changes, minor = new features (backwards compatible), patch = bug fixes
- **Git-based Workflow**: Version management will integrate with Git workflow (pre-commit hooks, branch analysis, etc.)
- **Component Boundaries**: Components are already architecturally defined and can be identified by directory structure or module boundaries
- **Monorepo Structure**: All components exist in a single repository, making it possible to analyze cross-component dependencies
- **Dependency Graph Initial Creation**: Developers will manually define the initial dependency graph (what depends on what) in a configuration file. The system may assist with validation and suggestions, but initial definition requires developer knowledge of component relationships
- **Developer Cooperation**: Developers will review and respond to version change suggestions rather than blindly accepting all recommendations
- **API Versioning Strategy**: For API versioning, additions (new endpoints, optional fields) are non-breaking, while removals or modifications to existing contracts are breaking changes
- **Backwards Compatibility Window**: The system will support compatibility rules like "requires v1.5+" without needing to specify exact versions
- **Change Detection**: The system can analyze code changes (via git diff, AST analysis, or similar) to infer the nature of changes when not explicitly marked

## Dependencies & Constraints

### Dependencies

- Git version control system (for tracking changes and triggering version checks)
- Access to commit history and diff information
- Ability to execute pre-commit or CI/CD hooks
- Component dependency information (may need to be manually defined initially)

### Constraints

- Cannot require developers to manually specify versions for every change (would fail to solve the "forgetting" problem)
- Cannot break existing development workflow significantly (must integrate smoothly)
- Version detection must be fast enough for pre-commit hooks (< 5 seconds)
- Must support the existing KTRDR architecture (Docker containers, host services, API, CLI)

## Out of Scope

- Automatic fixing of broken dependencies (system detects but doesn't auto-repair code)
- Version management for external dependencies (npm, pip packages) - only internal components
- Deployment automation or release management
- Rollback functionality
- Version branching strategies (which versions to support in parallel)
- Performance impact analysis of version changes
- Automated migration tools between versions
- Version documentation generation (beyond changelogs)
