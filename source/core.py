#core.py
#A part of NonVisual Desktop Access (NVDA)
#Copyright (C) 2006 Michael Curran <mick@kulgan.net>
#This file is covered by the GNU General Public License.
#See the file COPYING for more details.

import ctypes
import sys
import os
import time
import dictionaries
import globalVars
import winUser
from api import *
from constants import *
import NVDAObjects
import keyboardHandler
import mouseHandler
import MSAAHandler
import appModuleHandler
import audio
import config
import gui

lastProcessID=None
msg=winUser.msgType()

def event_foreground(window,objectID,childID):
	global lastProcessID
	obj=NVDAObjects.getNVDAObjectByLocator(window,objectID,childID)
	if not obj:
		return None
	processID=obj.getProcessID()
	if processID!=lastProcessID:
		appName=getAppName(processID)
		appModuleHandler.load(appName)
		lastProcessID=processID
	executeEvent("foreground",window,objectID,childID)

def event_mouseMove(point):
	obj=NVDAObjects.getNVDAObjectByPoint(point[0],point[1])
	if not obj:
		return None
	location=obj.getLocation()
	if location!=globalVars.mouse_location:
		audio.cancel()
		obj.speakObject()
		globalVars.mouse_location=location

def main():
	try:
		dictionaries.load("characterSymbols")
		dictionaries.load("textSymbols")
		dictionaries.load("roleNames")
		dictionaries.load("stateNames")
		audio.initialize()
		audio.speakMessage("NonVisual Desktop Acces started!",wait=True)
		foregroundWindow=winUser.getForegroundWindow()
		if (foregroundWindow is None) or (foregroundWindow==0):
			debug.writeError("core.main: failed to get foreground window")
			sys.exit()
		if not setFocusObjectByLocator(foregroundWindow,-4,0):
			debug.writeError("core.main: failed to set focus object (%s,%s,%s)"%(foregroundWindow,OBJID_CLIENT,0))
			return False
		event_foreground(foregroundWindow,-4,0)
		MSAAHandler.initialize()
		keyboardHandler.initialize()
		mouseHandler.initialize()
		gui.initialize()
	except:
		debug.writeException("core.py main init")
		sys.exit()
	try:
		globalVars.stayAlive=True
		while globalVars.stayAlive is True:
			if not MSAAHandler.queue_events.empty():
				MSAAEvent=MSAAHandler.queue_events.get()
				if MSAAEvent[0] in ["focusObject","foreground"]:
					setFocusObjectByLocator(MSAAEvent[1],MSAAEvent[2],MSAAEvent[3])
				if MSAAEvent[0]=="foreground":
					try:
						event_foreground(MSAAEvent[1],MSAAEvent[2],MSAAEvent[3])
					except:
						debug.writeException("core.main: while executing event_%s in core"%MSAAEvent[0])
						audio.speakMessage("Error executing MSAA event %s"%MSAAEvent[0])
				else:
					try:
						executeEvent(MSAAEvent[0],MSAAEvent[1],MSAAEvent[2],MSAAEvent[3])
					except:
						debug.writeException("core.main: while executing event_%s"%MSAAEvent[0])
						audio.speakMessage("Error executing MSAA event %s"%MSAAEvent[0])
			if not keyboardHandler.queue_keys.empty():
				keyPress=keyboardHandler.queue_keys.get()
				if keyPress == (None, "SilenceSpeech"):
					audio.cancel()
				else:
					executeScript(keyPress)
			if not mouseHandler.queue_events.empty():
				mouseEvent=mouseHandler.queue_events.get_nowait()
				if mouseEvent[0]=="mouseMove":
					try:
						event_mouseMove(mouseEvent[1])
					except:
						debug.writeException("event_mouseMove")
			# If there are no events already waiting, sleep to avoid needlessly hogging the CPU.
			if keyboardHandler.queue_keys.empty() and mouseHandler.queue_events.empty() and MSAAHandler.queue_events.empty():
				time.sleep(0.001)
				if winUser.peekMessage(ctypes.byref(msg),0,0,0,1):
					winUser.translateMessage(ctypes.byref(msg))
					winUser.dispatchMessage(ctypes.byref(msg))
	except:
			debug.writeException("core.py main loop")
			audio.speakMessage("Exception in main loop")
	gui.terminate()
	try:
		config.save()
	except:
		pass
	MSAAHandler.terminate()
	return True
