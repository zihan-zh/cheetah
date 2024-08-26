from typing import Literal, Optional, Union

import matplotlib.pyplot as plt
import numpy as np
import torch
from matplotlib.patches import Rectangle
from scipy.constants import physical_constants
from torch import Size, nn

from cheetah.particles import Beam, ParticleBeam
from cheetah.track_methods import base_rmatrix, rotation_matrix
from cheetah.utils import UniqueNameGenerator, bmadx

from .element import Element

generate_unique_name = UniqueNameGenerator(prefix="unnamed_element")

electron_mass_eV = torch.tensor(
    physical_constants["electron mass energy equivalent in MeV"][0] * 1e6,
    dtype=torch.float64,
)


class Dipole(Element):
    """
    Dipole magnet (by default a sector bending magnet).

    :param length: Length in meters.
    :param p0c: Reference momentum at dipole in eV/c.
    :param angle: Deflection angle in rad.
    :param k1: Focussing strength in 1/m^-2.
    :param e1: The angle of inclination of the entrance face [rad].
    :param e2: The angle of inclination of the exit face [rad].
    :param tilt: Tilt of the magnet in x-y plane [rad].
    :param gap: The magnet gap in meters. Note that in MAD and ELEGANT: HGAP = gap/2.
    :param gap_exit: The magnet gap at the entrance in meters. Note that in MAD and
        ELEGANT: HGAP = gap/2. Only set if different from `gap`.
    :param fringe_integral: Fringe field integral (of the enterance face).
    :param fringe_integral_exit: Fringe field integral of the exit face. Only set if
        different from `fringe_integral`.
    :param fringe_at: Where to apply the fringe fields. The available options are:
        - "both_ends": Apply fringe fields at both ends.
        - "entrance_end": Apply fringe fields at the entrance end.
        - "exit_end": Apply fringe fields at the exit end.
        - "no_end": Do not apply fringe fields.
    :param fringe_type: Type of fringe field. Currently only supports `"linear_edge"`.
    :param name: Unique identifier of the element.
    """

    def __init__(
        self,
        length: Union[torch.Tensor, nn.Parameter],
        p0c: Optional[Union[torch.Tensor, nn.Parameter]] = None,
        angle: Optional[Union[torch.Tensor, nn.Parameter]] = None,
        k1: Optional[Union[torch.Tensor, nn.Parameter]] = None,
        e1: Optional[Union[torch.Tensor, nn.Parameter]] = None,
        e2: Optional[Union[torch.Tensor, nn.Parameter]] = None,
        tilt: Optional[Union[torch.Tensor, nn.Parameter]] = None,
        gap: Optional[Union[torch.Tensor, nn.Parameter]] = None,
        gap_exit: Optional[Union[torch.Tensor, nn.Parameter]] = None,
        fringe_integral: Optional[Union[torch.Tensor, nn.Parameter]] = None,
        fringe_integral_exit: Optional[Union[torch.Tensor, nn.Parameter]] = None,
        fringe_at: Literal[
            "both_ends", "entrance_end", "exit_end", "no_end"
        ] = "both_ends",
        fringe_type: Literal["linear_edge"] = "linear_edge",
        tracking_method: Literal["cheetah", "bmadx"] = "cheetah",
        name: Optional[str] = None,
        device=None,
        dtype=torch.float32,
    ):
        factory_kwargs = {"device": device, "dtype": dtype}
        super().__init__(name=name)

        self.register_buffer("length", torch.as_tensor(length, **factory_kwargs))
        self.register_buffer(
            "p0c",
            (
                torch.as_tensor(p0c, **factory_kwargs)
                if p0c is not None
                else torch.zeros_like(self.length)
            ),
        )
        self.register_buffer(
            "angle",
            (
                torch.as_tensor(angle, **factory_kwargs)
                if angle is not None
                else torch.zeros_like(self.length)
            ),
        )
        self.register_buffer(
            "k1",
            (
                torch.as_tensor(k1, **factory_kwargs)
                if k1 is not None
                else torch.zeros_like(self.length)
            ),
        )
        self.register_buffer(
            "e1",
            (
                torch.as_tensor(e1, **factory_kwargs)
                if e1 is not None
                else torch.zeros_like(self.length)
            ),
        )
        self.register_buffer(
            "e2",
            (
                torch.as_tensor(e2, **factory_kwargs)
                if e2 is not None
                else torch.zeros_like(self.length)
            ),
        )
        self.register_buffer(
            "fringe_integral",
            (
                torch.as_tensor(fringe_integral, **factory_kwargs)
                if fringe_integral is not None
                else torch.zeros_like(self.length)
            ),
        )
        self.register_buffer(
            "fringe_integral_exit",
            (
                self.fringe_integral
                if fringe_integral_exit is None
                else torch.as_tensor(fringe_integral_exit, **factory_kwargs)
            ),
        )
        self.register_buffer(
            "gap",
            (
                torch.as_tensor(gap, **factory_kwargs)
                if gap is not None
                else torch.zeros_like(self.length)
            ),
        )
        self.register_buffer(
            "gap_exit",
            (
                torch.as_tensor(gap_exit, **factory_kwargs)
                if gap_exit is not None
                else 1.0 * self.gap
            ),
        )
        self.register_buffer(
            "tilt",
            (
                torch.as_tensor(tilt, **factory_kwargs)
                if tilt is not None
                else torch.zeros_like(self.length)
            ),
        )
        self.fringe_at = fringe_at
        self.fringe_type = fringe_type
        self.tracking_method = tracking_method

    @property
    def hx(self) -> torch.Tensor:
        value = torch.zeros_like(self.length)
        value[self.length != 0] = (
            self.angle[self.length != 0] / self.length[self.length != 0]
        )
        return value

    @property
    def is_skippable(self) -> bool:
        return self.tracking_method == "cheetah"

    @property
    def is_active(self):
        return torch.any(self.angle != 0)

    def track(self, incoming: Beam) -> Beam:
        """
        Track particles through the quadrupole element.

        :param incoming: Beam entering the element.
        :return: Beam exiting the element.
        """
        if self.tracking_method == "cheetah":
            return super().track(incoming)
        elif self.tracking_method == "bmadx":
            assert isinstance(
                incoming, ParticleBeam
            ), "Bmad-X tracking is currently only supported for `ParticleBeam`."
            return self._track_bmadx(incoming)
        else:
            raise ValueError(
                f"Invalid tracking method {self.tracking_method}. "
                + "Supported methods are 'cheetah' and 'bmadx'."
            )

    def _track_bmadx(self, incoming: ParticleBeam) -> ParticleBeam:
        """
        Track particles through the quadrupole element using the Bmad-X tracking method.

        :param incoming: Beam entering the element. Currently only supports
            `ParticleBeam`.
        :return: Beam exiting the element.
        """
        # Compute Bmad coordinates and p0c
        mc2 = electron_mass_eV.to(
            device=incoming.particles.device, dtype=incoming.particles.dtype
        )

        x = incoming.x
        px = incoming.px
        y = incoming.y
        py = incoming.py
        tau = incoming.tau
        delta = incoming.p

        z, pz, p0c_particle = bmadx.cheetah_to_bmad_z_pz(
            tau, delta, incoming.energy, mc2
        )

        # Begin Bmad-X tracking
        x, px, y, py = bmadx.offset_particle_set(
            torch.tensor(0.0), torch.tensor(0.0), self.tilt, x, px, y, py
        )

        if self.fringe_at == "entrance_end" or self.fringe_at == "both_ends":
            px, py = self._bmadx_fringe_linear(
                "entrance", x, px, y, py, pz, p0c_particle
            )
        x, px, y, py, z, pz = self._bmadx_body(x, px, y, py, z, pz, p0c_particle, mc2)
        if self.fringe_at == "exit_end" or self.fringe_at == "both_ends":
            px, py = self._bmadx_fringe_linear("exit", x, px, y, py, pz, p0c_particle)

        x, px, y, py = bmadx.offset_particle_unset(
            torch.tensor(0.0), torch.tensor(0.0), self.tilt, x, px, y, py
        )
        # End of Bmad-X tracking

        # Convert back to Cheetah coordinates
        tau, delta, ref_energy = bmadx.bmad_to_cheetah_z_pz(z, pz, p0c_particle, mc2)

        outgoing_beam = ParticleBeam(
            torch.stack((x, px, y, py, tau, delta, torch.ones_like(x)), dim=-1),
            ref_energy,
            particle_charges=incoming.particle_charges,
            device=incoming.particles.device,
            dtype=incoming.particles.dtype,
        )
        return outgoing_beam

    def _bmadx_body(self, x, px, y, py, z, pz, p0c_particle, mc2):
        px = px * p0c_particle / self.p0c
        py = py * p0c_particle / self.p0c
        pz = (pz + 1) * p0c_particle / self.p0c - 1

        px_norm = torch.sqrt((1 + pz) ** 2 - py**2)  # For simplicity
        phi1 = torch.arcsin(px / px_norm)
        g = self.angle / self.length
        gp = g / px_norm

        alpha = (
            2
            * (1 + g * x)
            * torch.sin(self.angle + phi1)
            * self.length
            * bmadx.sinc(self.angle)
            - gp * ((1 + g * x) * self.length * bmadx.sinc(self.angle)) ** 2
        )

        x2_t1 = x * torch.cos(self.angle) + self.length**2 * g * bmadx.cosc(self.angle)

        x2_t2 = torch.sqrt((torch.cos(self.angle + phi1) ** 2) + gp * alpha)
        x2_t3 = torch.cos(self.angle + phi1)

        c1 = x2_t1 + alpha / (x2_t2 + x2_t3)
        c2 = x2_t1 + (x2_t2 - x2_t3) / gp
        temp = torch.abs(self.angle + phi1)
        x2 = c1 * (temp < torch.pi / 2) + c2 * (temp >= torch.pi / 2)

        Lcu = (
            x2 - self.length**2 * g * bmadx.cosc(self.angle) - x * torch.cos(self.angle)
        )

        Lcv = -self.length * bmadx.sinc(self.angle) - x * torch.sin(self.angle)

        theta_p = 2 * (self.angle + phi1 - torch.pi / 2 - torch.arctan2(Lcv, Lcu))

        Lc = torch.sqrt(Lcu**2 + Lcv**2)
        Lp = Lc / bmadx.sinc(theta_p / 2)

        P = self.p0c * (1 + pz)  # in eV
        E = torch.sqrt(P**2 + mc2**2)  # in eV
        E0 = torch.sqrt(self.p0c**2 + mc2**2)  # in eV
        beta = P / E
        beta0 = self.p0c / E0

        x_f = x2
        px_f = px_norm * torch.sin(self.angle + phi1 - theta_p)
        y_f = y + py * Lp / px_norm
        z_f = z + (beta * self.length / beta0) - ((1 + pz) * Lp / px_norm)

        return x_f, px_f, y_f, py, z_f, pz

    def _bmadx_fringe_linear(
        self,
        location: Literal["entrance", "exit"],
        x: Union[torch.Tensor, nn.Parameter],
        px: Union[torch.Tensor, nn.Parameter],
        y: Union[torch.Tensor, nn.Parameter],
        py: Union[torch.Tensor, nn.Parameter],
        pz: Union[torch.Tensor, nn.Parameter],
        p0c_particle: Union[torch.Tensor, nn.Parameter],
    ):
        px = px * p0c_particle / self.p0c
        py = py * p0c_particle / self.p0c
        pz = (pz + 1) * p0c_particle / self.p0c - 1
        g = self.angle / self.length
        e = self.e1 * (location == "entrance") + self.e2 * (location == "exit")
        f_int = self.fringe_integral * (
            location == "entrance"
        ) + self.fringe_integral_exit * (location == "exit")
        h_gap = 0.5 * (
            self.gap * (location == "entrance") + self.gap_exit * (location == "exit")
        )

        hx = g * torch.tan(e)
        hy = -g * torch.tan(
            e - 2 * f_int * h_gap * g * (1 + torch.sin(e) ** 2) / torch.cos(e)
        )
        px_f = px + x * hx
        py_f = py + y * hy

        return px_f, py_f

    def transfer_map(self, energy: torch.Tensor) -> torch.Tensor:
        device = self.length.device
        dtype = self.length.dtype

        R_enter = self._transfer_map_enter()
        R_exit = self._transfer_map_exit()

        if torch.any(self.length != 0.0):  # Bending magnet with finite length
            R = base_rmatrix(
                length=self.length,
                k1=self.k1,
                hx=self.hx,
                tilt=torch.zeros_like(self.length),
                energy=energy,
            )  # Tilt is applied after adding edges
        else:  # Reduce to Thin-Corrector
            R = torch.eye(7, device=device, dtype=dtype).repeat(
                (*self.length.shape, 1, 1)
            )
            R[..., 0, 1] = self.length
            R[..., 2, 6] = self.angle
            R[..., 2, 3] = self.length

        # Apply fringe fields
        R = torch.matmul(R_exit, torch.matmul(R, R_enter))
        # Apply rotation for tilted magnets
        R = torch.matmul(
            rotation_matrix(-self.tilt), torch.matmul(R, rotation_matrix(self.tilt))
        )
        return R

    def _transfer_map_enter(self) -> torch.Tensor:
        """Linear transfer map for the entrance face of the dipole magnet."""
        device = self.length.device
        dtype = self.length.dtype

        sec_e = 1.0 / torch.cos(self.e1)
        phi = (
            self.fringe_integral
            * self.hx
            * self.gap
            * sec_e
            * (1 + torch.sin(self.e1) ** 2)
        )

        tm = torch.eye(7, device=device, dtype=dtype).repeat(*phi.shape, 1, 1)
        tm[..., 1, 0] = self.hx * torch.tan(self.e1)
        tm[..., 3, 2] = -self.hx * torch.tan(self.e1 - phi)

        return tm

    def _transfer_map_exit(self) -> torch.Tensor:
        """Linear transfer map for the exit face of the dipole magnet."""
        device = self.length.device
        dtype = self.length.dtype

        sec_e = 1.0 / torch.cos(self.e2)
        phi = (
            self.fringe_integral_exit
            * self.hx
            * self.gap
            * sec_e
            * (1 + torch.sin(self.e2) ** 2)
        )

        tm = torch.eye(7, device=device, dtype=dtype).repeat(*phi.shape, 1, 1)
        tm[..., 1, 0] = self.hx * torch.tan(self.e2)
        tm[..., 3, 2] = -self.hx * torch.tan(self.e2 - phi)

        return tm

    def broadcast(self, shape: Size) -> Element:
        return self.__class__(
            length=self.length.repeat(shape),
            angle=self.angle.repeat(shape),
            k1=self.k1.repeat(shape),
            e1=self.e1.repeat(shape),
            e2=self.e2.repeat(shape),
            tilt=self.tilt.repeat(shape),
            fringe_integral=self.fringe_integral.repeat(shape),
            fringe_integral_exit=self.fringe_integral_exit.repeat(shape),
            gap=self.gap.repeat(shape),
            name=self.name,
            device=self.length.device,
            dtype=self.length.dtype,
        )

    def split(self, resolution: torch.Tensor) -> list[Element]:
        # TODO: Implement splitting for dipole properly, for now just returns the
        # element itself
        return [self]

    def __repr__(self):
        return (
            f"{self.__class__.__name__}(length={repr(self.length)}, "
            + f"angle={repr(self.angle)}, "
            + f"k1={repr(self.k1)}, "
            + f"e1={repr(self.e1)},"
            + f"e2={repr(self.e2)},"
            + f"tilt={repr(self.tilt)},"
            + f"fringe_integral={repr(self.fringe_integral)},"
            + f"fringe_integral_exit={repr(self.fringe_integral_exit)},"
            + f"gap={repr(self.gap)},"
            + f"tracking_method={repr(self.tracking_method)}, "
            + f"name={repr(self.name)})"
        )

    @property
    def defining_features(self) -> list[str]:
        return super().defining_features + [
            "length",
            "angle",
            "k1",
            "e1",
            "e2",
            "fringe_integral",
            "fringe_integral_exit",
            "gap",
            "tilt",
        ]

    def plot(self, ax: plt.Axes, s: float) -> None:
        alpha = 1 if self.is_active else 0.2
        height = 0.8 * (np.sign(self.angle[0]) if self.is_active else 1)

        patch = Rectangle(
            (s, 0), self.length[0], height, color="tab:green", alpha=alpha, zorder=2
        )
        ax.add_patch(patch)
