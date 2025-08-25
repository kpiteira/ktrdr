# ProgressManager Integration Plan

## Goal: Clean DataManager Integration with Enhanced Progress Tracking

### Enhanced ProgressManager API
```python
class ProgressManager:
    def start_operation(self, total_steps: int, operation_name: str, expected_items: Optional[int] = None):
        """Start operation with optional item tracking"""
        
    def start_step(self, step_name: str, step_number: int, expected_items: Optional[int] = None):
        """Start a step with optional item count for this step"""
        
    def update_step_progress(
        self, 
        current: int, 
        total: int, 
        items_processed: int = 0,
        detail: str = ""
    ):
        """Update sub-step progress with item count"""
```

### DataManager Step Mapping (10 steps total)
1. **Validate symbol with IB** (2%) - Metadata lookup, symbol verification
2. **Validate request range** (4%) - Check against head timestamp data  
3. **Load existing local data** (6%) - Read from CSV files
4. **Analyze data gaps** (8%) - Intelligent gap detection with trading calendar
5. **Create IB-compliant segments** (10%) - Split gaps into fetchable chunks
6. **Fetch segments from IB** (10% → 96%) - The big phase with detailed sub-progress
7. **Merge all data sources** (80%) - Combine existing + fetched data chronologically  
8. **Save enhanced dataset** (98%) - Write merged data back to CSV
9. **Data loading completed** (100%) - Final cleanup
10. **Validate data quality** (98%) - Data integrity checks and repairs

### Domain Examples

**DataManager:**
```python
progress_manager.start_operation(total_steps=10, operation_name="load_AAPL_1h", expected_items=1632)
progress_manager.start_step("Fetch segments from IB", step_number=6, expected_items=1632)
progress_manager.update_step_progress(
    current=3, total=13, items_processed=456,
    detail="Segment 3/13: 2020-01-15 10:00 to 2020-01-20 15:00"
)
```

**Training (future):**
```python
progress_manager.start_operation(total_steps=100, operation_name="train_model", expected_items=50000)
progress_manager.start_step("Epoch 5", step_number=5, expected_items=50000)
progress_manager.update_step_progress(
    current=25, total=100, items_processed=12500,
    detail="Batch 25/100: loss=0.0234"
)
```

### Expected User Experience
```
Fetch segments from IB: Segment 3/13 (456/1632 bars) ━━━━╺━━━━━━━━━━━━  23% 0:00:05
```