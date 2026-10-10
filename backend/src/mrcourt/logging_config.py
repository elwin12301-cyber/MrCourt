"""Logging that never records personal data (constitution principle III)."""

import logging
import re

_EMAIL = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")
_PHONE = re.compile(r"(?<!\d)\+?\d[\d\s-]{8,}\d(?!\d)")


class RedactPersonalData(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        message = record.getMessage()
        message = _EMAIL.sub("[email]", message)
        message = _PHONE.sub("[phone]", message)
        record.msg, record.args = message, None
        return True


def configure_logging(level: int = logging.INFO) -> None:
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s %(message)s"))
    handler.addFilter(RedactPersonalData())
    root = logging.getLogger()
    root.handlers = [handler]
    root.setLevel(level)
