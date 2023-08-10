from pathlib import Path
import threading
import datetime
import cv2
import numpy as np

from .tools import (
    read_config,
    VideoStreamSubscriber,
)

class Server():
    def __init__(
        self,
        config_file
    ):

        # Read configuration
        self.config = read_config(config_file)
        self.publishers = self.config["PUBLISHERS"]
        self.data_dir = self.config["DATA_DIR"]
        self.exp_dir = self._create_dirs()
        self.stream = VideoStreamSubscriber(self.publishers, "5555")

        self._start_reciving = threading.Event()
        self._stop_threads = threading.Event()

    def save_images(self):
        try:
            t = threading.Thread(target=self._save_thread, args=(self.stream, Path(self.exp_dir))) 
            print("Starting reciving data")
            t.start()
        except:
            print("Stoped reciving data")
            self._stop_threads.set()
                    

    def _save_thread(self, stream, data_dir):
        cam_cnt = {}
        while True:
            if self._stop_threads.is_set():
                break
            msg, jpg_buffer = stream.receive()
            cnt = cam_cnt.setdefault(msg, 0)
            image = cv2.imdecode(np.frombuffer(jpg_buffer, dtype='uint8'), -1)
            img_name = data_dir / f"{msg}/frame_{cnt}.jpg"
            print(img_name)
            #cv2.imwrite(str(img_name), image)
            cam_cnt[msg] += 1
            cv2.imshow(msg, cv2.resize(image, (255, 255))) 
            cv2.waitKey(1)

        stream.close()

    def _create_dirs(self):
        root = Path(self.data_dir)
        current_datetime = datetime.datetime.now()
        exp_id = current_datetime.strftime("%Y-%m-%d_%H-%M-%S")
        exp_dir = root / exp_id
        pub_dirs = []
        for pub in self.publishers:
            pub_dir = exp_dir / pub
            pub_dir.mkdir(parents=True, exist_ok=True)
            pub_dirs.append(Path(pub_dir))

        return exp_dir