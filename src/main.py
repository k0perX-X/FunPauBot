import importlib
from time import sleep
from bot import bot
from os import listdir
from os.path import isfile, join
from threading import Thread
import logging
import warnings
warnings.simplefilter(action='ignore', category=FutureWarning)
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

secrets_path = "bot_secrets"

files = [f for f in listdir(secrets_path) if isfile(join(secrets_path, f)) and f != 'sample.py']
threads = []

for file in files:
    secret_module = importlib.import_module(secrets_path + "." + file[:-3])
    print(secret_module.__name__)
    threads.append(Thread(
        target=bot,
        args=(secret_module, len(threads),),
        daemon=True
    ))
    threads[-1].start()

while True:
    for thread in threads:
        if not thread.is_alive():
            thread.start()
    sleep(1)
