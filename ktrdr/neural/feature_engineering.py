"""
Advanced feature engineering for multi-timeframe neural networks.

This module provides comprehensive feature engineering capabilities including
multi-timeframe feature scaling, dimensionality reduction, and feature
importance analysis for neuro-fuzzy trading systems.
"""

import numpy as np
import pandas as pd
from typing import Dict, Any, List, Optional, Tuple, Union
from dataclasses import dataclass
from sklearn.preprocessing import StandardScaler, MinMaxScaler, RobustScaler, QuantileTransformer
from sklearn.feature_selection import SelectKBest, f_classif, mutual_info_classif, RFE
from sklearn.decomposition import PCA, FastICA, TruncatedSVD
from sklearn.ensemble import RandomForestClassifier
from sklearn.discriminant_analysis import LinearDiscriminantAnalysis
import warnings

from ktrdr import get_logger

# Set up module-level logger
logger = get_logger(__name__)


@dataclass
class FeatureStats:
    """Statistics for a feature across multiple timeframes."""
    mean: float
    std: float
    min_val: float
    max_val: float
    percentile_25: float
    percentile_75: float
    skewness: float
    correlation_with_target: Optional[float] = None


@dataclass
class FeatureEngineeringResult:
    """Result of feature engineering process."""
    transformed_features: np.ndarray
    feature_names: List[str]
    selected_features_mask: Optional[np.ndarray] = None
    scaler: Optional[Any] = None
    dimensionality_reducer: Optional[Any] = None
    feature_importance: Optional[Dict[str, float]] = None
    feature_stats: Optional[Dict[str, FeatureStats]] = None
    transformation_metadata: Dict[str, Any] = None


