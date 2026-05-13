import json
import logging
import logging.handlers
from datetime import datetime, timezone
from pathlib import Path
from config import settings


class _JSONFormatter(logging.Formatter):
    """Machine-readable JSON log lines for file output."""

    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "ts":     datetime.now(timezone.utc).isoformat(),
            "level":  record.levelname,
            "logger": record.name,
            "msg":    record.getMessage(),
        }
        if record.exc_info:
            payload["exc"] = self.formatException(record.exc_info)
        return json.dumps(payload)


def setup_logger() -> None:
    root = logging.getLogger()
    root.setLevel(logging.DEBUG)

    # ── Console (human-readable) ───────────────────────────────────────────
    ch = logging.StreamHandler()
    ch.setLevel(logging.INFO)
    ch.setFormatter(
        logging.Formatter("%(asctime)s [%(levelname)-8s] %(name)s — %(message)s",
                          datefmt="%H:%M:%S")
    )
    root.addHandler(ch)

    # ── Rotating file (JSON) ───────────────────────────────────────────────
    fh = logging.handlers.RotatingFileHandler(
        Path(settings.logs_path) / "bot.log",
        maxBytes=5 * 1024 * 1024,   # 5 MB per file
        backupCount=4,
        encoding="utf-8",
    )
    fh.setLevel(logging.DEBUG)
    fh.setFormatter(_JSONFormatter())
    root.addHandler(fh)

    # Silence noisy third-party loggers
    for noisy in ("httpx", "httpcore", "telegram", "chromadb", "urllib3"):
        logging.getLogger(noisy).setLevel(logging.WARNING)
