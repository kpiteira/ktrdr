# KTRDR Scripts

Utility scripts for KTRDR development and operations.

## Training Mode Switching

### switch-training-mode.sh

Easily switch between local (CPU) and host service (GPU) training modes.

**Usage:**

```bash
# Switch to local training mode (CPU in Docker)
./scripts/switch-training-mode.sh local

# Switch to host service training mode (GPU if available)
./scripts/switch-training-mode.sh host
```

**What it does:**

1. Sets the appropriate `USE_TRAINING_HOST_SERVICE` environment variable
2. Recreates the backend container with `docker-compose up -d` (not `restart`!)
3. New environment variables are applied immediately
4. Shows confirmation and log viewing instructions

**Important Notes:**

- ⚠️ **Must use `docker-compose up -d`**, not `restart`
  - `restart` keeps old environment variables
  - `up -d` recreates container with new config

- The backend container restart is fast (~3-5 seconds)
- Other services (IB host, training host, Redis) are NOT restarted

**Verify Mode:**

```bash
# View logs to confirm current mode
docker-compose -f docker/docker-compose.yml logs backend | grep "TRAINING MODE"
```

**Expected Output:**

```
# Host Service Mode:
🚀 TRAINING MODE: HOST SERVICE
   URL: http://host.docker.internal:5002
   GPU Training: Available (if host service has GPU)

# Local Mode:
💻 TRAINING MODE: LOCAL (Docker Container)
   GPU Training: Not available in Docker
   CPU Training: Available
```

## Manual Mode Switching (Alternative)

If you prefer not to use the script:

```bash
# Export the variable
export USE_TRAINING_HOST_SERVICE=false  # or true

# Recreate container (must use 'up -d', not 'restart')
cd docker && docker-compose up -d backend

# View logs
docker-compose logs -f backend | grep "TRAINING MODE"
```

## Why docker-compose restart Doesn't Work

```bash
# ❌ This does NOT work - restart keeps old env vars
docker-compose restart backend

# ✅ This works - up -d recreates with new env vars
docker-compose up -d backend
```

The `restart` command only restarts the container process, keeping the existing container configuration including environment variables. The `up -d` command recreates the container with the current docker-compose.yml configuration and environment.
