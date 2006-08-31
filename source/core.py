#core.py
#A part of NonVisual Desktop Access (NVDA)
#Copyright (C) 2006 Michael Curran <mick@kulgan.net>
#This file is covered by the GNU General Public License.
#See the file COPYING for more details.

import sys
import os
import time
import Queue
import win32api
import win32gui
import pythoncom
import winsound
import cPickle
from constants import *
import dictionaries
import globalVars
from api import *
from NVDAObjects import NVDAObject
import keyEventHandler
import mouseEventHandler
import MSAAEventHandler
import appModules
import audio
import config
import gui

def appChange(window,objectID,childID):
	accObject=getMSAAObjectFromEvent(window,objectID,childID)
	if not accObject:
		return None
	obj=NVDAObject(accObject)
	if not obj:
		return None
	name=obj.getName()
	appName = os.path.splitext(getProcessName(obj.getProcessID()))[0].lower()
	role=obj.getRole()
	if appModules.load(appName) is False:
		debug.writeError("core.event_appChange(): Error, could not load app module %s"%appName) 
		sys.exit()
	executeEvent("foreground",(window,objectID,childID))

def event_mouseMove(position):
	obj=NVDAObject(getMSAAObjectFromPoint(position))
	location=obj.getLocation()
	if location!=globalVars.mouse_location:
		speakObject(obj)
		globalVars.mouse_location=location

def main():
	try:
		dictionaries.load("characterSymbols")
		dictionaries.load("textSymbols")
		dictionaries.load("roleNames")
		dictionaries.load("stateNames")
		audio.initialize()
		audio.speakMessage("NonVisual Desktop Acces started!")
		foregroundWindow=getForegroundWindow()
		if (foregroundWindow is None) or (foregroundWindow==0):
			debug.writeError("core.main: failed to get foreground window")
			sys.exit()
		setFocusLocator(foregroundWindow,OBJID_CLIENT,0)
		setFocusObject(NVDAObject(getMSAAObjectFromEvent(foregroundWindow,OBJID_CLIENT,0)))
		appChange(foregroundWindow,OBJID_CLIENT,0)
		MSAAEventHandler.initialize()
		keyEventHandler.initialize()
		mouseEventHandler.initialize()
		gui.initialize()
		globalVars.stayAlive=True
	except:
		debug.writeException("core.py main init")
		sys.exit()
	try:
		globalVars.stayAlive=True
		while globalVars.stayAlive is True:
			try:
				pythoncom.PumpWaitingMessages()
			except KeyboardInterrupt:
				debug.writeException("core.main: keyboard interupt") 
				quit()
			try:
				MSAAEvent=MSAAEventHandler.queue_events.get_nowait()
				if (MSAAEvent[0]=="focusObject") or (MSAAEvent[0]=="foreground") or (MSAAEvent[0]=="appChange"):
					setFocusLocator(MSAAEvent[1],MSAAEvent[2],MSAAEvent[3])
					setFocusObject(NVDAObject(getMSAAObjectFromEvent(MSAAEvent[1],MSAAEvent[2],MSAAEvent[3])))
				if MSAAEvent[0]=="appChange":
					try:
						appChange(MSAAEvent[1],MSAAEvent[2],MSAAEvent[3])
					except:
						audio.speakMessage("Error executing MSAA event %s"%MSAAEvent[0])
						debug.writeException("core.main: while executing event_%s in app module"%MSAAEvent[0])
				else:
						executeEvent(MSAAEvent[0],MSAAEvent[1:])
			except Queue.Empty:
				pass
			try:
				keyPress=keyEventHandler.queue_keys.get_nowait()
				if keyPress == (None, "SilenceSpeech"):
					audio.cancel()
				else:
					executeScript(keyPress)
			except Queue.Empty:
				pass
			try:
				mouseEvent=mouseEventHandler.queue_events.get_nowait()
				if mouseEvent[0]=="mouseMove":
					try:
						event_mouseMove(position)
					except:
						debug.writeException("event_mouseMove")
			except Queue.Empty:
				pass
			# If there are no events already waiting, sleep to avoid needlessly hogging the CPU.
			if keyEventHandler.queue_keys.empty() and mouseEventHandler.queue_events.empty() and MSAAEventHandler.queue_events.empty():
				time.sleep(0.001)
	except:
			audio.speakMessage("Exception in main loop")
			debug.writeException("core.py main loop")
			sys.exit()
	gui.terminate()
	try:
		config.save()
	except:
		pass
	MSAAEventHandler.terminate()
