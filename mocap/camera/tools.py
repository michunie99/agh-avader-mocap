from pypylon import genicam
from pypylon import pylon
import numpy as np
import cv2 as cv

import time
import yaml

def read_config(config_file):
    with open(config_file, 'r') as f:
        config = yaml.safe_load(f)
 
    return config

def save_img(img, every_n=1):
    """ Save image to a folder for furure calibration etc"""
    pass

def detect_marker(img, config):
    """ Detect circular markers on an image """
    # Parse config
    b_thr = config["BIN_THR"]
    k_size = config["KERNEL"]
    c_thr = config["CIRC_THR"]
    w_h_diff = config["W_H_DIFF"]
    b_size = config["BALL_SIZE"]
    area_thr = config["AREA_THR"]
    
    
    # Do image processing
    height, width = img.shape[0], img.shape[1]

    _, thr = cv.threshold(
        img, 
        b_thr, 
        255, 
        cv.THRESH_BINARY,
    )
    
    # return thr
    kernel = cv.getStructuringElement(
        cv.MORPH_RECT,
        (k_size,k_size),
    )
    closing = cv.morphologyEx(
        thr, 
        cv.MORPH_CLOSE, 
        kernel,
    )
    # return closing

    connectivity = 8
    res =  cv.connectedComponentsWithStats(
        closing,
        connectivity,
        cv.CV_32S,
    )
    num_labels, labels, stats, centroids = res
    objs = []
    cnt = 0
    
    for i in range(1, num_labels):
        x, y = centroids[i]
        w = stats[i, cv.CC_STAT_WIDTH]
        h = stats[i, cv.CC_STAT_HEIGHT]
        r = (w + h) / 2
        area = stats[i, cv.CC_STAT_AREA]
        circularity = np.pi * r**2/(area)

        if (area >= area_thr and 
            circularity > c_thr and 
            abs(w - h) <= w_h_diff and
            x-b_size>=0 and x+b_size<=width and
            y-b_size>=0 and y+b_size<=height):
            # print(area)
            objs.append((cnt, *centroids[i], r))
            cnt += 1  

    return objs 

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

