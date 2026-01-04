---
design: docs/designs/strategy-grammar-v3/DESIGN.md
architecture: docs/designs/strategy-grammar-v3/ARCHITECTURE.md
---

# Milestone 6: CLI & Migration Tools

**Branch:** `feature/strategy-grammar-v3-m6`
**Prerequisite:** M5 complete (full pipeline works)
**Builds on:** M5 Backtest Pipeline

## Goal

Users can migrate v2 strategies to v3 format and inspect generated features using CLI commands.

## Why This Milestone

- Enables transition from v2 to v3
- Provides tooling for debugging strategy configs
- Required before M8 cleanup (need to migrate strategies first)

---

## Tasks

### Task 6.1: Create Migration Logic

**File(s):** `ktrdr/config/strategy_migration.py` (NEW)
**Type:** CODING
**Estimated time:** 2 hours

**Task Categories:** Configuration

**Description:**
Create migration logic to convert v2 strategy format to v3.

**Implementation Notes:**

Migration rules (from ARCHITECTURE.md lines 617-624):
1. Convert `indicators` list to dict (key = existing `feature_id`)
2. Add `indicator` field to each fuzzy_set (value = matching indicator key)
3. Generate `nn_inputs` from `training_data.timeframes` × fuzzy_sets
4. Remove deprecated fields: `feature_id` from indicators

```python
def migrate_v2_to_v3(v2_config: dict) -> dict:
    """
    Migrate v2 strategy config to v3 format.

    Args:
        v2_config: Raw dict from v2 YAML

    Returns:
        v3-compatible dict
    """
    v3_config = v2_config.copy()

    # 1. Convert indicators list to dict
    if isinstance(v2_config.get('indicators'), list):
        indicators_dict = {}
        for ind in v2_config['indicators']:
            # feature_id becomes the key
            ind_id = ind.get('feature_id', ind.get('name'))
            indicators_dict[ind_id] = {
                'type': ind['name'],
                **{k: v for k, v in ind.items()
                   if k not in ('name', 'feature_id')}
            }
        v3_config['indicators'] = indicators_dict

    # 2. Add indicator field to fuzzy_sets
    if 'fuzzy_sets' in v3_config:
        for fs_id, fs_def in v3_config['fuzzy_sets'].items():
            if 'indicator' not in fs_def:
                # In v2, fuzzy_set key matches indicator feature_id
                fs_def['indicator'] = fs_id

    # 3. Generate nn_inputs
    if 'nn_inputs' not in v3_config:
        timeframes = v3_config.get('training_data', {}).get('timeframes', {})
        tf_list = timeframes.get('list', ['1h'])

        nn_inputs = []
        for fs_id in v3_config.get('fuzzy_sets', {}).keys():
            nn_inputs.append({
                'fuzzy_set': fs_id,
                'timeframes': 'all'  # Conservative: apply to all TFs
            })
        v3_config['nn_inputs'] = nn_inputs

    # 4. Update version
    v3_config['version'] = '3.0'

    return v3_config


def validate_migration(original: dict, migrated: dict) -> list[str]:
    """
    Validate migration preserved expected behavior.

    Returns:
        List of warnings/issues found
    """
    issues = []

    # Check indicator count preserved
    orig_count = len(original.get('indicators', []))
    migrated_count = len(migrated.get('indicators', {}))
    if orig_count != migrated_count:
        issues.append(
            f"Indicator count changed: {orig_count} -> {migrated_count}"
        )

    # Check fuzzy set count preserved
    orig_fs = len(original.get('fuzzy_sets', {}))
    migrated_fs = len(migrated.get('fuzzy_sets', {}))
    if orig_fs != migrated_fs:
        issues.append(
            f"Fuzzy set count changed: {orig_fs} -> {migrated_fs}"
        )

    return issues
```

**Testing Requirements:**

