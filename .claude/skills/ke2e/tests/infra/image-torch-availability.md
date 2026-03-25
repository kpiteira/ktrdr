# Test: infra/image-torch-availability

**Purpose:** Validate that each Docker image has the correct torch availability and CUDA status based on its deployment role

**Duration:** ~60s (4 images x ~15s each for container spin-up and check)

**Category:** Infrastructure / Container Optimization (M3)

---

## Pre-Flight Checks

**Required modules:**
- None (this test validates image contents, not running services)

**Test-specific checks:**
- [ ] Docker daemon is running
- [ ] Docker images have been built (see Setup section)

**Pre-flight verification:**
```bash
# Verify Docker is available
docker info > /dev/null 2>&1 && echo "PASS: Docker available" || echo "FAIL: Docker not available"
```

---

## Background

This test validates the M3 Container Optimization milestone: splitting Dockerfiles to create right-sized images for each deployment role.

**Why this matters:**
- Production backend (API-only) saves ~500MB by excluding torch
- Worker images need torch for ML operations
- GPU workers need CUDA-enabled torch
- CPU workers use CPU-only torch (smaller, faster)

**Image Roles:**

| Image | Purpose | Torch Expected | CUDA Expected |
|-------|---------|----------------|---------------|
| ktrdr-backend:prod | API server (orchestration only) | NO | N/A |
| ktrdr-backend:dev | Development with full capabilities | YES | NO (CPU-only) |
| ktrdr-worker-cpu:test | Backtest/training workers (CPU) | YES | NO |
| ktrdr-worker-gpu:test | Training workers (GPU-enabled) | YES | Host-dependent |

---

## Setup

**Build images before testing:**

Images must be built from the project root. If images are not present, build them first.

```bash
# Build all images (run from project root)
docker build -f deploy/docker/Dockerfile.backend -t ktrdr-backend:prod .
docker build -f deploy/docker/Dockerfile.dev -t ktrdr-backend:dev .
docker build -f deploy/docker/Dockerfile.worker-cpu -t ktrdr-worker-cpu:test .
docker build -f deploy/docker/Dockerfile.worker-gpu -t ktrdr-worker-gpu:test .
```

**Verify images exist:**
```bash
docker images --format "{{.Repository}}:{{.Tag}}" | grep -E "^ktrdr-(backend|worker)"
```

**Expected output:**
```
ktrdr-backend:prod
ktrdr-backend:dev
ktrdr-worker-cpu:test
ktrdr-worker-gpu:test
```

---

## Test Data

```json
{
  "images": [
    {
      "name": "ktrdr-backend:prod",
      "dockerfile": "deploy/docker/Dockerfile.backend",
      "torch_expected": false,
      "cuda_expected": null,
      "description": "Production API - no ML dependencies"
    },
    {
      "name": "ktrdr-backend:dev",
      "dockerfile": "deploy/docker/Dockerfile.dev",
      "torch_expected": true,
      "cuda_expected": false,
      "description": "Development - CPU-only torch"
    },
    {
      "name": "ktrdr-worker-cpu:test",
      "dockerfile": "deploy/docker/Dockerfile.worker-cpu",
      "torch_expected": true,
      "cuda_expected": false,
      "description": "CPU worker - CPU-only torch"
    },
    {
      "name": "ktrdr-worker-gpu:test",
      "dockerfile": "deploy/docker/Dockerfile.worker-gpu",
      "torch_expected": true,
      "cuda_expected": "host_dependent",
      "description": "GPU worker - CUDA torch (GPU detection depends on host)"
    }
  ]
}
```

---

## Execution Steps

| Step | Action | Expected Result | Evidence to Capture |
|------|--------|-----------------|---------------------|
| 1 | Check ktrdr-backend:prod | torch import fails with ModuleNotFoundError | error_message, exit_code |
| 2 | Check ktrdr-backend:dev | torch available, cuda=False | torch_version, cuda_available |
| 3 | Check ktrdr-worker-cpu:test | torch available, cuda=False | torch_version, cuda_available |
| 4 | Check ktrdr-worker-gpu:test | torch available (CUDA status host-dependent) | torch_version, cuda_available |

**Detailed Steps:**

### Step 1: Validate ktrdr-backend:prod (No Torch)

**Command:**
```bash
echo "=== Testing ktrdr-backend:prod ==="

# Attempt to import torch - should FAIL with ModuleNotFoundError
RESULT=$(docker run --rm ktrdr-backend:prod python -c "
import sys
try:
    import torch
    print('FAIL: torch should not be available')
    print(f'torch version: {torch.__version__}')
    sys.exit(1)
except ModuleNotFoundError as e:
    print('PASS: torch correctly not installed')
    print(f'Error: {e}')
    sys.exit(0)
except Exception as e:
    print(f'UNEXPECTED: {type(e).__name__}: {e}')
    sys.exit(2)
" 2>&1)

EXIT_CODE=$?
echo "$RESULT"
echo "Exit code: $EXIT_CODE"

if [ $EXIT_CODE -eq 0 ]; then
    echo "RESULT: ktrdr-backend:prod - PASS (torch not installed)"
else
    echo "RESULT: ktrdr-backend:prod - FAIL (torch should not be available)"
fi
```

