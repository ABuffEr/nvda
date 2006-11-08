#api.py
#A part of NonVisual Desktop Access (NVDA)
#Copyright (C) 2006 Michael Curran <mick@kulgan.net>
#This file is covered by the GNU General Public License.
#See the file COPYING for more details.

import ctypes
import os.path
import debug
import winKernel
import globalVars
from constants import *
import dictionaries
import audio
from config import conf
import appModuleHandler
import gui
from keyboardHandler import key 
import NVDAObjects
import virtualBuffer

# Initialise WMI; required for getProcessName.
#_wmi = win32com.client.GetObject('winmgmts:')

#User functions

def quit():
	gui.exit()


def showGui():
	gui.showGui()
def getFocusObject():
	return globalVars.focusObject

def getForegroundObject():
	return globalVars.foregroundObject

def getForegroundLocator():
	return globalVars.foreground_locator

def setForegroundObjectByLocator(window,objectID,childID):
	foregroundObject=NVDAObjects.getNVDAObjectByLocator(window,objectID,childID)
	if not foregroundObject:
		return False
	globalVars.foreground_locator=(window,objectID,childID)
	globalVars.foregroundObject=foregroundObject
	if globalVars.navigatorTracksFocus:
		setNavigatorObject(foregroundObject)
	return True

def getFocusObject():
	return globalVars.focusObject

def getFocusLocator():
	return globalVars.focus_locator

def setFocusObjectByLocator(window,objectID,childID):
	if (window,objectID,childID)==getFocusLocator():
		return False
	if globalVars.focusObject and hasattr(globalVars.focusObject,"event_looseFocus"):
		try:
			globalVars.focusObject.event_looseFocus()
		except:
			debug.writeException("event_looseFocus in focusObject")
			audio.speakMessage("Error in event_looseFocus of focusObject")
	focusObject=NVDAObjects.getNVDAObjectByLocator(window,objectID,childID)
	if not focusObject:
		return False
	globalVars.focus_locator=(window,objectID,childID)
	globalVars.focusObject=focusObject
	if globalVars.navigatorTracksFocus:
		setNavigatorObject(focusObject)
	virtualBuffer.getVirtualBuffer(window)
	return True

def getNavigatorObject():
	return globalVars.navigatorObject

def setNavigatorObject(obj):
	globalVars.navigatorObject=obj
def keyHasScript(keyPress):
	#The keyboard help script is built in to hasScript and executeScript
	if globalVars.keyboardHelp:
		return True
	if keyPress==key("insert+1"):
		return True
	if appModuleHandler.current.keyMap.has_key(keyPress):
		return True
	if getFocusObject().keyMap.has_key(keyPress):
		return True
	return False

def executeScript(keyPress):
	#The keyboard help script is built in to hasScript and executeScript
	if keyPress==key("insert+1"):
		if not globalVars.keyboardHelp:
			globalVars.keyboardHelp=True
			audio.speakMessage("keyboard help on")
			return True
		else:
			globalVars.keyboardHelp=False
			audio.speakMessage("keyboard help off")
			return True
	script=appModuleHandler.current.keyMap.get(keyPress,None)
	if not script:
		script=getFocusObject().keyMap.get(keyPress,None)
	if globalVars.keyboardHelp:
		if script:
			name=script.__name__
			if script.im_self.__class__.__name__=="appModule":
				container="module %s"%script.im_self.__class__.__module__
			else:
				container=script.im_self.__class__.__name__
				container+=" in module %s"%script.im_self.__class__.__module__
			description=script.__doc__
			if not description:
				description="no description"
			audio.speakMessage("%s, from %s, %s"%(name,container,description))
		else:
			audio.speakMessage("no script")
		return
	if script:
		try:
			script(keyPress)
			return True
		except:
			audio.speakMessage("Error executing script %s bound to key %s"%(script.__name__,str(keyPress)))
			debug.writeException("Error executing script %s bound to key %s"%(script.__name__,str(keyPress)))
			return False

def eventExists(name,window,objectID,childID):
	if hasattr(appModuleHandler.current,"event_%s"%name):
		return True
	focusLocator=getFocusLocator()
	focusObject=getFocusObject()
	if ((window,objectID,childID)==focusLocator) and hasattr(focusObject,"event_%s"%name):
		return True
	thisObj=NVDAObjects.getNVDAObjectByLocator(window,objectID,childID)
	if thisObj:
		if hasattr(thisObj,"event_%s"%name):
			return True
	return False

