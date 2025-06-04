"""ZigZag label generation for supervised learning.

This module generates "perfect" trading labels using forward-looking ZigZag indicator.
NOTE: This is "cheating" and only for training - not for live trading!
"""

import pandas as pd
import numpy as np
from typing import Tuple, Optional
from dataclasses import dataclass


@dataclass
class ZigZagConfig:
    """Configuration for ZigZag labeling."""
    threshold: float = 0.05  # 5% movement threshold
    lookahead: int = 20      # maximum bars to look ahead
    min_swing_length: int = 3  # minimum bars between reversals


class ZigZagLabeler:
    """Generate trading labels based on future price movements."""
    
    def __init__(self, threshold: float = 0.05, lookahead: int = 20, 
                 min_swing_length: int = 3):
        """Initialize the ZigZag labeler.
        
        Args:
            threshold: Minimum percentage move to consider significant
            lookahead: Maximum bars to look ahead for price movements
            min_swing_length: Minimum bars between swing points
        """
        self.threshold = threshold
        self.lookahead = lookahead
        self.min_swing_length = min_swing_length
        
    def generate_labels(self, price_data: pd.DataFrame) -> pd.Series:
        """Generate BUY/SELL/HOLD labels based on future price movements.
        
        Logic:
        - BUY (0): if price will rise by threshold% within lookahead period
        - SELL (2): if price will fall by threshold% within lookahead period  
        - HOLD (1): if no significant movement or mixed signals
        
        Args:
            price_data: DataFrame with OHLCV data
            
        Returns:
            Series of labels (0=BUY, 1=HOLD, 2=SELL)
        """
        if 'close' not in price_data.columns:
            raise ValueError("price_data must contain 'close' column")
        
        labels = pd.Series(1, index=price_data.index, dtype=int)  # Default to HOLD (1)
        close_prices = price_data['close']
        
        for i in range(len(close_prices) - self.lookahead):
            current_price = close_prices.iloc[i]
            future_window = close_prices.iloc[i+1:i+self.lookahead+1]
            
            if len(future_window) == 0:
                continue
            
            # Calculate maximum gain and loss in future window
            max_gain = (future_window.max() - current_price) / current_price
            max_loss = (current_price - future_window.min()) / current_price
            
            # Find where these extremes occur
            max_gain_idx = future_window.idxmax()
            max_loss_idx = future_window.idxmin()
            
            # Label based on significant movements
            if max_gain >= self.threshold and max_gain > max_loss:
                # Additional check: ensure gain happens before any significant loss
                bars_to_max = len(close_prices.loc[close_prices.index[i]:max_gain_idx]) - 1
                if bars_to_max >= self.min_swing_length:
                    labels.iloc[i] = 0  # BUY
            elif max_loss >= self.threshold and max_loss > max_gain:
                # Additional check: ensure loss happens before any significant gain
                bars_to_min = len(close_prices.loc[close_prices.index[i]:max_loss_idx]) - 1
                if bars_to_min >= self.min_swing_length:
                    labels.iloc[i] = 2  # SELL
            # else: HOLD (already set to 1)
            
        return labels
    
    def generate_segment_labels(self, price_data: pd.DataFrame) -> pd.Series:
        """Generate BALANCED BUY/SELL/HOLD labels using ZigZag segment approach.
        
        This creates much more balanced training data by labeling entire trend segments
        instead of just extreme points. This should fix the class imbalance problem
        that causes neural network collapse.
        
        Logic:
        1. Find ZigZag extremes using threshold
        2. Label entire segments between extremes as BUY (upward) or SELL (downward)
        3. Only keep extremes themselves as HOLD (transition points)
        
        Args:
            price_data: DataFrame with OHLCV data
            
        Returns:
            Series of labels (0=BUY, 1=HOLD, 2=SELL) with better class balance
        """
        from ..indicators.zigzag_indicator import ZigZagIndicator
        
        if 'close' not in price_data.columns:
            raise ValueError("price_data must contain 'close' column")
        
        # Use ZigZag indicator to find extremes
        zigzag = ZigZagIndicator(threshold=self.threshold)
        return zigzag.get_zigzag_segment_labels(price_data)
    
    def generate_fitness_labels(self, price_data: pd.DataFrame) -> pd.DataFrame:
        """Generate labels with additional fitness metrics for evaluation.
        
        Args:
            price_data: DataFrame with OHLCV data
            
        Returns:
            DataFrame with labels and expected returns
        """
        labels = self.generate_labels(price_data)
        close_prices = price_data['close']
        
        # Calculate actual returns for each label
        returns = []
        max_returns = []
        time_to_target = []
        
        for i in range(len(labels)):
            if i >= len(close_prices) - self.lookahead:
                returns.append(0)
                max_returns.append(0)
                time_to_target.append(self.lookahead)
                continue
                
            current_price = close_prices.iloc[i]
            future_window = close_prices.iloc[i+1:i+self.lookahead+1]
            
            if labels.iloc[i] == 0:  # BUY label
                # Find best exit point
                best_exit_idx = future_window.idxmax()
                best_exit_price = future_window.max()
                actual_return = (best_exit_price - current_price) / current_price
                
                # Time to reach threshold
                for j, price in enumerate(future_window):
                    if (price - current_price) / current_price >= self.threshold:
                        time_to_target.append(j + 1)
                        break
                else:
                    time_to_target.append(self.lookahead)
                    
                returns.append(actual_return)
                max_returns.append(actual_return)
                
            elif labels.iloc[i] == 2:  # SELL label  
                # For SELL, we calculate as if we shorted
                worst_exit_idx = future_window.idxmin()
                worst_exit_price = future_window.min()
                actual_return = (current_price - worst_exit_price) / current_price
                
                # Time to reach threshold
                for j, price in enumerate(future_window):
                    if (current_price - price) / current_price >= self.threshold:
                        time_to_target.append(j + 1)
                        break
                else:
                    time_to_target.append(self.lookahead)
                    
                returns.append(actual_return)
                max_returns.append(actual_return)
                
            else:  # HOLD
                returns.append(0)
                max_returns.append(0)
                time_to_target.append(self.lookahead)
        
        return pd.DataFrame({
            'label': labels,
            'expected_return': returns,
            'max_return': max_returns,
            'time_to_target': time_to_target,
            'timestamp': price_data.index
        })
    
    def get_label_distribution(self, labels: pd.Series) -> dict:
        """Get distribution statistics for generated labels.
        
        Args:
            labels: Series of labels
            
        Returns:
            Dictionary with label counts and percentages
        """
        counts = labels.value_counts().sort_index()
        total = len(labels)
        
        distribution = {
            'buy_count': int(counts.get(0, 0)),
            'hold_count': int(counts.get(1, 0)),
            'sell_count': int(counts.get(2, 0)),
            'buy_pct': float(counts.get(0, 0) / total * 100),
            'hold_pct': float(counts.get(1, 0) / total * 100),
            'sell_pct': float(counts.get(2, 0) / total * 100),
            'total': total
        }
        
        return distribution