**Expected:**
- Exit code: 0
- Output contains: "PASS: torch correctly not installed"
- Output contains: "ModuleNotFoundError"

**Evidence to Capture:**
- Full output from container
- Exit code
- Error message confirming ModuleNotFoundError

---

### Step 2: Validate ktrdr-backend:dev (Torch + CPU-only)

**Command:**
```bash
echo "=== Testing ktrdr-backend:dev ==="

RESULT=$(docker run --rm ktrdr-backend:dev python -c "
import sys
try:
    import torch
    version = torch.__version__
    cuda_available = torch.cuda.is_available()

    print(f'torch version: {version}')
    print(f'cuda available: {cuda_available}')

    if cuda_available:
        print('FAIL: CUDA should NOT be available in dev image (CPU-only)')
        sys.exit(1)
    else:
        print('PASS: torch available with CUDA=False (CPU-only as expected)')
        sys.exit(0)
except ModuleNotFoundError as e:
    print(f'FAIL: torch should be installed but got: {e}')
    sys.exit(1)
except Exception as e:
    print(f'UNEXPECTED: {type(e).__name__}: {e}')
    sys.exit(2)
" 2>&1)

EXIT_CODE=$?
echo "$RESULT"
echo "Exit code: $EXIT_CODE"

if [ $EXIT_CODE -eq 0 ]; then
    echo "RESULT: ktrdr-backend:dev - PASS"
else
    echo "RESULT: ktrdr-backend:dev - FAIL"
fi
```

**Expected:**
- Exit code: 0
- Output shows torch version (e.g., "2.x.x+cpu")
- Output shows "cuda available: False"
- Output contains: "PASS: torch available with CUDA=False"

**Evidence to Capture:**
- Torch version string
- CUDA availability status
- Full output from container

---

### Step 3: Validate ktrdr-worker-cpu:test (Torch + CPU-only)

**Command:**
```bash
echo "=== Testing ktrdr-worker-cpu:test ==="

RESULT=$(docker run --rm ktrdr-worker-cpu:test python -c "
import sys
try:
    import torch
    version = torch.__version__
    cuda_available = torch.cuda.is_available()

    print(f'torch version: {version}')
    print(f'cuda available: {cuda_available}')

    if cuda_available:
        print('FAIL: CUDA should NOT be available in CPU worker image')
        sys.exit(1)
    else:
        print('PASS: torch available with CUDA=False (CPU-only as expected)')
        sys.exit(0)
except ModuleNotFoundError as e:
    print(f'FAIL: torch should be installed but got: {e}')
    sys.exit(1)
except Exception as e:
    print(f'UNEXPECTED: {type(e).__name__}: {e}')
    sys.exit(2)
" 2>&1)

EXIT_CODE=$?
echo "$RESULT"
echo "Exit code: $EXIT_CODE"

if [ $EXIT_CODE -eq 0 ]; then
    echo "RESULT: ktrdr-worker-cpu:test - PASS"
else
    echo "RESULT: ktrdr-worker-cpu:test - FAIL"
fi
```

**Expected:**
- Exit code: 0
- Output shows torch version (e.g., "2.x.x+cpu")
- Output shows "cuda available: False"
- Output contains: "PASS: torch available with CUDA=False"

**Evidence to Capture:**
- Torch version string
- CUDA availability status
- Full output from container

---

### Step 4: Validate ktrdr-worker-gpu:test (Torch + CUDA libs)

