# -*- coding: UTF-8 -*-
#brailleDisplayDrivers/freedomScientific.py
#A part of NonVisual Desktop Access (NVDA)
#This file is covered by the GNU General Public License.
#See the file COPYING for more details.
#Copyright (C) 2008-2017 NV Access Limited

from ctypes import *
from ctypes.wintypes import *
from collections import OrderedDict
from cStringIO import StringIO
import itertools
import os
import hwPortUtils
import braille
import inputCore
from baseObject import ScriptableObject
from logHandler import log
import bdDetect
import brailleInput
import hwIo
import serial
import _winreg


TIMEOUT = 0.2
BAUD_RATE = 57600
PARITY = serial.PARITY_NONE

#: Model names and number of cells
MODELS = {
	"Focus 14": 14,
	"Focus 40": 40,
	"Focus 44": 44,
	"Focus 70": 70,
	"Focus 80": 80,
	"Focus 84": 84,
	"pm display 20": 20,
	"pm display 40": 40,
}

# Packet types
FS_PKT_QUERY = "\x00"
FS_PKT_ACK = "\x01"
FS_PKT_NAK = "\x02"
FS_PKT_KEY = "\x03"
FS_PKT_BUTTON = "\x04"
FS_PKT_WHEEL = "\x05"
FS_PKT_HVADJ = "\x08"
FS_PKT_BEEP = "\x09"
FS_PKT_CONFIG = "\x0F"
FS_PKT_INFO = "\x80"
FS_PKT_WRITE = "\x81"
FS_PKT_EXT_KEY = "\x82"

def _makeTranslationTable(dotsTable):
	"""Create a translation table for braille dot combinations

	@param dotsTable: The list of 8 bitmasks to use for every dot
	"""
	def isoDot(number):
		return 1 << ((number + 1) - 1)

	outputTable = [0] * 256
	for byte in xrange(256):
		cell = 0
		for dot in xrange(8):
			if byte & isoDot(dot):
				cell |= dotsTable[dot]
		outputTable[byte] = cell
	return outputTable

def _translate(cells, dotsTable):
	"""Translate cells according to a dots table

	@param cells: The cells to translate, given in ISO 11548 format (used by most braille displays)
	@type cells: [int]
	@param dotsTable: A list of 8 items containing the bitmask to use for every dot
	@type dotsTable: [int]
	"""
	outCells = [0] * len(cells)
	for i, cell in enumerate(cells):
		outCells[i] = dotsTable[cell]
	return outCells

#: Dots table used by first generation Focus displays
FOCUS_1_DOTS_TABLE = [
	0X01, 0X02, 0X04, 0X10, 0X20, 0X40, 0X08, 0X80
]

FOCUS_1_TRANSLATION_TABLE = _makeTranslationTable(FOCUS_1_DOTS_TABLE)

