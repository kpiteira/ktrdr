# 🧱 KTRDR Project Folder Restructure Plan

## 📌 Status: Project Organization Complete ✅

### Phase 1: Frontend Isolation (Complete)
**Completed on:** May 29, 2025  
**What was done:** Successfully isolated frontend from `ktrdr/ui/frontend` to `./frontend`  
**Time taken:** ~15 minutes  
**Risk level:** Minimal - no Python code changes required  

### Phase 2: Docker & Scripts Organization (Complete)
**Completed on:** May 29, 2025  
**What was done:** 
- Moved all Docker files to `docker/` directory
- Moved backend Dockerfiles to `docker/backend/`
- Moved utility scripts to `scripts/`
- Created symlinks for backward compatibility
**Time taken:** ~20 minutes  
**Risk level:** Minimal - only file moves, no code changes  

## 📌 Original Objective

Reorganize the current KTRDR project into a clean and maintainable folder structure with a clear separation of concerns between the **backend** and **frontend**, aligning with modern best practices. This is important to:

* Improve scalability and developer onboarding.
* Simplify CI/CD workflows and Docker container boundaries.
* Make the codebase LLM-friendly for safe, automated refactoring.

## ✅ What We Actually Did

Instead of the full restructure, we took a pragmatic, incremental approach:

### Phase 1 - Frontend Isolation:
1. **Moved** `ktrdr/ui/frontend/` → `./frontend/`
2. **Updated** Docker configurations for new frontend path
3. **Updated** Development scripts
4. **Updated** Documentation (CLAUDE.md, .gitignore)
5. **Verified** Everything works after container restart

### Phase 2 - Docker & Scripts Organization:
1. **Created** `docker/` directory structure
2. **Moved** Docker compose files → `docker/`
3. **Moved** Backend Dockerfiles → `docker/backend/`
4. **Moved** Docker scripts → `docker/`
5. **Updated** All Docker paths and contexts
6. **Moved** Utility scripts → `scripts/`
7. **Created** Symlinks for backward compatibility
8. **Tested** Docker setup still works

### Total Impact:
- ✅ Frontend is now at root level
- ✅ All Docker configs organized in `docker/`
- ✅ Utility scripts organized in `scripts/`
- ✅ Cleaner root directory
- ✅ No Python import changes needed
- ✅ Backend code completely untouched
- ✅ Zero risk to functionality
- ✅ Total time: ~35 minutes vs 8 hours for full restructure

## ⚠️ Original Risk Assessment (for full restructure)

**High Risk Areas:**
- Import path updates across ~200+ Python files
- Docker volume mappings and build contexts
- Frontend API client paths
- Test discovery and pytest configuration
- CI/CD workflows (if any)
- Development scripts and tooling

**Estimated Effort:** 4-8 hours of careful work with high attention to detail

---

## 📂 Current State After All Improvements

```
project-root/
├── docker/                   # ✅ NEW - All Docker configs
│   ├── backend/              # Backend Dockerfiles
│   │   ├── Dockerfile
│   │   └── Dockerfile.dev
│   ├── docker-compose.yml    # Main compose file
│   ├── docker-compose.prod.yml
│   ├── docker_dev.sh         # Docker helper script
│   └── build_docker_dev.sh   # Build script
├── frontend/                 # ✅ MOVED FROM ktrdr/ui/frontend
│   ├── src/                  # React application source
│   ├── public/
│   ├── Dockerfile            # Frontend Dockerfile
│   ├── Dockerfile.dev        # Frontend dev Dockerfile
│   ├── package.json
│   ├── tsconfig.json
│   └── vite.config.ts
├── ktrdr/                    # Python package (unchanged)
│   ├── api/
│   ├── cli/
│   ├── config/
│   ├── data/
│   ├── errors/
│   ├── fuzzy/
│   ├── indicators/
│   ├── logging/
│   ├── neural/
│   └── visualization/
├── scripts/                  # ✅ EXPANDED - All utility scripts
│   ├── setup_dev.sh          # Setup script
│   ├── ktrdr_cli.py          # CLI script
│   ├── test_data_loading.py  # Test utility
│   └── ... (other scripts)
├── tests/                    # Backend tests (unchanged)
├── config/                   # YAML configurations (unchanged)
├── data/                     # Local CSVs and test data (unchanged)
├── docs/
├── examples/
├── specification/
├── README.md
├── docker_dev.sh            # ✅ SYMLINK → docker/docker_dev.sh
├── build_docker_dev.sh      # ✅ SYMLINK → docker/build_docker_dev.sh
└── setup_dev.sh             # ✅ SYMLINK → scripts/setup_dev.sh

```

## 📂 Original Proposed Full Restructure (Not Implemented)

