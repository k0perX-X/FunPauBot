import importlib
from logging.handlers import TimedRotatingFileHandler
from time import sleep
from typing import List
from bot_sheet import bot_sheet
from bot_messages import bot_messages
from os import listdir, environ
from os.path import isfile, join
from threading import Thread
import logging
import warnings
import gc
from pathlib import Path
import socket

class RestartableThread(Thread):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.__args = args
        self.__kwargs = kwargs

    def clone(self):
        return RestartableThread(*self.__args, **self.__kwargs)


def init_log():
    logs_dirname = Path('./logs/logs')
    log_filename = logs_dirname.joinpath(f'{socket.gethostname()}.log')
    logs_dirname.mkdir(parents=True, exist_ok=True)
    log_filename.touch(exist_ok=True)
    warnings.simplefilter(action='ignore', category=FutureWarning)
    files_handler = TimedRotatingFileHandler(str(log_filename), when="midnight")
    files_handler.suffix = "%Y-%m-%d"
    logging.basicConfig(
        level=logging.INFO if not environ.get("DEBUG") else logging.DEBUG,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[files_handler, logging.StreamHandler()]
    )


init_log()

secrets_path = "bot_secrets"
files = [f for f in listdir(secrets_path) if isfile(join(secrets_path, f)) and f != 'sample.py' and f[-3:] == '.py']
threads: List[RestartableThread] = []

for file in files:
    secret_module = importlib.import_module(secrets_path + "." + file[:-3])
    logging.info(secret_module.__name__)
    threads.append(RestartableThread(
        target=bot_sheet,
        args=(secret_module, len(threads),),
        daemon=True
    ))
    threads[-1].start()

    threads.append(RestartableThread(
        target=bot_messages,
        args=(secret_module, len(threads),),
        daemon=True
    ))
    threads[-1].start()

if not threads:
    raise Exception("No secrets")

del init_log
del secrets_path
del files
gc.collect()

while True:
    for i in range(len(threads)):
        if not threads[i].is_alive():
            threads[i] = threads[i].clone()
            threads[i].start()
            gc.collect()
    sleep(1)
