from pypylon import genicam
from pypylon import pylon
import paho.mqtt.client as mqtt
import cv2 as cv

from multiprocessing import Pipe, Process

from tools import read_config, SampleImageEventHandler

class MocapCamera():
    
    def __init__(
        self,
        config_file
    ):
        # Read configuration
        self.config = read_config(config_file)
        
        # Create a pipe for image passing
        self.camera_pipe = Pipe()
        self.post_pipe = Pipe()
         
        # Confgiure MQTT server
        host_name = self.config["MQTT"].get("HOST_NAME", "foo")
        self.client = mqtt.Client(
            host_name,
            clean_session=True,
        )

        # Parce camera configuration
        fps = self.config["CAMERA"].get("FPS", 60)
        exposure = self.config["CAMERA"].get("EXPOSURE", 10000.0)
        
        # Connect camera
        self.camera = pylon.InstantCamera(pylon.TlFactory.GetInstance().CreateFirstDevice()) 
        
        # Set fps
        self.camera.AcquisitionFrameRateEnable.SetValue(True)
        self.camera.AcquisitionFrameRate.SetValue(fps)
        
        # Set exposure time
        self.camera.ExposureTimeEnable.SetValue(True)
        self.camera.ExposureTime.SetValue(exposure)
        
        # Set pixel format to mono
        self.camera.PixelFormat.SetValue("Mono8")
        
        self.camera.RegisterImageEventHandler(
            SampleImageEventHandler(self.camera_pipe[0]), 
            pylon.RegistrationMode_Append,
            pylon.Cleanup_Delete,
        )

        # Initialize processes
        self.initialize_processes()
        
    def initialize_processes(self):
        """ Initialize processes and communitaion for processing pipe line """
        cam_proc = Process(target=self.post_process)
        self.processes = [cam_proc]
            
    def post_process(self):
        """ Thread used for post processing """
        while True:
            frame = self.camera_pipe[1].recv()
            if frame is None:
                break
            cv.imshow("Test if works", frame)
            
    def run(self):
        try:
            for proc in self.processes:
                proc.start()
                
            self.camera.StartGrabbing(
                pylon.GrabStrategy_OneByOne,
                pylon.GrabLoop_ProvidedByInstantCamera,
            )
        except:
            self.camera.StopGrabbing()
            # Send poison pill
            self.camera_pipe[0].send(None)
            for proc in self.processes:
                proc.join()