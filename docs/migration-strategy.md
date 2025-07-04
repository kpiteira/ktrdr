# KTRDR Strategy Migration Strategy

## Migration Plan: V1 → V2 Bulk Migration

### **Phase 1: Standardize Version Fields**
1. **Fix version field inconsistencies** across all strategies
2. **Add missing version fields** with appropriate values
3. **Standardize format**: Always use quoted strings (`"1.0"`, `"2.0"`)

### **Phase 2: Bulk Migration to V2**
1. **Migrate all V1 strategies** to V2 format for consistency
2. **Preserve original V1 files** with `.v1` suffix for backup
3. **Update all references** in documentation and code

### **Benefits of Bulk Migration:**
- ✅ **Consistency**: All strategies use same format
- ✅ **Future-proof**: Ready for multi-scope features
- ✅ **Simplified maintenance**: One format to support
- ✅ **Better defaults**: V2 has more robust validation
- ✅ **Enhanced capabilities**: Multi-symbol/timeframe ready

### **Migration Commands:**

```bash
# 1. Standardize version fields
ktrdr strategies standardize-versions strategies/

# 2. Bulk migrate to V2 (with backup)
ktrdr strategies migrate-all strategies/ --backup-suffix .v1

# 3. Validate all migrated strategies
ktrdr strategies validate-all strategies/

# 4. Optional: Clean up old files after verification
ktrdr strategies cleanup-v1-backups strategies/
```

### **Migration Rules:**

#### **Scope Detection Logic:**
```yaml
# Single symbol + single timeframe → symbol_specific
symbols: ["AAPL"]
timeframes: ["1h"]
→ scope: "symbol_specific"

# Multiple symbols + single timeframe → symbol_group  
symbols: ["AAPL", "MSFT", "GOOGL"]
timeframes: ["1h"]
→ scope: "symbol_group"

# Multiple symbols + multiple timeframes → universal
symbols: ["AAPL", "MSFT", "GOOGL"] 
timeframes: ["1h", "4h", "1d"]
→ scope: "universal"
```

#### **Version Progression:**
```yaml
# Current → Target
"1.0" → "2.0"
"1.0.neuro" → "2.0" 
missing → "2.0"
```

### **Rollback Strategy:**
If issues arise, we can quickly rollback:
```bash
# Restore from backups
for file in strategies/*.v1; do
  mv "$file" "${file%.v1}"
done

# Remove failed migrations
rm strategies/*_v2.yaml
```

### **Quality Assurance:**
1. **Automated validation** of all migrated strategies
2. **Regression testing** with existing model training
3. **Manual spot-checks** of complex strategies
4. **Backup verification** before cleanup

### **Timeline:**
- **Phase 1** (Version standardization): 1 hour
- **Phase 2** (Bulk migration): 2 hours  
- **Phase 3** (Validation & testing): 2 hours
- **Total**: Half day effort with full rollback capability