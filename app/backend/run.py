import uvicorn
import uvicorn.config

from src.core.config import get_settings

fmt = '[%(asctime)s] [%(levelno)s] [%(status_code)s] %(client_addr)s - "%(request_line)s"'
log_config = uvicorn.config.LOGGING_CONFIG
log_config["formatters"]["access"]["fmt"] = fmt
if __name__ == "__main__":
    settings = get_settings()
    uvicorn.run(
        "src.main:app",
        host=settings.BACKEND_HOST,
        port=settings.BACKEND_PORT,
        workers=settings.BACKEND_WORKERS,
        reload=settings.DEV_UVICORN_RELOAD,
    )
