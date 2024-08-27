import pytest
import torch

from cheetah import (
    Dipole,
    Drift,
    ParameterBeam,
    ParticleBeam,
    Quadrupole,
    RBend,
    Segment,
)


def test_dipole_off():
    """
    Test that a dipole with angle=0 behaves still like a drift.
    """
    dipole = Dipole(length=torch.tensor([1.0]), angle=torch.tensor([0.0]))
    drift = Drift(length=torch.tensor([1.0]))
    incoming_beam = ParameterBeam.from_parameters(
        sigma_px=torch.tensor([2e-7]), sigma_py=torch.tensor([2e-7])
    )
    outbeam_dipole_off = dipole(incoming_beam)
    outbeam_drift = drift(incoming_beam)

    dipole.angle = torch.tensor([1.0], device=dipole.angle.device)
    outbeam_dipole_on = dipole(incoming_beam)

    assert dipole.name is not None
    assert torch.allclose(outbeam_dipole_off.sigma_x, outbeam_drift.sigma_x)
    assert not torch.allclose(outbeam_dipole_on.sigma_x, outbeam_drift.sigma_x)


def test_dipole_focussing():
    """
    Test that a dipole with focussing moment behaves like a quadrupole.
    """
    dipole = Dipole(length=torch.tensor([1.0]), k1=torch.tensor([10.0]))
    quadrupole = Quadrupole(length=torch.tensor([1.0]), k1=torch.tensor([10.0]))
    incoming_beam = ParameterBeam.from_parameters(
        sigma_px=torch.tensor([2e-7]), sigma_py=torch.tensor([2e-7])
    )
    outbeam_dipole_on = dipole.track(incoming_beam)
    outbeam_quadrupole = quadrupole.track(incoming_beam)

    dipole.k1 = torch.tensor([0.0], device=dipole.k1.device)
    outbeam_dipole_off = dipole.track(incoming_beam)

    assert dipole.name is not None
    assert torch.allclose(outbeam_dipole_on.sigma_x, outbeam_quadrupole.sigma_x)
    assert not torch.allclose(outbeam_dipole_off.sigma_x, outbeam_quadrupole.sigma_x)


@pytest.mark.parametrize("DipoleType", [Dipole, RBend])
def test_dipole_batched_execution(DipoleType):
    """
    Test that a dipole with batch dimensions behaves as expected.
    """
    batch_shape = torch.Size([6])
    incoming = ParticleBeam.from_parameters(
        num_particles=torch.tensor(1_000_000),
        energy=torch.tensor([1e9]),
        mu_x=torch.tensor([1e-5]),
    ).broadcast(batch_shape)
    segment = Segment(
        [
            DipoleType(
                length=torch.tensor([0.5, 0.5, 0.5]),
                angle=torch.tensor([0.1, 0.2, 0.1]),
            ).broadcast((2,)),
            Drift(length=torch.tensor([0.5])).broadcast(batch_shape),
        ]
    )
    outgoing = segment(incoming)

    # Check that dipole with same bend angle produce same output
    assert torch.allclose(outgoing.particles[0], outgoing.particles[2])

    # Check different angles do make a difference
    assert not torch.allclose(outgoing.particles[0], outgoing.particles[1])