```
project-root/
├── backend/
│   ├── src/
│   │   └── ktrdr/            # Core backend Python package
│   ├── tests/                # Unit and integration tests
│   ├── scripts/              # Utility scripts (dev, build, verify, etc.)
│   ├── config/               # All YAML configurations (e.g. indicators, fuzzy logic)
│   ├── data/                 # Local CSVs and test data
│   ├── logs/                 # Backend logs directory
│   ├── output/               # Generated outputs
│   ├── Dockerfile            # Backend Dockerfile
│   ├── pyproject.toml        # Modern Python packaging
│   ├── requirements.txt      # Generated from pyproject.toml
│   ├── requirements-dev.txt  # Dev dependencies
│   ├── pytest.ini            # Pytest configuration
│   └── setup.cfg             # Optional, used to tell pytest about src layout
├── frontend/
│   ├── src/                  # React application source
│   ├── public/
│   ├── Dockerfile            # Frontend Dockerfile
│   ├── package.json
│   ├── tsconfig.json
│   ├── vite.config.ts
│   └── README.md             # Frontend-specific docs
├── docker/
│   ├── docker-compose.yml
│   ├── docker-compose.prod.yml
│   └── nginx.conf
├── .github/                  # GitHub Actions
├── docs/                     # Developer and user-facing documentation
├── examples/                 # Non-essential, demo/test examples
├── specification/            # Product specs, roadmaps, and architecture
├── strategies/               # Trading strategies YAML files
├── .env.example              # Environment variables template
├── CLAUDE.md                 # AI assistant instructions
├── README.md
├── Makefile                  # Common tasks automation
└── setup_dev.sh              # Initial setup script
```

---

## ✅ Design Rationale

### 1. `src/ktrdr/` instead of just `src/`

