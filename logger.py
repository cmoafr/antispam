import logging
import logging.handlers
import os
import sys

logger = logging.getLogger('discord')

def setup_logger():
    global logger
    logger.setLevel(logging.INFO)

    # Formatter
    fmt = '[{levelname:<8}] ({asctime}) {message}'
    datefmt = '%m/%d %H:%M:%S'
    formatter = logging.Formatter(fmt, datefmt, style='{')

    # Log to files
    if not os.path.exists('logs'):
        os.mkdir('logs')
    file_handler = logging.handlers.TimedRotatingFileHandler(
        filename='logs/log.txt',
        when='midnight',
        interval=1,
        encoding='utf-8',
        backupCount=7,
    )
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    # Log to stdout
    stdout_handler = logging.StreamHandler(sys.stdout)
    stdout_handler.setLevel(logging.DEBUG)
    stdout_handler.setFormatter(formatter)
    logger.addHandler(stdout_handler)

    return logger