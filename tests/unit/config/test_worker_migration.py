"""
Tests to verify worker code has been migrated to use WorkerSettings.

Task 4.5 Acceptance Criteria:
- Zero direct os.getenv("WORKER_*") calls in worker code
- Workers use get_worker_settings() instead
"""

import re
from pathlib import Path

import pytest


class TestWorkerMigrationComplete:
    """Verify worker code uses settings getters instead of os.getenv."""

    WORKER_PATHS = [
        "ktrdr/workers",
        "ktrdr/backtesting/backtest_worker.py",
        "ktrdr/backtesting/worker_registration.py",
        "ktrdr/backtesting/remote_api.py",
        "ktrdr/training/training_worker.py",
        "ktrdr/training/worker_registration.py",
        "ktrdr/training/training_worker_api.py",
    ]

    @staticmethod
    def find_os_getenv_worker_calls(file_path: Path) -> list[tuple[int, str]]:
        """Find os.getenv("WORKER_*") calls in a file.

        Returns:
            List of (line_number, matched_text) tuples.
        """
        matches = []
        content = file_path.read_text()

        # Pattern matches: os.getenv("WORKER_...) or os.getenv('WORKER_...)
        pattern = r'os\.getenv\(["\']WORKER_[^"\']*["\']'

        for i, line in enumerate(content.splitlines(), start=1):
            for match in re.finditer(pattern, line):
                matches.append((i, match.group()))

        return matches

    @staticmethod
    def find_os_environ_get_worker_calls(file_path: Path) -> list[tuple[int, str]]:
        """Find os.environ.get("WORKER_*") calls in a file.

        Returns:
            List of (line_number, matched_text) tuples.
        """
        matches = []
        content = file_path.read_text()

        # Pattern matches: os.environ.get("WORKER_...) or os.environ.get('WORKER_...)
        pattern = r'os\.environ\.get\(["\']WORKER_[^"\']*["\']'

        for i, line in enumerate(content.splitlines(), start=1):
            for match in re.finditer(pattern, line):
                matches.append((i, match.group()))

        return matches

    def test_no_os_getenv_worker_calls_in_worker_code(self):
        """Worker code should not use os.getenv("WORKER_*") directly.

        All worker configuration should go through get_worker_settings().
        """
        project_root = Path(
            __file__
        ).parent.parent.parent.parent  # tests/unit/config -> root

        all_violations = []

        for path_str in self.WORKER_PATHS:
            path = project_root / path_str

            if path.is_file():
                files_to_check = [path]
            elif path.is_dir():
                files_to_check = list(path.glob("**/*.py"))
            else:
                continue  # Path doesn't exist

            for file_path in files_to_check:
                # Check os.getenv
                getenv_matches = self.find_os_getenv_worker_calls(file_path)
                for line_num, matched_text in getenv_matches:
                    rel_path = file_path.relative_to(project_root)
                    all_violations.append(f"{rel_path}:{line_num}: {matched_text}")

                # Check os.environ.get
                environ_matches = self.find_os_environ_get_worker_calls(file_path)
                for line_num, matched_text in environ_matches:
                    rel_path = file_path.relative_to(project_root)
                    all_violations.append(f"{rel_path}:{line_num}: {matched_text}")

        if all_violations:
            pytest.fail(
                f"Found {len(all_violations)} os.getenv('WORKER_*') calls in worker code. "
                f"Use get_worker_settings() instead:\n" + "\n".join(all_violations)
            )

    def test_worker_settings_import_present(self):
        """Worker files that were migrated should import get_worker_settings.

        Note: This test only checks files that need the import (those that
        previously had os.getenv WORKER calls). Some files may not need it
        if they get settings from another module.
        """
        # These files must import get_worker_settings after migration
        files_requiring_import = [
            "ktrdr/workers/base.py",
            "ktrdr/backtesting/backtest_worker.py",
            "ktrdr/backtesting/worker_registration.py",
            "ktrdr/backtesting/remote_api.py",
            "ktrdr/training/training_worker.py",
            "ktrdr/training/worker_registration.py",
            "ktrdr/training/training_worker_api.py",
        ]

        project_root = Path(__file__).parent.parent.parent.parent

        missing_imports = []

        for path_str in files_requiring_import:
            file_path = project_root / path_str
            if not file_path.exists():
                continue

            content = file_path.read_text()

            # Check if file imports get_worker_settings
            has_import = (
                "from ktrdr.config.settings import" in content
                and "get_worker_settings" in content
            ) or (
                "from ktrdr.config import" in content
                and "get_worker_settings" in content
            )

            if not has_import:
                missing_imports.append(path_str)

        if missing_imports:
            pytest.fail(
                "The following files should import get_worker_settings:\n"
                + "\n".join(missing_imports)
            )
