# Troubleshooting: Common

General issues that affect multiple test types.

---

## API Schema Differences

**Symptom:**
- Expected field not in response
- JSON path doesn't work
- Test passes but gets wrong values

**Cause:** API response schema changed or documented incorrectly.

**Diagnosis Steps:**
```bash
# Get full response structure
curl -s "http://localhost:${KTRDR_API_PORT:-8000}/api/v1/operations/op_xxx" | jq 'keys'

# Check specific field path
curl -s "http://localhost:${KTRDR_API_PORT:-8000}/api/v1/operations/op_xxx" | jq '.data | keys'
```

**Solution:**
1. Update test to use correct field path
2. Check API docs: `/api/v1/docs`
3. Report if API should be fixed

**Common Differences:**
- `row_count` vs `point_count`
- `file_exists` may be missing
- Nested vs flat response structures

---

## Operation Not Found (After Restart)

**Symptom:**
- 404 for operation that was just created
- Operation ID exists but can't be queried

**Cause:** Operations are in-memory, lost on restart.

**Diagnosis Steps:**
```bash
# Check if backend restarted
docker compose logs backend --since 5m | grep -i "starting\|ready"
```

**Solution:**
1. Re-run the test to create new operation
2. Note: Operations persist in database after completion
3. Only in-progress operations may be lost on restart

---

## Timeout During Test

**Symptom:**
- curl hangs or times out
- Operation never completes
- No response from API

**Cause:** Backend overloaded, deadlock, or network issue.

**Diagnosis Steps:**
```bash
# Check backend health
curl -s -m 5 "http://localhost:${KTRDR_API_PORT:-8000}/api/v1/health"

# Check container status
docker compose ps

# Check for errors
docker compose logs backend --since 5m | grep -i "error\|timeout"
```

**Solution:**
1. Restart backend: `docker compose restart backend`
2. Check resource usage: `docker stats`
3. Use smaller test dataset

---

## Permission Denied

**Symptom:**
- "Permission denied" errors
- Can't write to data/models directory
- Docker volume access issues

**Cause:** File ownership mismatch between container and host.

**Diagnosis Steps:**
```bash
# Check file ownership
ls -la data/
ls -la models/

# Check container user
docker compose exec backend id
```

**Solution:**
1. Fix ownership: `sudo chown -R $USER:$USER data/ models/`
2. Check Docker volume permissions in compose file
3. Use shared directory with proper permissions

---

## Test Works Locally But Fails in CI

**Symptom:**
- Test passes on dev machine
- Fails in CI/CD pipeline
- Different behavior in different environments

**Cause:** Environment differences, timing issues, or missing dependencies.

**Solution:**
1. Check CI environment variables
2. Add explicit waits for async operations
3. Use `--ci` flag if available
4. Ensure same Docker versions

**Prevention:**
- Always test in sandbox (simulates clean environment)
- Don't rely on local-only data or config
