import asyncore, asynchat, socket
import globalVars
from synthDriverHandler import getSynth
import keyboardHandler
from logHandler import log
from synthDriverHandler import SynthDriver
import winUser
from gui import scriptUI

#constants
terminator = "konec"
command_closeConnection = '0'
command_keyDown = '1'
command_keyUp = '2'
command_terminateSynth = '3'
command_speakText = '4'
command_cancelSpeech = '5'
command_setVoice = '6'
command_setRate = '7'
command_setPitch = '8'
command_setVolume = '9'
command_setVariant = 'a'
command_setInflection = 'b'
command_pauseSpeech = 'c'
serverPort = 2402

#global definitions
server = None
remoteConnectionList = None

class ConnectionList:
	conns = []

	def __init__(self,onJoin,onLeave):
		self.onJoin = onJoin
		self.onLeave = onLeave

	def join(self,conn):
		self.conns.append(conn)
		self.onJoin(conn)

	def leave(self,conn):
		self.conns.remove(conn)
		self.onLeave(conn)

	def sendToAll(self,data):
		for conn in self.conns:
			conn.push(data+terminator)

	def closeAll(self):
		for conn in self.conns: conn.close_when_done()

class Session(asynchat.async_chat):
	inputBuf = ""

	def __init__(self,connectionList,sock=None):
		global terminator
		asynchat.async_chat.__init__(self,sock)
		self.set_terminator(terminator)
		self.connectionList = connectionList
		self.connectionList.join(self)

	def handle_close(self):
		self.connectionList.leave(self)
		asynchat.async_chat.handle_close(self)

	def collect_incoming_data(self, data):
		self.inputBuf+=data

	def found_terminator(self):
		log.io("Incoming tandem command: %s"%self.inputBuf)
		command = self.inputBuf[0]
		self.inputBuf= self.inputBuf[1:]
		self.processCommand(command,self.inputBuf)
		self.inputBuf = ""

	def processCommand(self,command,data):
		if command == command_keyDown:
			vkCode,scanCode,extended,injected = data.split(" ")
			res = keyboardHandler.internal_keyDownEvent(int(vkCode),int(scanCode),bool(extended),bool(injected))
			if not res: return
			if extended:
				flags = 1
			else:
				flags = 0
			winUser.keybd_event(int(vkCode),0,flags,0)
		elif command == command_keyUp:
			vkCode,scanCode,extended,injected = data.split(" ")
			res = keyboardHandler.internal_keyUpEvent(int(vkCode),int(scanCode),bool(extended),bool(injected))
			if not res: return
			if extended:
				flags = 1
			else:
				flags = 0
			winUser.keybd_event(int(vkCode),0,flags+2,0)
		elif command == command_closeConnection:
			self.close_when_done()
		elif command == command_speakText:
			index, text = data.split(" ")
			if index == "None": 
				index = None
			else:
				index = int(index)
			getSynth().speakText(text,index)
		elif command == command_cancelSpeech:
			getSynth().cancel()

class TandemServer(asynchat.async_chat):
	def __init__(self):
		log.info("Starting tandem server")
		asynchat.async_chat.__init__(self)
		globalVars.tandemServerActive = True
		self.clients = ConnectionList(self.logJoiningClient, self.logLeavingClient)
		self.create_socket(socket.AF_INET, socket.SOCK_STREAM)
		self.set_reuse_addr()
		self.bind(('', serverPort))
		self.listen(2)
		log.debug("Listening tandem connections")

	def handle_accept(self):
		sock, addr = self.accept()
		log.info("incoming tandem connection")
		log.debug(addr)
		client = Session(self.clients,sock)

	def sendToAll(self,data):
		clients.sendToAll(data)

	def close(self):
		clients.closeAll()
		globalVars.tandemServerActive = False
		log.info("Tandem server stopped")

	def logJoiningClient(self,client):
		log.info("Connected tandem client")

	def logLeavingClient(self,client):
		log.info("Disconnected tandem client")

class ClientSession(Session):
	def __init__(self,connectionList,addr):
		Session.__init__(self,connectionList)
		self.create_socket (socket.AF_INET, socket.SOCK_STREAM)
		self.connect((addr,serverPort))

	def handle_connect(self):
		log.info("connection established")

