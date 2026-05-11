import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path

from app.core.config import Settings

_file_handler_added = False


def configure_logging(settings: Settings | None = None) -> Path | None:
    """
    Console logging always. Optional rotating file under data_dir/logs/api.log when settings provided.
    """
    global _file_handler_added
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
    if settings is None or _file_handler_added:
        return None
    log_dir = settings.data_dir / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    log_path = log_dir / "api.log"
    root = logging.getLogger()
    fmt = logging.Formatter("%(asctime)s %(levelname)s %(name)s %(message)s")
    fh = RotatingFileHandler(
        str(log_path),
        maxBytes=int(settings.system_log_max_bytes),
        backupCount=int(settings.system_log_backup_count),
        encoding="utf-8",
    )
    fh.setFormatter(fmt)
    fh.setLevel(logging.INFO)
    root.addHandler(fh)
    _file_handler_added = True
    return log_path