def executeEvent(name,window,objectID,childID):
	#If caret event is on object that has not got focus, then set focus and then continue
	if (name=="caret") and (window!=getFocusLocator()[0]):
		setFocusObjectByLocator(window,OBJID_CLIENT,0)
		executeEvent("gainFocus",window,objectID,childID)
	#If this event is for the same window as a virtualBuffer, then give it to the virtualBuffer and then continue
	v=virtualBuffer.getVirtualBuffer(window)
	if v and (v.getWindowHandle()==window) and hasattr(v,"event_%s"%name):
		event=getattr(v,"event_%s"%name)
		try:
			event(objectID,childID)
		except:
			audio.speakMessage("Error in virtualBuffer event")
			debug.writeException("virtualBuffer event")
	#If this is a hide event and it it is specifically for a window and there is a virtualBuffer for this window, remove the virtualBuffer 
	#and then continue 
	if (name=="hide") and (objectID==0) and virtualBuffer.isVirtualBufferWindow(window): 
		virtualBuffer.removeVirtualBuffer(window)
	#This event is either for the current appModule if the appModule has an event handler,
	#the foregroundObject if its a foreground event and the foreground object handles this event,
	#the focus object if the focus object has a handler for this event,
	#the specific object that this event describes if the object has a handler for this event.
	if hasattr(appModuleHandler.current,"event_%s"%name):
		event=getattr(appModuleHandler.current,"event_%s"%name)
		try:
			event(window,objectID,childID)
		except:
			audio.speakMessage("Error executing event %s from appModule"%event.__name__)
			debug.writeException("Error executing event %s from appModule"%event.__name__)
		return
	if (name=="foreground") and (getForegroundLocator()==(window,objectID,childID)) and hasattr(getForegroundObject(),"event_%s"%name):
		try:
			getattr(getForegroundObject(),"event_%s"%name)()
		except:
			debug.writeException("foregroundObject: event_%s"%name)
			audio.speakMessage("Error in event_%s of foreground object"%name)
		return
	if ((getFocusLocator()==(window,objectID,childID)) or (name=="caret")) and hasattr(getFocusObject(),"event_%s"%name):
		try:
			getattr(getFocusObject(),"event_%s"%name)()
		except:
			audio.speakMessage("Error executing event event_%s from focusObject"%name)
			debug.writeException("Error executing event event_%s from focusObject"%name)
		return
	thisObj=NVDAObjects.getNVDAObjectByLocator(window,objectID,childID)
	if thisObj and hasattr(thisObj,"event_%s"%name):
		try:
			getattr(thisObj,"event_%s"%name)()
		except:
			audio.speakMessage("Error executing event event_%s from object"%name)
			debug.writeException("Error executing event event_%s from object"%name)
		return

def getObjectGroupName(accObject):
	try:
		(objectLeft,objectTop,objectRight,objectBottom)=accObject.GetLocation()
	except:
		debug.writeError("api.getObjectGrouping: fialed to get location of object %s"%accObject)
		return None
	try:
		while (accObject is not None) and (accObject.GetRole()!=ROLE_SYSTEM_GROUPING):
			accObject=getObjectPrevious(accObject)
			if accObject is None:
				debug.writeError("api.getObjectGroupName: no more previous objects")
				return None
		if accObject.GetRole()==ROLE_SYSTEM_GROUPING:
			(groupLeft,groupTop,groupRight,groupBottom)=accObject.GetLocation()
			if (objectLeft>=groupLeft) and (objectTop>=groupTop) and (objectRight<=groupRight) and (objectBottom<=groupBottom):
				return accObject.GetName()
			else:
				debug.writeError("api.getObjectGroupName: object is not with in bounds of cloest grouping")
				return None
		debug.writeError("api.getObjectGroupName: could not find a grouping on this level")
		return None
	except:
		debug.writeError("api.getObjectGroupName: error finding group name")
		return None

def makeStateList(stateText):
	stateList=stateText.split("+")
	return stateList

def getAppName(processID):
	procHandle=winKernel.openProcess(PROCESS_ALL_ACCESS,False,processID[0])
	buf=ctypes.create_unicode_buffer(1024)
	res=ctypes.windll.psapi.GetProcessImageFileNameW(procHandle,buf,1024)
	winKernel.closeHandle(procHandle)
	return os.path.splitext(buf.value.split('\\')[-1])[0].lower()


def setMenuMode(switch):
	globalVars.menuMode=switch

def getMenuMode():
	return globalVars.menuMode

