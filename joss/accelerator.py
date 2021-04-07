from itertools import chain
from sys import path

import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle
import numpy as np
from numpy.lib.shape_base import hsplit
from scipy import constants

from joss.utils import ocelot2joss


ELEMENT_COUNT = 0
REST_ENERGY = constants.electron_mass * constants.speed_of_light**2 / constants.elementary_charge
        

class Element:

    def __init__(self, name=None):
        global ELEMENT_COUNT

        if name is not None:
            self.name = name
        else:
            self.name = f"{self.__class__.__name__}_{ELEMENT_COUNT:06d}"
        
        ELEMENT_COUNT += 1
    
    @property
    def transfer_map(self):
        raise NotImplementedError

    def __call__(self, particles):
        return np.matmul(particles, self.transfer_map.transpose())
    
    def split(self, resolution):
        raise NotImplementedError
    
    def plot(self, ax, s):
        raise NotImplementedError
    
    def __repr__(self):
        return f"{self.__class__.__name__}(name=\"{self.name}\")"


class Drift(Element):

    def __init__(self, length, energy=1e+8, name=None):
        """Create the transfer matrix of a drift section of given length."""
        self.length = length
        self.energy = energy

        super().__init__(name=name)
    
    @property
    def transfer_map(self):
        gamma = self.energy / REST_ENERGY
        igamma2 = 1 / gamma**2 if gamma != 0 else 0

        return np.array([[1, self.length, 0,           0, 0,                     0, 0],
                         [0,           1, 0,           0, 0,                     0, 0],
                         [0,           0, 1, self.length, 0,                     0, 0],
                         [0,           0, 0,           1, 0,                     0, 0],
                         [0,           0, 0,           0, 1, self.length * igamma2, 0],
                         [0,           0, 0,           0, 0,                     1, 0],
                         [0,           0, 0,           0, 0,                     0, 1]])
    
    def split(self, resolution):
        split_elements = []
        remaining = self.length
        while remaining > 0:
            element = Drift(min(resolution, remaining), energy=self.energy)
            split_elements.append(element)
            remaining -= resolution
        return split_elements
    
    def plot(self, ax, s):
        pass

    def __repr__(self):
        return f"{self.__class__.__name__}(length={self.length:.2f}, name=\"{self.name}\")"


class Quadrupole(Element):

    def __init__(self, length, k1, energy=1e+8, name=None):
        """Create the transfer matrix of a quadrupole magnet of the given parameters."""
        self.length = length
        self.k1 = k1
        self.energy = energy

        super().__init__(name=name)
    
    @property
    def transfer_map(self):
        gamma = self.energy / REST_ENERGY
        igamma2 = 1 / gamma**2 if gamma != 0 else 0

        beta = np.sqrt(1 - igamma2)
        
        hx = 0
        kx2 = self.k1 + hx**2
        ky2 = -self.k1
        kx = np.sqrt(kx2 + 0.j)
        ky = np.sqrt(ky2 + 0.j)
        cx = np.cos(kx * self.length).real
        cy = np.cos(ky * self.length).real
        sy = (np.sin(ky * self.length) / ky).real if ky != 0 else self.length

        if kx != 0:
            sx = (np.sin(kx * self.length) / kx).real
            dx = hx / kx2 * (1. - cx)
            r56 = hx**2 * (self.length - sx) / kx2 / beta**2
        else:
            sx = self.length
            dx = self.length**2 * hx / 2
            r56 = hx**2 * self.length**3 / 6 / beta**2
        
        r56 -= self.length / beta**2 * igamma2

        return np.array([[            cx,        sx,         0,  0, 0,      dx / beta, 0],
                         [     -kx2 * sx,        cx,         0,  0, 0, sx * hx / beta, 0],
                         [             0,         0,        cy, sy, 0,              0, 0],
                         [             0,         0, -ky2 * sy, cy, 0,              0, 0],
                         [sx * hx / beta, dx / beta,         0,  0, 1,            r56, 0],
                         [             0,         0,         0,  0, 0,              1, 0],
                         [             0,         0,         0,  0, 0,              0, 1]])
    
    def split(self, resolution):
        split_elements = []
        remaining = self.length
        while remaining > 0:
            element = Quadrupole(min(resolution, remaining), self.k1, energy=self.energy)
            split_elements.append(element)
            remaining -= resolution
        return split_elements
    
    def plot(self, ax, s):
        alpha = 1 if self.k1 != 0 else 0.2
        height = np.sign(self.k1) if self.k1 != 0 else 1
        patch = Rectangle((s, 0),
                           self.length,
                           height,
                           color="tab:red",
                           alpha=alpha,
                           zorder=2)
        ax.add_patch(patch)
    
    def __repr__(self):
        return f"{self.__class__.__name__}(length={self.length:.2f}, " + \
                                         f"k1={self.k1}, " + \
                                         f"name=\"{self.name}\")"


