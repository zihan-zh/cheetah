from typing import Optional

import torch


def are_all_the_same_device(tensors: list[torch.Tensor]) -> torch.device:
    """
    Determines whether all arguments are on the same device and, if so, returns that
    device. If no arguments are passed, global default PyTorch device is returned.
    """
    if len(tensors) > 1:
        assert all(
            argument.device == tensors[0].device for argument in tensors
        ), "All tensors must be on the same device."

    return tensors[0].device if len(tensors) > 0 else torch.get_default_device()


def are_all_the_same_dtype(tensors: list[torch.Tensor]) -> torch.dtype:
    """
    Determines whether all arguments have the same dtype and, if so, returns that dtype.
    If no arguments are passed, global default PyTorch dtype is returned.
    """
    if len(tensors) > 1:
        assert all(
            argument.dtype == tensors[0].dtype for argument in tensors
        ), "All arguments must have the same dtype."

    return tensors[0].dtype if len(tensors) > 0 else torch.get_default_dtype()


def extract_argument_shape(tensors: list[torch.Tensor]) -> torch.Size:
    """Determines whether all arguments have the same shape."""
    if len(tensors) > 1:
        assert all(
            argument.shape == tensors[0].shape for argument in tensors
        ), "Arguments must have the same shape."

    return tensors[0].shape if len(tensors) > 0 else torch.Size([1])


def verify_device_and_dtype(
    tensors: list[Optional[torch.Tensor]],
    desired_device: Optional[torch.device],
    desired_dtype: Optional[torch.dtype],
) -> tuple[torch.device, torch.dtype]:
    """
    Verifies that passed tensors (if they are tensors and not `None`) have the same
    device and dtype and that that device and dtype are the same as the desired device
    and dtype if they are requested.

    If all verifications pass, this function returns the device and dtype shared by all
    tensors.
    """
    not_nones = [tensor for tensor in tensors if tensor is not None]

    chosen_device = (
        desired_device
        if desired_device is not None
        else are_all_the_same_device(not_nones)
    )
    chosen_dtype = (
        desired_dtype
        if desired_dtype is not None
        else are_all_the_same_dtype(not_nones)
    )
    return (chosen_device, chosen_dtype)
