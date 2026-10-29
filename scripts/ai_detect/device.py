"""Pick the compute device: cuda, then Apple's mps, then cpu.

AI_DEVICE=cpu|mps|cuda forces one. PYTORCH_ENABLE_MPS_FALLBACK=1 is set so that an operation
the Metal backend does not implement runs on the CPU instead of raising.
"""
import os

os.environ.setdefault("PYTORCH_ENABLE_MPS_FALLBACK", "1")


def pick_device(torch, requested=None):
    """`torch` is passed in so tests can fake what is available."""
    requested = requested or os.environ.get("AI_DEVICE")
    if requested:
        return requested
    if torch.cuda.is_available():
        return "cuda"
    mps = getattr(torch.backends, "mps", None)
    if mps is not None and mps.is_available():
        return "mps"
    return "cpu"


def pick_dtype(torch, device, requested=None):
    """bfloat16 on cuda, float16 on mps (bfloat16 is not reliably supported there), float32 on cpu.

    AI_DTYPE=float32|float16|bfloat16 overrides."""
    name = requested or os.environ.get("AI_DTYPE")
    if name:
        return getattr(torch, name)
    return {"cuda": torch.bfloat16, "mps": torch.float16}.get(device, torch.float32)
