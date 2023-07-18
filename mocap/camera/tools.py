from pypylon import genicam
from pypylon import pylon
import numpy as np
import cv2 as cv

import time
import yaml
import os
from pathlib import Path

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

def get_calibration_results(imgs_path, config):
    ROWS, COLS = config["ROWS"], config["COLS"]
    
    # termination criteria
    criteria = (cv.TERM_CRITERIA_EPS + cv.TERM_CRITERIA_MAX_ITER, 30, 0.001)
    # prepare object points, like (0,0,0), (1,0,0), (2,0,0) ....,(6,5,0)
    objp = np.zeros((ROWS*COLS,3), np.float32)
    objp[:,:2] = np.mgrid[0:COLS,0:ROWS].T.reshape(-1,2)
    # Arrays to store object points and image points from all the images.
    objpoints = [] # 3d point in real world space
    imgpoints = [] # 2d points in image plane.
    
    # Extract images from the directory 
    imgs_path = Path(imgs_path)
    
    # Find all images
    imgs = imgs_path.glob("*.bmp")
    for frame in imgs:
        img = cv.imread(str(frame))
         # Find the chess board corners
        ret, corners = cv.findChessboardCorners(img, (COLS,ROWS), None)
        # If found, add object points, image points (after refining them)
        if ret == True:
            objpoints.append(objp)
            
        corners2 = cv.cornerSubPix(img,corners, (11,11), (-1,-1), criteria)
        imgpoints.append(corners2)
        # Draw and display the corners
        cv.drawChessboardCorners(img, (COLS,ROWS), corners2, ret)
        cv.imshow('img', img)
        cv.waitKey(500)
    cv.destroyAllWindows()
    
    calib_res = cv.calibrateCamera(
        objpoints, 
        imgpoints, 
        img.shape[::-1], 
        None, 
        None,
    )
    
    return calib_res

# Example of an image event handler.
class SampleImageEventHandler(pylon.ImageEventHandler):
    def __init__(self, pipe_out, shared_arr, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.pipe_out = pipe_out
        self.shared_arr = shared_arr
        self.shared_arr_np = np.frombuffer(self.shared_arr.get_obj(), dtype=np.uint8)
        
    def OnImageGrabbed(self, camera, grabResult):
        if grabResult.GrabSucceeded():
            img = grabResult.GetArray()
            with self.shared_arr.get_lock():
                self.shared_arr_np[:] = img.reshape(-1)
            cnt = grabResult.ImageNumber
            # self.pipe_out.send(time.perf_counter_ns())
            self.pipe_out.send((cnt, time.perf_counter_ns()))

class ImageSaver():
    """ 
    Simple class for saving images to a temporary dir,
    can be used for calibration/debuging
    """
    def __init__(self, tmp_dir, num_imgs, every_n, presistant=False):
        self.tmp_dir = Path(tmp_dir)
        if not self.tmp_dir.exists():
            self.tmp_dir.mkdir(parents=True)
        self.num_imgs = num_imgs
        self.every_n = every_n
        self.current = 0
        self.saved = 0
        self.presistant = presistant
        
    def save_image(self, img):
        if self.saved >= self.num_imgs:
            return True
        
        if self.current % self.every_n == 0:
            img_name = f"frame_{self.saved:03}.bmp"
            cv.imwrite(str(self.tmp_dir / img_name), img)
            self.saved += 1
        
        self.current += 1
        
        return False
    
    def __del__(self):
        # Remove temporaty dir
        if not self.presistant:
            for file in self.tmp_dir.glob("*"):
                os.remove(file)
            self.tmp_dir.rmdir()
     
        
if __name__ == "__main__":
    saver = ImageSaver("tmp", 10, 1, True)
    
    while saver.save_image(np.random.randint(0,255, (224, 224, 3))):
        time.sleep(1)
        
    input("After this the dir will be deleted")
    
    del saver
    
    print("Tmp dir was deleted")
    