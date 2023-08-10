import sys

import socket
import traceback
import cv2
import numpy as np
import threading

from .imagezmq import ImageHub
import time
import yaml
import os
from pathlib import Path

def read_config(config_file):
    with open(config_file, 'r') as f:
        config = yaml.safe_load(f)
 
    return config

# Helper class implementing an IO deamon thread
class VideoStreamSubscriber:

    def __init__(self, hostnames, port):
        self.hostnames = hostnames
        self.port = port
        self._stop = False
        self._data_ready = threading.Event()
        self._thread = threading.Thread(target=self._run, args=())
        self._thread.daemon = True
        self._thread.start()

    def receive(self, timeout=15.0):
        flag = self._data_ready.wait(timeout=timeout)
        if not flag:
            raise TimeoutError(
                "Timeout while reading from subscriber")
        self._data_ready.clear()
        return self._data

    def _run(self):
        receiver = ImageHub("tcp://{}:{}".format(self.hostnames[0], self.port), REQ_REP=False)
        for pub in self.hostnames[1:]:
            receiver.connect(f"tcp://{pub}:{self.port}")        
        while not self._stop:
            self._data = receiver.recv_jpg()
            self._data_ready.set()
        receiver.close()

    def close(self):
        self._stop = True



