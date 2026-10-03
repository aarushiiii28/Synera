"""AI Discovery Engine subpackage."""

from .interactions import factorial_interaction
from .classify import classify_factorial
from .continuous import continuous_interaction

__all__ = [
    "factorial_interaction",
    "classify_factorial",
    "continuous_interaction",
]
