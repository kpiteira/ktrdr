"""
Central registry of error codes for the KTRDR application.

This module provides a centralized, organized registry of all error codes used
throughout the application. Error codes follow the pattern: CATEGORY-ErrorName

Categories:
- CONFIG: Configuration and validation errors
- STRATEGY: Strategy-specific validation errors
- DATA: Data loading, validation, and processing errors
- PROC: Processing and computation errors
- MODEL: Model training and inference errors
- MTFUZZ: Multi-timeframe fuzzy processing errors
- IB: Interactive Brokers connection and data errors
- TRAIN: Training pipeline errors

Usage:
    from ktrdr.errors.error_codes import ErrorCodes

    raise ConfigurationError(
        message="Strategy validation failed",
        error_code=ErrorCodes.STRATEGY_VALIDATION_FAILED,
        ...
    )
"""


class ErrorCodes:
    """Central registry of error codes for consistent error handling."""

    # Configuration errors
    CONFIG_LOAD_FAILED = "CONFIG-LoadFailed"
    CONFIG_INVALID_FORMAT = "CONFIG-InvalidFormat"
    CONFIG_MISSING_FIELD = "CONFIG-MissingField"
    CONFIG_VALIDATION_FAILED = "CONFIG-ValidationFailed"

    # Strategy validation errors
    STRATEGY_VALIDATION_FAILED = "STRATEGY-ValidationFailed"
    STRATEGY_FUZZY_MISMATCH = "STRATEGY-FuzzyMismatch"
    STRATEGY_INVALID_SCOPE = "STRATEGY-InvalidScope"

    # Indicator errors
    CONFIG_INDICATOR_CREATION_FAILED = "CONFIG-IndicatorCreationFailed"
    CONFIG_INDICATOR_INITIALIZATION_FAILED = "CONFIG-IndicatorInitializationFailed"
    CONFIG_INDICATOR_TYPE_NOT_FOUND = "CONFIG-IndicatorTypeNotFound"
    CONFIG_INDICATOR_INVALID_PARAMS = "CONFIG-IndicatorInvalidParams"

    # Data errors
    DATA_NOT_FOUND = "DATA-NotFound"
    DATA_INSUFFICIENT = "DATA-InsufficientData"
    DATA_MISSING_COLUMN = "DATA-MissingColumn"
    DATA_INVALID_FORMAT = "DATA-InvalidFormat"
    DATA_LOAD_FAILED = "DATA-LoadFailed"
    DATA_VALIDATION_FAILED = "DATA-ValidationFailed"
    DATA_GAP_DETECTED = "DATA-GapDetected"
    DATA_OUTLIER_DETECTED = "DATA-OutlierDetected"

    # Processing errors
    PROC_INDICATOR_FAILED = "PROC-IndicatorFailed"
    PROC_FUZZY_FAILED = "PROC-FuzzyFailed"
    PROC_FEATURE_CREATION_FAILED = "PROC-FeatureCreationFailed"
    PROC_LABEL_CREATION_FAILED = "PROC-LabelCreationFailed"

    # Multi-timeframe fuzzy processing errors
    MTFUZZ_NO_TIMEFRAMES = "MTFUZZ-NoTimeframes"
    MTFUZZ_NO_MATCHES = "MTFUZZ-NoMatches"
    MTFUZZ_CONFIG_ERROR = "MTFUZZ-ConfigError"
    MTFUZZ_ALL_TIMEFRAMES_FAILED = "MTFUZZ-AllTimeframesFailed"

    # Model errors
    MODEL_NOT_FOUND = "MODEL-NotFound"
    MODEL_LOAD_FAILED = "MODEL-LoadFailed"
    MODEL_SAVE_FAILED = "MODEL-SaveFailed"
    MODEL_INVALID_ARCHITECTURE = "MODEL-InvalidArchitecture"
    MODEL_TRAINING_FAILED = "MODEL-TrainingFailed"
    MODEL_INFERENCE_FAILED = "MODEL-InferenceFailed"

    # Training errors
    TRAIN_INSUFFICIENT_DATA = "TRAIN-InsufficientData"
    TRAIN_VALIDATION_SPLIT_FAILED = "TRAIN-ValidationSplitFailed"
    TRAIN_CONVERGENCE_FAILED = "TRAIN-ConvergenceFailed"
    TRAIN_GPU_ERROR = "TRAIN-GpuError"

    # IB Gateway errors
    IB_CONNECTION_FAILED = "IB-ConnectionFailed"
    IB_AUTHENTICATION_FAILED = "IB-AuthenticationFailed"
    IB_RATE_LIMIT = "IB-RateLimit"
    IB_NO_DATA = "IB-NoData"
    IB_TIMEOUT = "IB-Timeout"

    @classmethod
    def get_all_codes(cls) -> dict[str, str]:
        """
        Get all error codes as a dictionary.

        Returns:
            Dictionary mapping constant names to error code strings
        """
        return {
            name: value
            for name, value in vars(cls).items()
            if not name.startswith("_") and isinstance(value, str)
        }

    @classmethod
    def get_codes_by_category(cls, category: str) -> dict[str, str]:
        """
        Get all error codes for a specific category.

        Args:
            category: The category prefix (e.g., "STRATEGY", "DATA")

        Returns:
            Dictionary of error codes in that category
        """
        all_codes = cls.get_all_codes()
        return {
            name: code
            for name, code in all_codes.items()
            if code.startswith(f"{category}-")
        }

    @classmethod
    def validate_code(cls, code: str) -> bool:
        """
        Check if an error code is valid (exists in the registry).

        Args:
            code: The error code to validate

        Returns:
            True if the code exists in the registry
        """
        return code in cls.get_all_codes().values()