class MultiTimeframeFeatureEngineer:
    """
    Advanced feature engineering for multi-timeframe neuro-fuzzy systems.
    
    This class provides comprehensive feature engineering capabilities including:
    - Multi-timeframe feature scaling with multiple scaler types
    - Feature selection using various algorithms
    - Dimensionality reduction techniques
    - Feature importance analysis
    - Cross-timeframe feature correlation analysis
    """
    
    def __init__(self, config: Dict[str, Any]):
        """
        Initialize the feature engineer.
        
        Args:
            config: Feature engineering configuration containing:
                - scaling: Scaling method and parameters
                - selection: Feature selection method and parameters
                - dimensionality_reduction: Dimensionality reduction settings
                - analysis: Feature analysis settings
        """
        self.config = config
        self.scaler = None
        self.feature_selector = None
        self.dimensionality_reducer = None
        self.feature_names = []
        self.selected_feature_names = []
        self.is_fitted = False
        
        logger.info("Initialized MultiTimeframeFeatureEngineer")
    
    def fit_transform(
        self,
        features: Dict[str, np.ndarray],
        labels: Optional[np.ndarray] = None,
        timeframe_weights: Optional[Dict[str, float]] = None
    ) -> FeatureEngineeringResult:
        """
        Fit the feature engineering pipeline and transform features.
        
        Args:
            features: Dictionary mapping timeframes to feature arrays
            labels: Optional target labels for supervised feature selection
            timeframe_weights: Optional weights for each timeframe
            
        Returns:
            FeatureEngineeringResult with transformed features and metadata
        """
        logger.info(f"Fitting feature engineering pipeline for {len(features)} timeframes")
        
        # Combine features from all timeframes
        combined_features, feature_names = self._combine_timeframe_features(
            features, timeframe_weights
        )
        
        self.feature_names = feature_names
        
        # Calculate feature statistics
        feature_stats = self._calculate_feature_stats(combined_features, feature_names, labels)
        
        # Apply scaling
        scaled_features, scaler = self._apply_scaling(combined_features)
        
        # Apply feature selection
        selected_features, selected_mask, feature_selector = self._apply_feature_selection(
            scaled_features, labels, feature_names
        )
        
        # Apply dimensionality reduction
        reduced_features, dimensionality_reducer = self._apply_dimensionality_reduction(
            selected_features
        )
        
        # Calculate feature importance
        feature_importance = self._calculate_feature_importance(
            selected_features, labels, self.selected_feature_names
        )
        
        # Store for get_feature_ranking method
        self.feature_importance = feature_importance
        
        # Store fitted components
        self.scaler = scaler
        self.feature_selector = feature_selector
        self.dimensionality_reducer = dimensionality_reducer
        self.is_fitted = True
        
        # Create transformation metadata
        transformation_metadata = {
            "original_feature_count": len(feature_names),
            "selected_feature_count": len(self.selected_feature_names),
            "final_feature_count": reduced_features.shape[1],
            "scaling_method": self.config.get("scaling", {}).get("method", "standard"),
            "selection_method": self.config.get("selection", {}).get("method", "none"),
            "reduction_method": self.config.get("dimensionality_reduction", {}).get("method", "none"),
            "timeframes": list(features.keys())
        }
        
        logger.info(f"Feature engineering complete: {transformation_metadata['original_feature_count']} -> "
                   f"{transformation_metadata['selected_feature_count']} -> "
                   f"{transformation_metadata['final_feature_count']} features")
        
        return FeatureEngineeringResult(
            transformed_features=reduced_features,
            feature_names=self._get_final_feature_names(reduced_features.shape[1]),
            selected_features_mask=selected_mask,
            scaler=scaler,
            dimensionality_reducer=dimensionality_reducer,
            feature_importance=feature_importance,
            feature_stats=feature_stats,
            transformation_metadata=transformation_metadata
        )
    
    def transform(self, features: Dict[str, np.ndarray]) -> np.ndarray:
        """
        Transform new features using fitted pipeline.
        
        Args:
            features: Dictionary mapping timeframes to feature arrays
            
        Returns:
            Transformed feature array
            
        Raises:
            ValueError: If pipeline is not fitted
        """
        if not self.is_fitted:
            raise ValueError("Feature engineering pipeline not fitted. Call fit_transform() first.")
        
        # Combine features from all timeframes
        combined_features, _ = self._combine_timeframe_features(features)
        
        # Apply scaling
        if self.scaler is not None:
            scaled_features = self.scaler.transform(combined_features)
        else:
            scaled_features = combined_features
        
        # Apply feature selection
        if self.feature_selector is not None:
            selected_features = self.feature_selector.transform(scaled_features)
        else:
            selected_features = scaled_features
        
        # Apply dimensionality reduction
        if self.dimensionality_reducer is not None:
            reduced_features = self.dimensionality_reducer.transform(selected_features)
        else:
            reduced_features = selected_features
        
        return reduced_features
    
    def _combine_timeframe_features(
        self,
        features: Dict[str, np.ndarray],
        timeframe_weights: Optional[Dict[str, float]] = None
    ) -> Tuple[np.ndarray, List[str]]:
        """Combine features from multiple timeframes into a single array."""
        if not features:
            raise ValueError("No features provided")
        
        combined_arrays = []
        feature_names = []
        
        # Sort timeframes for consistent ordering
        timeframe_order = self._get_timeframe_order(list(features.keys()))
        
        for timeframe in timeframe_order:
            if timeframe not in features:
                continue
            
            tf_features = features[timeframe]
            weight = timeframe_weights.get(timeframe, 1.0) if timeframe_weights else 1.0
            
            # Apply timeframe weight
            if weight != 1.0:
                tf_features = tf_features * weight
            
            combined_arrays.append(tf_features)
            
            # Generate feature names for this timeframe
            num_features = tf_features.shape[1] if tf_features.ndim > 1 else 1
            for i in range(num_features):
                feature_names.append(f"feature_{i}_{timeframe}")
        
        # Combine all features
        if len(combined_arrays) == 1:
            combined_features = combined_arrays[0]
        else:
            combined_features = np.concatenate(combined_arrays, axis=1)
        
        logger.debug(f"Combined features shape: {combined_features.shape}")
        return combined_features, feature_names
    
    def _get_timeframe_order(self, timeframes: List[str]) -> List[str]:
        """Get consistent timeframe ordering (shortest to longest)."""
        timeframe_priority = {
            "1m": 1, "5m": 2, "15m": 3, "30m": 4,
            "1h": 5, "2h": 6, "4h": 7, "6h": 8, "8h": 9,
            "12h": 10, "1d": 11, "3d": 12, "1w": 13, "1M": 14
        }
        
        return sorted(timeframes, key=lambda tf: timeframe_priority.get(tf, 999))
    
    def _calculate_feature_stats(
        self,
        features: np.ndarray,
        feature_names: List[str],
        labels: Optional[np.ndarray] = None
    ) -> Dict[str, FeatureStats]:
        """Calculate comprehensive statistics for each feature."""
        feature_stats = {}
        
        for i, feature_name in enumerate(feature_names):
            feature_values = features[:, i]
            
            # Calculate correlation with target if labels provided
            correlation = None
            if labels is not None:
                try:
                    correlation = float(np.corrcoef(feature_values, labels)[0, 1])
                    if np.isnan(correlation):
                        correlation = 0.0
                except:
                    correlation = 0.0
            
            # Calculate skewness
            mean_val = float(np.mean(feature_values))
            std_val = float(np.std(feature_values))
            if std_val > 0:
                skewness = float(np.mean(((feature_values - mean_val) / std_val) ** 3))
            else:
                skewness = 0.0
            
            feature_stats[feature_name] = FeatureStats(
                mean=mean_val,
                std=std_val,
                min_val=float(np.min(feature_values)),
                max_val=float(np.max(feature_values)),
                percentile_25=float(np.percentile(feature_values, 25)),
                percentile_75=float(np.percentile(feature_values, 75)),
                skewness=skewness,
                correlation_with_target=correlation
            )
        
        return feature_stats
    
    def _apply_scaling(self, features: np.ndarray) -> Tuple[np.ndarray, Optional[Any]]:
        """Apply feature scaling based on configuration."""
        scaling_config = self.config.get("scaling", {})
        method = scaling_config.get("method", "standard").lower()
        
        if method == "none":
            return features, None
        
        # Choose scaler
        if method == "standard":
            scaler = StandardScaler()
        elif method == "minmax":
            scaler = MinMaxScaler(
                feature_range=scaling_config.get("feature_range", (0, 1))
            )
        elif method == "robust":
            scaler = RobustScaler(
                quantile_range=scaling_config.get("quantile_range", (25.0, 75.0))
            )
        elif method == "quantile":
            scaler = QuantileTransformer(
                n_quantiles=scaling_config.get("n_quantiles", 1000),
                output_distribution=scaling_config.get("output_distribution", "uniform")
            )
        else:
            logger.warning(f"Unknown scaling method: {method}, using standard")
            scaler = StandardScaler()
        
        # Fit and transform
        try:
            scaled_features = scaler.fit_transform(features)
            logger.debug(f"Applied {method} scaling")
            return scaled_features, scaler
        except Exception as e:
            logger.error(f"Scaling failed: {e}")
            return features, None
    
    def _apply_feature_selection(
        self,
        features: np.ndarray,
        labels: Optional[np.ndarray],
        feature_names: List[str]
    ) -> Tuple[np.ndarray, Optional[np.ndarray], Optional[Any]]:
        """Apply feature selection based on configuration."""
        selection_config = self.config.get("selection", {})
        method = selection_config.get("method", "none").lower()
        
        if method == "none" or labels is None:
            self.selected_feature_names = feature_names.copy()
            return features, None, None
        
        try:
            # Choose feature selector
            if method == "kbest_f":
                k = min(selection_config.get("k", 20), features.shape[1])
                selector = SelectKBest(score_func=f_classif, k=k)
            elif method == "kbest_mutual_info":
                k = min(selection_config.get("k", 20), features.shape[1])
                selector = SelectKBest(score_func=mutual_info_classif, k=k)
            elif method == "rfe":
                estimator = RandomForestClassifier(
                    n_estimators=selection_config.get("n_estimators", 50),
                    random_state=42
                )
                n_features = min(selection_config.get("n_features", 20), features.shape[1])
                selector = RFE(estimator=estimator, n_features_to_select=n_features)
            elif method == "variance_threshold":
                from sklearn.feature_selection import VarianceThreshold
                threshold = selection_config.get("threshold", 0.01)
                selector = VarianceThreshold(threshold=threshold)
            else:
                logger.warning(f"Unknown selection method: {method}")
                self.selected_feature_names = feature_names.copy()
                return features, None, None
            
            # Fit and transform
            selected_features = selector.fit_transform(features, labels)
            selected_mask = selector.get_support()
            
            # Update selected feature names
            self.selected_feature_names = [
                name for name, selected in zip(feature_names, selected_mask) if selected
            ]
            
            logger.debug(f"Selected {len(self.selected_feature_names)} features using {method}")
            return selected_features, selected_mask, selector
            
        except Exception as e:
            logger.error(f"Feature selection failed: {e}")
            self.selected_feature_names = feature_names.copy()
            return features, None, None
    
    def _apply_dimensionality_reduction(
        self,
        features: np.ndarray
    ) -> Tuple[np.ndarray, Optional[Any]]:
        """Apply dimensionality reduction based on configuration."""
        reduction_config = self.config.get("dimensionality_reduction", {})
        method = reduction_config.get("method", "none").lower()
        
        if method == "none":
            return features, None
        
        try:
            # Choose dimensionality reducer
            if method == "pca":
                n_components = min(
                    reduction_config.get("n_components", 10),
                    features.shape[1],
                    features.shape[0] - 1
                )
                reducer = PCA(n_components=n_components)
            elif method == "ica":
                n_components = min(
                    reduction_config.get("n_components", 10),
                    features.shape[1]
                )
                reducer = FastICA(
                    n_components=n_components,
                    random_state=42,
                    max_iter=reduction_config.get("max_iter", 200)
                )
            elif method == "lda":
                n_components = min(
                    reduction_config.get("n_components", 2),
                    features.shape[1],
                    len(np.unique(labels)) - 1 if labels is not None else features.shape[1]
                )
                reducer = LinearDiscriminantAnalysis(n_components=n_components)
            elif method == "svd":
                n_components = min(
                    reduction_config.get("n_components", 10),
                    features.shape[1],
                    features.shape[0] - 1
                )
                reducer = TruncatedSVD(n_components=n_components, random_state=42)
            else:
                logger.warning(f"Unknown reduction method: {method}")
                return features, None
            
            # Fit and transform
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                reduced_features = reducer.fit_transform(features)
            
            logger.debug(f"Reduced features from {features.shape[1]} to {reduced_features.shape[1]} using {method}")
            return reduced_features, reducer
            
        except Exception as e:
            logger.error(f"Dimensionality reduction failed: {e}")
            return features, None
    
    def _calculate_feature_importance(
        self,
        features: np.ndarray,
        labels: Optional[np.ndarray],
        feature_names: List[str]
    ) -> Optional[Dict[str, float]]:
        """Calculate feature importance using multiple methods."""
        if labels is None or len(feature_names) == 0:
            return None
        
        try:
            # Use Random Forest for feature importance
            rf = RandomForestClassifier(n_estimators=100, random_state=42)
            rf.fit(features, labels)
            
            importances = rf.feature_importances_
            feature_importance = {
                name: float(importance) 
                for name, importance in zip(feature_names, importances)
            }
            
            logger.debug(f"Calculated feature importance for {len(feature_names)} features")
            return feature_importance
            
        except Exception as e:
            logger.error(f"Feature importance calculation failed: {e}")
            return None
    
    def _get_final_feature_names(self, num_features: int) -> List[str]:
        """Generate final feature names after all transformations."""
        if self.dimensionality_reducer is not None:
            # If dimensionality reduction was applied, use generic names
            reducer_name = self.dimensionality_reducer.__class__.__name__.lower()
            return [f"{reducer_name}_component_{i}" for i in range(num_features)]
        else:
            # Use selected feature names
            return self.selected_feature_names[:num_features]
    
    def get_feature_ranking(self) -> Optional[List[Tuple[str, float]]]:
        """
        Get feature ranking based on importance scores.
        
        Returns:
            List of (feature_name, importance_score) tuples sorted by importance
        """
        if not hasattr(self, 'feature_importance') or self.feature_importance is None:
            return None
        
        # Calculate feature importance using last fitted selector
        if self.feature_selector is not None and hasattr(self.feature_selector, 'scores_'):
            scores = self.feature_selector.scores_
            selected_mask = self.feature_selector.get_support()
            
            # Create ranking for selected features
            ranking = []
            for i, (name, selected) in enumerate(zip(self.feature_names, selected_mask)):
                if selected and i < len(scores):
                    score = scores[i]
                    ranking.append((name, float(score)))
            
            return sorted(ranking, key=lambda x: x[1], reverse=True)
        
        # Fallback: use feature importance if available
        if hasattr(self, 'feature_importance') and self.feature_importance is not None:
            return sorted(self.feature_importance.items(), key=lambda x: x[1], reverse=True)
        
        return None
    
    def analyze_timeframe_contributions(
        self,
        features: Dict[str, np.ndarray],
        labels: Optional[np.ndarray] = None
    ) -> Dict[str, Any]:
        """
        Analyze the contribution of each timeframe to overall predictive power.
        
        Args:
            features: Dictionary mapping timeframes to feature arrays
            labels: Optional target labels
            
        Returns:
            Dictionary with timeframe contribution analysis
        """
        analysis = {
            "timeframe_feature_counts": {},
            "timeframe_importance_scores": {},
            "cross_timeframe_correlations": {},
            "recommended_weights": {}
        }
        
        # Count features per timeframe
        for timeframe, tf_features in features.items():
            num_features = tf_features.shape[1] if tf_features.ndim > 1 else 1
            analysis["timeframe_feature_counts"][timeframe] = num_features
        
        # Calculate individual timeframe importance (if labels provided)
        if labels is not None:
            timeframe_scores = {}
            
            for timeframe, tf_features in features.items():
                try:
                    # Use mutual information as importance metric
                    from sklearn.feature_selection import mutual_info_classif
                    
                    scores = mutual_info_classif(tf_features, labels)
                    avg_score = float(np.mean(scores))
                    timeframe_scores[timeframe] = avg_score
                    
                except Exception as e:
                    logger.warning(f"Could not calculate importance for {timeframe}: {e}")
                    timeframe_scores[timeframe] = 0.0
            
            analysis["timeframe_importance_scores"] = timeframe_scores
            
            # Calculate recommended weights based on importance
            total_importance = sum(timeframe_scores.values())
            if total_importance > 0:
                analysis["recommended_weights"] = {
                    tf: score / total_importance 
                    for tf, score in timeframe_scores.items()
                }
            else:
                # Equal weights as fallback
                num_timeframes = len(features)
                analysis["recommended_weights"] = {
                    tf: 1.0 / num_timeframes for tf in features.keys()
                }
        
        # Calculate cross-timeframe correlations
        try:
            if len(features) > 1:
                correlations = {}
                timeframes = list(features.keys())
                
                for i, tf1 in enumerate(timeframes):
                    for j, tf2 in enumerate(timeframes[i+1:], i+1):
                        # Calculate correlation between timeframe feature means
                        features1 = np.mean(features[tf1], axis=1)
                        features2 = np.mean(features[tf2], axis=1)
                        
                        corr = float(np.corrcoef(features1, features2)[0, 1])
                        if not np.isnan(corr):
                            correlations[f"{tf1}_vs_{tf2}"] = corr
                
                analysis["cross_timeframe_correlations"] = correlations
                
        except Exception as e:
            logger.warning(f"Could not calculate cross-timeframe correlations: {e}")
        
        return analysis


def create_feature_engineer(config: Dict[str, Any]) -> MultiTimeframeFeatureEngineer:
    """
    Factory function to create a feature engineer.
    
    Args:
        config: Feature engineering configuration
        
    Returns:
        Configured MultiTimeframeFeatureEngineer instance
    """
    return MultiTimeframeFeatureEngineer(config)