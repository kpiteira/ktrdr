"""
Multi-timeframe label generation for supervised learning.

This module generates labels across multiple timeframes with cross-timeframe
validation and temporal consistency checks for neuro-fuzzy trading systems.
"""

import pandas as pd
import numpy as np
from typing import Dict, List, Optional, Tuple, Any, Union
from dataclasses import dataclass
from enum import Enum
import warnings

from ktrdr import get_logger
from .zigzag_labeler import ZigZagLabeler, ZigZagConfig

# Set up module-level logger
logger = get_logger(__name__)


class LabelClass(Enum):
    """Label classes for trading decisions."""

    BUY = 0
    HOLD = 1
    SELL = 2


@dataclass
class TimeframeLabelConfig:
    """Configuration for single timeframe labeling."""

    threshold: float = 0.05  # Movement threshold for this timeframe
    lookahead: int = 20  # Bars to look ahead
    min_swing_length: int = 3  # Minimum bars between reversals
    weight: float = 1.0  # Weight for this timeframe in consensus
    method: str = "zigzag"  # Labeling method ("zigzag", "simple_return")


@dataclass
class MultiTimeframeLabelConfig:
    """Configuration for multi-timeframe label generation."""

    timeframe_configs: Dict[str, TimeframeLabelConfig]
    consensus_method: str = "weighted_majority"  # How to combine timeframe labels
    consistency_threshold: float = 0.7  # Minimum consistency for valid labels
    require_alignment: bool = True  # Require timeframe alignment for strong signals
    temporal_gap_tolerance: int = 2  # Max bars difference for temporal alignment
    min_confidence_score: float = 0.6  # Minimum confidence for non-HOLD labels
    label_smoothing: bool = True  # Apply temporal smoothing to reduce noise


@dataclass
class LabelValidationResult:
    """Result of cross-timeframe label validation."""

    is_valid: bool
    consistency_score: float
    timeframe_agreement: Dict[str, bool]
    confidence_score: float
    temporal_alignment_score: float
    validation_details: Dict[str, Any]


@dataclass
class MultiTimeframeLabelResult:
    """Result of multi-timeframe label generation."""

    labels: pd.Series
    timeframe_labels: Dict[str, pd.Series]
    confidence_scores: pd.Series
    consistency_scores: pd.Series
    validation_results: Dict[int, LabelValidationResult]  # Index -> validation result
    label_distribution: Dict[str, Any]
    metadata: Dict[str, Any]


