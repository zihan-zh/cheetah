"""Utility functions"""

import math
from typing import Optional, Tuple, Union

import torch
from torch import Tensor


class UniqueNameGenerator:
    """Generates a unique name given a prefix."""

    def __init__(self, prefix: str):
        self._prefix = prefix
        self._counter = 0

    def __call__(self):
        name = f"{self._prefix}_{self._counter}"
        self._counter += 1
        return name


# Kernel density Estimation functionalities
# Modified from kornia.enhance.histogram


def kde_marginal_pdf(
    values: torch.Tensor,
    bins: torch.Tensor,
    sigma: torch.Tensor,
    weights: Optional[Union[Tensor, float]] = None,
) -> Tuple[torch.Tensor, torch.Tensor]:
    """Calculate the 1D marginal probability distribution function of the input tensor
      based on the number of histogram bins.

    Args:
        values: shape [BxNx1].
        bins: shape [NUM_BINS].
        sigma: shape [1], gaussian smoothing factor.

    Returns:
        Tuple[torch.Tensor, torch.Tensor]:
          - torch.Tensor: shape [BxN].
          - torch.Tensor: shape [BxNxNUM_BINS].
    """

    if not isinstance(values, torch.Tensor):
        raise TypeError(f"Input values type is not a torch.Tensor. Got {type(values)}")

    if not isinstance(bins, torch.Tensor):
        raise TypeError(f"Input bins type is not a torch.Tensor. Got {type(bins)}")

    if not isinstance(sigma, torch.Tensor):
        raise TypeError(f"Input sigma type is not a torch.Tensor. Got {type(sigma)}")

    if not bins.dim() == 1:
        raise ValueError(
            "Input bins must be a of the shape NUM_BINS" " Got {}".format(bins.shape)
        )

    if not sigma.dim() == 0:
        raise ValueError(
            "Input sigma must be a of the shape 1" " Got {}".format(sigma.shape)
        )

    if isinstance(weights, float):
        weights = torch.ones(values.shape[:-1])
    elif weights is None:
        weights = 1.0

    residuals = values - bins.repeat(*values.shape)
    kernel_values = (
        weights
        * torch.exp(-0.5 * (residuals / sigma).pow(2))
        / torch.sqrt(2 * math.pi * sigma**2)
    )

    prob_mass = torch.sum(kernel_values, dim=-2)
    return prob_mass, kernel_values


def kde_joint_pdf_2d(
    kernel_values1: torch.Tensor, kernel_values2: torch.Tensor, epsilon: float = 1e-10
) -> torch.Tensor:
    """Calculate the joint probability distribution function of the input tensors based
    on the number of histogram bins.

    Args:
        kernel_values1: shape [BxNxNUM_BINS].
        kernel_values2: shape [BxNxNUM_BINS].
        epsilon: scalar, for numerical stability.

    Returns:
        shape [BxNUM_BINSxNUM_BINS].
    """

    if not isinstance(kernel_values1, torch.Tensor):
        raise TypeError(
            "Input kernel_values1 type is not a torch.Tensor."
            + f"Got {type(kernel_values1)}"
        )

    if not isinstance(kernel_values2, torch.Tensor):
        raise TypeError(
            "Input kernel_values2 type is not a torch.Tensor."
            + f"Got {type(kernel_values2)}"
        )

    joint_kernel_values = torch.matmul(kernel_values1.transpose(-2, -1), kernel_values2)
    normalization = (
        torch.sum(joint_kernel_values, dim=(-2, -1)).unsqueeze(-1).unsqueeze(-1)
        + epsilon
    )
    pdf = joint_kernel_values / normalization

    return pdf


def kde_histogram_1d(
    x: torch.Tensor, bins: torch.Tensor, bandwidth: torch.Tensor, epsilon: float = 1e-10
) -> torch.Tensor:
    """Estimate the histogram using KDE of the input tensor.

    The calculation uses kernel density estimation which requires a bandwidth
    (smoothing) parameter.

    Args:
        x: Input tensor to compute the histogram with shape :math:`(B, D)`.
        bins: The number of bins to use the histogram :math:`(N_{bins})`.
        bandwidth: Gaussian smoothing factor with shape shape [1].
        epsilon: A scalar, for numerical stability.

    Returns:
        Computed histogram of shape :math:`(B, N_{bins})`.

    Examples:
        >>> x = torch.rand(1, 10)
        >>> bins = torch.torch.linspace(0, 255, 128)
        >>> hist = kde_histogram_1d(x, bins, bandwidth=torch.tensor(0.9))
        >>> hist.shape
        torch.Size([1, 128])
    """

    pdf, _ = kde_marginal_pdf(x.unsqueeze(-1), bins, bandwidth, epsilon)

    return pdf


def kde_histogram_2d(
    x1: torch.Tensor,
    x2: torch.Tensor,
    bins1: torch.Tensor,
    bins2: torch.Tensor,
    bandwidth: torch.Tensor,
    weights=None,
    epsilon: Union[float, torch.Tensor] = 1e-10,
) -> torch.Tensor:
    """Estimate the 2d histogram of the input tensor.

    The calculation uses kernel density estimation which requires a bandwidth
    (smoothing) parameter.

    Args:
        x1: Input tensor to compute the histogram with shape :math:`(B, D1)`.
        x2: Input tensor to compute the histogram with shape :math:`(B, D2)`.
        bins: bin coordinates.
        bandwidth: Gaussian smoothing factor with shape shape [1].
        epsilon: A scalar, for numerical stability. Default: 1e-10.

    Returns:
        Computed histogram of shape :math:`(B, N_{bins}), N_{bins})`.

    Examples:
        >>> x1 = torch.rand(2, 32)
        >>> x2 = torch.rand(2, 32)
        >>> bins = torch.torch.linspace(0, 255, 128)
        >>> hist = kde_histogram_2d(x1, x2, bins, bandwidth=torch.tensor(0.9))
        >>> hist.shape
        torch.Size([2, 128, 128])
    """

    _, kernel_values1 = kde_marginal_pdf(x1.unsqueeze(-1), bins1, bandwidth, weights)
    _, kernel_values2 = kde_marginal_pdf(x2.unsqueeze(-1), bins2, bandwidth, weights)

    pdf = kde_joint_pdf_2d(kernel_values1, kernel_values2, epsilon=epsilon)

    return pdf
