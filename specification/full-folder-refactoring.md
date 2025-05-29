# 🧱 KTRDR Project Folder Restructure Plan

## 📌 Objective

Reorganize the current KTRDR project into a clean and maintainable folder structure with a clear separation of concerns between the **backend** and **frontend**, aligning with modern best practices. This is important to:

* Improve scalability and developer onboarding.
* Simplify CI/CD workflows and Docker container boundaries.
* Make the codebase LLM-friendly for safe, automated refactoring.

---

## 📂 Proposed Folder Layout

```
project-root/
├── backend/
│   ├── src/
│   │   └── ktrdr/            # Core backend Python package
│   ├── tests/                # Unit and integration tests
│   ├── scripts/              # Utility scripts (dev, build, verify, etc.)
│   ├── config/               # All YAML configurations (e.g. indicators, fuzzy logic)
│   ├── data/                 # Local CSVs and test data
│   ├── Dockerfile            # Backend Dockerfile
│   ├── requirements.txt      # Or pyproject.toml
│   └── setup.cfg             # Optional, used to tell pytest about src layout
├── frontend/
│   ├── src/                  # React application source
│   ├── public/
│   ├── Dockerfile            # Frontend Dockerfile
│   ├── package.json
│   ├── tsconfig.json
│   └── vite.config.ts
├── docker/
│   ├── docker-compose.yml
│   ├── docker-compose.prod.yml
│   └── nginx.conf
├── .github/                  # GitHub Actions
├── docs/                     # Developer and user-facing documentation
├── examples/                 # Non-essential, demo/test examples
├── specification/            # Product specs, roadmaps, and architecture
├── README.md
└── Makefile or setup_dev.sh
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

## 🔧 Suggested Next Steps

1. Migrate files according to structure.
2. Update:

   * `vite.config.ts`
   * `pytest.ini` or `setup.cfg`
   * Dockerfiles and docker-compose paths
   * Any relative import paths in JS or Python
3. Run `docker-compose up` to verify everything still works.
4. Optional: write a script to validate all import paths are still valid.

---

## 📦 Optional Extras

* Add `.editorconfig` or VSCode workspace settings per folder.
* Consider monorepo tools like `nx`, `turborepo`, or `devcontainers` in the future.

---

This plan is intended to be executed safely by an LLM agent, and verified automatically by analyzing all source files for path consistency.
