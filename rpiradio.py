import gi

gi.require_version('Gst', '1.0')
from gi.repository import GObject, Gst

import os.path
import numpy as np
import time
import ConfigParser
import urllib
from buttonIO import RotaryEncoder, PushButton


GObject.threads_init()
Gst.init(None)

class StreamData():
    def __init__(self, location, display_name):
        self.location = location
        self.display_name = display_name
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
        
        self.stations_list = []     # we store all the StreamData objects here
        self.station_cfg_file = 'stations.list'
        # check if config file exists and write a default one if not
        if not os.path.isfile(self.station_cfg_file):   
            print "Unable to open config file. Creating default %s" %self.station_cfg_file
            self.create_default_stations_list() 
    
        # try to read the stations fron config
        self.stations_list = self.read_stations_list(self.station_cfg_file)# reads 'stations.list' config file
        
        # fallback if file exists but is invalid, e.g. urls are wrong. We don't want to change the file in this case...
        if not self.stations_list:
            print "Config file exists but there's no valid URL. Adding default stream."
            self.stations_list.append(StreamData('http://stream-uk1.radioparadise.com/aac-128', 'Radio Paradise'))
        
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
    
    def read_stations_list(self, fname):
        # read the config file
        stations_list = []
        config_parser = ConfigParser.ConfigParser()
        ret = config_parser.read(fname)   # returns an empty list if file doesn't exist
        if len(ret) > 0:
            print "Reading %s" %fname
            stations = config_parser.sections()

            for sname in stations:   # iterate all sections, i.e. stations in our case
                try:
                    location = config_parser.get(sname, 'url')  # this option is mandatory for obvious resons...
                    urllib.urlopen(location)    # test whether or not the url exists 
                    if config_parser.has_option(sname, 'displayName'):  # this is optional -> default value: None
                        display_name = config_parser.get(sname, 'displayName')
                    else:
                        display_name = None
                    # if no exception got thrown at this point we can add the station to the list now    
                    stations_list.append(StreamData(location, display_name))
                    print "added %s" %location
                    
                except ConfigParser.NoOptionError:  # no url option in section
                    #print sys.exc_info()[0]
                    print "Error in 'stations.list' entry %s: url option missing!" %sname
                except IOError:                     # url could not be opened
                    print "Unable to open URL %s" %location
            
        return stations_list
    
    def create_default_stations_list(self):
        sfile = open(self.station_cfg_file,'w')
        sfile.write("# \n")
        sfile.write("# This is the RPiRadio default config file. You can add your own streams by\n")
        sfile.write("# adding a new section and at least an URL field. \n")
        sfile.write("# \n")
        sfile.write("# A new section starts with a unique ID in square brackets, e.g. [4]. For \n")
        sfile.write("# each section a URL field is mandatory before the start of the next section.\n")
        sfile.write("# The optional field 'displayName' is a custom string that is displayed as the\n")
        sfile.write("# stream's name. If it's not given here it is replaced by the appropriate stream\n")
        sfile.write("# tag.\n")  
        sfile.write("# See below for examples! \n")
        sfile.write("# \n")
        
        config_parser = ConfigParser.ConfigParser()
        config_parser.add_section('1')
        config_parser.set('1','url', 'http://stream-uk1.radioparadise.com/aac-128')
        config_parser.set('1','displayName', 'Radio Paradise')
        config_parser.add_section('2')
        config_parser.set('2','url', 'http://koelncampus.uni-koeln.de:8001')
        #config_parser.set('2','displayName', 'Koelncampus')
        config_parser.add_section('3')
        config_parser.set('3','url', 'http://mp3.live.tv-radio.com/fip/all/fiphautdebit.mp3')
        config_parser.set('3','displayName', 'fip')
        config_parser.write(sfile)
        
        sfile.close()
        return
    
    # These are callback routines handling button events
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
            time_hold = self.time_up - self.time_down   # 
            # a short press will toggle Play/Pause
            if (time_hold < 1 and time_hold > 0):
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
