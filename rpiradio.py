import gi
gi.require_version('Gst', '1.0')
from gi.repository import GObject, Gst

import numpy as np
from buttonIO import RotaryEncoder, PushButton


GObject.threads_init()
Gst.init(None)
       
    
class RPiRadio():
    def __init__(self):
        print "[RPiRadio] init "
        
        pipeline = Gst.Pipeline()
        source = Gst.ElementFactory.make("souphttpsrc", "src")
        decode = Gst.ElementFactory.make("decodebin", "dec")
        convert = Gst.ElementFactory.make("audioconvert", "cvt")
        volume = Gst.ElementFactory.make("volume", "vol")
        audiosink = Gst.ElementFactory.make("alsasink", "sink")
    
        # add elements
        ret = pipeline.add(source) 
        print "added source %r" %ret
        ret = pipeline.add(convert) 
        print "added convert %r" %ret
        ret = pipeline.add(decode)
        print "added decode %r" %ret
        ret = pipeline.add(volume)
        print "added volume %r" %ret
        ret = pipeline.add(audiosink)
        print "added sink %r" %ret
        
        # link elements
        ret = source.link(decode)
        print "linked src to decode %r" %ret
        # we cannot link decode and convert at this stage! We have to wait for the decode pad to arrive...
        # See http://stackoverflow.com/questions/2993777/gstreamer-of-pythons-gst-linkerror-problem for details!
        ret = convert.link(volume)
        print " linked cvt to volume %r" %ret
        ret = volume.link(audiosink)
        print "linked volume to sink %r" %ret
     
        source.set_property("location", "http://koelncampus.uni-koeln.de:8001")
        source.set_property("iradio-mode", True)
        volume.set_property("volume", 0.5)
        decode.connect("pad-added", self.on_new_decoded_pad)
        pipeline.set_state(Gst.State.PAUSED)
        
        # Define GPIO inputs
        VOL_UP_PIN = 24      
        VOL_DOWN_PIN = 23        
        vol_input = RotaryEncoder(VOL_UP_PIN, VOL_DOWN_PIN, self.switch_volume_event) 
        # a simple pushbutton for settint toggling play/pause 
        PLAY_PAUSE_PIN = 18
        BTN_BOUNCETIME = 200
        play_pause_input = PushButton(PLAY_PAUSE_PIN, BTN_BOUNCETIME, self.switch_play_pause_event)
        
        #self.volume = volume
        self.pipeline = pipeline
        
        return
        
    # This is the event callback routine to handle events
    def switch_volume_event(self, event):
        volume = self.pipeline.get_by_name("vol")
        if event == RotaryEncoder.CLOCKWISE:
            vol = volume.get_property("volume")
            if vol < 1:
                vol = vol + 0.01
                volume.set_property("volume", vol)
                print "Volume up %i" % (vol*100)
        elif event == RotaryEncoder.ANTICLOCKWISE:
            vol = volume.get_property("volume")
            if vol > 0:
                vol = vol - 0.01
                volume.set_property("volume", vol)
                print "Volume down %i" % (vol*100)
        return
    
    def switch_play_pause_event(self, event):
        if event == PushButton.BUTTONDOWN:
            state = self.pipeline.get_state(0)[1]   # current state of the pipeline
            if state == Gst.State.PAUSED:
                self.pipeline.set_state(Gst.State.PLAYING)
                print "set pipeline to PLAYING"
                return
            elif state == Gst.State.PLAYING:
                self.pipeline.set_state(Gst.State.PAUSED)
                print "set pipeline to PAUSED"
                return
        elif event == PushButton.BUTTONUP:
            print "Pushbutton up - ignored"
            
        return
    
    # callback for received decode pad
    def on_new_decoded_pad(self, decodebin, pad):
        convert = self.pipeline.get_by_name("cvt")  # link decodebin to audioconvert
        ret = decodebin.link(convert)
        print "linked decode to convert %r" %ret
        
        self.pipeline.set_state(Gst.State.PLAYING)  # only now we can set the pipeline to PLAYING
        return
    
def main():
    
    print "This is "+Gst.version_string()
    rpiradio = RPiRadio()


main()
GObject.MainLoop().run()