*Unit Tests:* `tests/unit/config/test_strategy_migration.py`
- [ ] Converts indicator list to dict correctly
- [ ] Adds indicator field to fuzzy sets
- [ ] Generates nn_inputs when missing
- [ ] Preserves all indicator parameters
- [ ] Updates version to "3.0"
- [ ] Handles edge cases (empty fuzzy_sets, etc.)

*Smoke Test:*
```bash
uv run python -c "
from ktrdr.config.strategy_migration import migrate_v2_to_v3

v2 = {
    'name': 'test',
    'indicators': [
        {'name': 'rsi', 'feature_id': 'rsi_14', 'period': 14}
    ],
    'fuzzy_sets': {
        'rsi_14': {'oversold': {'type': 'triangular', 'parameters': [0, 20, 35]}}
    },
    'training_data': {'timeframes': {'list': ['1h']}},
}

v3 = migrate_v2_to_v3(v2)
assert v3['version'] == '3.0'
assert 'rsi_14' in v3['indicators']
assert v3['fuzzy_sets']['rsi_14']['indicator'] == 'rsi_14'
assert len(v3['nn_inputs']) > 0
print('Migration logic: OK')
"
```

**Acceptance Criteria:**
- [ ] Matches migration rules in ARCHITECTURE.md
- [ ] Preserves all meaningful config
- [ ] Unit tests pass

---

### Task 6.2: Add CLI `strategy migrate` Command

**File(s):** `ktrdr/cli/strategy_commands.py`
**Type:** CODING
**Estimated time:** 1.5 hours

**Task Categories:** API Endpoint

**Description:**
Add `ktrdr strategy migrate` command to convert v2 strategies to v3.

**Implementation Notes:**

```python
@strategy.command()
@click.argument('path', type=click.Path(exists=True))
@click.option('--output', '-o', type=click.Path(),
              help='Output path (default: overwrite in place)')
@click.option('--backup', is_flag=True,
              help='Create .bak backup before overwriting')
@click.option('--dry-run', is_flag=True,
              help='Show what would change without writing')
def migrate(path: str, output: str, backup: bool, dry_run: bool):
    """Migrate v2 strategy to v3 format."""
    input_path = Path(path)

    # Handle directory or file
    if input_path.is_dir():
        files = list(input_path.glob('*.yaml')) + list(input_path.glob('*.yml'))
    else:
        files = [input_path]

    for file_path in files:
        click.echo(f"\nProcessing: {file_path}")

        with open(file_path) as f:
            original = yaml.safe_load(f)

        # Check if already v3
        if (isinstance(original.get('indicators'), dict) and
            'nn_inputs' in original):
            click.echo("  Already v3 format, skipping")
            continue

        # Migrate
        migrated = migrate_v2_to_v3(original)

        # Validate migration
        issues = validate_migration(original, migrated)
        for issue in issues:
            click.echo(f"  Warning: {issue}")

        if dry_run:
            click.echo("  [Dry run] Would migrate to v3")
            # Show diff preview
            click.echo(f"  Indicators: list[{len(original.get('indicators', []))}] "
                      f"-> dict[{len(migrated['indicators'])}]")
            click.echo(f"  NN Inputs: {len(migrated['nn_inputs'])} entries")
            continue

        # Determine output path
        out_path = Path(output) if output else file_path

        # Backup if requested
        if backup and out_path == file_path:
            backup_path = file_path.with_suffix(file_path.suffix + '.bak')
            shutil.copy(file_path, backup_path)
            click.echo(f"  Backup: {backup_path}")

        # Write migrated config
        with open(out_path, 'w') as f:
            yaml.dump(migrated, f, default_flow_style=False, sort_keys=False)

        click.echo(f"  Migrated to: {out_path}")

        # Validate the result
        try:
            loader = StrategyConfigurationLoader()
            loader.load(out_path)
            click.echo("  Validation: PASSED")
        except Exception as e:
            click.echo(f"  Validation: FAILED - {e}", err=True)
```

