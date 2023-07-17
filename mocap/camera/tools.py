from pypylon import genicam
from pypylon import pylon
import numpy as np

import time
import yaml

def read_config(config_file):
    with open(config_file, 'r') as f:
        config = yaml.safe_load(f)
 
    return config

# Example of an image event handler.
class SampleImageEventHandler(pylon.ImageEventHandler):
    
    # def __init__(self, pipe_out, *args, **kwargs):
        # super().__init__(*args, **kwargs)
        # self.pipe_out = pipe_out
        
    def __init__(self, pipe_out, shared_arr, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.pipe_out = pipe_out
        self.shared_arr = shared_arr
        self.shared_arr_np = np.frombuffer(self.shared_arr.get_obj(), dtype=np.uint8)
        
    # def OnImageGrabbed(self, camera, grabResult):
    #     if grabResult.GrabSucceeded():
    #         img = grabResult.GetArray()
    #         print(img.shape)
    #         img = np.zeros(1)
    #         cnt = grabResult.ImageNumber
    #         self.pipe_out.send((time.perf_counter_ns(), img))
            
    
    def OnImageGrabbed(self, camera, grabResult):
        if grabResult.GrabSucceeded():
            img = grabResult.GetArray()
            with self.shared_arr.get_lock():
                self.shared_arr_np[:] = img.reshape(-1)
            cnt = grabResult.ImageNumber
            # self.pipe_out.send(time.perf_counter_ns())
            self.pipe_out.send((cnt, time.perf_counter_ns()))

