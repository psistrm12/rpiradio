import gi

gi.require_version('Gst', '1.0')
from gi.repository import GObject, Gst

import numpy as np
import time
from buttonIO import RotaryEncoder, PushButton


GObject.threads_init()
Gst.init(None)

class StreamData():
    def __init__(self, location):
        self.location = location
        self.organization = None
        self.nominal_bitrate = None
        self.title = None
        return
    
    def get_location(self):
        return self.location
    
    def set_taglist(self, tag_list):
        #print tag_list.to_string()
        organization = tag_list.get_value_index("organization", 0)
        if organization != self.organization:
            self.organization = organization
            print self.organization
        
        nominal_bitrate = tag_list.get_value_index("nominal-bitrate", 0)
        
        title = tag_list.get_value_index("title", 0)
        if title != self.title:
            self.title = title
            print title
        
        return
    

class RPiRadio():
    def __init__(self):
        print "[RPiRadio] init "
        
        # setup the pipeline for playing internet radio streams
        pipeline = Gst.Pipeline()
        source = Gst.ElementFactory.make("souphttpsrc", "src")
        decode = Gst.ElementFactory.make("decodebin", "dec")
        convert = Gst.ElementFactory.make("audioconvert", "cvt")
        volume = Gst.ElementFactory.make("volume", "vol")
        audiosink = Gst.ElementFactory.make("alsasink", "sink")
        # add elements
        ret = pipeline.add(source) 
        print "added source: %r" %ret
        ret = pipeline.add(convert) 
        print "added convert: %r" %ret
        ret = pipeline.add(decode)
        print "added decode: %r" %ret
        ret = pipeline.add(volume)
        print "added volume: %r" %ret
        ret = pipeline.add(audiosink)
        print "added sink: %r" %ret
        # link elements
        ret = source.link(decode)
        print "linked src to decode: %r" %ret
        # we cannot link decode and convert at this stage! We have to wait for the decode pad to arrive...
        # See http://stackoverflow.com/questions/2993777/gstreamer-of-pythons-gst-linkerror-problem for details!
        ret = convert.link(volume)
        print "linked cvt to volume: %r" %ret
        ret = volume.link(audiosink)
        print "linked volume to sink: %r" %ret
        # --
        
        # create some StreamData objects
        strm_kc = StreamData("http://koelncampus.uni-koeln.de:8001") 
        strm_fip = StreamData("http://mp3.live.tv-radio.com/fip/all/fiphautdebit.mp3")
        strm_rp_ogg = StreamData("http://stream-dc1.radioparadise.com/rp_192m.ogg")
        strm_rp_aac = StreamData("http://stream-uk1.radioparadise.com/aac-128")#http://stream-uk1.radioparadise.com/mp3-192"
        strm_cr = StreamData("http://173.193.14.162:8020")
        
        self.stations_list = []
        self.stations_list.append(strm_rp_aac)
        self.stations_list.append(strm_kc)
        self.stations_list.append(strm_fip)
        self.stations_list.append(strm_cr)
        
        self.stations_list_current_pos = 0;                             # keep track of where we are in the list now...
        self.stations_list_next_pos = self.stations_list_current_pos    # ...and where we want to go next (using thr rotary encoder)
        source.set_property("location", self.stations_list[0].get_location())   
        source.set_property("iradio-mode", True)
        volume.set_property("volume", 0.5)
        audiosink.set_property("sync", False) # 
        decode.connect("pad-added", self.on_new_decoded_pad)
        pipeline.set_state(Gst.State.PAUSED)  # wait for a decode pad
        
        #listen for tags on the message bus; tag event might be called more than once
        bus = pipeline.get_bus()
        bus.enable_sync_message_emission()
        bus.add_signal_watch()
        bus.connect('message::tag', self.on_new_tag)
        
        # setup the IO logic using 2 button switches and 2 rotary decoders
        # define GPIO inputs for volume control
        VOL_UP_PIN = 15      
        VOL_DOWN_PIN = 14        
        vol_input = RotaryEncoder(VOL_UP_PIN, VOL_DOWN_PIN, self.on_volume_event) 
        # a simple pushbutton for settint toggling play/pause 
        PLAY_PAUSE_PIN = 4
        BTN_BOUNCETIME = 50
        play_pause_input = PushButton(PLAY_PAUSE_PIN, BTN_BOUNCETIME, self.on_play_pause_event)
        
        # define GPIO inputs for selector
        SEL_UP_PIN = 22
        SEL_DOWN_PIN = 27
        SEL_SELECT_PIN = 17
        rotate_stations_input = RotaryEncoder(SEL_UP_PIN, SEL_DOWN_PIN, self.on_rotate_stations_event) 
        select_station_input = PushButton(SEL_SELECT_PIN, BTN_BOUNCETIME, self.on_select_station_event)
        
        self.CHANGE_VOL_STEP = 0.02
        
        self.pipeline = pipeline
        
        self.mainloop = GObject.MainLoop()
        self.mainloop.run()
        return
        
    # These are the event callback routines to handle events
    def on_volume_event(self, event):
        volume = self.pipeline.get_by_name("vol")
        if event == RotaryEncoder.CLOCKWISE:
            vol = volume.get_property("volume")
            if vol < 1-self.CHANGE_VOL_STEP:
                vol = vol + self.CHANGE_VOL_STEP
                volume.set_property("volume", vol)
                print "Volume up %i" % (vol*100)
        elif event == RotaryEncoder.ANTICLOCKWISE:
            vol = volume.get_property("volume")
            if vol > self.CHANGE_VOL_STEP:
                vol = vol - self.CHANGE_VOL_STEP
                volume.set_property("volume", vol)
                print "Volume down %i" % (vol*100)
        return
    
    def on_play_pause_event(self, event):
        state = self.pipeline.get_state(0)[1]   # get current state of the pipeline
        if event == PushButton.BUTTONDOWN:
            self.time_down = time.time()          
            return
        
        elif event == PushButton.BUTTONUP:
            self.time_up = time.time()
            time_hold = self.time_up - self.time_down
            print time_hold
            # a short press will toggle Play/Pause
            if (time_hold < 1):
                if state == Gst.State.PAUSED:
                    self.pipeline.set_state(Gst.State.PLAYING)
                    print "set pipeline to PLAYING"
                    return
                elif state == Gst.State.PLAYING:
                    self.pipeline.set_state(Gst.State.PAUSED)
                    print "set pipeline to PAUSED"
            # a long press will set the pipeline to NULL, i.e. stop the stream connection 
            else:
                if state == Gst.State.PLAYING or state == Gst.State.PAUSED:
                    print "setting pipeline to NULL"
                    self.pipeline.set_state(Gst.State.NULL)
                    #self.mainloop.quit()
                    print "Goodbye"
                    return
                elif state == Gst.State.NULL:
                    print "wake up!!!"
                    #self.mainloop.run()
                    self.pipeline.set_state(Gst.State.PLAYING)
        return
    
    def on_rotate_stations_event(self, event):
        if event == RotaryEncoder.CLOCKWISE:
                if self.stations_list_next_pos < len(self.stations_list)-1:
                    self.stations_list_next_pos = self.stations_list_next_pos + 1
                else: 
                    self.stations_list_next_pos = 0
        elif event == RotaryEncoder.ANTICLOCKWISE:
                if self.stations_list_next_pos-1 >=0:
                    self.stations_list_next_pos = self.stations_list_next_pos -1
                else: 
                    self.stations_list_next_pos = len(self.stations_list)-1
                
        print "[Rotate Stations]:  %s" %self.stations_list[self.stations_list_next_pos].get_location()
        return
    
    def on_select_station_event(self, event):
        if event == PushButton.BUTTONDOWN:
            print "select event"
            if self.stations_list_next_pos != self.stations_list_current_pos:
                source = self.pipeline.get_by_name("src")
                self.pipeline.set_state(Gst.State.READY)
                source.set_property("location", self.stations_list[self.stations_list_next_pos].get_location())
                self.stations_list_current_pos = self.stations_list_next_pos
                self.pipeline.set_state(Gst.State.PLAYING)
        return
    
    # callback for new stream tags
    def on_new_tag(self, bus, msg):
        #print "received new taglist"
        taglist = msg.parse_tag()
        self.stations_list[self.stations_list_current_pos].set_taglist(taglist)
        return
    
    # callback for received decode pad
    def on_new_decoded_pad(self, decodebin, pad):
        print "received decode pad"
        convert = self.pipeline.get_by_name("cvt")  # link decodebin to audioconvert
        ret = decodebin.link(convert)
        print "linked decode to convert %r" %ret
        self.pipeline.set_state(Gst.State.PLAYING)  # only now we can set the pipeline to PLAYING
        print "set pipeline to PLAYING"
        return
    
def main():
    
    print "This is "+Gst.version_string()
    rpiradio = RPiRadio()


main()
