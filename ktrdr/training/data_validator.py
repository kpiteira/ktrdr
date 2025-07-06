"""Data validation and sanitization for robust KTRDR training."""

import torch
import numpy as np
import pandas as pd
from typing import Dict, Any, Optional, List, Tuple, Union, Set
from dataclasses import dataclass, field
from datetime import datetime
import warnings
import math

from ktrdr import get_logger

logger = get_logger(__name__)


@dataclass
class ValidationRule:
    """Data validation rule configuration."""

    name: str
    description: str
    severity: str  # "error", "warning", "info"
    auto_fix: bool = False  # Whether to automatically fix violations
    enabled: bool = True

    def __post_init__(self):
        """Validate rule configuration."""
        if self.severity not in ["error", "warning", "info"]:
            raise ValueError(f"Invalid severity: {self.severity}")


@dataclass
class ValidationResult:
    """Result of data validation."""

    rule_name: str
    passed: bool
    severity: str
    message: str
    affected_indices: List[int] = field(default_factory=list)
    suggested_fix: Optional[str] = None
    fixed_automatically: bool = False

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "rule_name": self.rule_name,
            "passed": self.passed,
            "severity": self.severity,
            "message": self.message,
            "affected_count": len(self.affected_indices),
            "affected_indices": self.affected_indices[:10],  # Limit for readability
            "suggested_fix": self.suggested_fix,
            "fixed_automatically": self.fixed_automatically,
        }