* This follows the ["src layout" best practice](https://blog.ionelmc.ro/2014/05/25/python-packaging/#the-structure).
* It avoids namespace collisions and makes it easy to install via `pip install -e .`.
* Encourages modularization and prevents tests or scripts from polluting the main import path.

### 2. Dedicated `frontend/` and `backend/`

* Each side of the app is clearly isolated.
* Tools (Docker, linters, test runners) can be scoped to their respective root.
* Makes monorepo logic easier to scale.

### 3. Central `docker/` config

* House shared Docker Compose and NGINX config in one location.
* Supports multi-container orchestration:

  * `frontend` container serves the React app
  * `backend` container serves the FastAPI app

### 4. Clean separation of config, data, and scripts

* `config/` holds YAML, JSON, or INI files.
* `data/` is only for CSVs or test input/output.
* `scripts/` is where ad-hoc CLI or debug scripts live.

---

## ⚠️ Migration Considerations

### 🧪 Relative Imports

* **Python (Backend):**

  * Ensure `PYTHONPATH=backend/src` in any Dockerfile, `pytest.ini`, or IDE setting.
  * You can also use `setup.cfg` to explicitly configure test discovery:

    ```ini
    [tool.pytest.ini_options]
    python_paths = backend/src
    ```

* **React (Frontend):**

  * Move to Vite path aliases to eliminate fragile `../../../utils/logger.ts` imports.

    Update `vite.config.ts`:

    ```ts
    resolve: {
      alias: {
        '@': path.resolve(__dirname, './src')
      }
    }
    ```

  * Then, refactor imports from:

    ```ts
    import { logger } from '../../../utils/logger'
    ```

    to:

    ```ts
    import { logger } from '@/utils/logger'
    ```

### 🐳 Docker

* You can keep a \*\*single \*\*\`\` to orchestrate multiple services:

```yaml
services:
  backend:
    build: ./backend
    volumes:
      - ./backend:/app
    ports:
      - "8000:8000"
    env_file:
      - .env

  frontend:
    build: ./frontend
    volumes:
      - ./frontend:/app
    ports:
      - "5173:5173"
    env_file:
      - .env
```

* Each service gets its own Dockerfile scoped to its context.
* Add optional `nginx` reverse proxy for production.

---

## 🔧 Migration Steps (In Order)

### Phase 1: Preparation
1. **Create feature branch:** `git checkout -b refactor/folder-structure`
2. **Full backup:** `cp -r . ../ktrdr2-backup-$(date +%Y%m%d)`
3. **Document current state:** Run tests, ensure everything passes

### Phase 2: Directory Structure
1. Create new directory structure:
   ```bash
   mkdir -p backend/src backend/tests backend/scripts backend/config backend/data
   mkdir -p frontend docker
   ```

2. Move backend files:
   ```bash
   # Move Python package
   mv ktrdr backend/src/
   mv tests/* backend/tests/
   mv scripts/* backend/scripts/
   mv config/* backend/config/
   mv data/* backend/data/
   mv logs backend/
   mv output backend/
   
   # Move Python config files
   mv pyproject.toml requirements*.txt pytest.ini backend/
   ```

3. Move frontend:
   ```bash
   mv ktrdr/ui/frontend/* frontend/
   rm -rf ktrdr/ui  # Clean up old structure
   ```

4. Move Docker files:
   ```bash
   mv docker-compose*.yml docker/
   mv frontend/nginx.conf docker/
   ```

### Phase 3: Update Import Paths
1. **Python imports:** Use automated script to update all imports from `ktrdr.` to remain `ktrdr.`
2. **Test imports:** Update `from tests.` to appropriate paths
3. **Config paths:** Update all hardcoded paths in Python code
4. **Frontend API paths:** Ensure `/api` endpoints still work

### Phase 4: Configuration Updates
1. Update `backend/pytest.ini`:
   ```ini
   [tool:pytest]
   pythonpath = src
   testpaths = tests
   ```

2. Update Docker contexts in `docker/docker-compose.yml`
3. Update `backend/Dockerfile` WORKDIR and COPY paths
4. Update `frontend/Dockerfile` paths
5. Update `setup_dev.sh` for new structure
6. Update `CLAUDE.md` with new paths

### Phase 5: Verification Checklist
- [ ] All Python tests pass: `cd backend && pytest`
- [ ] Frontend builds: `cd frontend && npm run build`
- [ ] Docker containers start: `cd docker && docker-compose up`
- [ ] API endpoints respond correctly
- [ ] Frontend can connect to backend
- [ ] All scripts in `backend/scripts/` still work
- [ ] Documentation paths are updated

---

## 🚨 Critical Path Dependencies to Verify

Before starting, grep/search for these hardcoded paths that WILL break:

1. **Python hardcoded paths:**
   ```bash
   grep -r "ktrdr/ui/frontend" --include="*.py"
   grep -r "config/" --include="*.py"
   grep -r "data/" --include="*.py"
   grep -r "logs/" --include="*.py"
   ```

2. **Frontend API configuration:**
   - Check `frontend/src/config.ts` for API base URL
   - Verify `frontend/src/api/client.ts` endpoints

3. **Docker volume mounts:**
   - Current: `./ktrdr:/app/ktrdr`
   - New: `./backend/src/ktrdr:/app/ktrdr`

4. **Test fixtures and data paths:**
   - Many tests likely use relative paths to `data/` or `test_data/`

5. **Configuration file loaders:**
   - `ktrdr/config/loader.py` likely has hardcoded paths

---

## 📦 Optional Extras

* Add `.editorconfig` or VSCode workspace settings per folder.
* Consider monorepo tools like `nx`, `turborepo`, or `devcontainers` in the future.
* Add pre-commit hooks to prevent accidental commits during migration.

---

## 🎯 Final Decision on Backend Restructure

**Decision: NO BACKEND RESTRUCTURE** ❌

After careful analysis:
- The backend is already self-contained in the `ktrdr/` folder
- Moving it would require updating ~200+ Python imports
- Risk/reward ratio is terrible: 8 hours of work for marginal benefit
- The current structure works fine for development and deployment

**This decision is FINAL.** The backend stays where it is.

## 🚀 Remaining Low-Risk, High-Value Improvements

Instead of risky restructuring, focus on these pragmatic improvements:

### 1. **Docker Consolidation** (~10 minutes) ⭐ RECOMMENDED
Create `docker/` directory and organize all Docker files:
```
docker/
├── backend/
│   ├── Dockerfile
│   └── Dockerfile.dev
├── docker-compose.yml
├── docker-compose.prod.yml
├── build_docker_dev.sh
└── docker_dev.sh
```
**Impact:** Cleaner root, all container configs in one place

### 2. **Scripts Consolidation** (~5 minutes) ⭐ RECOMMENDED
Move utility scripts to `scripts/`:
- `ktrdr_cli.py` → `scripts/`
- `test_data_loading.py` → `scripts/`
- `setup_dev.sh` → `scripts/`

**Impact:** Less root clutter, clear utility organization

### 3. **Build Directory Cleanup** (~2 minutes)
- Check if `build/` is empty or has generated files
- Add to `.gitignore` if needed or remove entirely

### 4. **Documentation Restructure** (~20 minutes) - OPTIONAL
Consolidate overlapping `docs/api/` and `docs/api-reference/`:
```
docs/
├── architecture/     # System design docs
├── guides/          # How-to guides  
├── api-reference/   # API documentation
└── development/     # Dev setup, contributing
```

### 5. **Future Ideas** (Not immediate priority)
- Move `strategies/` into `config/strategies/`
- Create `deployment/` for production configs
- Add `.github/` for CI/CD workflows

## 📝 Lessons Learned

1. **Incremental refactoring > Big bang refactoring**
2. **Frontend isolation was low-risk, high-reward**
3. **Backend is fine where it is - don't fix what ain't broken**
4. **Focus on organization that doesn't touch code imports**
5. **15 minutes vs 8 hours - pragmatism wins**

## 🎯 Action Plan

1. ✅ Frontend isolation (COMPLETE - Phase 1)
2. ✅ Docker consolidation (COMPLETE - Phase 2)
3. ✅ Scripts consolidation (COMPLETE - Phase 2)
4. ✅ Build directory cleanup (COMPLETE - verified .gitignore)
5. ❓ Documentation restructure (DEFERRED - not critical)

## 📊 Final Results

**Time Investment:** ~35 minutes total
**Risk Level:** Zero - no code changes, only file organization
**Benefits Achieved:**
- Much cleaner root directory
- Docker configs centralized
- Frontend properly isolated
- Scripts organized
- Backward compatibility maintained via symlinks
- No import changes required
- No functionality affected

**Pragmatic Win:** Got 80% of the organizational benefit with 5% of the risk!

---

This document now serves as both a historical record and a pragmatic guide for ongoing improvements.
