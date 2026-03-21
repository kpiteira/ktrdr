"""Custom loss functions for neural network training."""

from typing import Optional

import torch
import torch.nn as nn
import torch.nn.functional as F


class FocalLoss(nn.Module):
    """Focal Loss for handling class imbalance.

    Down-weights easy (well-classified) examples and focuses training on hard examples.
    When gamma=0, this reduces to standard cross-entropy loss.

    Reference: Lin et al., "Focal Loss for Dense Object Detection", ICCV 2017.

    Args:
        gamma: Focusing parameter. 0 = standard CE, 2 = standard focal loss.
        alpha: Optional per-class weight tensor.
    """

    def __init__(self, gamma: float = 2.0, alpha: Optional[torch.Tensor] = None):
        super().__init__()
        self.gamma = gamma
        if alpha is not None:
            self.register_buffer("alpha", alpha)
        else:
            self.alpha = None

    def forward(self, logits: torch.Tensor, targets: torch.Tensor) -> torch.Tensor:
        """Compute focal loss.

        Args:
            logits: Raw model outputs (N, C) where C is number of classes.
            targets: Ground truth class indices (N,).

        Returns:
            Scalar loss value.
        """
        # Compute log-softmax for numerical stability
        log_probs = F.log_softmax(logits, dim=1)
        # Gather log-probability for the true class
        log_pt = log_probs.gather(1, targets.unsqueeze(1)).squeeze(1)
        pt = log_pt.exp()

        # Focal modulating factor: (1 - p_t)^gamma
        focal_weight = (1 - pt) ** self.gamma

        # Apply per-class alpha weights if provided
        if self.alpha is not None:
            alpha_t = self.alpha[targets]
            focal_weight = alpha_t * focal_weight

        loss = -focal_weight * log_pt
        return loss.mean()
