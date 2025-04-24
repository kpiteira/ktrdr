# Adding New Indicators to KTRDR

This document provides a comprehensive guide for adding new technical indicators to the KTRDR system with integrated testing.

## Overview

The KTRDR system has a built-in validation framework that allows all indicators to be automatically tested against reference values. When you add a new indicator, you should follow this process to ensure it's properly integrated with the testing system.

## Step-by-Step Guide

### 1. Create Your Indicator Class

Start by creating a new module file for your indicator in the `ktrdr/indicators` directory:

```python
# ktrdr/indicators/my_indicator.py

import pandas as pd
import numpy as np
from typing import Union, Optional

from ktrdr import get_logger
from ktrdr.errors import DataError
from ktrdr.indicators.base_indicator import BaseIndicator

logger = get_logger(__name__)


class MyNewIndicator(BaseIndicator):
    """
    Your indicator description here.
    """
    
    def __init__(self, period: int = 14, source: str = 'close', other_param: float = 0.5):
        """Initialize your indicator."""
        super().__init__(name="MY_INDICATOR", period=period, source=source, other_param=other_param)
        logger.debug(f"Initialized {self.name} indicator with parameters: {self.params}")
    
    def _validate_params(self, params):
        """Validate parameters for your indicator."""
        # Parameter validation logic
        # ...
        return params
    
    def compute(self, df: pd.DataFrame) -> pd.Series:
        """Compute your indicator."""
        # Validate input data
        source = self.params['source']
        period = self.params['period']
        self.validate_input_data(df, [source])
        self.validate_sufficient_data(df, period)
        
        try:
            # Your indicator calculation logic
            # ...
            
            # Example result (replace with actual calculation)
            result = df[source].rolling(window=period).mean()
            
            # Set the name for the result Series
            result.name = self.get_column_name()
            return result
            
        except Exception as e:
            error_msg = f"Error calculating {self.name}: {str(e)}"
            logger.error(error_msg)
            raise DataError(
                message=error_msg,
                error_code="DATA-CalculationError",
                details={"indicator": self.name, "error": str(e)}
            ) from e
```

> **Tip**: You can use the template file at `ktrdr/indicators/indicator_template.py` as a starting point.

### 2. Update the Indicators Package

Add your indicator to the package exports in `ktrdr/indicators/__init__.py`:

```python
from .base_indicator import BaseIndicator
from .ma_indicators import SimpleMovingAverage, ExponentialMovingAverage
from .rsi_indicator import RSIIndicator
from .my_indicator import MyNewIndicator  # Add your indicator here

__all__ = [
    'BaseIndicator',
    'SimpleMovingAverage',
    'ExponentialMovingAverage',
    'RSIIndicator',
    'MyNewIndicator'  # Add your indicator here
]
```

### 3. Create Reference Values

To test your indicator, you need to define reference values - these are known values that your indicator should produce for specific datasets:

1. Determine what values your indicator should produce for the reference datasets
2. Add these values to `tests/indicators/reference_datasets.py`:

```python
# Define reference values for your indicator
MY_INDICATOR_REFERENCE_DATASET_1 = {
    # For period=14
    'MY_INDICATOR_14': {
        13: 105.0,  # Expected value at index 13
        19: 110.0,  # Expected value at index 19
        29: 105.0,  # Expected value at index 29
        # Add more reference points
    }
}

# Update the main REFERENCE_VALUES dictionary
REFERENCE_VALUES = {
    # Existing indicators...
    'SMA': {...},
    'EMA': {...},
    'RSI': {...},
    
    # Add your indicator
    'MY_INDICATOR': {
        'dataset_1': MY_INDICATOR_REFERENCE_DATASET_1,
    }
}

# Update the TOLERANCES dictionary to define acceptable deviation
TOLERANCES = {
    # Existing indicators...
    'SMA': 0.5,
    'EMA': 5.0,
    'RSI': 5.0,
    
    # Add your indicator's tolerance
    'MY_INDICATOR': 1.0,  # 1% tolerance for your indicator
}
```

### 4. Register Your Indicator for Testing

Register your indicator in the indicator registry to enable automated testing:

1. Open `tests/indicators/indicator_registry.py`
2. Add your indicator to the `register_builtin_indicators()` function:

```python
def register_builtin_indicators():
    """Register all built-in indicators with their validation parameters."""
    from ktrdr.indicators import (
        SimpleMovingAverage,
        ExponentialMovingAverage,
        RSIIndicator,
        MyNewIndicator  # Import your indicator
    )
    
    from .reference_datasets import (
        REFERENCE_VALUES,
        TOLERANCES
    )
    
    # Existing indicators...
    
    # Register your indicator
    register_indicator(
        indicator_class=MyNewIndicator,
        default_params={'period': 14, 'source': 'close', 'other_param': 0.5},
        reference_datasets=['reference_dataset_1'],
        reference_values=REFERENCE_VALUES.get('MY_INDICATOR', {}),
        tolerance=TOLERANCES.get('MY_INDICATOR', 1.0)
    )
```

### 5. Run the Tests

After you've implemented your indicator and registered it for testing, run the tests to ensure it works correctly:

```bash
# Run just the tests for your indicator
pytest tests/indicators/test_all_indicators.py::TestAutomatedIndicatorValidation::test_indicator_against_references[MyNewIndicator] -v

# Run all indicator tests
pytest tests/indicators/
```

## Special Considerations

### Specialized Edge Cases

If your indicator has specific edge cases that need special testing, you can add them to the registration:

```python
register_indicator(
    indicator_class=MyNewIndicator,
    # ...other parameters...
    known_edge_cases=[
        {
            'name': 'constant_values',
            'data': pd.DataFrame({'close': [100] * 20}),
            'should_raise': False,
            'expected_values': {14: 50.0}  # Expected output at index 14
        }
    ]
)
```

### Using Different Reference Datasets

If your indicator requires specific data patterns for testing, you can:

1. Create a custom reference dataset in `tests/indicators/reference_datasets.py`
2. Register this dataset in the `DATASET_CREATORS` dictionary in `tests/indicators/test_all_indicators.py`

## Validation Process

The testing framework follows this process:

1. Creates an instance of your indicator with default parameters
2. Generates the reference datasets
3. Computes your indicator on these datasets
4. Compares the results against your defined reference values
5. Checks that the deviation between actual and expected values is within tolerance
6. Tests your indicator against common edge cases
7. Verifies basic properties expected of all indicators

Your indicator must pass all these validations to be considered correctly implemented.

## Best Practices

- **Provide Comprehensive Reference Values**: Include reference values for various parts of your indicator's output (beginning, middle, end)
- **Test Multiple Parameter Configurations**: If your indicator has important parameters, register multiple versions with different configurations
- **Document Your Algorithm**: Include clear documentation about how your indicator is calculated
- **Include Edge Cases**: Make sure your indicator correctly handles extreme scenarios like constant values, all zeros, etc.
- **Optimize Performance**: For computationally intensive indicators, consider using vectorized operations

By following this guide, you'll ensure that your indicator is properly integrated with KTRDR's testing framework and will be automatically validated against any future changes.