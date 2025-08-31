# TASK: Eliminate Periodic Save Duplication Catastrophe

**OBJECTIVE**: Complete architectural refactoring to eliminate massive periodic save code duplication across 6+ layers, restore proper separation of concerns, and consolidate save functionality into a single source of truth within DataManager's domain.

**BRANCH**: `feature/eliminate-periodic-save-duplication` (from `feature/continue-async-architecture-implementation`)

**CONTEXT**: The periodic save functionality has catastrophically violated separation of concerns by bleeding through CLI → API Client → API Endpoint → API Service → DataManager → DataFetcher layers. We have 30+ lines of identical code in both SegmentManager and DataFetcher, 9+ parameter definitions cascading through the entire stack, and inconsistent defaults (API: 2.0 minutes, components: 0.5 minutes). Periodic saving is purely DataManager's internal concern and should never have escaped its boundaries.

**TECHNICAL IMPLEMENTATION**:

1. **API Layer Cleanup** (`ktrdr/api/models/data.py`, `ktrdr/api/endpoints/data.py`, `ktrdr/api/services/data_service.py`):
   ```python
   # BEFORE: Polluted with save concerns
   class LoadDataRequest(BaseModel):
       periodic_save_minutes: float = Field(default=2.0, ...)  # DELETE THIS
       
   # AFTER: Clean interface
   class LoadDataRequest(BaseModel):
       symbol: str = Field(..., description="Trading symbol")
       timeframe: str = Field(..., description="Data timeframe")
       # DataManager handles saves internally - no external parameter needed
   ```

2. **CLI Layer Purification** (`ktrdr/cli/data_commands.py`):
   ```python
   # BEFORE: CLI knows about internal save details
   @click.option("--periodic-save-minutes", default=2.0, ...)  # DELETE THIS
   
   # AFTER: CLI focused on user intent only
   @click.command()
   def load_data(symbol: str, timeframe: str):
       """Load data - automatic 30-second saves, no configuration needed"""
   ```

3. **DataFetcher Component Restoration** (`ktrdr/data/components/data_fetcher.py`):
   ```python
   # REMOVE 30+ lines of duplicated periodic save logic
   async def fetch_segments_async(
       self,
       segments: list[tuple[datetime, datetime]],
       # REMOVE: periodic_save_callback parameter (DUPLICATION)
       # REMOVE: periodic_save_minutes parameter (DUPLICATION)  
   ) -> list[pd.DataFrame]:
       # REMOVE: Lines 188-251 - periodic save tracking/logic
       # RESTORE: Pure HTTP session persistence role
       for segment in segments:
           result = await self.fetch_single_segment(...)
           # NO SAVE LOGIC - just return data
   ```

4. **DataManager Consolidation** (`ktrdr/data/data_manager.py`):
   ```python
   # REMOVE from all external method signatures
   async def load_data(
       self,
       symbol: str,
       timeframe: str,
       # REMOVE: periodic_save_minutes=0.5  (9 occurrences to remove)
   ):
       # Internal constant - not exposed externally
       INTERNAL_SAVE_INTERVAL = 0.5  
       
       # Route to SegmentManager ONLY (eliminate DataFetcher path)
       return await self._load_with_segment_manager_only(...)
   ```