**Testing Requirements:**

*Unit Tests:* `tests/unit/cli/test_strategy_migrate.py`
- [ ] Single file migration works
- [ ] Directory migration works
- [ ] Backup created when requested
- [ ] Dry-run shows changes without writing
- [ ] Output path option works
- [ ] Already-v3 files skipped

*Smoke Test:*
```bash
ktrdr strategy migrate --help
```

**Acceptance Criteria:**
- [ ] Matches CLI spec in ARCHITECTURE.md lines 614-615
- [ ] Backup option works
- [ ] Dry-run useful for previewing changes
- [ ] Validation runs after migration

---

### Task 6.3: Add CLI `strategy features` Command

**File(s):** `ktrdr/cli/strategy_commands.py`
**Type:** CODING
**Estimated time:** 1 hour

**Task Categories:** API Endpoint

**Description:**
Add `ktrdr strategy features` command to display resolved NN input features.

**Implementation Notes:**

```python
@strategy.command()
@click.argument('path', type=click.Path(exists=True))
@click.option('--group-by', type=click.Choice(['timeframe', 'fuzzy_set', 'none']),
              default='none', help='Group features by attribute')
def features(path: str, group_by: str):
    """List generated NN input features for a strategy."""
    loader = StrategyConfigurationLoader()
    config = loader.load(Path(path))

    resolver = FeatureResolver()
    resolved = resolver.resolve(config)

    click.echo(f"Strategy: {config.name}")
    click.echo(f"Features ({len(resolved)} total):")
    click.echo()

    if group_by == 'none':
        for f in resolved:
            click.echo(f"  {f.feature_id}")

    elif group_by == 'timeframe':
        by_tf = {}
        for f in resolved:
            by_tf.setdefault(f.timeframe, []).append(f)
        for tf in sorted(by_tf.keys()):
            click.echo(f"  [{tf}]")
            for f in by_tf[tf]:
                click.echo(f"    {f.fuzzy_set_id}_{f.membership_name}")
            click.echo()

    elif group_by == 'fuzzy_set':
        by_fs = {}
        for f in resolved:
            by_fs.setdefault(f.fuzzy_set_id, []).append(f)
        for fs_id in by_fs.keys():
            click.echo(f"  [{fs_id}] -> {config.fuzzy_sets[fs_id].indicator}")
            for f in by_fs[fs_id]:
                click.echo(f"    {f.timeframe}_{f.membership_name}")
            click.echo()
```

**Testing Requirements:**

*Smoke Test:*
```bash
ktrdr strategy features strategies/v3_test_example.yaml
ktrdr strategy features strategies/v3_test_example.yaml --group-by timeframe
ktrdr strategy features strategies/v3_test_example.yaml --group-by fuzzy_set
```

**Acceptance Criteria:**
- [ ] Matches CLI spec in ARCHITECTURE.md lines 639-657
- [ ] Grouping options work correctly
- [ ] Output clear and readable

---

### Task 6.4: Update Strategy Commands Help Text

**File(s):** `ktrdr/cli/strategy_commands.py`
**Type:** CODING
**Estimated time:** 30 min

**Task Categories:** Configuration

**Description:**
Update help text for all strategy commands to reflect v3 focus.

**Implementation Notes:**

```python
@click.group()
def strategy():
    """
    Manage trading strategies (v3 format).

    Commands for validating, migrating, and inspecting strategies.
    All commands expect v3 format unless otherwise noted.

    Examples:
        ktrdr strategy validate my_strategy.yaml
        ktrdr strategy migrate old_v2_strategy.yaml --backup
        ktrdr strategy features my_strategy.yaml --group-by timeframe
    """
    pass
```

**Acceptance Criteria:**
- [ ] Help text mentions v3
- [ ] Examples are accurate
- [ ] All commands documented

---

## E2E Test Scenario

