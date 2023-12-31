from pypylon import genicam
from pypylon import pylon
import paho.mqtt.client as mqtt
import cv2 as cv
import matplotlib.pyplot as plt
import numpy as np
from .imagezmq import ImageSender

from multiprocessing import Pipe, Process, Array
import time
import ctypes
import socket   


from .tools import (
    read_config, 
    SampleImageEventHandler, 
    detect_marker,
    ImageSaver,
    get_calibration_results,
    )

class MocapCamera():
    
    def __init__(
        self,
        config_file
    ):
        # Read configuration
        self.config = read_config(config_file)
        
        # TODO - add to config
        self.img_saver = ImageSaver(
            tmp_dir="tmp/", 
            num_imgs=30, 
            every_n=10, 
            presistant=self.config["SAVE_CALIB"],
        )
        
        # Confgiure MQTT server
       # self.host_name = self.config["MQTT"].get("HOST_NAME", "foo")
       # self.client = mqtt.Client(
       #         self.host_name,
       #         clean_session=True,
       # )

        hostname=socket.gethostname()   
        self.IPAddr=socket.gethostbyname(hostname)   
        # self.init_mqtt()
        # Create a pipe for image passing
        self.camera_pipe = Pipe()

        # Parse camera configuration
        fps = self.config["CAMERA"].get("FPS", 60)
        exposure = self.config["CAMERA"].get("EXPOSURE", 10000.0)
        hard_trigg =  self.config["CAMERA"].get("HARD_TRIGG", False)
        
        # Connect camera
        self.camera = pylon.InstantCamera(pylon.TlFactory.GetInstance().CreateFirstDevice()) 
        
        self.camera.Open() 
        # Set fps
        self.camera.AcquisitionFrameRateEnable.SetValue(True)
        self.camera.AcquisitionFrameRate.SetValue(fps)
        # Set exposure time
        self.camera.ExposureTime.SetValue(exposure)
        # Set pixel format to mono
        self.camera.PixelFormat.SetValue("Mono8")
        self.WIDTH = self.camera.Width.GetValue()
        self.HEIGHT = self.camera.Height.GetValue()

        self.camera.Close()
         
        ARR_SIZE = self.WIDTH * self.HEIGHT
        
        self.shared_arr = Array(
            ctypes.c_ubyte, 
            ARR_SIZE,
        )
        
        if hard_trigg: 
            # TODO - add as a hardware trigger
            self.camera.RegisterConfiguration(
                pylon.SoftwareTriggerConfiguration(), 
                pylon.RegistrationMode_ReplaceAll,
                pylon.Cleanup_Delete,
            )
        
        self.camera.RegisterImageEventHandler(
            # SampleImageEventHandler(self.camera_pipe[0]),
            SampleImageEventHandler(self.camera_pipe[0], self.shared_arr), 
            pylon.RegistrationMode_Append,
            pylon.Cleanup_Delete,
        )
       
        # Initialize processes
        self.initialize_processes()
        
    def initialize_processes(self):
        """ Initialize processes and communitaion for processing pipe line """
        detect = Process(
            target=self._detect, 
            args=(self.camera_pipe[1], self.shared_arr)
        )
        
        calibration = Process(
            target=self._calibraion,
            args=(self.camera_pipe[1], self.shared_arr)
        )

        send_images  = Process(
            target=self._send_image,
            args=(self.camera_pipe[1], self.shared_arr)
        )
        
        self.processes = {
            "detect": [detect],
            "calibration": [calibration],
            "send_images": [send_images],
        }
     
    def _send_image(self, pipe_in, shared_memory):
        """ Send images to the server to be saved """
        shared_np = np.frombuffer(
            shared_memory.get_obj(), 
            dtype=np.uint8,
        )
        sender = ImageSender(
                connect_to=f"tcp://*:5555",
                REQ_REP=False
        )

        while True:
            item = pipe_in.recv()
            if item is None:
                    break
            status = item
            with shared_memory.get_lock():
                frame = np.copy(shared_np)

            frame = frame.reshape((self.HEIGHT, self.WIDTH))
            print(f"Sending images: {frame.shape}")
            # Send zeroM
            ret_code, frame = cv.imencode(
                ".jpg", frame, [int(cv.IMWRITE_JPEG_QUALITY), 95])
            sender.send_jpg_pubsub(
                f"{self.IPAddr}", 
                frame
            )

    def _detect(self, pipe_in, shared_memory):
        """ Thread used for marker detection """

        shared_np = np.frombuffer(
            shared_memory.get_obj(), 
            dtype=np.uint8,
        )
        
        while True:
            item = pipe_in.recv()
            if item is None:
                break
            cnt, ts = item
            with shared_memory.get_lock():
                frame = np.copy(shared_np)
                frame = frame.reshape((self.HEIGHT, self.WIDTH))

            # Post processing as in old project
            objs = detect_marker(frame, self.config["POST_PROC"]) 
            print("Delay: ", f"{(time.perf_counter_ns() - ts)*1e-9:.4f} sec")
            for _ ,x, y, r in objs:
                img = cv.circle(frame, (int(x), int(y)), int(r), (0,0,255), 5)
            cv.putText(frame, str(cnt), (50, 50), cv.FONT_HERSHEY_SIMPLEX, 1, (255, 0, 0), 2, cv.LINE_AA)
            cv.imshow("Frame", frame)
            cv.waitKey(1)
            # TODO - send detections to processor
    
    def _calibraion(self, pipe_in, shared_memory):
        """ Thread used for marker detection """
        
        shared_np = np.frombuffer(
            shared_memory.get_obj(), 
            dtype=np.uint8,
        )
        
        while True:
            #item = pipe_in.recv()
            #if item is None:
            #    break
            #cnt, ts = item
            with shared_memory.get_lock():
                frame = np.copy(shared_np)
                frame = frame.reshape((self.HEIGHT, self.WIDTH))

            res = self.img_saver.save_image(frame)            
            if res:
                print("exiting ..")
                # End after images has been colected
                break
    
    def start_sending(self):
        self.running = "send_images"
        for proc in self.processes["send_images"]:
            proc.start()
            
        self.camera.StartGrabbing(
            # pylon.GrabStrategy_OneByOne, 
            pylon.GrabStrategy_LatestImageOnly,
            pylon.GrabLoop_ProvidedByInstantCamera,
        )
            
        
    def run_calibration(self):
        self.running = "calibration"
        
        for proc in self.processes["calibration"]:
            proc.start() 
            
        self.camera.StartGrabbing(
            # pylon.GrabStrategy_OneByOne, 
            pylon.GrabStrategy_LatestImageOnly,
            pylon.GrabLoop_ProvidedByInstantCamera,
        )
            
        # Wait for photos
        for proc in self.processes["calibration"]:
            proc.join()
        self.camera.StopGrabbing()  
        
        # Perform calibration
        calib_res = get_calibration_results(
            self.img_saver.tmp_dir,
            self.config["CALIB"],
        )
        
        # TODO - send calibration results to the MQTT server
        
        return calib_res
        
    def start_detect(self):
        self.running = "detect"
        for proc in self.processes["detect"]:
            proc.start()
            
        self.camera.StartGrabbing(
            # pylon.GrabStrategy_OneByOne, 
            pylon.GrabStrategy_LatestImageOnly,
            pylon.GrabLoop_ProvidedByInstantCamera,
        )
            
     
    def stop(self):      
        self.camera.StopGrabbing()
        
        # Send poison pill
        # self.camera_pipe[0].send(None)
        # TODO - kill all child processes
        for proc in self.processes[self.running]:
            proc.join()
