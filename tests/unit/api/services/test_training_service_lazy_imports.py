"""
Unit tests for lazy imports (M2 Tasks 2.1, 2.2).

Verifies that torch-dependent modules are not imported at module level,
enabling the backend to start without torch installed.
"""

import ast
from pathlib import Path


class TestTrainingServiceLazyImports:
    """Verify training_service.py doesn't have module-level torch imports."""

    def test_no_module_level_model_loader_import(self) -> None:
        """ModelLoader should not be imported at module level."""
        source = Path("ktrdr/api/services/training_service.py").read_text()
        tree = ast.parse(source)

        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom):
                # Check for ModelLoader import
                if node.module and "model_loader" in node.module:
                    names = [alias.name for alias in node.names]
                    assert "ModelLoader" not in names, (
                        "ModelLoader should not be imported at module level in "
                        "training_service.py - it was removed as unused"
                    )

    def test_no_self_model_loader_attribute(self) -> None:
        """self.model_loader should not exist in TrainingService."""
        source = Path("ktrdr/api/services/training_service.py").read_text()

        # Check that self.model_loader is not assigned
        assert (
            "self.model_loader" not in source
        ), "self.model_loader should not exist - ModelLoader was removed as unused"

    def test_model_storage_import_is_lazy(self) -> None:
        """ModelStorage should be imported inside methods, not at module level."""
        source = Path("ktrdr/api/services/training_service.py").read_text()
        tree = ast.parse(source)

        # Check that there's no module-level import of ModelStorage
        for node in tree.body:
            if isinstance(node, ast.ImportFrom):
                if node.module and "model_storage" in node.module:
                    names = [alias.name for alias in node.names]
                    assert "ModelStorage" not in names, (
                        "ModelStorage should not be imported at module level - "
                        "use lazy import inside methods that need it"
                    )

    def test_health_check_does_not_reference_model_loader(self) -> None:
        """Health check should not reference model_loader_ready."""
        source = Path("ktrdr/api/services/training_service.py").read_text()

        assert (
            "model_loader_ready" not in source
        ), "health_check should not reference model_loader after removal"


class TestStrategiesEndpointLazyImports:
    """Verify strategies.py doesn't have module-level torch imports (Task 2.2)."""

    def test_no_module_level_model_storage_import(self) -> None:
        """ModelStorage should not be imported at module level in strategies.py."""
        source = Path("ktrdr/api/endpoints/strategies.py").read_text()
        tree = ast.parse(source)

        # Check that there's no module-level import of ModelStorage
        for node in tree.body:
            if isinstance(node, ast.ImportFrom):
                if node.module and "model_storage" in node.module:
                    names = [alias.name for alias in node.names]
                    assert "ModelStorage" not in names, (
                        "ModelStorage should not be imported at module level in "
                        "strategies.py - use lazy import inside list_strategies()"
                    )