class BrailleDisplayDriver(braille.BrailleDisplayDriver, ScriptableObject):
	name = "freedomScientific"
	# Translators: Names of braille displays.
	description = _("Freedom Scientific Focus/PAC Mate series")
	isThreadSafe = True

	wizWheelActions = [
		# Translators: The name of a key on a braille display, that scrolls the display to show previous/next part of a long line.
		(_("display scroll"), ("globalCommands", "GlobalCommands", "braille_scrollBack"),
		("globalCommands", "GlobalCommands", "braille_scrollForward")),
		# Translators: The name of a key on a braille display, that scrolls the display to show the next/previous line.
		(_("line scroll"), ("globalCommands", "GlobalCommands", "braille_previousLine"),
		("globalCommands", "GlobalCommands", "braille_nextLine")),
	]

	def __init__(self, port="auto"):
		self.numCells = 0
		self._ackPending = False
		self._pendingCells = []
		self._keyBits = 0
		self._extendedKeyBits = 0
		self.translationTable = None
		self.leftWizWheelActionCycle = itertools.cycle(self.wizWheelActions)
		action = self.leftWizWheelActionCycle.next()
		self.gestureMap.add("br(freedomScientific):leftWizWheelUp", *action[1])
		self.gestureMap.add("br(freedomScientific):leftWizWheelDown", *action[2])
		self.rightWizWheelActionCycle = itertools.cycle(self.wizWheelActions)
		action = self.rightWizWheelActionCycle.next()
		self.gestureMap.add("br(freedomScientific):rightWizWheelUp", *action[1])
		self.gestureMap.add("br(freedomScientific):rightWizWheelDown",*action[2])
		super(BrailleDisplayDriver,self).__init__()
		for portType, portId, port, portInfo in self._getTryPorts(port):
			self.isUsb = portType == bdDetect.KEY_CUSTOM
			# Try talking to the display.
			try:
				if self.isUsb:
					self._dev = hwIo.Bulk(port, 1, 0, self._onReceive, writeSize=0, onReceiveSize=56)
				else:
					self._dev = hwIo.Serial(port, baudrate=BAUD_RATE, parity=PARITY, timeout=TIMEOUT, writeTimeout=TIMEOUT, onReceive=self._onReceive)
			except EnvironmentError:
				log.debugWarning("", exc_info=True)
				continue

			# Send an identification request
			self._sendPacket(FS_PKT_QUERY)
			for _i in xrange(1):
				self._dev.waitForRead(TIMEOUT)
				if self.numCells and self._model:
					# A display responded.
					log.info("Found {device} connected via {type} ({port})".format(
						device=self._model, type=portType, port=port))
					break
			self._dev.close()
		else:
			raise RuntimeError("No Freedom Scientific display found")

		self._configureDisplay()
		self.gestureMap.add("br(freedomScientific):topRouting1", "globalCommands", "GlobalCommands", "braille_scrollBack")
		self.gestureMap.add("br(freedomScientific):topRouting%d" % self.numCells,"globalCommands", "GlobalCommands", "braille_scrollForward")

	def terminate(self):
		try:
			super(BrailleDisplayDriver, self).terminate()
		finally:
			# Make sure the device gets closed.
			# If it doesn't, we may not be able to re-open it later.
			self._dev.close()

	def _sendPacket(self, packetType, arg1="\x00", arg2="\x00", arg3="\x00", data=""):
		"""Send a packet to the display

		@param packetType: Type of packet (first byte), use one of the FS_PKT constants
		@type packetType: str
		@param arg1: First argument (second byte of packet)
		@type arg1: str
		@param arg2: Second argument (third byte of packet)
		@type arg2: str
		@param arg3: Third argument (fourth byte of packet)
		@type arg3: str
		@param data: Data to send if this is an extended packet, required checksum will be added automatically
		@type data: str
		"""
		def handleArg(arg):
			if type(arg) == int:
				return chr(arg)
			return arg
		arg1 = handleArg(arg1)
		arg2 = handleArg(arg2)
		arg3 = handleArg(arg3)
		packet = [packetType, arg1, arg2, arg3, data]
		if data:
			packet.append(chr(self._calculateChecksum(''.join(packet))))
		self._dev.write("".join(packet))

	def _onReceive(self, data):
		if self.isUsb:
			data = StringIO(data)
			packetType = data.read(1)
		else:
			packetType = data
			data = self._dev
		
		arg1 = data.read(1)
		arg2 = data.read(1)
		arg3 = data.read(1)
		log.debug("Got packet of type %r with args: %r %r %r" % (packetType, arg1, arg2, arg3))
		# Info and extended key responses are the only packets with payload and checksum
		if packetType in (FS_PKT_INFO, FS_PKT_EXT_KEY):
			length = ord(arg1)
			payload = data.read(length)
			checksum = ord(data.read(1))
			calculatedChecksum = self._calculateChecksum(packetType + arg1 + arg2 + arg3 + payload)
			assert calculatedChecksum == checksum, "Checksum mismatch, expected %s but got %s" % (checksum, payload[-1])
		else:
			payload = ""

		self._handlePacket(packetType, arg1, arg2, arg3, payload)

	def _handlePacket(self, packetType, arg1, arg2, arg3, payload):
		"Handle a packet from the device"
		if packetType == FS_PKT_ACK:
			self._awaitingAck = False
			if self._pendingCells:
				self.display(self._pendingCells)
		elif packetType == FS_PKT_NAK:
			log.debugWarning("NAK received!")
			self._awaitingAck = False
			if self._pendingCells:
				self.display(self._pendingCells)

		elif packetType == FS_PKT_INFO:
			self._manufacturer = payload[:24].replace("\x00", "")
			self._model = payload[24:40].replace("\x00", "")
			self._firmwareVersion = payload[40:48].replace("\x00", "")
			self.numCells = MODELS.get(self._model, 0)
			if self.numCells in (44, 70, 84,):
				# Focus 1: apply custom translation table
				self.translationTable = FOCUS_1_TRANSLATION_TABLE
			log.debug("Device info: manufacturer: %s model: %s, version: %s" % (self._manufacturer, self._model, self._firmwareVersion))
		elif packetType == FS_PKT_WHEEL:
			wheelNumber = ((ord(arg1) >> 3) & 0X7)
			count = ord(arg1) & 0X7
			if wheelNumber < 2:
				isRight = False
			else:
				isRight = True
			isDown = wheelNumber % 2 == 1
			if isRight:
				isDown = not isDown
			for i in xrange(count):
				gesture = WizWheelGesture(isDown, isRight)
				try:
					inputCore.manager.executeGesture(gesture)
				except inputCore.NoInputGestureAction:
					pass
		elif packetType == FS_PKT_BUTTON:
			key = ord(arg1)
			isPress = (ord(arg2) & 0X01) != 0
			keyGroup = ord(arg3)
			isTopRow = (self._model.lower().startswith("focus") and keyGroup == -1) or \
				(self._model.lower().startswith("pm display") and keyGroup == 1)
			if isPress:
				# Ignore keypresses, 
				return
			gesture = RoutingGesture(key, isTopRow)
			try:
				inputCore.manager.executeGesture(gesture)
			except inputCore.NoInputGestureAction:
				pass
		elif packetType == FS_PKT_KEY:
			keyBits = ord(arg1) | (ord(arg2) << 8) | (ord(arg3) << 16)
			self._handleKeys(keyBits)
		elif packetType == FS_PKT_EXT_KEY:
			keyBits = ord(payload[0]) >> 4
			self._handleExtendedKeys(keyBits)
		else:
			log.debugWarning("Unknown packet of type: %r" % packetType)

	def _updateKeyBits(self, keyBits, oldKeyBits, keyCount):
		"""Helper function that reports if keys have been pressed and which keys have been released
		based on old and new keybits.
		"""
		isRelease = False
		keyBitsBeforeRelease = 0
		newKeysPressed = False
		keyBit = 0X1
		keyBits |= oldKeyBits & ~((0X1 << keyCount) - 1)
		while oldKeyBits != keyBits:
			oldKey = oldKeyBits & keyBit
			newKey = keyBits & keyBit

			if oldKey and not newKey:
				# A key has been released
				isRelease = True
				keyBitsBeforeRelease = oldKeyBits
				oldKeyBits &= ~keyBit
			elif newKey and not oldKey:
				oldKeyBits |= keyBit
				newKeysPressed = True

			keyBit <<= 1
		return oldKeyBits, isRelease, keyBitsBeforeRelease, newKeysPressed
		
	def _handleKeys(self, keyBits):
		"""Send gestures if keys are released and update self._keyBits"""
		keyBits, isRelease, keyBitsBeforeRelease, newKeysPressed = self._updateKeyBits(keyBits, self._keyBits, 24)
		if newKeysPressed:
			self._ignoreKeyReleases = False
		self._keyBits = keyBits
		if isRelease and not self._ignoreKeyReleases:
			gesture = KeyGesture(keyBitsBeforeRelease, self._extendedKeyBits)
			try:
				inputCore.manager.executeGesture(gesture)
			except inputCore.NoInputGestureAction:
				pass
			self._ignoreKeyReleases = True

	def _handleExtendedKeys(self, keyBits):
		"""Send gestures if keys are released and update self._extendedKeyBits"""
		keyBits, isRelease, keyBitsBeforeRelease, newKeysPressed = self._updateKeyBits(keyBits, self._extendedKeyBits, 24)
		if newKeysPressed:
			self._ignoreKeyReleases = False
		self._extendedKeyBits = keyBits
		if isRelease and not self._ignoreKeyReleases:
			gesture = KeyGesture(self._keyBits, keyBitsBeforeRelease)
			try:
				inputCore.manager.executeGesture(gesture)
			except inputCore.NoInputGestureAction:
				pass
			self._ignoreKeyReleases = True

	def _calculateChecksum(self, data):
		"Calculate the checksum for extended packets"
		checksum = 0
		for byte in data:
			checksum -= ord(byte)
		checksum = checksum & 0xFF
		return checksum

	def display(self,cells):
		if self.translationTable:
			cells = _translate(cells, FOCUS_1_DOTS_TABLE)
		if not self._awaitingAck:
			cells="".join([chr(x) for x in cells])
			self._sendPacket(FS_PKT_WRITE, chr(self.numCells), 0, 0, cells)
			self._awaitingAck = True
			self._pendingCells = []
		else:
			self._pendingCells = cells

	def _configureDisplay(self):
		"""Enable extended keys on Focus firmware 3 and up"""
		if self._model and self._firmwareVersion and self._model.startswith("Focus") and ord(self._firmwareVersion[0]) >= ord('3'):
			# Focus 2 or later. Make sure extended keys support is enabled.
			log.debug("Activating extended keys on freedom Scientific display. Display name: %s, firmware version: %s.", self._model, self._firmwareVersion)
			self._sendPacket(FS_PKT_CONFIG, "\x02")

	def script_toggleLeftWizWheelAction(self,gesture):
		action = self.leftWizWheelActionCycle.next()
		self.gestureMap.add("br(freedomScientific):leftWizWheelUp",*action[1],replace=True)
		self.gestureMap.add("br(freedomScientific):leftWizWheelDown",*action[2],replace=True)
		braille.handler.message(action[0])

	def script_toggleRightWizWheelAction(self,gesture):
		action = self.rightWizWheelActionCycle.next()
		self.gestureMap.add("br(freedomScientific):rightWizWheelUp",*action[1],replace=True)
		self.gestureMap.add("br(freedomScientific):rightWizWheelDown",*action[2],replace=True)
		braille.handler.message(action[0])

	__gestures={
		"br(freedomScientific):leftWizWheelPress": "toggleLeftWizWheelAction",
		"br(freedomScientific):rightWizWheelPress": "toggleRightWizWheelAction",
	}

	gestureMap=inputCore.GlobalGestureMap({
		"globalCommands.GlobalCommands": {
			"braille_routeTo": ("br(freedomScientific):routing",),
			"braille_scrollBack": ("br(freedomScientific):leftAdvanceBar", "br(freedomScientific):leftBumperBarUp","br(freedomScientific):rightBumperBarUp",),
			"braille_scrollForward": ("br(freedomScientific):rightAdvanceBar", "br(freedomScientific):leftBumperBarDown", "br(freedomScientific):rightBumperBarDown",),
			"braille_previousLine": ("br(freedomScientific):leftRockerBarUp", "br(freedomScientific):rightRockerBarUp",),
			"braille_nextLine": ("br(freedomScientific):leftRockerBarDown", "br(freedomScientific):rightRockerBarDown",),
			"kb:shift+tab": ("br(freedomScientific):dot1+dot2+brailleSpaceBar",),
			"kb:tab": ("br(freedomScientific):dot4+dot5+brailleSpaceBar",),
			"kb:upArrow": ("br(freedomScientific):dot1+brailleSpaceBar",),
			"kb:downArrow": ("br(freedomScientific):dot4+brailleSpaceBar",),
			"kb:leftArrow": ("br(freedomScientific):dot3+brailleSpaceBar",),
			"kb:rightArrow": ("br(freedomScientific):dot6+brailleSpaceBar",),
			"kb:control+leftArrow": ("br(freedomScientific):dot2+brailleSpaceBar",),
			"kb:control+rightArrow": ("br(freedomScientific):dot5+brailleSpaceBar",),
			"kb:home": ("br(freedomScientific):dot1+dot3+brailleSpaceBar",),
			"kb:control+home": ("br(freedomScientific):dot1+dot2+dot3+brailleSpaceBar",),
			"kb:end": ("br(freedomScientific):dot4+dot6+brailleSpaceBar",),
			"kb:control+end": ("br(freedomScientific):dot4+dot5+dot6+brailleSpaceBar",),
			"kb:alt": ("br(freedomScientific):dot1+dot3+dot4+brailleSpaceBar",),
			"kb:alt+tab": ("br(freedomScientific):dot2+dot3+dot4+dot5+brailleSpaceBar",),
			"kb:escape": ("br(freedomScientific):dot1+dot5+brailleSpaceBar",),
			"kb:windows": ("br(freedomScientific):dot2+dot4+dot5+dot6+brailleSpaceBar",),
			"kb:windows+d": ("br(freedomScientific):dot1+dot2+dot3+dot4+dot5+dot6+brailleSpaceBar",),
			"reportCurrentLine": ("br(freedomScientific):dot1+dot4+brailleSpaceBar",),
			"showGui": ("br(freedomScientific):dot1+dot3+dot4+dot5+brailleSpaceBar",),
			"braille_toggleTether": ("br(freedomScientific):leftGDFButton+rightGDFButton",),
		}
	})

