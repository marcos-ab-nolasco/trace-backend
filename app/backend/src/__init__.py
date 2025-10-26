from src.core.logging_config.local import configure_logging

from .version import __version__

configure_logging()

__all__ = ["__version__"]
