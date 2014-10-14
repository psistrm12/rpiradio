#!/usr/bin/env python
#
# Raspberry Pi input using buttons and rotary encoders
#
# Acknowledgement: This code is a variation oft the Rotary Switch Tutorial by Bob Rathbone.
# See http://www.bobrathbone.com/raspberrypi_rotary.htm for further information!


import RPi.GPIO as GPIO

class PushButton:
	BUTTONDOWN = 1
	BUTTONUP = 2
	
	def __init__(self, pin, bouncetime, callback):
		self.pin = pin
		self.bouncetime = bouncetime
		self.callback = callback
		
		GPIO.setmode(GPIO.BCM)
		GPIO.setwarnings(False)
		
		GPIO.setup(self.pin, GPIO.IN, pull_up_down=GPIO.PUD_DOWN)
		GPIO.add_event_detect(self.pin, GPIO.BOTH, callback=self.button_event, bouncetime=self.bouncetime)
		return
		
	# Push button up event
	def button_event(self, b_event):
		if GPIO.input(b_event): 
			event = self.BUTTONDOWN
		else:
			event = self.BUTTONUP 
		self.callback(event)
		return
	
# end class PushButton

		
class RotaryEncoder:

	CLOCKWISE = 3
	ANTICLOCKWISE = 4

	rotary_a = 0
	rotary_b = 0
	rotary_c = 0
	last_state = 0
	direction = 0

	# Initialise rotary encoder object
	def __init__(self,pinA,pinB,callback):
		self.pinA = pinA
		self.pinB = pinB
		#self.button = button
		self.callback = callback

		GPIO.setmode(GPIO.BCM)
		
		GPIO.setwarnings(False)
		GPIO.setup(self.pinA, GPIO.IN, pull_up_down=GPIO.PUD_UP)
		GPIO.setup(self.pinB, GPIO.IN, pull_up_down=GPIO.PUD_UP)
		
		# add events
		GPIO.add_event_detect(self.pinA, GPIO.FALLING, callback=self.switch_event)
		GPIO.add_event_detect(self.pinB, GPIO.FALLING, callback=self.switch_event)
		return

	# Call back routine called by switch events
	def switch_event(self,switch):
		if GPIO.input(self.pinA):
			self.rotary_a = 1
		else:
			self.rotary_a = 0

		if GPIO.input(self.pinB):
			self.rotary_b = 1
		else:
			self.rotary_b = 0

		self.rotary_c = self.rotary_a ^ self.rotary_b
		new_state = self.rotary_a * 4 + self.rotary_b * 2 + self.rotary_c * 1
		delta = (new_state - self.last_state) % 4
		self.last_state = new_state
		event = 0

		if delta == 1:
			if self.direction == self.CLOCKWISE:
				event = self.direction
			else:
				self.direction = self.CLOCKWISE
		elif delta == 3:
			if self.direction == self.ANTICLOCKWISE:
				event = self.direction
			else:
				self.direction = self.ANTICLOCKWISE
		if event > 0:
			self.callback(event)
		return


# end class RotaryEncoder

