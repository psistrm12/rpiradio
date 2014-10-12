import gi
gi.require_version('Gst', '1.0')
from gi.repository import GObject, Gst

import numpy as np
from buttonIO import RotaryEncoder, PushButton


GObject.threads_init()
Gst.init(None)
       

print "This is "+Gst.version_string()

def on_new_decoded_pad(dbin, pad):
    print "decode pad"
    decode = pad.get_parent()
    pipeline = dbin.get_parent()
    convert = pipeline.get_by_name("cvt")
    decode.link(convert)
    pipeline.set_state(Gst.State.PLAYING)
    print "linked!"
    
    
# This is the event callback routine to handle events
def switch_volume_event(event):
    if event == RotaryEncoder.CLOCKWISE:
        print "Volume up"
    elif event == RotaryEncoder.ANTICLOCKWISE:
        print "Volume down"
    return

def switch_play_pause_event(event):
    if event == PushButton.BUTTONDOWN:
        print "Toggle Play/Pause"
    elif event == PushButton.BUTTONUP:
        print "Pushbutton up - ignored"

def main():
    print "init"

    # Define GPIO inputs
    VOL_UP_PIN = 24 	 
    VOL_DOWN_PIN = 18		
    vol_input = RotaryEncoder(VOL_UP_PIN, VOL_DOWN_PIN, switch_volume_event)
    
    # a simple pushbutton for settint toggling play/pause 
    PLAY_PAUSE_PIN = 23
    play_pause_input = PushButton(PLAY_PAUSE_PIN, 200, switch_play_pause_event)

    pipeline = Gst.Pipeline()
    source = Gst.ElementFactory.make("souphttpsrc", "source")
    print source
    #self.icydemux = Gst.ElementFactory.make("icydemux", "demux")
    #print self.icydemux
    decode = Gst.ElementFactory.make("decodebin", "decode")
    print decode
    convert = Gst.ElementFactory.make("audioconvert", "cvt")
    print convert
    audiosink = Gst.ElementFactory.make("alsasink", "sink")
    print audiosink
        
    ret = pipeline.add(source) 
    print "added source %r" % ret
    ret = pipeline.add(convert) 
    print "added convert %r" % ret
    ret = pipeline.add(decode)
    print "added decode %r" % ret
    ret = pipeline.add(audiosink)
    print "added sink %r" % ret
    
    ret = source.link(decode)
    print "linked src to decode %r" % ret 
    #ret = decode.link(convert)
    #print "linked decode to cvt %r" % ret
    ret = convert.link(audiosink)
    print "linked cvt to sink %r" % ret
 
    source.set_property("location", "http://koelncampus.uni-koeln.de:8001")
    source.set_property("iradio-mode", True)
    
    
    decode.connect("pad-added", on_new_decoded_pad)

    pipeline.set_state(Gst.State.PAUSED)
    #pipeline.set_state(Gst.State.PLAYING)
        #stream_pipe = "souphttpsrc location=http://koelncampus.uni-koeln.de:8001 iradio-mode=true ! icydemux ! mpegaudioparse ! mad ! alsasink"

main()
GObject.MainLoop().run()