class InputGesture(braille.BrailleDisplayGesture):
	source = BrailleDisplayDriver.name

class KeyGesture(InputGesture, brailleInput.BrailleInputGesture):

	keyLabels = [
		# Braille keys (byte 1)
		'dot1','dot2','dot3','dot4','dot5','dot6','dot7','dot8',
		# Assorted keys (byte 2)
		'leftWizWheelPress','rightWizWheelPress',
		'leftShiftKey','rightShiftKey',
		'leftAdvanceBar','rightAdvanceBar',
		None,
		'brailleSpaceBar',
		# GDF keys (byte 3)
		'leftGDFButton','rightGDFButton',
		None,
		'leftBumperBarUp','leftBumperBarDown','rightBumperBarUp','rightBumperBarDown',
	]
	extendedKeyLabels = [
	# Rocker bar keys.
	"leftRockerBarUp", "leftRockerBarDown", "rightRockerBarUp", "rightRockerBarDown",
	]

	def __init__(self, keyBits, extendedKeyBits):
		super(KeyGesture,self).__init__()
		keys=[self.keyLabels[num] for num in xrange(24) if (keyBits>>num) & 1]
		extendedKeys=[self.extendedKeyLabels[num] for num in xrange(4) if (extendedKeyBits>>num) & 1]
		self.id = "+".join(keys+extendedKeys)
		# Don't say is this a dots gesture if some keys either from dots and space are pressed.
		if not extendedKeyBits and not keyBits & ~(0xff | (1 << 0xf)):
			self.dots = keyBits & 0xff
			# Is space?
			if keyBits & (1 << 0xf):
				self.space = True

class RoutingGesture(InputGesture):
	def __init__(self, routingIndex, topRow=False):
		if topRow:
			self.id = "topRouting%d"%(routingIndex+1)
		else:
			self.id = "routing"
			self.routingIndex = routingIndex
		super(RoutingGesture,self).__init__()

class WizWheelGesture(InputGesture):
	def __init__(self, isDown, isRight):
		which = "right" if isRight else "left"
		direction = "Down" if isDown else "Up"
		self.id = "%sWizWheel%s" % (which, direction)
		super(WizWheelGesture, self).__init__()
