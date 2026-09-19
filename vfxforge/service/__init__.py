"""Intent-driven VFX generation service built on the canonical document model."""

from .result import ForgeStatus, make_result

__all__ = ["ForgeStatus", "make_result"]


def __getattr__(name: str):
    if name == "forge":
        from .pipeline import forge

        return forge
    if name == "plan":
        from .pipeline import plan

        return plan
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