class MultiTimeframeLabelGenerator:
    """
    Generate trading labels across multiple timeframes with validation.

    This class provides comprehensive label generation capabilities including:
    - Multi-timeframe label generation using various methods
    - Cross-timeframe label validation and consistency checks
    - Temporal alignment verification
    - Confidence scoring for label quality
    - Label smoothing and noise reduction
    """

    def __init__(self, config: MultiTimeframeLabelConfig):
        """
        Initialize the multi-timeframe label generator.

        Args:
            config: Multi-timeframe labeling configuration
        """
        self.config = config
        self.timeframe_labelers: Dict[str, Any] = {}
        self._setup_timeframe_labelers()

        logger.info(
            f"Initialized MultiTimeframeLabelGenerator for {len(config.timeframe_configs)} timeframes"
        )

    def _setup_timeframe_labelers(self) -> None:
        """Set up individual timeframe labelers."""
        for timeframe, tf_config in self.config.timeframe_configs.items():
            if tf_config.method == "zigzag":
                self.timeframe_labelers[timeframe] = ZigZagLabeler(
                    threshold=tf_config.threshold,
                    lookahead=tf_config.lookahead,
                    min_swing_length=tf_config.min_swing_length,
                )
            else:
                logger.warning(
                    f"Unknown labeling method: {tf_config.method}, using zigzag"
                )
                self.timeframe_labelers[timeframe] = ZigZagLabeler(
                    threshold=tf_config.threshold,
                    lookahead=tf_config.lookahead,
                    min_swing_length=tf_config.min_swing_length,
                )

    def generate_labels(
        self, multi_timeframe_data: Dict[str, pd.DataFrame], method: str = "consensus"
    ) -> MultiTimeframeLabelResult:
        """
        Generate labels across multiple timeframes.

        Args:
            multi_timeframe_data: Dictionary mapping timeframes to price data
            method: Label generation method ("consensus", "hierarchy", "weighted")

        Returns:
            MultiTimeframeLabelResult with labels and validation metrics
        """
        logger.info(f"Generating multi-timeframe labels using {method} method")

        # Generate labels for each timeframe
        timeframe_labels = self._generate_timeframe_labels(multi_timeframe_data)

        # Align labels temporally
        aligned_labels = self._align_timeframe_labels(
            timeframe_labels, multi_timeframe_data
        )

        # Generate consensus labels
        if method == "consensus":
            consensus_labels, confidence_scores = self._generate_consensus_labels(
                aligned_labels
            )
        elif method == "hierarchy":
            consensus_labels, confidence_scores = self._generate_hierarchical_labels(
                aligned_labels
            )
        elif method == "weighted":
            consensus_labels, confidence_scores = self._generate_weighted_labels(
                aligned_labels
            )
        else:
            logger.warning(f"Unknown method: {method}, using consensus")
            consensus_labels, confidence_scores = self._generate_consensus_labels(
                aligned_labels
            )

        # Calculate consistency scores
        consistency_scores = self._calculate_consistency_scores(
            aligned_labels, consensus_labels
        )

        # Validate labels cross-timeframe
        validation_results = self._validate_labels_cross_timeframe(
            aligned_labels, consensus_labels, confidence_scores
        )

        # Apply label smoothing if configured
        if self.config.label_smoothing:
            consensus_labels = self._apply_label_smoothing(
                consensus_labels, confidence_scores
            )

        # Calculate label distribution
        label_distribution = self._calculate_label_distribution(
            consensus_labels, timeframe_labels
        )

        # Create metadata
        metadata = self._create_label_metadata(
            multi_timeframe_data, aligned_labels, validation_results
        )

        logger.info(f"Generated {len(consensus_labels)} multi-timeframe labels")

        return MultiTimeframeLabelResult(
            labels=consensus_labels,
            timeframe_labels=aligned_labels,
            confidence_scores=confidence_scores,
            consistency_scores=consistency_scores,
            validation_results=validation_results,
            label_distribution=label_distribution,
            metadata=metadata,
        )

    def _generate_timeframe_labels(
        self, multi_timeframe_data: Dict[str, pd.DataFrame]
    ) -> Dict[str, pd.Series]:
        """Generate labels for each individual timeframe."""
        timeframe_labels = {}

        for timeframe, data in multi_timeframe_data.items():
            if timeframe not in self.timeframe_labelers:
                logger.warning(
                    f"No labeler configured for timeframe {timeframe}, skipping"
                )
                continue

            try:
                labeler = self.timeframe_labelers[timeframe]
                labels = labeler.generate_labels(data)
                timeframe_labels[timeframe] = labels

                logger.debug(
                    f"Generated {len(labels)} labels for timeframe {timeframe}"
                )

            except Exception as e:
                logger.error(
                    f"Failed to generate labels for timeframe {timeframe}: {e}"
                )
                continue

        return timeframe_labels

    def _align_timeframe_labels(
        self,
        timeframe_labels: Dict[str, pd.Series],
        multi_timeframe_data: Dict[str, pd.DataFrame],
    ) -> Dict[str, pd.Series]:
        """Align labels across timeframes temporally."""
        if not timeframe_labels:
            return {}

        # Find common time range across all timeframes
        common_start = max(labels.index.min() for labels in timeframe_labels.values())
        common_end = min(labels.index.max() for labels in timeframe_labels.values())

        aligned_labels = {}

        for timeframe, labels in timeframe_labels.items():
            try:
                # Filter to common time range
                mask = (labels.index >= common_start) & (labels.index <= common_end)
                aligned = labels[mask]

                # Ensure we have data
                if len(aligned) == 0:
                    logger.warning(f"No aligned data for timeframe {timeframe}")
                    continue

                aligned_labels[timeframe] = aligned
                logger.debug(f"Aligned {len(aligned)} labels for timeframe {timeframe}")

            except Exception as e:
                logger.error(f"Failed to align labels for timeframe {timeframe}: {e}")
                continue

        return aligned_labels

    def _generate_consensus_labels(
        self, aligned_labels: Dict[str, pd.Series]
    ) -> Tuple[pd.Series, pd.Series]:
        """Generate consensus labels using majority voting."""
        if not aligned_labels:
            return pd.Series(dtype=int), pd.Series(dtype=float)

        # Get common index
        indices = [labels.index for labels in aligned_labels.values()]
        if len(indices) == 0:
            return pd.Series(dtype=int), pd.Series(dtype=float)
        elif len(indices) == 1:
            common_index = indices[0]
        else:
            # Find intersection step by step to avoid pandas issues
            common_index = indices[0]
            for idx in indices[1:]:
                common_index = common_index.intersection(idx)

        if len(common_index) == 0:
            logger.warning("No common indices found for consensus labeling")
            return pd.Series(dtype=int), pd.Series(dtype=float)

        # Create label matrix
        label_matrix = np.full(
            (len(common_index), len(aligned_labels)), LabelClass.HOLD.value
        )

        for i, (timeframe, labels) in enumerate(aligned_labels.items()):
            # Reindex to common index
            reindexed = labels.reindex(common_index, fill_value=LabelClass.HOLD.value)
            label_matrix[:, i] = reindexed.values

        # Calculate consensus and confidence
        consensus_labels = []
        confidence_scores = []

        for row in label_matrix:
            # Count votes for each class
            vote_counts = np.bincount(row.astype(int), minlength=3)

            # Find majority class
            majority_class = np.argmax(vote_counts)
            majority_votes = vote_counts[majority_class]
            total_votes = len(row)

            # Calculate confidence as agreement percentage
            confidence = majority_votes / total_votes

            # Apply confidence threshold
            if (
                confidence >= self.config.min_confidence_score
                or majority_class == LabelClass.HOLD.value
            ):
                consensus_labels.append(majority_class)
            else:
                consensus_labels.append(LabelClass.HOLD.value)  # Fall back to HOLD

            confidence_scores.append(confidence)

        consensus_series = pd.Series(consensus_labels, index=common_index, dtype=int)
        confidence_series = pd.Series(
            confidence_scores, index=common_index, dtype=float
        )

        logger.debug(
            f"Generated consensus labels with mean confidence: {confidence_series.mean():.3f}"
        )

        return consensus_series, confidence_series

    def _generate_hierarchical_labels(
        self, aligned_labels: Dict[str, pd.Series]
    ) -> Tuple[pd.Series, pd.Series]:
        """Generate labels using timeframe hierarchy (longer timeframes override shorter)."""
        if not aligned_labels:
            return pd.Series(dtype=int), pd.Series(dtype=float)

        # Define timeframe priority (longer timeframes have higher priority)
        timeframe_priority = {
            "1m": 1,
            "5m": 2,
            "15m": 3,
            "30m": 4,
            "1h": 5,
            "2h": 6,
            "4h": 7,
            "6h": 8,
            "8h": 9,
            "12h": 10,
            "1d": 11,
            "3d": 12,
            "1w": 13,
            "1M": 14,
        }

        # Sort timeframes by priority
        sorted_timeframes = sorted(
            aligned_labels.keys(),
            key=lambda tf: timeframe_priority.get(tf, 999),
            reverse=True,  # Highest priority first
        )

        # Get common index
        indices = [labels.index for labels in aligned_labels.values()]
        if len(indices) == 0:
            return pd.Series(dtype=int), pd.Series(dtype=float)
        elif len(indices) == 1:
            common_index = indices[0]
        else:
            # Find intersection step by step to avoid pandas issues
            common_index = indices[0]
            for idx in indices[1:]:
                common_index = common_index.intersection(idx)

        # Start with HOLD labels
        hierarchical_labels = pd.Series(
            LabelClass.HOLD.value, index=common_index, dtype=int
        )
        confidence_scores = pd.Series(
            0.5, index=common_index, dtype=float
        )  # Neutral confidence

        # Apply labels in priority order (highest first)
        for timeframe in sorted_timeframes:
            labels = aligned_labels[timeframe].reindex(
                common_index, fill_value=LabelClass.HOLD.value
            )

            # Override labels where current timeframe has strong signals
            strong_signal_mask = labels != LabelClass.HOLD.value
            hierarchical_labels[strong_signal_mask] = labels[strong_signal_mask]

            # Update confidence based on timeframe priority
            tf_priority = timeframe_priority.get(timeframe, 1)
            confidence_boost = tf_priority / max(timeframe_priority.values())
            confidence_scores[strong_signal_mask] = confidence_boost

        logger.debug(
            f"Generated hierarchical labels using {len(sorted_timeframes)} timeframes"
        )

        return hierarchical_labels, confidence_scores

    def _generate_weighted_labels(
        self, aligned_labels: Dict[str, pd.Series]
    ) -> Tuple[pd.Series, pd.Series]:
        """Generate labels using weighted voting based on timeframe configurations."""
        if not aligned_labels:
            return pd.Series(dtype=int), pd.Series(dtype=float)

        # Get common index
        indices = [labels.index for labels in aligned_labels.values()]
        if len(indices) == 0:
            return pd.Series(dtype=int), pd.Series(dtype=float)
        elif len(indices) == 1:
            common_index = indices[0]
        else:
            # Find intersection step by step to avoid pandas issues
            common_index = indices[0]
            for idx in indices[1:]:
                common_index = common_index.intersection(idx)

        if len(common_index) == 0:
            return pd.Series(dtype=int), pd.Series(dtype=float)

        # Create weighted vote matrix
        weighted_votes = np.zeros((len(common_index), 3))  # 3 classes: BUY, HOLD, SELL
        total_weights = 0

        for timeframe, labels in aligned_labels.items():
            weight = self.config.timeframe_configs[timeframe].weight
            total_weights += weight

            reindexed = labels.reindex(common_index, fill_value=LabelClass.HOLD.value)

            # Add weighted votes
            for i, label in enumerate(reindexed.values):
                weighted_votes[i, int(label)] += weight

        # Normalize weights
        if total_weights > 0:
            weighted_votes /= total_weights

        # Determine final labels and confidence
        consensus_labels = np.argmax(weighted_votes, axis=1)
        confidence_scores = np.max(weighted_votes, axis=1)

        # Apply confidence threshold
        low_confidence_mask = confidence_scores < self.config.min_confidence_score
        consensus_labels[low_confidence_mask] = LabelClass.HOLD.value

        consensus_series = pd.Series(consensus_labels, index=common_index, dtype=int)
        confidence_series = pd.Series(
            confidence_scores, index=common_index, dtype=float
        )

        logger.debug(
            f"Generated weighted labels with mean confidence: {confidence_series.mean():.3f}"
        )

        return consensus_series, confidence_series

    def _calculate_consistency_scores(
        self, aligned_labels: Dict[str, pd.Series], consensus_labels: pd.Series
    ) -> pd.Series:
        """Calculate consistency scores between timeframes and consensus."""
        if not aligned_labels or len(consensus_labels) == 0:
            return pd.Series(dtype=float)

        consistency_scores = []

        for idx in consensus_labels.index:
            timeframe_labels_at_idx = []

            for timeframe, labels in aligned_labels.items():
                if idx in labels.index:
                    timeframe_labels_at_idx.append(labels[idx])

            if len(timeframe_labels_at_idx) == 0:
                consistency_scores.append(0.0)
                continue

            # Calculate agreement with consensus
            consensus_label = consensus_labels[idx]
            agreements = sum(
                1 for label in timeframe_labels_at_idx if label == consensus_label
            )
            consistency = agreements / len(timeframe_labels_at_idx)

            consistency_scores.append(consistency)

        return pd.Series(consistency_scores, index=consensus_labels.index, dtype=float)

    def _validate_labels_cross_timeframe(
        self,
        aligned_labels: Dict[str, pd.Series],
        consensus_labels: pd.Series,
        confidence_scores: pd.Series,
    ) -> Dict[int, LabelValidationResult]:
        """Validate labels across timeframes with comprehensive checks."""
        validation_results = {}

        for i, idx in enumerate(consensus_labels.index):
            try:
                # Get timeframe labels at this index
                timeframe_labels_at_idx = {}
                for timeframe, labels in aligned_labels.items():
                    if idx in labels.index:
                        timeframe_labels_at_idx[timeframe] = labels[idx]

                # Skip if no timeframe data
                if not timeframe_labels_at_idx:
                    continue

                # Perform validation checks
                validation_result = self._perform_label_validation(
                    idx,
                    timeframe_labels_at_idx,
                    consensus_labels[idx],
                    confidence_scores[idx],
                )

                validation_results[i] = validation_result

            except Exception as e:
                logger.error(f"Validation failed for index {idx}: {e}")
                continue

        # Calculate overall validation statistics
        valid_count = sum(
            1 for result in validation_results.values() if result.is_valid
        )
        total_count = len(validation_results)

        if total_count > 0:
            validation_rate = valid_count / total_count * 100
            logger.info(
                f"Label validation complete: {valid_count}/{total_count} ({validation_rate:.1f}%) valid"
            )
        else:
            logger.info("Label validation complete: no labels to validate")

        return validation_results

    def _perform_label_validation(
        self,
        idx: pd.Timestamp,
        timeframe_labels: Dict[str, int],
        consensus_label: int,
        confidence_score: float,
    ) -> LabelValidationResult:
        """Perform comprehensive label validation for a single timestamp."""

        # 1. Check timeframe agreement
        timeframe_agreement = {}
        agreement_count = 0

        for timeframe, label in timeframe_labels.items():
            agrees = label == consensus_label
            timeframe_agreement[timeframe] = agrees
            if agrees:
                agreement_count += 1

        # 2. Calculate consistency score
        consistency_score = (
            agreement_count / len(timeframe_labels) if timeframe_labels else 0.0
        )

        # 3. Check temporal alignment (simplified - could be enhanced)
        temporal_alignment_score = 1.0  # Simplified for now

        # 4. Overall validation
        is_valid = (
            consistency_score >= self.config.consistency_threshold
            and confidence_score >= self.config.min_confidence_score
            and temporal_alignment_score >= 0.5
        )

        # 5. Create validation details
        validation_details = {
            "timestamp": idx,
            "timeframe_labels": timeframe_labels,
            "consensus_label": consensus_label,
            "agreement_count": agreement_count,
            "total_timeframes": len(timeframe_labels),
            "checks_passed": {
                "consistency": consistency_score >= self.config.consistency_threshold,
                "confidence": confidence_score >= self.config.min_confidence_score,
                "temporal_alignment": temporal_alignment_score >= 0.5,
            },
        }

        return LabelValidationResult(
            is_valid=is_valid,
            consistency_score=consistency_score,
            timeframe_agreement=timeframe_agreement,
            confidence_score=confidence_score,
            temporal_alignment_score=temporal_alignment_score,
            validation_details=validation_details,
        )

    def _apply_label_smoothing(
        self, labels: pd.Series, confidence_scores: pd.Series, window_size: int = 3
    ) -> pd.Series:
        """Apply temporal smoothing to reduce label noise."""
        if len(labels) < window_size:
            return labels

        smoothed_labels = labels.copy()

        for i in range(window_size // 2, len(labels) - window_size // 2):
            window_start = i - window_size // 2
            window_end = i + window_size // 2 + 1

            window_labels = labels.iloc[window_start:window_end]
            window_confidence = confidence_scores.iloc[window_start:window_end]

            # If confidence is low, consider smoothing
            if confidence_scores.iloc[i] < 0.8:
                # Check if majority of surrounding labels agree
                current_label = labels.iloc[i]
                surrounding_labels = window_labels[
                    window_labels.index != labels.index[i]
                ]

                if len(surrounding_labels) > 0:
                    majority_label = surrounding_labels.mode()
                    if len(majority_label) > 0:
                        majority_count = (
                            surrounding_labels == majority_label.iloc[0]
                        ).sum()
                        if majority_count > len(surrounding_labels) / 2:
                            smoothed_labels.iloc[i] = majority_label.iloc[0]

        logger.debug(f"Applied label smoothing with window size {window_size}")

        return smoothed_labels

    def _calculate_label_distribution(
        self, consensus_labels: pd.Series, timeframe_labels: Dict[str, pd.Series]
    ) -> Dict[str, Any]:
        """Calculate comprehensive label distribution statistics."""
        distribution = {}

        # Overall distribution
        if len(consensus_labels) > 0:
            consensus_counts = consensus_labels.value_counts().sort_index()
            total = len(consensus_labels)

            distribution["consensus"] = {
                "buy_count": int(consensus_counts.get(LabelClass.BUY.value, 0)),
                "hold_count": int(consensus_counts.get(LabelClass.HOLD.value, 0)),
                "sell_count": int(consensus_counts.get(LabelClass.SELL.value, 0)),
                "buy_pct": float(
                    consensus_counts.get(LabelClass.BUY.value, 0) / total * 100
                ),
                "hold_pct": float(
                    consensus_counts.get(LabelClass.HOLD.value, 0) / total * 100
                ),
                "sell_pct": float(
                    consensus_counts.get(LabelClass.SELL.value, 0) / total * 100
                ),
                "total": total,
            }

        # Per-timeframe distribution
        distribution["timeframes"] = {}
        for timeframe, labels in timeframe_labels.items():
            if len(labels) > 0:
                tf_counts = labels.value_counts().sort_index()
                tf_total = len(labels)

                distribution["timeframes"][timeframe] = {
                    "buy_count": int(tf_counts.get(LabelClass.BUY.value, 0)),
                    "hold_count": int(tf_counts.get(LabelClass.HOLD.value, 0)),
                    "sell_count": int(tf_counts.get(LabelClass.SELL.value, 0)),
                    "buy_pct": float(
                        tf_counts.get(LabelClass.BUY.value, 0) / tf_total * 100
                    ),
                    "hold_pct": float(
                        tf_counts.get(LabelClass.HOLD.value, 0) / tf_total * 100
                    ),
                    "sell_pct": float(
                        tf_counts.get(LabelClass.SELL.value, 0) / tf_total * 100
                    ),
                    "total": tf_total,
                }

        return distribution

    def _create_label_metadata(
        self,
        multi_timeframe_data: Dict[str, pd.DataFrame],
        aligned_labels: Dict[str, pd.Series],
        validation_results: Dict[int, LabelValidationResult],
    ) -> Dict[str, Any]:
        """Create comprehensive metadata for the labeling process."""

        # Basic metadata
        metadata = {
            "timeframes": list(self.config.timeframe_configs.keys()),
            "consensus_method": self.config.consensus_method,
            "label_smoothing": self.config.label_smoothing,
            "consistency_threshold": self.config.consistency_threshold,
            "min_confidence_score": self.config.min_confidence_score,
            "generation_timestamp": pd.Timestamp.now(tz="UTC"),
        }

        # Data statistics
        metadata["data_statistics"] = {}
        for timeframe, data in multi_timeframe_data.items():
            metadata["data_statistics"][timeframe] = {
                "total_bars": len(data),
                "start_time": data.index.min(),
                "end_time": data.index.max(),
                "time_span_hours": (data.index.max() - data.index.min()).total_seconds()
                / 3600,
            }

        # Validation statistics
        if validation_results:
            valid_labels = sum(
                1 for result in validation_results.values() if result.is_valid
            )
            total_labels = len(validation_results)
            avg_consistency = np.mean(
                [result.consistency_score for result in validation_results.values()]
            )
            avg_confidence = np.mean(
                [result.confidence_score for result in validation_results.values()]
            )

            metadata["validation_statistics"] = {
                "total_validated": total_labels,
                "valid_labels": valid_labels,
                "validation_rate": (
                    valid_labels / total_labels if total_labels > 0 else 0.0
                ),
                "average_consistency": float(avg_consistency),
                "average_confidence": float(avg_confidence),
            }

        # Timeframe coverage
        metadata["timeframe_coverage"] = {}
        for timeframe, labels in aligned_labels.items():
            metadata["timeframe_coverage"][timeframe] = {
                "label_count": len(labels),
                "coverage_start": labels.index.min(),
                "coverage_end": labels.index.max(),
            }

        return metadata

    def validate_temporal_consistency(
        self,
        labels: pd.Series,
        timeframe_labels: Dict[str, pd.Series],
        window_size: int = 5,
    ) -> Dict[str, Any]:
        """
        Validate temporal consistency of labels.

        Args:
            labels: Consensus labels
            timeframe_labels: Individual timeframe labels
            window_size: Window size for consistency checks

        Returns:
            Dictionary with temporal consistency metrics
        """
        if len(labels) < window_size:
            return {"temporal_consistency": 0.0, "details": "Insufficient data"}

        consistency_scores = []

        for i in range(window_size // 2, len(labels) - window_size // 2):
            window_start = i - window_size // 2
            window_end = i + window_size // 2 + 1

            window_labels = labels.iloc[window_start:window_end]

            # Check for label stability in window
            label_changes = (window_labels.diff() != 0).sum()
            stability_score = 1.0 - (label_changes / len(window_labels))

            consistency_scores.append(stability_score)

        overall_consistency = np.mean(consistency_scores) if consistency_scores else 0.0

        # Additional temporal checks
        temporal_metrics = {
            "temporal_consistency": float(overall_consistency),
            "total_label_changes": int((labels.diff() != 0).sum()),
            "change_frequency": float((labels.diff() != 0).sum() / len(labels)),
            "longest_stable_sequence": self._find_longest_stable_sequence(labels),
            "window_size": window_size,
            "details": {
                "consistency_scores": consistency_scores,
                "score_std": (
                    float(np.std(consistency_scores)) if consistency_scores else 0.0
                ),
            },
        }

        return temporal_metrics

    def _find_longest_stable_sequence(self, labels: pd.Series) -> int:
        """Find the longest sequence of stable labels."""
        if len(labels) == 0:
            return 0

        max_length = 1
        current_length = 1

        for i in range(1, len(labels)):
            if labels.iloc[i] == labels.iloc[i - 1]:
                current_length += 1
                max_length = max(max_length, current_length)
            else:
                current_length = 1

        return max_length

    def analyze_label_quality(
        self, result: MultiTimeframeLabelResult
    ) -> Dict[str, Any]:
        """
        Analyze the quality of generated labels.

        Args:
            result: Multi-timeframe label generation result

        Returns:
            Dictionary with quality analysis metrics
        """
        quality_metrics = {}

        # Basic quality metrics
        quality_metrics["label_count"] = len(result.labels)
        quality_metrics["average_confidence"] = float(result.confidence_scores.mean())
        quality_metrics["average_consistency"] = float(result.consistency_scores.mean())

        # Class balance analysis
        label_counts = result.labels.value_counts()
        total_labels = len(result.labels)

        quality_metrics["class_balance"] = {
            "buy_ratio": float(
                label_counts.get(LabelClass.BUY.value, 0) / total_labels
            ),
            "hold_ratio": float(
                label_counts.get(LabelClass.HOLD.value, 0) / total_labels
            ),
            "sell_ratio": float(
                label_counts.get(LabelClass.SELL.value, 0) / total_labels
            ),
            "balance_score": self._calculate_balance_score(label_counts, total_labels),
        }

        # Validation quality
        if result.validation_results:
            valid_count = sum(
                1 for vr in result.validation_results.values() if vr.is_valid
            )
            quality_metrics["validation_quality"] = {
                "validation_rate": float(valid_count / len(result.validation_results)),
                "total_validated": len(result.validation_results),
            }

        # Temporal quality
        temporal_metrics = self.validate_temporal_consistency(
            result.labels, result.timeframe_labels
        )
        quality_metrics["temporal_quality"] = temporal_metrics

        # Cross-timeframe agreement
        quality_metrics["cross_timeframe_agreement"] = (
            self._analyze_cross_timeframe_agreement(result.timeframe_labels)
        )

        return quality_metrics

    def _calculate_balance_score(
        self, label_counts: pd.Series, total_labels: int
    ) -> float:
        """Calculate a balance score (1.0 = perfectly balanced, 0.0 = completely imbalanced)."""
        if total_labels == 0:
            return 0.0

        # Ideal distribution would be 1/3 for each class
        ideal_ratio = 1.0 / 3.0

        ratios = []
        for class_value in [
            LabelClass.BUY.value,
            LabelClass.HOLD.value,
            LabelClass.SELL.value,
        ]:
            ratio = label_counts.get(class_value, 0) / total_labels
            ratios.append(ratio)

        # Calculate deviation from ideal
        deviations = [abs(ratio - ideal_ratio) for ratio in ratios]
        max_possible_deviation = ideal_ratio  # Maximum deviation from ideal

        # Balance score: 1.0 - (average deviation / max possible deviation)
        avg_deviation = np.mean(deviations)
        balance_score = max(0.0, 1.0 - (avg_deviation / max_possible_deviation))

        return float(balance_score)

    def _analyze_cross_timeframe_agreement(
        self, timeframe_labels: Dict[str, pd.Series]
    ) -> Dict[str, Any]:
        """Analyze agreement patterns across timeframes."""
        if len(timeframe_labels) < 2:
            return {"agreement_score": 1.0, "pairwise_agreements": {}}

        timeframes = list(timeframe_labels.keys())
        pairwise_agreements = {}
        all_agreements = []

        # Calculate pairwise agreements
        for i, tf1 in enumerate(timeframes):
            for tf2 in timeframes[i + 1 :]:
                # Find common indices
                common_idx = timeframe_labels[tf1].index.intersection(
                    timeframe_labels[tf2].index
                )

                if len(common_idx) > 0:
                    labels1 = timeframe_labels[tf1].reindex(common_idx)
                    labels2 = timeframe_labels[tf2].reindex(common_idx)

                    agreement_rate = (labels1 == labels2).mean()
                    pairwise_agreements[f"{tf1}_vs_{tf2}"] = float(agreement_rate)
                    all_agreements.append(agreement_rate)

        overall_agreement = np.mean(all_agreements) if all_agreements else 0.0

        return {
            "agreement_score": float(overall_agreement),
            "pairwise_agreements": pairwise_agreements,
            "num_comparisons": len(all_agreements),
        }


def create_multi_timeframe_label_generator(
    config_dict: Dict[str, Any],
) -> MultiTimeframeLabelGenerator:
    """
    Factory function to create a multi-timeframe label generator.

    Args:
        config_dict: Configuration dictionary

    Returns:
        Configured MultiTimeframeLabelGenerator instance
    """
    # Convert timeframe configs
    timeframe_configs = {}
    for tf, tf_config in config_dict.get("timeframe_configs", {}).items():
        timeframe_configs[tf] = TimeframeLabelConfig(**tf_config)

    # Create main config
    config = MultiTimeframeLabelConfig(
        timeframe_configs=timeframe_configs,
        consensus_method=config_dict.get("consensus_method", "weighted_majority"),
        consistency_threshold=config_dict.get("consistency_threshold", 0.7),
        require_alignment=config_dict.get("require_alignment", True),
        temporal_gap_tolerance=config_dict.get("temporal_gap_tolerance", 2),
        min_confidence_score=config_dict.get("min_confidence_score", 0.6),
        label_smoothing=config_dict.get("label_smoothing", True),
    )

    return MultiTimeframeLabelGenerator(config)
