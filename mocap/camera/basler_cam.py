from pypylon import genicam
from pypylon import pylon
import paho.mqtt.client as mqtt
import cv2 as cv
import matplotlib.pyplot as plt
import numpy as np

from multiprocessing import Pipe, Process, Array
import time
import ctypes

from .tools import read_config, SampleImageEventHandler

class MocapCamera():
    
    def __init__(
        self,
        config_file
    ):
        # Read configuration
        self.config = read_config(config_file)
        
        # Create a pipe for image passing
        self.camera_pipe = Pipe()
        
        ARR_SIZE = 1080*1440
        
        self.shared_arr = Array(
            ctypes.c_ubyte, 
            ARR_SIZE,
        )
         
        # Confgiure MQTT server
        host_name = self.config["MQTT"].get("HOST_NAME", "foo")
        self.client = mqtt.Client(
            host_name,
            clean_session=True,
        )

        # Parse camera configuration
        fps = self.config["CAMERA"].get("FPS", 60)
        exposure = self.config["CAMERA"].get("EXPOSURE", 10000.0)
        hard_trigg =  self.config["CAMERA"].get("HARD_TRIGG", False)
        
        # Connect camera
        self.camera = pylon.InstantCamera(pylon.TlFactory.GetInstance().CreateFirstDevice()) 
        if hard_trigg: 
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
       
        self.camera.Open() 
        # Set fps
        self.camera.AcquisitionFrameRateEnable.SetValue(True)
        self.camera.AcquisitionFrameRate.SetValue(fps)
        # Set exposure time
        self.camera.ExposureTime.SetValue(exposure)
        # Set pixel format to mono
        self.camera.PixelFormat.SetValue("Mono8")
        self.camera.Close()
         
        # Initialize processes
        self.initialize_processes()
        
    def initialize_processes(self):
        """ Initialize processes and communitaion for processing pipe line """
        cam_proc = Process(
            target=self.post_process, 
            args=(self.camera_pipe[1], self.shared_arr)
        )
        self.processes = [cam_proc]
            
    def post_process(self, pipe_in, shared_memory):
        """ Thread used for post processing """

        shared_np = np.frombuffer(
            shared_memory.get_obj(), 
            dtype=np.uint8,
        )
        
        while True:
            cnt, ts = pipe_in.recv()
            with shared_memory.get_lock():
                frame = np.copy(shared_np)
                frame = frame.reshape((1080, 1440))
        
            cv.putText(frame, str(cnt), (50, 50), cv.FONT_HERSHEY_SIMPLEX, 1, (255, 0, 0), 2, cv.LINE_AA)
            cv.imshow("Frame", frame)
            cv.waitKey(1)
            
            # frame = np.zeros((100, 100))
            print("Delay: ", (time.perf_counter_ns() - ts)*1e-9)

            
    def run(self):
        try:
            for proc in self.processes:
                proc.start()
                
            self.camera.StartGrabbing(
                # pylon.GrabStrategy_OneByOne, 
                pylon.GrabStrategy_LatestImageOnly,
                pylon.GrabLoop_ProvidedByInstantCamera,
            )
            
            while True:
               pass
           
        except KeyboardInterrupt:
            self.camera.StopGrabbing()
            # Send poison pill
            self.camera_pipe[0].send(None)
            for proc in self.processes:
                proc.join()