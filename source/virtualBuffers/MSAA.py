import debug
from constants import *
import winUser
from keyboardHandler import key
import api
import audio
import NVDAObjects
from constants import *
import MSHTML
import gecko

runningTable={}

def getVirtualBuffer(obj):
	if len(runningTable)==0:
		return None
	if isinstance(obj,int):
		hwnd=obj
	elif isinstance(obj,NVDAObjects.MSAA.NVDAObject_MSAA):
		hwnd=obj.windowHandle
	else:
		return
	for existingHwnd in runningTable:
		if winUser.isDescendantWindow(existingHwnd,hwnd):
			return runningTable[existingHwnd]
	return None

def update(obj):
	for w in filter(lambda x: not winUser.isWindow(x),runningTable):
		debug.writeMessage("virtualBuffers.MSAA.removeVirtualBuffer: removed %s at %s"%(runningTable[w],w))
		del runningTable[w]
	if isinstance(obj,NVDAObjects.MSAA.NVDAObject_MSAA) :
		hwnd=obj.windowHandle
	elif isinstance(obj,int):
		hwnd=obj
	else:
		return
	debug.writeMessage("virtualBuffers.MSAA.update: trying to update with %s (%s)"%(hwnd,winUser.getClassName(hwnd)))
	if getVirtualBuffer(obj):
		return
	while hwnd:
		obj=NVDAObjects.MSAA.getNVDAObjectFromEvent(hwnd,OBJID_CLIENT,0)
		if obj:
			className=obj.windowClassName
			role=obj.role
			if _dynamicMap.has_key((className,role)):
				virtualBufferClass=_dynamicMap[(className,role)]
			elif _dynamicMap.has_key((className,None)):
				virtualBufferClass=_dynamicMap[(className,None)]
			elif _staticMap.has_key((className,role)):
				virtualBufferClass=_staticMap[(className,role)]
			elif _staticMap.has_key((className,None)):
				virtualBufferClass=_staticMap[(className,None)]
			else:
				virtualBufferClass=None
			if virtualBufferClass:
				debug.writeMessage("virtualBuffers.MSAA.update: adding %s at %s (%s)"%(virtualBufferClass,obj.windowHandle,className))
				virtualBufferObject=virtualBufferClass(obj)
				runningTable[obj.windowHandle]=virtualBufferObject
				return 
		hwnd=winUser.getAncestor(hwnd,GA_PARENT)

def registerVirtualBufferClass(windowClass,role,cls):
	_dynamicMap[(windowClass,role)]=cls

def unregisterVirtualBufferClass(windowClass,role):
	del _dynamicMap[(windowClass,role)]

_staticMap={
("Internet Explorer_Server",None):MSHTML.virtualBuffer_MSHTML,
("MozillaContentWindowClass",ROLE_SYSTEM_DOCUMENT):gecko.virtualBuffer_gecko,
}

_dynamicMap={}