class DataValidator:
    """Comprehensive data validation and sanitization system."""

    def __init__(self):
        """Initialize data validator with default rules."""
        self.rules: Dict[str, ValidationRule] = {}
        self.validation_history: List[Dict[str, Any]] = []

        # Setup default validation rules
        self._setup_default_rules()

        logger.info("DataValidator initialized with default validation rules")

    def _setup_default_rules(self):
        """Setup default data validation rules."""

        # Feature validation rules
        self.add_rule(
            ValidationRule(
                name="no_infinite_values",
                description="Check for infinite values in features",
                severity="error",
                auto_fix=True,
            )
        )

        self.add_rule(
            ValidationRule(
                name="no_nan_values",
                description="Check for NaN values in features",
                severity="error",
                auto_fix=True,
            )
        )

        self.add_rule(
            ValidationRule(
                name="feature_range_check",
                description="Check if features are in reasonable ranges",
                severity="warning",
                auto_fix=False,
            )
        )

        self.add_rule(
            ValidationRule(
                name="feature_variance_check",
                description="Check for zero or very low variance features",
                severity="warning",
                auto_fix=False,
            )
        )

        # Label validation rules
        self.add_rule(
            ValidationRule(
                name="valid_label_range",
                description="Check if labels are in valid range (0, 1, 2 for 3-class)",
                severity="error",
                auto_fix=True,
            )
        )

        self.add_rule(
            ValidationRule(
                name="label_distribution_check",
                description="Check for severely imbalanced label distribution",
                severity="warning",
                auto_fix=False,
            )
        )

        # Tensor validation rules
        self.add_rule(
            ValidationRule(
                name="tensor_shape_consistency",
                description="Check for consistent tensor shapes",
                severity="error",
                auto_fix=False,
            )
        )

        self.add_rule(
            ValidationRule(
                name="tensor_dtype_check",
                description="Check for appropriate tensor data types",
                severity="warning",
                auto_fix=True,
            )
        )

        # Symbol validation rules
        self.add_rule(
            ValidationRule(
                name="symbol_indices_valid",
                description="Check if symbol indices are valid",
                severity="error",
                auto_fix=True,
            )
        )

        self.add_rule(
            ValidationRule(
                name="symbol_balance_check",
                description="Check for balanced symbol representation",
                severity="warning",
                auto_fix=False,
            )
        )

        # Timeframe validation rules
        self.add_rule(
            ValidationRule(
                name="timeframe_feature_naming",
                description="Check if timeframe features are properly named",
                severity="warning",
                auto_fix=False,
            )
        )

        # Memory and performance rules
        self.add_rule(
            ValidationRule(
                name="tensor_size_check",
                description="Check for excessively large tensors",
                severity="warning",
                auto_fix=False,
            )
        )

    def add_rule(self, rule: ValidationRule):
        """Add a custom validation rule."""
        self.rules[rule.name] = rule
        logger.debug(f"Added validation rule: {rule.name}")

    def disable_rule(self, rule_name: str):
        """Disable a validation rule."""
        if rule_name in self.rules:
            self.rules[rule_name].enabled = False
            logger.debug(f"Disabled validation rule: {rule_name}")

    def enable_rule(self, rule_name: str):
        """Enable a validation rule."""
        if rule_name in self.rules:
            self.rules[rule_name].enabled = True
            logger.debug(f"Enabled validation rule: {rule_name}")

    def validate_features(
        self, features: torch.Tensor, feature_names: Optional[List[str]] = None
    ) -> List[ValidationResult]:
        """Validate feature tensor.

        Args:
            features: Feature tensor to validate
            feature_names: Optional feature names

        Returns:
            List of validation results
        """
        results = []

        # Check for infinite values
        if self.rules["no_infinite_values"].enabled:
            results.append(self._check_infinite_values(features, "features"))

        # Check for NaN values
        if self.rules["no_nan_values"].enabled:
            results.append(self._check_nan_values(features, "features"))

        # Check feature ranges
        if self.rules["feature_range_check"].enabled:
            results.append(self._check_feature_ranges(features))

        # Check feature variance
        if self.rules["feature_variance_check"].enabled:
            results.append(self._check_feature_variance(features, feature_names))

        # Check tensor size
        if self.rules["tensor_size_check"].enabled:
            results.append(self._check_tensor_size(features, "features"))

        # Check tensor dtype
        if self.rules["tensor_dtype_check"].enabled:
            results.append(
                self._check_tensor_dtype(features, "features", torch.float32)
            )

        # Check timeframe feature naming
        if self.rules["timeframe_feature_naming"].enabled and feature_names:
            results.append(self._check_timeframe_naming(feature_names))

        return results

    def validate_labels(
        self, labels: torch.Tensor, num_classes: int = 3
    ) -> List[ValidationResult]:
        """Validate label tensor.

        Args:
            labels: Label tensor to validate
            num_classes: Number of expected classes

        Returns:
            List of validation results
        """
        results = []

        # Check for infinite values
        if self.rules["no_infinite_values"].enabled:
            results.append(self._check_infinite_values(labels, "labels"))

        # Check for NaN values
        if self.rules["no_nan_values"].enabled:
            results.append(self._check_nan_values(labels, "labels"))

        # Check valid label range
        if self.rules["valid_label_range"].enabled:
            results.append(self._check_label_range(labels, num_classes))

        # Check label distribution
        if self.rules["label_distribution_check"].enabled:
            results.append(self._check_label_distribution(labels, num_classes))

        # Check tensor dtype
        if self.rules["tensor_dtype_check"].enabled:
            results.append(self._check_tensor_dtype(labels, "labels", torch.long))

        return results

    def validate_symbols(
        self, symbol_indices: torch.Tensor, symbols: List[str]
    ) -> List[ValidationResult]:
        """Validate symbol indices.

        Args:
            symbol_indices: Symbol indices tensor
            symbols: List of symbol names

        Returns:
            List of validation results
        """
        results = []

        # Check symbol indices validity
        if self.rules["symbol_indices_valid"].enabled:
            results.append(self._check_symbol_indices(symbol_indices, len(symbols)))

        # Check symbol balance
        if self.rules["symbol_balance_check"].enabled:
            results.append(self._check_symbol_balance(symbol_indices, symbols))

        return results

    def validate_tensor_consistency(
        self, *tensors: torch.Tensor
    ) -> List[ValidationResult]:
        """Validate consistency between multiple tensors.

        Args:
            *tensors: Tensors to check for consistency

        Returns:
            List of validation results
        """
        results = []

        if self.rules["tensor_shape_consistency"].enabled:
            results.append(self._check_tensor_shape_consistency(tensors))

        return results

    def sanitize_features(
        self, features: torch.Tensor
    ) -> Tuple[torch.Tensor, List[str]]:
        """Sanitize features tensor by fixing common issues.

        Args:
            features: Feature tensor to sanitize

        Returns:
            Tuple of (sanitized_features, list_of_fixes_applied)
        """
        sanitized = features.clone()
        fixes_applied = []

        # Fix infinite values
        inf_mask = torch.isinf(sanitized)
        if inf_mask.any():
            # Replace inf with large but finite values
            sanitized[inf_mask & (sanitized > 0)] = 1e6
            sanitized[inf_mask & (sanitized < 0)] = -1e6
            fixes_applied.append(f"Replaced {inf_mask.sum().item()} infinite values")

        # Fix NaN values
        nan_mask = torch.isnan(sanitized)
        if nan_mask.any():
            # Replace NaN with zeros
            sanitized[nan_mask] = 0.0
            fixes_applied.append(
                f"Replaced {nan_mask.sum().item()} NaN values with zeros"
            )

        # Clip extreme values
        extreme_threshold = 1e3
        extreme_mask = torch.abs(sanitized) > extreme_threshold
        if extreme_mask.any():
            sanitized = torch.clamp(sanitized, -extreme_threshold, extreme_threshold)
            fixes_applied.append(
                f"Clipped {extreme_mask.sum().item()} extreme values to ±{extreme_threshold}"
            )

        return sanitized, fixes_applied

    def sanitize_labels(
        self, labels: torch.Tensor, num_classes: int = 3
    ) -> Tuple[torch.Tensor, List[str]]:
        """Sanitize labels tensor.

        Args:
            labels: Label tensor to sanitize
            num_classes: Number of expected classes

        Returns:
            Tuple of (sanitized_labels, list_of_fixes_applied)
        """
        sanitized = labels.clone()
        fixes_applied = []

        # Fix out-of-range labels
        invalid_mask = (sanitized < 0) | (sanitized >= num_classes)
        if invalid_mask.any():
            # Map invalid labels to closest valid class
            sanitized[sanitized < 0] = 0
            sanitized[sanitized >= num_classes] = num_classes - 1
            fixes_applied.append(
                f"Fixed {invalid_mask.sum().item()} out-of-range labels"
            )

        # Ensure integer type
        if sanitized.dtype != torch.long:
            sanitized = sanitized.long()
            fixes_applied.append("Converted labels to long tensor")

        return sanitized, fixes_applied

    def _check_infinite_values(
        self, tensor: torch.Tensor, tensor_name: str
    ) -> ValidationResult:
        """Check for infinite values."""
        inf_mask = torch.isinf(tensor)
        inf_count = inf_mask.sum().item()

        if inf_count > 0:
            affected_indices = torch.where(
                inf_mask.any(dim=1) if tensor.dim() > 1 else inf_mask
            )[0].tolist()
            return ValidationResult(
                rule_name="no_infinite_values",
                passed=False,
                severity="error",
                message=f"Found {inf_count} infinite values in {tensor_name}",
                affected_indices=affected_indices,
                suggested_fix="Replace infinite values with large finite numbers or remove affected samples",
            )
        else:
            return ValidationResult(
                rule_name="no_infinite_values",
                passed=True,
                severity="error",
                message=f"No infinite values found in {tensor_name}",
            )

    def _check_nan_values(
        self, tensor: torch.Tensor, tensor_name: str
    ) -> ValidationResult:
        """Check for NaN values."""
        nan_mask = torch.isnan(tensor)
        nan_count = nan_mask.sum().item()

        if nan_count > 0:
            affected_indices = torch.where(
                nan_mask.any(dim=1) if tensor.dim() > 1 else nan_mask
            )[0].tolist()
            return ValidationResult(
                rule_name="no_nan_values",
                passed=False,
                severity="error",
                message=f"Found {nan_count} NaN values in {tensor_name}",
                affected_indices=affected_indices,
                suggested_fix="Replace NaN values with zeros, means, or remove affected samples",
            )
        else:
            return ValidationResult(
                rule_name="no_nan_values",
                passed=True,
                severity="error",
                message=f"No NaN values found in {tensor_name}",
            )

    def _check_feature_ranges(self, features: torch.Tensor) -> ValidationResult:
        """Check if features are in reasonable ranges."""
        feature_mins = features.min(dim=0)[0]
        feature_maxs = features.max(dim=0)[0]
        feature_ranges = feature_maxs - feature_mins

        # Check for extreme ranges
        extreme_threshold = 1e6
        extreme_features = torch.where(feature_ranges > extreme_threshold)[0].tolist()

        if extreme_features:
            return ValidationResult(
                rule_name="feature_range_check",
                passed=False,
                severity="warning",
                message=f"Found {len(extreme_features)} features with extreme ranges (>{extreme_threshold})",
                affected_indices=extreme_features,
                suggested_fix="Consider feature scaling or normalization",
            )
        else:
            return ValidationResult(
                rule_name="feature_range_check",
                passed=True,
                severity="warning",
                message="All features have reasonable ranges",
            )

    def _check_feature_variance(
        self, features: torch.Tensor, feature_names: Optional[List[str]]
    ) -> ValidationResult:
        """Check for low variance features."""
        feature_vars = torch.var(features, dim=0)
        low_variance_threshold = 1e-6
        low_var_features = torch.where(feature_vars < low_variance_threshold)[
            0
        ].tolist()

        if low_var_features:
            feature_info = []
            for idx in low_var_features[:5]:  # Show first 5
                if feature_names and idx < len(feature_names):
                    name = feature_names[idx]
                else:
                    name = f"feature_{idx}"
                feature_info.append(f"{name} (var={feature_vars[idx]:.2e})")

            return ValidationResult(
                rule_name="feature_variance_check",
                passed=False,
                severity="warning",
                message=f"Found {len(low_var_features)} low-variance features: {', '.join(feature_info)}",
                affected_indices=low_var_features,
                suggested_fix="Consider removing constant or near-constant features",
            )
        else:
            return ValidationResult(
                rule_name="feature_variance_check",
                passed=True,
                severity="warning",
                message="All features have sufficient variance",
            )

    def _check_label_range(
        self, labels: torch.Tensor, num_classes: int
    ) -> ValidationResult:
        """Check if labels are in valid range."""
        invalid_mask = (labels < 0) | (labels >= num_classes)
        invalid_count = invalid_mask.sum().item()

        if invalid_count > 0:
            affected_indices = torch.where(invalid_mask)[0].tolist()
            unique_invalid = torch.unique(labels[invalid_mask]).tolist()

            return ValidationResult(
                rule_name="valid_label_range",
                passed=False,
                severity="error",
                message=f"Found {invalid_count} labels outside valid range [0, {num_classes-1}]: {unique_invalid}",
                affected_indices=affected_indices,
                suggested_fix=f"Map invalid labels to valid range [0, {num_classes-1}]",
            )
        else:
            return ValidationResult(
                rule_name="valid_label_range",
                passed=True,
                severity="error",
                message=f"All labels are in valid range [0, {num_classes-1}]",
            )

    def _check_label_distribution(
        self, labels: torch.Tensor, num_classes: int
    ) -> ValidationResult:
        """Check label distribution balance."""
        class_counts = torch.bincount(labels, minlength=num_classes)
        total_samples = len(labels)

        # Calculate class proportions
        class_props = class_counts.float() / total_samples

        # Check for severe imbalance (any class < 5% or > 80%)
        min_prop, max_prop = class_props.min().item(), class_props.max().item()

        if min_prop < 0.05 or max_prop > 0.8:
            distribution_info = {
                f"class_{i}": f"{count} ({prop:.1%})"
                for i, (count, prop) in enumerate(
                    zip(class_counts.tolist(), class_props.tolist())
                )
            }

            return ValidationResult(
                rule_name="label_distribution_check",
                passed=False,
                severity="warning",
                message=f"Severe class imbalance detected: {distribution_info}",
                suggested_fix="Consider class balancing techniques or stratified sampling",
            )
        else:
            return ValidationResult(
                rule_name="label_distribution_check",
                passed=True,
                severity="warning",
                message=f"Label distribution is reasonably balanced: min={min_prop:.1%}, max={max_prop:.1%}",
            )

    def _check_symbol_indices(
        self, symbol_indices: torch.Tensor, num_symbols: int
    ) -> ValidationResult:
        """Check symbol indices validity."""
        invalid_mask = (symbol_indices < 0) | (symbol_indices >= num_symbols)
        invalid_count = invalid_mask.sum().item()

        if invalid_count > 0:
            affected_indices = torch.where(invalid_mask)[0].tolist()
            unique_invalid = torch.unique(symbol_indices[invalid_mask]).tolist()

            return ValidationResult(
                rule_name="symbol_indices_valid",
                passed=False,
                severity="error",
                message=f"Found {invalid_count} invalid symbol indices: {unique_invalid}",
                affected_indices=affected_indices,
                suggested_fix=f"Map invalid indices to valid range [0, {num_symbols-1}]",
            )
        else:
            return ValidationResult(
                rule_name="symbol_indices_valid",
                passed=True,
                severity="error",
                message=f"All symbol indices are valid [0, {num_symbols-1}]",
            )

    def _check_symbol_balance(
        self, symbol_indices: torch.Tensor, symbols: List[str]
    ) -> ValidationResult:
        """Check symbol balance."""
        symbol_counts = torch.bincount(symbol_indices, minlength=len(symbols))
        total_samples = len(symbol_indices)

        # Calculate symbol proportions
        symbol_props = symbol_counts.float() / total_samples
        min_prop, max_prop = symbol_props.min().item(), symbol_props.max().item()

        if min_prop < 0.15 or max_prop > 0.6:  # More lenient than class balance
            distribution_info = {}
            for i, (count, prop) in enumerate(
                zip(symbol_counts.tolist(), symbol_props.tolist())
            ):
                symbol_name = symbols[i] if i < len(symbols) else f"invalid_symbol_{i}"
                distribution_info[symbol_name] = f"{count} ({prop:.1%})"

            return ValidationResult(
                rule_name="symbol_balance_check",
                passed=False,
                severity="warning",
                message=f"Symbol imbalance detected: {distribution_info}",
                suggested_fix="Consider symbol-balanced sampling or more balanced data collection",
            )
        else:
            return ValidationResult(
                rule_name="symbol_balance_check",
                passed=True,
                severity="warning",
                message=f"Symbol distribution is balanced: min={min_prop:.1%}, max={max_prop:.1%}",
            )

    def _check_tensor_shape_consistency(
        self, tensors: Tuple[torch.Tensor, ...]
    ) -> ValidationResult:
        """Check tensor shape consistency."""
        if len(tensors) < 2:
            return ValidationResult(
                rule_name="tensor_shape_consistency",
                passed=True,
                severity="error",
                message="Only one tensor provided, cannot check consistency",
            )

        first_shape = tensors[0].shape[0]  # Check first dimension (batch size)
        inconsistent_tensors = []

        for i, tensor in enumerate(tensors[1:], 1):
            if tensor.shape[0] != first_shape:
                inconsistent_tensors.append(f"tensor_{i}: {tensor.shape[0]}")

        if inconsistent_tensors:
            return ValidationResult(
                rule_name="tensor_shape_consistency",
                passed=False,
                severity="error",
                message=f"Inconsistent tensor batch sizes. Expected {first_shape}, got: {', '.join(inconsistent_tensors)}",
                suggested_fix="Ensure all tensors have the same batch size (first dimension)",
            )
        else:
            return ValidationResult(
                rule_name="tensor_shape_consistency",
                passed=True,
                severity="error",
                message=f"All tensors have consistent batch size: {first_shape}",
            )

    def _check_tensor_dtype(
        self, tensor: torch.Tensor, tensor_name: str, expected_dtype: torch.dtype
    ) -> ValidationResult:
        """Check tensor data type."""
        actual_dtype = tensor.dtype

        if actual_dtype != expected_dtype:
            return ValidationResult(
                rule_name="tensor_dtype_check",
                passed=False,
                severity="warning",
                message=f"{tensor_name} has dtype {actual_dtype}, expected {expected_dtype}",
                suggested_fix=f"Convert {tensor_name} to {expected_dtype}",
            )
        else:
            return ValidationResult(
                rule_name="tensor_dtype_check",
                passed=True,
                severity="warning",
                message=f"{tensor_name} has correct dtype: {actual_dtype}",
            )

    def _check_tensor_size(
        self, tensor: torch.Tensor, tensor_name: str
    ) -> ValidationResult:
        """Check tensor memory size."""
        tensor_size_mb = tensor.numel() * tensor.element_size() / (1024**2)
        size_threshold_mb = 1000  # 1GB threshold

        if tensor_size_mb > size_threshold_mb:
            return ValidationResult(
                rule_name="tensor_size_check",
                passed=False,
                severity="warning",
                message=f"{tensor_name} is very large: {tensor_size_mb:.1f}MB (>{size_threshold_mb}MB)",
                suggested_fix="Consider batch processing or data reduction techniques",
            )
        else:
            return ValidationResult(
                rule_name="tensor_size_check",
                passed=True,
                severity="warning",
                message=f"{tensor_name} size is reasonable: {tensor_size_mb:.1f}MB",
            )

    def _check_timeframe_naming(self, feature_names: List[str]) -> ValidationResult:
        """Check timeframe feature naming conventions."""
        common_timeframes = [
            "1m",
            "5m",
            "15m",
            "30m",
            "1h",
            "2h",
            "4h",
            "8h",
            "12h",
            "1d",
            "1w",
        ]

        timeframe_features = {}
        unnamed_features = []

        for i, name in enumerate(feature_names):
            found_timeframe = False
            for tf in common_timeframes:
                if f"_{tf}_" in name or name.endswith(f"_{tf}"):
                    if tf not in timeframe_features:
                        timeframe_features[tf] = []
                    timeframe_features[tf].append(name)
                    found_timeframe = True
                    break

            if not found_timeframe:
                unnamed_features.append(name)

        if len(unnamed_features) > len(feature_names) * 0.5:  # >50% unnamed
            return ValidationResult(
                rule_name="timeframe_feature_naming",
                passed=False,
                severity="warning",
                message=f"Many features ({len(unnamed_features)}/{len(feature_names)}) don't follow timeframe naming convention",
                suggested_fix="Use naming convention: indicator_timeframe (e.g., rsi_1h, macd_15m)",
            )
        else:
            return ValidationResult(
                rule_name="timeframe_feature_naming",
                passed=True,
                severity="warning",
                message=f"Most features follow timeframe naming. Found timeframes: {list(timeframe_features.keys())}",
            )

    def comprehensive_validation(
        self,
        features: torch.Tensor,
        labels: torch.Tensor,
        symbol_indices: Optional[torch.Tensor] = None,
        feature_names: Optional[List[str]] = None,
        symbols: Optional[List[str]] = None,
        auto_fix: bool = False,
    ) -> Dict[str, Any]:
        """Perform comprehensive validation on all data.

        Args:
            features: Feature tensor
            labels: Label tensor
            symbol_indices: Symbol indices (optional)
            feature_names: Feature names (optional)
            symbols: Symbol names (optional)
            auto_fix: Whether to automatically fix issues

        Returns:
            Comprehensive validation report
        """
        logger.info("Starting comprehensive data validation...")

        validation_start = datetime.now()
        all_results = []
        fixes_applied = []

        # Validate features
        feature_results = self.validate_features(features, feature_names)
        all_results.extend(feature_results)

        # Validate labels
        label_results = self.validate_labels(labels)
        all_results.extend(label_results)

        # Validate symbols if provided
        if symbol_indices is not None and symbols is not None:
            symbol_results = self.validate_symbols(symbol_indices, symbols)
            all_results.extend(symbol_results)

        # Validate tensor consistency
        tensors_to_check = [features, labels]
        if symbol_indices is not None:
            tensors_to_check.append(symbol_indices)

        consistency_results = self.validate_tensor_consistency(*tensors_to_check)
        all_results.extend(consistency_results)

        # Auto-fix if requested
        if auto_fix:
            # Fix features
            fixed_features, feature_fixes = self.sanitize_features(features)
            fixes_applied.extend(feature_fixes)

            # Fix labels
            fixed_labels, label_fixes = self.sanitize_labels(labels)
            fixes_applied.extend(label_fixes)

        # Generate summary
        total_rules = len(all_results)
        passed_rules = sum(1 for result in all_results if result.passed)
        failed_rules = total_rules - passed_rules

        error_count = sum(
            1
            for result in all_results
            if not result.passed and result.severity == "error"
        )
        warning_count = sum(
            1
            for result in all_results
            if not result.passed and result.severity == "warning"
        )

        validation_end = datetime.now()
        validation_duration = (validation_end - validation_start).total_seconds()

        # Prepare comprehensive report
        report = {
            "validation_summary": {
                "total_rules_checked": total_rules,
                "rules_passed": passed_rules,
                "rules_failed": failed_rules,
                "success_rate": passed_rules / total_rules if total_rules > 0 else 1.0,
                "error_count": error_count,
                "warning_count": warning_count,
                "validation_duration_seconds": validation_duration,
            },
            "data_summary": {
                "feature_shape": list(features.shape),
                "label_shape": list(labels.shape),
                "symbol_indices_shape": (
                    list(symbol_indices.shape) if symbol_indices is not None else None
                ),
                "num_features": features.shape[1] if features.dim() > 1 else 1,
                "num_samples": features.shape[0],
                "num_symbols": len(symbols) if symbols else None,
                "feature_dtype": str(features.dtype),
                "label_dtype": str(labels.dtype),
            },
            "validation_results": [result.to_dict() for result in all_results],
            "failed_validations": [
                result.to_dict() for result in all_results if not result.passed
            ],
            "auto_fixes_applied": fixes_applied if auto_fix else [],
            "recommendations": self._generate_recommendations(all_results),
        }

        # Log summary
        if error_count > 0:
            logger.error(
                f"Validation completed with {error_count} errors and {warning_count} warnings"
            )
        elif warning_count > 0:
            logger.warning(f"Validation completed with {warning_count} warnings")
        else:
            logger.info("Validation completed successfully - all checks passed")

        # Store in history
        self.validation_history.append(
            {"timestamp": validation_start.isoformat(), "report": report}
        )

        return report

    def _generate_recommendations(self, results: List[ValidationResult]) -> List[str]:
        """Generate actionable recommendations based on validation results."""
        recommendations = []

        # Check for common issues
        error_results = [r for r in results if not r.passed and r.severity == "error"]
        warning_results = [
            r for r in results if not r.passed and r.severity == "warning"
        ]

        if any(
            r.rule_name in ["no_infinite_values", "no_nan_values"]
            for r in error_results
        ):
            recommendations.append(
                "Critical data quality issues detected. Clean data before training."
            )

        if any(r.rule_name == "feature_variance_check" for r in warning_results):
            recommendations.append(
                "Remove low-variance features to improve model performance."
            )

        if any(r.rule_name == "label_distribution_check" for r in warning_results):
            recommendations.append(
                "Consider class balancing techniques for better model performance."
            )

        if any(r.rule_name == "symbol_balance_check" for r in warning_results):
            recommendations.append("Use symbol-balanced sampling during training.")

        if any(r.rule_name == "tensor_size_check" for r in warning_results):
            recommendations.append("Consider batch processing to manage memory usage.")

        if any(r.rule_name == "feature_range_check" for r in warning_results):
            recommendations.append(
                "Apply feature scaling/normalization before training."
            )

        return recommendations
