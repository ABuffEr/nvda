import ctypes
import ctypes.wintypes

user32=ctypes.windll.user32

class pointType(ctypes.Structure):
	_fields_=[
	('x',ctypes.c_int),
	('y',ctypes.c_int),
	]

class msgType(ctypes.Structure):
	_fields_=[
	('hwnd',ctypes.c_int),
	('message',ctypes.c_int),
	('wParam',ctypes.c_int),
	('lParam',ctypes.c_int),
	('time',ctypes.c_int),
	('pt',pointType),
	]

def LOBYTE(word):
	return word&0xFF
 
def HIBYTE(word):
	return word>>8

def MAKEWORD(lo,hi):
	return (hi<<8)+lo

def LOWORD(long):
	return long&0xFFFF
 
def HIWORD(long):
	return long>>16

def MAKELONG(lo,hi):
	return (hi<<16)+lo

def waitMessage():
	return user32.WaitMessage()

def getMessage(*args):
	return user32.GetMessageW(*args)

def translateMessage(*args):
	return user32.TranslateMessage(*args)

def dispatchMessage(*args):
	return user32.DispatchMessageW(*args)

def peekMessage(*args):
	return user32.PeekMessageW(*args)

def registerWindowMessage(name):
	return user32.RegisterWindowMessageW(name)

def getAsyncKeyState(v):
	return user32.GetAsyncKeyState(v)

def getKeyState(v):
	return user32.GetKeyState(v)

def isWindow(hwnd):
	return user32.IsWindow(hwnd)

def isDecendantWindow(parentHwnd,childHwnd):
	if (parentHwnd==childHwnd) or user32.IsChild(parentHwnd,childHwnd):
		return True
	else:
		return False

def getForegroundWindow():
	return user32.GetForegroundWindow()

def setForegroundWindow(hwnd):
	user32.SetForegroundWindow(hwnd)

def setFocus(hwnd):
	user32.SetFocus(hwnd)

def getDesktopWindow():
		return user32.GetDesktopWindow()

def getControlID(hwnd):
	return user32.GetWindowLong(hwnd)

def getClientRect(hwnd):
	return user32.GetClientRect(hwnd)

def setWinEventHook(*args):
		return user32.SetWinEventHook(*args)

def unhookWinEvent(*args):
	return user32.UnhookWinEvent(*args)

def sendMessage(*args):
	return user32.SendMessageW(*args)

def getWindowThreadProcessID(hwnd):
	processID=ctypes.c_int()
	threadID=user32.GetWindowThreadProcessId(hwnd,ctypes.byref(processID))
	return (processID.value,threadID)

def getClassName(window):
	buf=ctypes.create_unicode_buffer(256)
	user32.GetClassNameW(window,buf,255)
	return buf.value

def keybd_event(*args):
	return user32.keybd_event(*args)

def getAncestor(hwnd,flags):
	return user32.GetAncestor(hwnd,flags)

def setCursorPos(x,y):
	user32.SetCursorPos(x,y)

def getCursorPos():
	point=ctypes.wintypes.POINT()
	user32.GetCursorPos(ctypes.byref(point))
	return [point.x,point.y]


