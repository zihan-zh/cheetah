import pytest
import torch
from torch import Size

from cheetah.utils import kde_histogram_1d, kde_histogram_2d
from cheetah.utils.kde import _kde_marginal_pdf


def test_weighted_samples_1d():
    """
    Test that the 1d KDE histogram implementation correctly handles
    heterogeneously weighted samples.
    """
    x_unweighted = torch.tensor([1.0, 1.0, 1.0, 2.0])
    x_weighted = torch.tensor([1.0, 2.0])

    bins = torch.linspace(0, 3, 10)
    sigma = torch.tensor(0.3)

    # Explicitly use all the samples with the same weights
    hist_unweighted = kde_histogram_1d(x_unweighted, bins, sigma)
    # Use samples and taking the weights into account
    hist_weighted = kde_histogram_1d(
        x_weighted, bins, sigma, weights=torch.tensor([3.0, 1.0])
    )
    # Use samples but neglect the weights
    hist_neglect_weights = kde_histogram_1d(x_weighted, bins, sigma)

    assert torch.allclose(hist_unweighted, hist_weighted)
    assert not torch.allclose(hist_weighted, hist_neglect_weights)


def test_kde_1d():
    # test basic usage
    data = torch.randn(100)  # 5 beamline states, 100 particles in 1D
    bins = torch.linspace(0, 1, 10)  # a single histogram
    sigma = torch.tensor(0.1)  # a single bandwidth

    pdf = kde_histogram_1d(data, bins, sigma)

    assert pdf.shape == Size([10])  # 5 histograms at 10 points

    # test bad bins
    with pytest.raises(ValueError):
        _kde_marginal_pdf(data, bins, torch.rand(3) + 0.1)


def test_kde_1d_vectorized():
    # test basic usage
    data = torch.randn((5, 100))  # 5 beamline states, 100 particles in 1D
    bins = torch.linspace(0, 1, 10)  # a single histogram
    sigma = torch.tensor(0.1)  # a single bandwidth

    pdf = kde_histogram_1d(data, bins, sigma)

    assert pdf.shape == Size([5, 10])  # 5 histograms at 10 points

    # test bad bins
    with pytest.raises(ValueError):
        _kde_marginal_pdf(data, bins, torch.rand(3) + 0.1)


def test_kde_2d_vectorized():
    data = torch.randn((3, 2, 100, 6))
    # 2 diagnostic paths,
    # 3 states per diagnostic paths,
    # 100 particles in 6D space

    # two different bins (1 per path)
    n = 30
    bins_x = torch.linspace(-20, 20, n)

    sigma = torch.tensor(0.1)  # a single bandwidth

    pdf = kde_histogram_2d(data[..., 0], data[..., 1], bins_x, bins_x, sigma)

    assert pdf.shape == Size([3, 2, n, n])


def test_weighted_samples_2d():
    """
    Test that the 2d KDE histogram implementation correctly handles
    heterogeneously weighted samples.
    """
    x_unweighted = torch.tensor([[1.0, 2.0], [1.0, 2.0], [1.0, 2.0], [2.0, 1.0]])
    x_weighted = torch.tensor([[1.0, 2.0], [2.0, 1.0]])

    bins1 = torch.linspace(0, 3, 10)
    bins2 = torch.linspace(0, 3, 10)
    sigma = torch.tensor(0.3)

    # Explicitly use all the samples with the same weights
    hist_unweighted = kde_histogram_2d(
        x_unweighted[:, 0], x_unweighted[:, 1], bins1, bins2, sigma
    )
    # Use samples and taking the weights into account
    hist_weighted = kde_histogram_2d(
        x_weighted[:, 0],
        x_weighted[:, 1],
        bins1,
        bins2,
        sigma,
        weights=torch.tensor([3.0, 1.0]),
    )
    # Use samples but neglect the weights
    hist_neglect_weights = kde_histogram_2d(
        x_weighted[:, 0], x_weighted[:, 1], bins1, bins2, sigma
    )

    assert torch.allclose(hist_unweighted, hist_weighted)
    assert not torch.allclose(hist_weighted, hist_neglect_weights)
