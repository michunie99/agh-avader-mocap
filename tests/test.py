from mocap.camera import MocapCamera

cam = MocapCamera("configs/nano_cam.yaml")
cam.start_detect()

input()

cam.stop()

print(cam.run_calibration()[1])