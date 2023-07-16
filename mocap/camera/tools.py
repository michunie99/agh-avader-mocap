from pypylon import genicam
from pypylon import pylon

from configurationeventprinter import ConfigurationEventPrinter
from imageeventprinter import ImageEventPrinter

import time
import yaml

def read_config(config_file):
    with open(config_file, 'r') as f:
        config = yaml.safe_load(f)
 
    return config

# Example of an image event handler.
class SampleImageEventHandler(pylon.ImageEventHandler):
    
    def __init__(self, pipe_out, converter, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.pipe_out = pipe_out
        self.converted = converter
        
    def OnImageGrabbed(self, camera, grabResult):
        if grabResult.GrabSucceeded():
            image = self.converter.Convert(grabResult)
            img = image.GetArray()
            self.pipe_out.send(img)