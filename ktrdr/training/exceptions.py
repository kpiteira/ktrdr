"""Pipeline exception types for infrastructure errors.

These exceptions represent bugs to fix, not experiments to learn from.
They should fail operations visibly so issues can be diagnosed and resolved.

Infrastructure errors (raise these):
- Data pipeline failures (no test data, empty features)
- Configuration mismatches (multi-symbol/multi-timeframe issues)
- Model loading failures

NOT infrastructure errors (don't use these for):
- Poor model performance (that's an experiment result)
- Gate rejections (that's valid experiment data)
"""


class PipelineError(Exception):
    """Base class for pipeline infrastructure errors.

    These are bugs to fix, not experiments to learn from.
    They should fail operations visibly.

    Use this base class when catching any pipeline error,
    or when raising an error that doesn't fit a more specific subclass.
    """


class TrainingDataError(PipelineError):
    """Raised when training cannot produce valid data.

    Examples:
    - X_test is None (data pipeline failed)
    - Feature alignment produced empty result
    - Train/test split failed
    - Multi-symbol data combination failed

    This indicates the training pipeline has a bug or configuration issue,
    not that the experiment had poor results.
    """


class BacktestDataError(PipelineError):
    """Raised when backtest cannot run due to data issues.

    Examples:
    - No price data for symbol
    - Feature mismatch between training and backtest
    - Date range has no data
    - Required indicators missing

    This indicates the backtest infrastructure has an issue,
    not that the strategy performed poorly.
    """


class ModelLoadError(PipelineError):
    """Raised when model cannot be loaded for backtest.

    Examples:
    - Model file not found
    - Model format incompatible
    - Model metadata missing or corrupt
    - Feature names don't match

    This indicates model storage/loading has an issue,
    not that the model is bad.
    """