**Command:**
```bash
echo "=== Testing ktrdr-worker-gpu:test ==="

# Note: CUDA availability depends on host GPU + nvidia-container-toolkit
# This test validates torch is installed; CUDA detection is informational

RESULT=$(docker run --rm ktrdr-worker-gpu:test python -c "
import sys
try:
    import torch
    version = torch.__version__
    cuda_available = torch.cuda.is_available()
    cuda_version = torch.version.cuda if hasattr(torch.version, 'cuda') else 'N/A'

    print(f'torch version: {version}')
    print(f'cuda built-in version: {cuda_version}')
    print(f'cuda runtime available: {cuda_available}')

    # GPU image should have CUDA libraries even if no GPU present
    if 'cu' in version or cuda_version != 'N/A':
        print('PASS: torch with CUDA support is installed')
        print(f'Note: CUDA runtime availability ({cuda_available}) depends on host GPU')
        sys.exit(0)
    else:
        # Check if it's explicitly a CPU build
        if '+cpu' in version:
            print('FAIL: GPU image has CPU-only torch')
            sys.exit(1)
        else:
            # Could be a default build without version suffix
            print('WARN: torch version string unclear, checking CUDA build...')
            # If torch.version.cuda is set, it was built with CUDA
            if cuda_version and cuda_version != 'N/A':
                print('PASS: CUDA build confirmed')
                sys.exit(0)
            else:
                print('FAIL: Cannot confirm CUDA build')
                sys.exit(1)
except ModuleNotFoundError as e:
    print(f'FAIL: torch should be installed but got: {e}')
    sys.exit(1)
except Exception as e:
    print(f'UNEXPECTED: {type(e).__name__}: {e}')
    sys.exit(2)
" 2>&1)

EXIT_CODE=$?
echo "$RESULT"
echo "Exit code: $EXIT_CODE"

if [ $EXIT_CODE -eq 0 ]; then
    echo "RESULT: ktrdr-worker-gpu:test - PASS"
else
    echo "RESULT: ktrdr-worker-gpu:test - FAIL"
fi
```

**Expected:**
- Exit code: 0
- Output shows torch version with CUDA suffix (e.g., "2.x.x+cu126")
- Output shows cuda built-in version (e.g., "12.6")
- cuda runtime available: depends on host (True if GPU present, False otherwise)
- Output contains: "PASS: torch with CUDA support is installed"

**Evidence to Capture:**
- Torch version string (should contain "cu" for CUDA build)
- Built-in CUDA version
- Runtime CUDA availability
- Full output from container

---

### Step 5: Summary Report

**Command:**
```bash
echo "=== SUMMARY: Image Torch Availability ==="
echo ""
echo "| Image | Torch | CUDA | Expected | Actual |"
echo "|-------|-------|------|----------|--------|"

# ktrdr-backend:prod
PROD_RESULT=$(docker run --rm ktrdr-backend:prod python -c "
import sys
try:
    import torch
    print('YES|N/A|FAIL')
    sys.exit(1)
except ModuleNotFoundError:
    print('NO|N/A|PASS')
    sys.exit(0)
" 2>&1 | tail -1)
echo "| ktrdr-backend:prod | ${PROD_RESULT} |"

# ktrdr-backend:dev
DEV_RESULT=$(docker run --rm ktrdr-backend:dev python -c "
import sys
try:
    import torch
    cuda = torch.cuda.is_available()
    if not cuda:
        print(f'YES|NO|PASS')
    else:
        print(f'YES|YES|FAIL')
except ModuleNotFoundError:
    print('NO|N/A|FAIL')
" 2>&1 | tail -1)
echo "| ktrdr-backend:dev | ${DEV_RESULT} |"

# ktrdr-worker-cpu:test
CPU_RESULT=$(docker run --rm ktrdr-worker-cpu:test python -c "
import sys
try:
    import torch
    cuda = torch.cuda.is_available()
    if not cuda:
        print(f'YES|NO|PASS')
    else:
        print(f'YES|YES|FAIL')
except ModuleNotFoundError:
    print('NO|N/A|FAIL')
" 2>&1 | tail -1)
echo "| ktrdr-worker-cpu:test | ${CPU_RESULT} |"

# ktrdr-worker-gpu:test
GPU_RESULT=$(docker run --rm ktrdr-worker-gpu:test python -c "
import sys
try:
    import torch
    cuda = torch.cuda.is_available()
    cuda_ver = torch.version.cuda or 'N/A'
    # Check if built with CUDA
    if 'cu' in torch.__version__ or (cuda_ver and cuda_ver != 'N/A'):
        print(f'YES|{cuda_ver}|PASS')
    else:
        print(f'YES|NO|FAIL')
except ModuleNotFoundError:
    print('NO|N/A|FAIL')
" 2>&1 | tail -1)
echo "| ktrdr-worker-gpu:test | ${GPU_RESULT} |"

echo ""
echo "=== Test Complete ==="
```

**Expected output:**
```
=== SUMMARY: Image Torch Availability ===

| Image | Torch | CUDA | Expected | Actual |
|-------|-------|------|----------|--------|
| ktrdr-backend:prod | NO|N/A|PASS |
| ktrdr-backend:dev | YES|NO|PASS |
| ktrdr-worker-cpu:test | YES|NO|PASS |
| ktrdr-worker-gpu:test | YES|12.6|PASS |

=== Test Complete ===
```

---

## Success Criteria

All must pass for test to pass:

