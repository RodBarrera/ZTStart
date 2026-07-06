"""Errores propios del motor de aprobación."""

from __future__ import annotations


class ExcepcionNoEncontradaError(LookupError):
    """No existe ninguna solicitud de excepción con el ID dado."""


class TransicionInvalidaError(ValueError):
    """Se intentó una transición de estado no permitida (ej. aprobar algo ya rechazado)."""
