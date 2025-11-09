import logging
import logging.handlers
import os

from src.core.config import get_settings

settings = get_settings()

_LOG_ROTATE_MAXBYTES = 500 * 1024**2
_LOG_ROTATE_BACKUPCOUNT = 5

_LOG_DEBUG_ROTATE_MAXBYTES = 500 * 1024**2
_LOG_DEBUG_ROTATE_BACKUPCOUNT = 3


def configure_logging() -> None:
    standard_logformat = "[%(asctime)s][%(levelname)s][%(name)s]: %(message)s"
    debug_logformat = "[%(asctime)s][%(levelname)s][%(name)s]: %(message)s %(pathname)s:%(lineno)d"
    formatter = logging.Formatter(standard_logformat)
    debug_formatter = logging.Formatter(debug_logformat)

    console_handler = logging.StreamHandler()
    if settings.LOG_LEVEL == "DEBUG":
        console_handler.setFormatter(debug_formatter)
    else:
        console_handler.setFormatter(formatter)
    console_handler.setLevel(settings.LOG_LEVEL)

    log_name = "src"

    log = logging.getLogger(log_name)
    log.handlers = []
    log.setLevel(level=logging.DEBUG)
    log.addHandler(console_handler)

    log_dir = "./logs"
    if not os.path.exists(log_dir):
        os.makedirs(log_dir)
    log_file_path = os.path.join(log_dir, "backend.log")
    file_handler = logging.handlers.RotatingFileHandler(
        log_file_path,
        maxBytes=_LOG_ROTATE_MAXBYTES,
        backupCount=_LOG_ROTATE_BACKUPCOUNT,
    )
    file_handler.setFormatter(formatter)
    file_handler.setLevel(logging.INFO)
    log.addHandler(file_handler)

    debug_log_file_path = os.path.join(log_dir, "backend.debug.log")
    debug_file_handler = logging.handlers.RotatingFileHandler(
        debug_log_file_path,
        maxBytes=_LOG_DEBUG_ROTATE_MAXBYTES,
        backupCount=_LOG_DEBUG_ROTATE_BACKUPCOUNT,
    )
    debug_file_handler.setFormatter(debug_formatter)
    debug_file_handler.setLevel(logging.DEBUG)
    log.addHandler(debug_file_handler)
