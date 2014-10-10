import gi
gi.require_version('Gst', '1.0')
from gi.repository import GObject, Gst

import numpy as np
import RPi.GPIO as GPIO

GPIO.setmode(GPIO.BCM)
GPIO.setup(23, GPIO.IN, pull_up_down = GPIO.PUD_DOWN)
GPIO.setup(22, GPIO.IN, pull_up_down = GPIO.PUD_UP)


GObject.threads_init()
Gst.init(None)

def btnCallback(channel):
        print("Button 1 pressed!!")
        

print "This is "+Gst.version_string()

GPIO.add_event_detect(23, GPIO.RISING, callback=btnCallback, bouncetime=500)

# create a pipline
stream_pipe = "souphttpsrc location=http://koelncampus.uni-koeln.de:8001 iradio-mode=true ! icydemux ! mpegaudioparse ! mad ! alsasink"
pipline = Gst.parse_launch(stream_pipe)
pipline.set_state(Gst.State.PLAYING)
GObject.MainLoop().run()