class HorizontalCorrector(Element):

    def __init__(self, length, angle, energy=1e+8, name=None):
        """Create the transfer matrix of a horizontal corrector magnet of the given parameters."""
        self.length = length
        self.angle = angle

        super().__init__(name=name)

    @property
    def transfer_map(self):
        return np.array([[1, self.length, 0,           0, 0, 0,          0],
                         [0,           1, 0,           0, 0, 0, self.angle],
                         [0,           0, 1, self.length, 0, 0,          0],
                         [0,           0, 0,           1, 0, 0,          0],
                         [0,           0, 0,           0, 1, 0,          0],
                         [0,           0, 0,           0, 0, 1,          0],
                         [0,           0, 0,           0, 0, 0,          1]])
    
    def split(self, resolution):
        split_elements = []
        remaining = self.length
        while remaining > 0:
            length = min(resolution, remaining)
            element = HorizontalCorrector(length,
                                          self.angle * length / self.length)
            split_elements.append(element)
            remaining -= resolution
        return split_elements
    
    def plot(self, ax, s):
        alpha = 1 if self.angle != 0 else 0.2
        height = np.sign(self.angle) if self.angle != 0 else 1
        patch = Rectangle((s, 0),
                           self.length,
                           height,
                           color="tab:blue",
                           alpha=alpha,
                           zorder=2)
        ax.add_patch(patch)
    
    def __repr__(self):
        return f"{self.__class__.__name__}(length={self.length:.2f}, " + \
                                         f"angle={self.angle}, " + \
                                         f"name=\"{self.name}\")"


class VerticalCorrector(Element):

    def __init__(self, length, angle, energy=1e+8, name=None):
        """Create the transfer matrix of a vertical corrector magnet of the given parameters."""
        self.length = length
        self.angle = angle

        super().__init__(name=name)

    @property
    def transfer_map(self):
        return np.array([[1, self.length, 0,           0, 0, 0,          0],
                         [0,           1, 0,           0, 0, 0,          0],
                         [0,           0, 1, self.length, 0, 0,          0],
                         [0,           0, 0,           1, 0, 0, self.angle],
                         [0,           0, 0,           0, 1, 0,          0],
                         [0,           0, 0,           0, 0, 1,          0],
                         [0,           0, 0,           0, 0, 0,          1]])
    
    def split(self, resolution):
        split_elements = []
        remaining = self.length
        while remaining > 0:
            length = min(resolution, remaining)
            element = HorizontalCorrector(length,
                                          self.angle * length / self.length)
            split_elements.append(element)
            remaining -= resolution
        return split_elements
    
    def plot(self, ax, s):
        alpha = 1 if self.angle != 0 else 0.2
        height = np.sign(self.angle) if self.angle != 0 else 1
        patch = Rectangle((s, 0),
                           self.length,
                           height,
                           color="tab:cyan",
                           alpha=alpha,
                           zorder=2)
        ax.add_patch(patch)
    
    def __repr__(self):
        return f"{self.__class__.__name__}(length={self.length:.2f}, " + \
                                         f"angle={self.angle}, " + \
                                         f"name=\"{self.name}\")"


class Screen(Element):

    length = 0
    transfer_map = np.eye(7)

    def __call__(self, particles):
        return particles
    
    def split(self, resolution):
        return []
    
    def plot(self, ax, s):
        patch = Rectangle((s, -0.6),
                           0,
                           0.6 * 2,
                           color="gold",
                           zorder=2)
        ax.add_patch(patch)


class Segment(Element):

    def __init__(self, ocelot_cell, name=None):
        self.elements = [ocelot2joss(element) for element in ocelot_cell]
        for element in self.elements:
            self.__dict__[element.name] = element
        
        super().__init__(name=name)
    
    @property
    def transfer_map(self):
        transfer_map = np.eye(7)
        for element in self.elements:
            transfer_map = np.matmul(element.transfer_map, transfer_map)
        return transfer_map
    
    def split(self, resolution):
        return [split_element for element in self.elements
                              for split_element in element.split(resolution)]

    def plot_reference_particles(self, particles, n=10, resolution=0.01):
        splits = self.split(resolution)

        split_lengths = [split.length for split in splits]
        ss = [0] + [sum(split_lengths[:i+1]) for i, _ in enumerate(split_lengths)]

        references = np.zeros((len(ss), n, particles.shape[1]))
        references[0] = particles[np.random.choice(len(particles), n, replace=False)]
        for i, split in enumerate(splits):
            references[i+1] = split(references[i])

        fig = plt.figure()
        gs = fig.add_gridspec(3, hspace=0, height_ratios=[2,2,1])
        axs = gs.subplots(sharex=True)

        axs[0].set_title("Reference Particle Traces")
        for particle in range(references.shape[1]):
            axs[0].plot(ss, references[:,particle,0])
        axs[0].set_ylabel("x (m)")
        axs[0].grid()

        for particle in range(references.shape[1]):
            axs[1].plot(ss, references[:,particle,2])
        axs[1].set_ylabel("y (m)")
        axs[1].grid()

        element_lengths = [element.length for element in self.elements]
        element_ss = [0] + [sum(element_lengths[:i+1]) for i, _ in enumerate(element_lengths[:-1])]
        axs[2].plot([0, ss[-1]], [0, 0], "--", color="black")
        for element, s in zip(self.elements, element_ss):
            element.plot(axs[2], s)
        axs[2].set_ylim(-1.2, 1.2)
        axs[2].set_xlabel("s (m)")
        axs[2].set_yticks([])
        axs[2].grid()

        plt.tight_layout()
        plt.show()

    def __repr__(self):
        start = f"{self.__class__.__name__}(["

        s = start + self.elements[0].__repr__()
        x = ["\n" + (" " * len(start)) + element.__repr__() for element in self.elements[1:]]
        s += "".join(x)
        s += "])"

        return s
