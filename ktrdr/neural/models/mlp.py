"""Multi-Layer Perceptron implementation for trading decisions."""

import torch
import torch.nn as nn
import torch.nn.functional as F
import numpy as np
import pandas as pd
from typing import Dict, Any, List, Optional

from .base_model import BaseNeuralModel


class MLPTradingModel(BaseNeuralModel):
    """Multi-Layer Perceptron for neuro-fuzzy trading strategies."""
    
    def build_model(self, input_size: int) -> nn.Module:
        """Build MLP with configurable architecture.
        
        Args:
            input_size: Number of input features
            
        Returns:
            Sequential neural network model
        """
        self.input_size = input_size
        layers = []
        
        # Get architecture config
        hidden_layers = self.config['architecture']['hidden_layers']
        dropout = self.config['architecture'].get('dropout', 0.2)
        activation = self.config['architecture'].get('activation', 'relu')
        
        # Map activation functions
        activation_fn = {
            'relu': nn.ReLU,
            'tanh': nn.Tanh,
            'sigmoid': nn.Sigmoid,
            'leaky_relu': nn.LeakyReLU
        }.get(activation.lower(), nn.ReLU)
        
        # Build layers
        prev_size = input_size
        for hidden_size in hidden_layers:
            layers.extend([
                nn.Linear(prev_size, hidden_size),
                activation_fn(),
                nn.Dropout(dropout)
            ])
            prev_size = hidden_size
        
        # Output layer (3 classes: BUY=0, HOLD=1, SELL=2)
        layers.append(nn.Linear(prev_size, 3))
        
        # Use softmax for output activation
        output_activation = self.config['architecture'].get('output_activation', 'softmax')
        if output_activation.lower() == 'softmax':
            layers.append(nn.Softmax(dim=1))
        
        return nn.Sequential(*layers)
    
    def prepare_features(self, fuzzy_data: pd.DataFrame, 
                        indicators: pd.DataFrame) -> torch.Tensor:
        """Create feature vector from fuzzy memberships and context.
        
        Args:
            fuzzy_data: DataFrame with fuzzy membership values
            indicators: DataFrame with raw indicator values
            
        Returns:
            Tensor of prepared features
        """
        features = []
        
        # Core fuzzy membership values
        fuzzy_columns = [col for col in fuzzy_data.columns if 'membership' in col.lower()]
        for column in fuzzy_columns:
            if column in fuzzy_data.columns:
                features.append(fuzzy_data[column].values)
        
        # Price context features (if enabled)
        if self.config.get('features', {}).get('include_price_context', False):
            # Current price relative to SMA
            if 'close' in indicators.columns and 'sma_20' in indicators.columns:
                price_ratio = indicators['close'] / indicators['sma_20']
                features.append(price_ratio.values)
            
            # Price momentum (rate of change)
            if 'close' in indicators.columns:
                roc = indicators['close'].pct_change(5).fillna(0)
                features.append(roc.values)
        
        # Volume context (if enabled)
        if self.config.get('features', {}).get('include_volume_context', False):
            if 'volume' in indicators.columns:
                # Volume relative to average
                volume_sma = indicators['volume'].rolling(20).mean()
                volume_ratio = indicators['volume'] / volume_sma.fillna(indicators['volume'])
                features.append(volume_ratio.values)
        
        # Lookback features (temporal context)
        lookback = self.config.get('features', {}).get('lookback_periods', 1)
        if lookback > 1:
            # Add lagged fuzzy values
            for i in range(1, lookback):
                for column in fuzzy_columns:
                    if column in fuzzy_data.columns:
                        shifted = fuzzy_data[column].shift(i).fillna(0.5)  # 0.5 = neutral
                        features.append(shifted.values)
        
        # Stack all features
        if not features:
            raise ValueError("No features could be extracted from the data")
        
        feature_matrix = np.column_stack(features)
        
        # Handle NaN values
        feature_matrix = np.nan_to_num(feature_matrix, nan=0.0)
        
        # Convert to tensor
        return torch.FloatTensor(feature_matrix)
    
    def train(self, X: torch.Tensor, y: torch.Tensor, 
              validation_data: Optional[tuple] = None) -> Dict[str, Any]:
        """Train the MLP model.
        
        Args:
            X: Training features
            y: Training labels (0=BUY, 1=HOLD, 2=SELL)
            validation_data: Optional (X_val, y_val) tuple
            
        Returns:
            Training history dictionary
        """
        if self.model is None:
            raise ValueError("Model not built. Call build_model() first.")
        
        # Get training parameters
        training_config = self.config.get('training', {})
        learning_rate = training_config.get('learning_rate', 0.001)
        batch_size = training_config.get('batch_size', 32)
        epochs = training_config.get('epochs', 100)
        
        # Setup optimizer and loss
        optimizer_name = training_config.get('optimizer', 'adam').lower()
        if optimizer_name == 'adam':
            optimizer = torch.optim.Adam(self.model.parameters(), lr=learning_rate)
        elif optimizer_name == 'sgd':
            optimizer = torch.optim.SGD(self.model.parameters(), lr=learning_rate, momentum=0.9)
        else:
            optimizer = torch.optim.Adam(self.model.parameters(), lr=learning_rate)
        
        criterion = nn.CrossEntropyLoss()
        
        # Training history
        history = {
            'train_loss': [],
            'train_accuracy': [],
            'val_loss': [],
            'val_accuracy': []
        }
        
        # Convert labels to LongTensor for CrossEntropyLoss
        y = y.long()
        
        # Simple training loop (placeholder - would be more sophisticated in production)
        self.model.train()
        for epoch in range(epochs):
            # Forward pass
            outputs = self.model(X)
            loss = criterion(outputs, y)
            
            # Backward pass
            optimizer.zero_grad()
            loss.backward()
            optimizer.step()
            
            # Calculate accuracy
            _, predicted = torch.max(outputs.data, 1)
            accuracy = (predicted == y).float().mean()
            
            history['train_loss'].append(float(loss))
            history['train_accuracy'].append(float(accuracy))
            
            # Validation
            if validation_data is not None:
                X_val, y_val = validation_data
                y_val = y_val.long()
                
                self.model.eval()
                with torch.no_grad():
                    val_outputs = self.model(X_val)
                    val_loss = criterion(val_outputs, y_val)
                    _, val_predicted = torch.max(val_outputs.data, 1)
                    val_accuracy = (val_predicted == y_val).float().mean()
                
                history['val_loss'].append(float(val_loss))
                history['val_accuracy'].append(float(val_accuracy))
                
                self.model.train()
        
        self.is_trained = True
        return history