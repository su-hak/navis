"""Logging utilities for the AI agent."""
import logging
import sys
from pathlib import Path
from config.settings import settings

# httpx가 요청 URL(텔레그램 봇 토큰 포함)을 INFO 레벨로 출력하지 않도록 억제
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)


def setup_logger(name: str = "navis_agent") -> logging.Logger:
    """
    Set up and configure logger.

    Args:
        name: Logger name

    Returns:
        Configured logger instance
    """
    logger = logging.getLogger(name)
    logger.setLevel(getattr(logging, settings.log_level))

    # Remove existing handlers
    logger.handlers = []

    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.INFO)
    console_format = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    console_handler.setFormatter(console_format)
    logger.addHandler(console_handler)

    # File handler
    log_file = Path(settings.log_file)
    log_file.parent.mkdir(parents=True, exist_ok=True)
    file_handler = logging.FileHandler(log_file)
    file_handler.setLevel(logging.DEBUG)
    file_format = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(filename)s:%(lineno)d - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    file_handler.setFormatter(file_format)
    logger.addHandler(file_handler)

    return logger


# Global logger instance
logger = setup_logger()
