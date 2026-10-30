"""Renderers turn a SessionReport into terminal text, SVG or JSON."""

from .svg import render_svg
from .terminal import render_terminal

__all__ = ["render_terminal", "render_svg"]
