#MSAAHandler.py
#A part of NonVisual Desktop Access (NVDA)
#Copyright (C) 2006 Michael Curran <mick@kulgan.net>
#This file is covered by the GNU General Public License.
#See the file COPYING for more details.

import time
import ctypes
import comtypesClient
import comtypes.automation
import debug
import lang
import winUser
import audio
from constants import *
import api
import core

#A list to store handles received from setWinEventHook, for use with unHookWinEvent  
objectEventHandles=[]

#Load IAccessible from oleacc.dll
IAccessible=comtypesClient.GetModule('oleacc.dll').IAccessible

def getRoleName(role):
	dictRole=lang.roleNames.get(role,None)
	if dictRole:
		return dictRole
	elif isinstance(role,int):
		return getRoleText(role)
	else:
		return role

def createStateList(stateBits):
	stateList=[]
	for bitPos in range(32):
		bitVal=1<<bitPos
		if stateBits&bitVal:
			stateList+=[bitVal]
	return stateList

def getStateNames(states,opposite=False):
	str=""
	for state in createStateList(states):
		str="%s %s"%(str,getStateName(state,opposite=opposite))
	return str

def getStateName(state,opposite=False):
	dictState=lang.stateNames.get(state,None)
	if dictState:
		newState=dictstate
	elif isinstance(state,int):
		newState=getStateText(state)
	else:
		newState=state
	if opposite:
		newState=lang.messages["not"]+" "+newState
	return newState

#A class to wrap an IAccessible object in to handle addRef and Release
class IAccWrapper(object):

	def __init__(self,IAccPointer):
		IAccPointer.AddRef()
		getattr(self,'__dict__')['ia']=IAccPointer

	def __del__(self):
		getattr(self,'__dict__')['ia'].Release()

	def __getattr__(self,attr):
		ia=getattr(self,'__dict__')['ia']
		return getattr(ia,attr)

	def __setattr__(self,attr,value):
		ia=getattr(self,'__dict__')['ia']
		setattr(ia,attr,value)

	def __repr__(self):
		return "IAccWrapper object: ia %s"%getattr(self,'__dict__')['ia']

#A c ctypes struct to hold the x and y of a point on the screen 
class screenPointType(ctypes.Structure):
	_fields_=[
	('x',ctypes.c_int),
	('y',ctypes.c_int)
	]

def accessibleObjectFromWindow(window,objectID):
	if not winUser.isWindow(window):
		return None
	ptr=ctypes.POINTER(IAccessible)()
	res=ctypes.windll.oleacc.AccessibleObjectFromWindow(window,objectID,ctypes.byref(IAccessible._iid_),ctypes.byref(ptr))
	if res==0:
		return IAccWrapper(ptr)
	else:
		return None

def accessibleObjectFromEvent(window,objectID,childID):
	if not winUser.isWindow(window):
		return None
	pacc=ctypes.POINTER(IAccessible)()
	varChild=comtypes.automation.VARIANT()
	res=ctypes.windll.oleacc.AccessibleObjectFromEvent(window,objectID,childID,ctypes.byref(pacc),ctypes.byref(varChild))
	if res==0:
		if not isinstance(varChild.value,int):
			child=0
		else:
			child=varChild.value
		return (IAccWrapper(pacc),child)
	else:
		return None

def accessibleObjectFromPoint(x,y):
	point=screenPointType(x,y)
	pacc=ctypes.POINTER(IAccessible)()
	varChild=comtypes.automation.VARIANT()
	res=ctypes.windll.oleacc.AccessibleObjectFromPoint(point,ctypes.byref(pacc),ctypes.byref(varChild))
	if res==0:
		if not isinstance(varChild.value,int):
			child=0
		else:
			child=varChild.value
		return (IAccWrapper(pacc),child)

def windowFromAccessibleObject(ia):
	hwnd=ctypes.c_int()
	res=ctypes.windll.oleacc.WindowFromAccessibleObject(getattr(ia,'__dict__')['ia'],ctypes.byref(hwnd))
	if res==0:
		return hwnd.value
	else:
		return 0

def getRoleText(role):
	len=ctypes.windll.oleacc.GetRoleTextW(role,0,0)
	if len:
		buf=ctypes.create_unicode_buffer(len+2)
		ctypes.windll.oleacc.GetRoleTextW(role,buf,len+1)
		return buf.value
	else:
		return None

def getStateText(state):
	len=ctypes.windll.oleacc.GetStateTextW(state,0,0)
	if len:
		buf=ctypes.create_unicode_buffer(len+2)
		ctypes.windll.oleacc.GetStateTextW(state,buf,len+1)
		return buf.value
	else:
		return None

def accName(ia,child):
	try:
		return ia.accName(child)
	except:
		return ""

def accValue(ia,child):
	try:
		return ia.accValue(child)
	except:
		return ""

def accRole(ia,child):
	try:
		return ia.accRole(child)
	except:
		return 0

def accState(ia,child):
	try:
		return ia.accState(child)
	except:
		return 0

def accDescription(ia,child):
	try:
		return ia.accDescription(child)
	except:
		return ""

def accHelp(ia,child):
	try:
		return ia.accHelp(child)
	except:
		return ""

def accKeyboardShortcut(ia,child):
	try:
		return ia.accKeyboardShortcut(child)
	except:
		return ""

def accDoDefaultAction(ia,child):
	try:
		ia.accDoDefaultAction(child)
	except:
		pass

