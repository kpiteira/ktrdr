# Troubleshooting: Environment

Common environment issues during E2E testing.

---

## Docker Daemon Issues

**Symptom:**
- `Cannot connect to Docker daemon`
- `docker compose` commands fail
- Containers don't start

**Cause:** Docker daemon not running or permissions issue.

**Diagnosis Steps:**
```bash
# Check Docker daemon status
docker info

# Check if Docker socket exists
ls -la /var/run/docker.sock
```

**Solution:**
1. Start Docker Desktop (macOS/Windows)
2. Or start daemon: `sudo systemctl start docker` (Linux)
3. Check permissions: `sudo usermod -aG docker $USER`

**Prevention:**
- Ensure Docker Desktop is running before starting dev work
- Add Docker startup to login items

---

## Sandbox Port Confusion

**Symptom:**
- API calls to port 8000 fail when in sandbox
- Tests pass locally but fail in sandbox
- "Connection refused" errors

**Cause:** Using hardcoded port 8000 instead of sandbox port.

**Diagnosis Steps:**
```bash
# Check if in sandbox
ls .env.sandbox && echo "IN SANDBOX" || echo "NOT SANDBOX"

# Get correct port
[ -f .env.sandbox ] && source .env.sandbox && echo "Port: $KTRDR_API_PORT" || echo "Port: 8000"
```

**Solution:**
1. Always use `${KTRDR_API_PORT:-8000}` in commands
2. Source `.env.sandbox` before running tests
3. Use `uv run ktrdr sandbox status` to see all ports

**Prevention:**
- Run `uv run ktrdr sandbox status` at start of session
- Use template variable `${KTRDR_API_PORT:-8000}` not hardcoded 8000

---

## Container Resource Exhaustion

**Symptom:**
- Containers restart frequently
- OOM (Out of Memory) kills
- Tests timeout unexpectedly

**Cause:** Docker resource limits too low.

**Diagnosis Steps:**
```bash
# Check container stats
docker stats --no-stream

# Check for OOM kills
docker compose logs backend 2>&1 | grep -i "killed\|oom"
```

**Solution:**
1. Increase Docker memory allocation (Docker Desktop → Settings → Resources)
2. Reduce parallel workers
3. Close other memory-intensive apps

---

## Port Already in Use

**Symptom:**
- `port is already allocated`
- Container fails to start
- Bind errors

**Cause:** Another process using the same port.

**Diagnosis Steps:**
```bash
# Check what's using port 8000
lsof -i :8000

# For sandbox ports
lsof -i :8001
lsof -i :5010
```

**Solution:**
1. Stop conflicting process: `kill <PID>`
2. Use different sandbox slot
3. Check for zombie containers: `docker ps -a`

**Prevention:**
- Use `uv run ktrdr sandbox status` to check port availability
- Clean up old containers: `docker compose down`
