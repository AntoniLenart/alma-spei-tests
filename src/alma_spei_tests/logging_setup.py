"""Shared logger factory so steps and orchestration log consistently."""

import logging

_CONFIGURED = False


def get_logger(name: str = "alma_spei_tests") -> logging.Logger:
    """Return a module logger, configuring a sane default handler once."""
    global _CONFIGURED
    if not _CONFIGURED:
        logging.basicConfig(
            level=logging.INFO,
            format="%(asctime)s %(levelname)-5s %(name)s: %(message)s",
            datefmt="%H:%M:%S",
        )
        _CONFIGURED = True
    return logging.getLogger(name)