**TDD APPROACH**:
```python
class TestPeriodicSaveConsolidation:
    async def test_api_no_periodic_save_parameter(self):
        """API should reject periodic_save_minutes - not our concern"""
        request = {"symbol": "AAPL", "timeframe": "1h", "periodic_save_minutes": 2.0}
        response = await client.post("/data/load", json=request)
        assert response.status_code == 422  # ValidationError
        
    async def test_datafetcher_pure_fetching_role(self):
        """DataFetcher should only handle HTTP sessions - no save logic"""
        fetcher = DataFetcher()
        
        # Should not accept save parameters at all
        with pytest.raises(TypeError):
            await fetcher.fetch_segments_async(
                segments=[...], 
                periodic_save_callback=mock_callback  # Should fail
            )
            
    async def test_datamanager_internal_save_handling(self):
        """DataManager should handle saves internally via SegmentManager"""
        dm = DataManager()
        
        # External interface - no save parameters
        await dm.load_data("AAPL", "1h")
        
        # Internal implementation should have triggered saves
        assert dm._last_save_occurred_within(seconds=30)
        
    async def test_segmentmanager_remains_authoritative(self):
        """SegmentManager should be the ONLY place with save logic"""
        # This is our single source of truth
        sm = SegmentManager()
        save_calls = []
        
        await sm.fetch_segments_with_resilience(
            ...,
            periodic_save_callback=lambda data: save_calls.append(len(data))
        )
        
        assert len(save_calls) > 0  # Saves occurred
        
    async def test_no_code_duplication_remains(self):
        """Verify no periodic save code exists in DataFetcher"""
        fetcher_source = inspect.getsource(DataFetcher.fetch_segments_async)
        
        # Should not contain save-related code
        assert "periodic_save" not in fetcher_source
        assert "save_interval" not in fetcher_source  
        assert "last_save_time" not in fetcher_source
        
    async def test_backwards_compatibility_maintained(self):
        """Existing CLI/API workflows should work identically"""
        # CLI should work without periodic save options
        result = subprocess.run(["ktrdr", "data", "load", "AAPL", "1h"])
        assert result.returncode == 0
        
        # API should work with simplified interface
        response = await client.post("/data/load", 
                                   json={"symbol": "AAPL", "timeframe": "1h"})
        assert response.status_code == 200
        
        # Save behavior should be identical to before
        # (30-second interval, cancellation safety, etc.)
```

**DUPLICATION ELIMINATION SCENARIOS**:

1. **Parameter Cascade Removal**:
   - Remove `periodic_save_minutes` from 9+ method signatures
   - Clean up validation code in API models
   - Remove CLI options and help text
   - Update service layer method calls

2. **Identical Code Block Deletion**:
   - Delete lines 188-251 from DataFetcher (30+ lines)
   - Preserve lines 290-381 in SegmentManager (single source)
   - Remove duplicate test cases in DataFetcher tests
   - Update imports (remove `time` from DataFetcher)

3. **Architecture Boundary Restoration**:
   - External layers: Complete ignorance of save intervals
   - DataManager: Internal save strategy management  
   - SegmentManager: Authoritative save implementation
   - DataFetcher: Pure HTTP session component

4. **Interface Simplification Testing**:
   - CLI commands lose save-related options
   - API models remove save fields
   - Service methods remove save parameters
   - Component interfaces simplified and focused

**ACCEPTANCE CRITERIA**:
- [ ] Zero code duplication between SegmentManager and DataFetcher
- [ ] Zero `periodic_save_minutes` parameters in external interfaces (CLI/API/Services)
- [ ] DataFetcher contains zero save-related logic (pure HTTP component)
- [ ] SegmentManager remains single authoritative save implementation
- [ ] All existing save behavior preserved (30-second interval, cancellation safety)
- [ ] All 109+ component tests pass with simplified interfaces
- [ ] Integration tests confirm identical save behavior from user perspective
- [ ] Performance improved (reduced parameter passing overhead)
- [ ] Memory usage stable or improved (less object parameter bloat)

**VALIDATION REQUIREMENTS**:
- End-to-end data loading with automatic 30-second saves confirmed
- Cancellation testing confirms data preservation unchanged
- Load testing with multiple symbols shows consistent save behavior  
- Code review confirms complete duplication elimination
- Architecture review confirms proper separation of concerns restored

**QUALITY ASSURANCE**:
- PyTest: All component tests pass with new clean interfaces
- MyPy: Type checking passes (simplified parameter signatures)
- Black/Ruff: Code quality maintained with reduced complexity
- Integration testing: User workflows unchanged despite internal cleanup
- Performance testing: Equal or better performance (less parameter overhead)
- Memory profiling: Stable usage with reduced object parameter bloat

**PR REQUIREMENTS**:
- Architecture diagram: Before (6-layer cascade) vs After (clean boundaries)
- Duplication metrics: Lines eliminated, parameters removed, interfaces simplified
- Test coverage report: All functionality preserved with cleaner codebase
- Performance comparison: Should show slight improvement from reduced overhead
- User impact assessment: Zero user-visible changes, identical save behavior
- Code quality metrics: Reduced complexity, improved maintainability scores

This task eliminates catastrophic architectural debt while maintaining 100% functional compatibility - users get identical save behavior through a clean, maintainable implementation.