def accFocus(ia,child):
	try:
		res=ia.accFocus(child)
		if isinstance(res,ctypes.POINTER(IAccessible)):
			new_ia=IAccWrapper(res)
			new_child=0
		elif isinstance(res,int):
			new_ia=ia
			new_child=res
		return (new_ia,new_child)
	except:
		return None

def accChild(ia,child):
	try:
		res=ia.accChild(child)
		if isinstance(res,ctypes.POINTER(IAccessible)):
			new_ia=IAccWrapper(res)
			new_child=0
		elif isinstance(res,int):
			new_ia=ia
			new_child=res
		return (new_ia,new_child)
	except:
		return None

def accChildCount(ia,child):
	if child==0:
		count=ia.accChildCount
	else:
		count=0
	return count

def accParent(ia,child):
	try:
		if not child:
			res=ia.accParent
			if isinstance(res,ctypes.POINTER(IAccessible)):
				new_ia=IAccWrapper(res)
				new_child=0
			elif isinstance(res,int): 
				new_ia=ia
				new_child=res
		else:
			new_ia=ia
			new_child=0
		return (new_ia,new_child)
	except:
		return None

def accNavigate(ia,child,direction):
	try:
		res=ia.accNavigate(direction,child)
		if isinstance(res,ctypes.POINTER(IAccessible)):
			new_ia=IAccWrapper(res)
			new_child=0
		elif isinstance(res,int):
			new_ia=ia
			new_child=res
		return (new_ia,new_child)
	except:
		return None

def accLocation(ia,child):
	try:
		return ia.accLocation(child)
	except:
		return None

eventMap={
EVENT_SYSTEM_FOREGROUND:"foreground",
EVENT_SYSTEM_MENUSTART:"menuStart",
EVENT_SYSTEM_MENUEND:"menuEnd",
EVENT_SYSTEM_MENUPOPUPSTART:"menuStart",
EVENT_SYSTEM_MENUPOPUPEND:"menuEnd",
EVENT_SYSTEM_SWITCHSTART:"switchStart",
EVENT_SYSTEM_SWITCHEND:"switchEnd",
EVENT_OBJECT_FOCUS:"gainFocus",
EVENT_OBJECT_SHOW:"show",
EVENT_OBJECT_HIDE:"hide",
EVENT_OBJECT_DESCRIPTIONCHANGE:"descriptionChange",
EVENT_OBJECT_HELPCHANGE:"helpChange",
EVENT_OBJECT_LOCATIONCHANGE:"locationChange",
EVENT_OBJECT_NAMECHANGE:"nameChange",
EVENT_OBJECT_REORDER:"reorder",
EVENT_OBJECT_SELECTION:"selection",
EVENT_OBJECT_SELECTIONADD:"selectionAdd",
EVENT_OBJECT_SELECTIONREMOVE:"selectionRemove",
EVENT_OBJECT_SELECTIONWITHIN:"selectionWithIn",
EVENT_OBJECT_STATECHANGE:"stateChange",
EVENT_OBJECT_VALUECHANGE:"valueChange"
}

#Internal function for object events

def objectEventCallback(handle,eventID,window,objectID,childID,threadID,timestamp):
	try:
		eventName=eventMap[eventID]
		if objectID==0:
			objectID=OBJID_CLIENT
		#Let tooltips through
		if (eventID==EVENT_OBJECT_SHOW) and (winUser.getClassName(window)=="tooltips_class32"):
			core.executeFunction(EXEC_USERINTERFACE,api.executeEvent,"toolTip",window,objectID,childID)
		#Let caret events through
		elif ((eventID==EVENT_OBJECT_SHOW) or (eventID==EVENT_OBJECT_LOCATIONCHANGE)) and (objectID==OBJID_CARET):
			core.executeFunction(EXEC_USERINTERFACE,api.executeEvent,"caret",window,objectID,childID)
		#Let menu events through
		elif eventID in [EVENT_SYSTEM_MENUSTART,EVENT_SYSTEM_MENUEND,EVENT_SYSTEM_MENUPOPUPSTART,EVENT_SYSTEM_MENUPOPUPEND]:
			core.executeFunction(EXEC_USERINTERFACE,api.executeEvent,eventName,window,objectID,childID)
		#Let foreground and focus events through
		elif (eventID==EVENT_SYSTEM_FOREGROUND) or (eventID==EVENT_OBJECT_FOCUS):
			core.executeFunction(EXEC_USERINTERFACE,api.executeEvent,eventName,window,objectID,childID)
		#Let events for the focus object through
		elif (window,objectID,childID)==api.getFocusLocator():
			core.executeFunction(EXEC_USERINTERFACE,api.executeEvent,eventName,window,objectID,childID)
	except:
		debug.writeException("objectEventCallback")

#Register internal object event with MSAA
cObjectEventCallback=ctypes.CFUNCTYPE(ctypes.c_voidp,ctypes.c_int,ctypes.c_int,ctypes.c_int,ctypes.c_int,ctypes.c_int,ctypes.c_int,ctypes.c_int)(objectEventCallback)

def initialize():
	for eventType in eventMap.keys():
		handle=winUser.setWinEventHook(eventType,eventType,0,cObjectEventCallback,0,0,0)
		if handle:
			objectEventHandles.append(handle)
			debug.writeMessage("Initialize: registered 0x%x (%s) as handle %s"%(eventType,eventMap[eventType],handle))
		else:
			debug.writeError("initialize: could not register callback for event %s (%s)"%(eventType,eventMap[eventType]))

def terminate():
	for handle in objectEventHandles:
		winUser.unhookWinEvent(handle)
