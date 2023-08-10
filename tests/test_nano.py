from mocap.camera import MocapCamera

cam = MocapCamera("configs/nano_cam.yaml")
cam.start_sending()

input()

cam.stop()
