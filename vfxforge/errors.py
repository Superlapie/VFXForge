"""Errors shared by the machine-facing and human-facing interfaces."""

from __future__ import annotations


class VFXForgeError(Exception):
    """Base error with a stable machine-readable code."""

    def __init__(self, message: str, code: str = "VFXFORGE_ERROR", path: str | None = None):
        super().__init__(message)
        self.message = message
        self.code = code
        self.path = path


class DocumentError(VFXForgeError):
    """The document could not be read, parsed, or migrated safely."""


class ValidationError(VFXForgeError):
    """A document failed validation and must not be exported or saved."""


class ExportError(VFXForgeError):
    """An export or preview artifact could not be produced."""


class RecipeBindingError(VFXForgeError):
    """A recipe binding target does not exist on the compiled document."""
