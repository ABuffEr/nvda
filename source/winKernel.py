import ctypes

kernel32=ctypes.windll.kernel32

class consoleCoordType(ctypes.Structure):
	_fields_=[
('x',ctypes.c_short),
('y',ctypes.c_short),
]

class consoleWindowRectType(ctypes.Structure):
	_fields_=[
('left',ctypes.c_short),
('top',ctypes.c_short),
('right',ctypes.c_short),
('bottom',ctypes.c_short),
]

class consoleScreenBufferInfoType(ctypes.Structure):
	_fields_=[
('consoleSize',consoleCoordType),
('cursorPosition',consoleCoordType),
('attributes',ctypes.c_short),
('windowRect',consoleWindowRectType),
('maxWindowSize',consoleCoordType),
]

def attachConsole(processID):
	return kernel32.AttachConsole(processID)

def freeConsole():
	return kernel32.FreeConsole()

def getStdHandle(handleID):
	return kernel32.GetStdHandle(handleID)

def readConsoleOutputCharacter(handle,length,x,y):
	point=consoleCoordType()
	point.x=x
	point.y=y
	buf=ctypes.create_unicode_buffer(length)
	kernel32.ReadConsoleOutputCharacterW(handle,buf,length,point,ctypes.byref(ctypes.c_int(0)))
	return buf.value

def getConsoleScreenBufferInfo(handle):
	info=consoleScreenBufferInfoType()
	kernel32.GetConsoleScreenBufferInfo(handle,ctypes.byref(info))
	return info

def openProcess(*args):
	return kernel32.OpenProcess(*args)

def closeHandle(*args):
	return kernel32.CloseHandle(*args)