**Purpose:** Prove migration and feature listing work
**Duration:** ~5 seconds
**Prerequisites:** M5 complete, v2 strategy exists for testing

### Test Steps

```bash
#!/bin/bash
# M6 E2E Test: CLI & Migration Tools

set -e

echo "=== M6 E2E Test: CLI & Migration Tools ==="

# Create a v2-style strategy for testing
echo "Creating v2 test strategy..."
cat > /tmp/v2_test_strategy.yaml << 'EOF'
name: "v2_test"
version: "2.0"

training_data:
  symbols:
    mode: single_symbol
    list: [EURUSD]
  timeframes:
    mode: multi_timeframe
    list: [5m, 1h]
    base_timeframe: 1h
  history_required: 100

indicators:
  - name: rsi
    feature_id: rsi_14
    period: 14
  - name: bbands
    feature_id: bbands_20_2
    period: 20
    multiplier: 2.0

fuzzy_sets:
  rsi_14:
    oversold:
      type: triangular
      parameters: [0, 20, 35]
    overbought:
      type: triangular
      parameters: [65, 80, 100]

model:
  type: mlp
  architecture:
    hidden_layers: [64, 32]

decisions:
  output_format: classification

training:
  method: supervised
  labels:
    source: zigzag
EOF

# Test 1: Dry-run migration
echo "Test 1: Dry-run migration..."
ktrdr strategy migrate /tmp/v2_test_strategy.yaml --dry-run
echo "Test 1: PASS"

# Test 2: Actual migration with backup
echo "Test 2: Migration with backup..."
ktrdr strategy migrate /tmp/v2_test_strategy.yaml --backup --output /tmp/v3_migrated.yaml

# Verify backup created
if [ -f "/tmp/v2_test_strategy.yaml.bak" ]; then
    echo "  Backup created: OK"
else
    # Backup only created when overwriting in place
    echo "  (No backup needed - wrote to different file)"
fi

# Verify migrated file is v3
if grep -q "nn_inputs:" /tmp/v3_migrated.yaml; then
    echo "  Has nn_inputs: OK"
else
    echo "FAIL: Migrated file missing nn_inputs"
    exit 1
fi

echo "Test 2: PASS"

# Test 3: Validate migrated strategy
echo "Test 3: Validate migrated strategy..."
ktrdr strategy validate /tmp/v3_migrated.yaml
echo "Test 3: PASS"

# Test 4: List features
echo "Test 4: List features..."
OUTPUT=$(ktrdr strategy features /tmp/v3_migrated.yaml)
echo "$OUTPUT"

echo "$OUTPUT" | grep -q "5m_rsi_14_oversold" || { echo "FAIL: Missing expected feature"; exit 1; }
echo "Test 4: PASS"

# Test 5: Features grouped by timeframe
echo "Test 5: Features grouped by timeframe..."
ktrdr strategy features /tmp/v3_migrated.yaml --group-by timeframe
echo "Test 5: PASS"

# Cleanup
rm -f /tmp/v2_test_strategy.yaml /tmp/v2_test_strategy.yaml.bak /tmp/v3_migrated.yaml

echo ""
echo "=== M6 E2E Test: ALL PASSED ==="
```

### Success Criteria

- [ ] Dry-run shows migration preview
- [ ] Migration produces valid v3 file
- [ ] `nn_inputs` section generated
- [ ] Validation passes on migrated file
- [ ] Feature listing works with grouping options

---

## Completion Checklist

- [ ] Task 6.1: Migration logic created
- [ ] Task 6.2: `strategy migrate` command works
- [ ] Task 6.3: `strategy features` command works
- [ ] Task 6.4: Help text updated
- [ ] All unit tests pass: `make test-unit`
- [ ] E2E test script passes
- [ ] M1-M5 E2E tests still pass
- [ ] Quality gates pass: `make quality`
- [ ] Code reviewed and merged