class TandemSynthDriver(SynthDriver):
	"""A proxy SynthDriver which transports all operations to clients, also performing they on local side."""
	#the actual synth
	synth = None

	def __init__(self,synth):
		#the @synth is already initialized
		self.synth = synth
		self.name = synth.name
		self.description = synth.description
		self.hasVoice = synth.hasVoice
		self.hasVariant = synth.hasVariant
		self.hasPitch = synth.hasPitch
		self.hasRate = synth.hasRate
		self.hasVolume = synth.hasVolume
		self.pitchMinStep = synth.pitchMinStep
		self.rateMinStep = synth.rateMinStep
		self.volumeMinStep = synth.volumeMinStep
		self.inflectionMinStep = synth.inflectionMinStep
		self.hasInflection = synth.hasInflection
		self.availableVoices = synth.availableVoices
		self.availableVariants = synth.availableVariants

	def terminate(self):
		self.synth.terminate()
		self.synth = None
		if server is not None:
			server.sendToAll(command_terminateSynth)

	def speakText(self, text, index=None):
		self.synth.speakText(text,index)
		if server is not None:
			server.sendToAll(command_speakText+"%s %s"%(index,text))

	def _get_lastIndex(self):
		return self.synth._get_lastIndex()

	def cancel(self):
		self.synth.cancel()
		if server is not None:
			server.sendToAll(command_cancelSpeech)

	def _get_voice(self):
		return self.synth._get_voice()

	def _set_voice(self, value):
		self.synth._set_voice(value)
		if server is not None:
			server.sendToAll(command_setVoice+str(value))

	def _getAvailableVoices(self):
		return self.synth._getAvailableVoices()

	def _get_availableVoices(self):
		return self.synth._get_availableVoices()

	def _get_rate(self):
		return  self.synth._get_rate()

	def _set_rate(self, value):
		self.synth._set_rate(value)
		if server is not None:
			server.sendToAll(command_setRate+str(value))

	def _get_pitch(self):
		return self.synth._get_pitch()

	def _set_pitch(self, value):
		self.synth._set_pitch(value)
		if server is not None:
			server.sendToAll(command_setPitch+str(value))

	def _get_volume(self):
		return self.synth._get_volume()

	def _set_volume(self, value):
		self.synth._set_volume(value)
		if server is not None:
			server.sendToAll(command_setVolume+str(value))

	def _get_variant(self):
		return self.synth._get_variant()

	def _set_variant(self, value):
		self.synth._set_variant(value)
		if server is not None:
			server.sendToAll(command_setVariant+str(value))

	def _getAvailableVariants(self):
		return self.synth._getAvailableVariants()

	def _get_availableVariants(self):
		return self.synth._get_availableVariants()

	def _get_inflection(self):
		return synth._get_inflection()

	def _set_inflection(self, value):
		self.synth._set_inflection(value)
		if server is not None:
			server.sendToAll(command_setInflection+str(value))

	def pause(self, switch):
		self.synth.pause(switch)
		if server is not None:
			server.sendToAll(command_pauseSpeech+str(switch))

	def getVoiceInfoByID(self,ID):
		return self.synth.getVoiceInfoByID(ID)

def update():
	asyncore.poll()

def startTandemServer():
	if globalVars.tandemServerActive: return
	global server
	server = TandemServer()

def stopTandemServer():
	global server
	if server is None: return
	server.close()
	server = None

def onJoinClient(client):
	log.info("Connecting  to remote machine")

def onLeaveClient(client):
	log.info("Disconnected from remote machine")

def connectToServer():
	d = scriptUI.TextEntryDialog(_("Enter remote server's IP address"),callback=handleAddressDialog)
	d.run()

def handleAddressDialog(text):
	global remoteConnectionList
	if remoteConnectionList is None: remoteConnectionList = ConnectionList(onJoinClient,onLeaveClient)
	ClientSession(remoteConnectionList,text)
	globalVars.tandemClientActive = True

def sendKey(keyDown, vkCode,scanCode,extended,injected):
	global remoteConnectionList
	#have python expr ? true : false syntax? 
	if keyDown: 
		comm = command_keyDown
	else:
		comm = command_keyUp
	remoteConnectionList.sendToAll(comm+"%d %d %s %s"%(vkCode,scanCode,extended,injected))