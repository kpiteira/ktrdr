"""
Membership function definitions for fuzzy logic.

This module defines the abstract base class for membership functions
and implements the triangular membership function for Phase 1.
"""

from abc import ABC, abstractmethod
from typing import List, Union

import numpy as np
import pandas as pd

from ktrdr.errors import ConfigurationError
from ktrdr import get_logger

# Set up module-level logger
logger = get_logger(__name__)


class MembershipFunction(ABC):
    """
    Abstract base class for fuzzy membership functions.
    
    All membership functions must implement the evaluate method
    that converts input values to membership degrees.
    """
    
    @abstractmethod
    def evaluate(self, x: Union[float, pd.Series, np.ndarray]) -> Union[float, pd.Series, np.ndarray]:
        """
        Evaluate the membership function for a given input.
        
        Args:
            x: Input value(s) to evaluate
            
        Returns:
            Membership degree(s) in the range [0, 1]
        """
        pass


# Note: Actual implementation of TriangularMF will be done in Task 4.2