- [ ] ktrdr-backend:prod: `import torch` raises ModuleNotFoundError
- [ ] ktrdr-backend:dev: torch imports successfully
- [ ] ktrdr-backend:dev: `torch.cuda.is_available()` returns False
- [ ] ktrdr-worker-cpu:test: torch imports successfully
- [ ] ktrdr-worker-cpu:test: `torch.cuda.is_available()` returns False
- [ ] ktrdr-worker-gpu:test: torch imports successfully
- [ ] ktrdr-worker-gpu:test: torch version includes CUDA suffix OR `torch.version.cuda` is set

---

## Sanity Checks

Catch false positives:

| Check | Threshold | Failure Indicates |
|-------|-----------|-------------------|
| Container starts | Fails to start | Image build broken |
| Python runs | Python not found | Image build broken |
| Test duration > 10s | < 10s fails | Test skipped/cached |
| torch.version valid | Empty or error | Partial torch install |
| backend:prod size < 1GB | > 1.5GB fails | ML deps accidentally included |

---

## Failure Categorization

| Failure Type | Category | Suggested Action |
|--------------|----------|------------------|
| Image not found | ENVIRONMENT | Run build commands in Setup section |
| torch in backend:prod | CODE_BUG | Check Dockerfile.backend - should use `uv sync` without `--extra ml` |
| No torch in worker images | CODE_BUG | Check Dockerfile.worker-* - should use `--extra ml` |
| CUDA in CPU images | CODE_BUG | Check CPU Dockerfiles inject CPU-only PyTorch source |
| No CUDA in GPU image | CODE_BUG | Check Dockerfile.worker-gpu injects CUDA PyTorch source |
| Container crash | ENVIRONMENT | Check Docker resources, run `docker logs` |

---

## Cleanup

```bash
# Optional: Remove test containers if any failed to clean up
docker ps -a --filter "ancestor=ktrdr-backend:prod" -q | xargs -r docker rm -f
docker ps -a --filter "ancestor=ktrdr-backend:dev" -q | xargs -r docker rm -f
docker ps -a --filter "ancestor=ktrdr-worker-cpu:test" -q | xargs -r docker rm -f
docker ps -a --filter "ancestor=ktrdr-worker-gpu:test" -q | xargs -r docker rm -f
```

---

## Troubleshooting

**If images don't exist:**
- **Cause:** Images not built yet
- **Cure:** Run the build commands in the Setup section

**If torch is found in backend:prod:**
- **Cause:** Dockerfile.backend uses `--extra ml` or imports ML code
- **Check:** `grep -n "extra ml" deploy/docker/Dockerfile.backend`
- **Cure:** Ensure Dockerfile.backend uses `uv sync --frozen --no-dev` without ML extras

**If torch is missing from worker images:**
- **Cause:** Dockerfile.worker-* missing `--extra ml`
- **Check:** `grep -n "extra ml" deploy/docker/Dockerfile.worker-*`
- **Cure:** Add `--extra ml` to uv sync commands

**If CPU image has CUDA:**
- **Cause:** Not injecting CPU-only PyTorch source
- **Check:** Look for `pytorch-cpu` source injection in Dockerfile
- **Cure:** Add CPU-only source configuration before `uv sync`

**If GPU image has CPU-only torch:**
- **Cause:** Not injecting CUDA PyTorch source
- **Check:** Look for `pytorch-cu` source injection in Dockerfile
- **Cure:** Add CUDA source configuration before `uv sync`

---

## Evidence to Capture

- Image existence verification (docker images output)
- Per-image test output (full stdout/stderr)
- Per-image exit codes
- Torch version strings (for version tracking)
- CUDA availability status (for each image)
- Summary table showing all results

---

## Notes

### Why This Complements backend-lazy-imports

The `infra/backend-lazy-imports` test validates CODE-level behavior: that importing the API module does not eagerly load torch into sys.modules.

This test (`infra/image-torch-availability`) validates IMAGE-level configuration: that the right packages are installed in each Docker image.

Both tests are needed:
- Lazy imports prevent runtime errors when torch is not installed (backend:prod)
- Image separation ensures proper dependency isolation per deployment role

### Version String Interpretation

PyTorch version strings indicate the build type:
- `2.5.1+cpu` - CPU-only build (no CUDA support)
- `2.5.1+cu126` - CUDA 12.6 build (full GPU support)
- `2.5.1` - Default build (may or may not have CUDA)

### CUDA Runtime vs Build-time

- **Build-time CUDA** (`torch.version.cuda`): CUDA libraries compiled into torch
- **Runtime CUDA** (`torch.cuda.is_available()`): Actual GPU detected at runtime

A container can have CUDA built-in torch but still report `cuda.is_available() = False` if:
- No GPU is present on the host
- nvidia-container-toolkit is not installed
- Container not started with `--gpus` flag

---

## Related Tests

- `infra/backend-lazy-imports` - Validates CODE-level lazy imports (complements this test)
- `workers/startup-registration` - Validates workers start and register (uses these images)
- `training/smoke` - Validates training works (exercises torch in worker images)
