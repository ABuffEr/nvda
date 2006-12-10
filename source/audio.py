"""High-level functions to speak information.
@var allowSpeech: allows speech if true
@type allowSpeech: boolean
""" 

import winsound
import debug
from textProcessing import *
from config import conf
import synthDriverHandler

allowSpeech=True

def initialize():
	"""Loads and sets the synth driver configured in nvda.ini."""
	synthDriverHandler.setDriver(conf["speech"]["synth"])

def getLastIndex():
	"""Gets the last index passed by the synthesizer. Indexing is used so that its possible to find out when a certain peace of text has been spoken yet. Usually the character position of the text is passed to speak functions as the index.
@returns: the last index encountered
@rtype: int
"""
	return synthDriverHandler.getLastIndex()

def processText(text):
	"""Processes the text using the L{textProcessing} module which converts punctuation so it is suitable to be spoken by the synthesizer. This function makes sure that all punctuation is included if it is configured so in nvda.ini.
@param text: the text to be processed
@type text: string
"""
	text=processTextSymbols(text,expandPunctuation=conf["speech"][synthDriverHandler.driverName]["speakPunctuation"])
	return text

def playSound(fileName,wait=False):
	"""Plays a given sound file.
@param fileName: the file path of the sound
@type fileName: string 
@param wait: if true, the function will not return until the sound has finished playing, if false, the function will return straight away.
@type wait: boolean
"""
	flags=0
	if wait is False:
		flags=winsound.SND_ASYNC
	winsound.PlaySound(fileName,flags)

def cancel():
	"""Interupts the synthesizer from currently speaking"""
	synthDriverHandler.cancel()

def speakMessage(text,wait=False,index=None):
	"""Speaks a given message.
This function will not speak if L{allowSpeech} is false.
@param text: the message to speak
@type text: string
@param wait: if true, the function will not return until the text has finished being spoken. If false, the function will return straight away.
@type wait: boolean
@param index: the index to mark this current text with 
@type index: int
"""
	if not allowSpeech:
		return
	text=processText(text)
	if text and not text.isspace():
		synthDriverHandler.speakText("\n"+text+"\n",wait=wait,index=index)

def speakObjectProperties(name=None,typeString=None,stateText=None,value=None,description=None,keyboardShortcut=None,position=None,wait=False,index=None):
	"""Speaks some given object properties.
This function will not speak if L{allowSpeech} is false.
@param name: object name
@type name: string
@param typeString: object type string
@type typeString: string
@param stateText: object state text
@type stateText: string
@param value: object value
@type value: string
@param description: object description
@type description: string
@param keyboardShortcut: object keyboard shortcut
@type keyboardShortcut: string
@param position: object position info
@type position: string
@param wait: if true, the function will not return until the text has finished being spoken. If false, the function will return straight away.
@type wait: boolean
@param index: the index to mark this current text with 
@type index: int
"""
	if not allowSpeech:
		return
	text=""
	if conf["presentation"]["sayStateFirst"] and (stateText is not None):
		text="%s %s"%(text,stateText)
	if name is not None:
		text="%s %s"%(text,name)
	if typeString is not None:
		text+=" %s"%typeString
	if not conf["presentation"]["sayStateFirst"] and (stateText is not None):
		text="%s %s"%(text,stateText)
	if value is not None:
		text="%s %s"%(text,value)
	if description is not None:
		text="%s %s"%(text,description)
	if keyboardShortcut is not None:
		text="%s %s"%(text,keyboardShortcut)
	if position is not None:
		text="%s %s"%(text,position)
	text=processText(text)
	if text and not text.isspace():
		synthDriverHandler.speakText(text,wait=wait,index=index)

def speakSymbol(symbol,wait=False,index=None):
	"""Speaks a given single character.
This function will not speak if L{allowSpeech} is false.
If the character is uppercase, then the pitch of the synthesizer will be altered by a value in nvda.ini and then set back to its origional value. This is to audibly denote capital letters.
Before passing the symbol to the synthersizer, L{textProcessing.processSymbol} is used to expand the symbol to a  speakable word.
@param symbol: the symbol to speak
@type symbol: string
@param wait: if true, the function will not return until the text has finished being spoken. If false, the function will return straight away.
@type wait: boolean
@param index: the index to mark this current text with 
@type index: int
"""
	if not allowSpeech:
		return
	symbol=processSymbol(symbol)
	if (symbol[0]>='A') and (symbol[0]<='Z'):
		uppercase=True
	else:
		uppercase=False
	if uppercase:
		oldPitch=synthDriverHandler.getPitch()
		synthDriverHandler.setPitch(oldPitch+conf["speech"][synthDriverHandler.driverName]["relativeUppercasePitch"])
	synthDriverHandler.speakText(symbol,wait=wait,index=index)
	if uppercase:
		synthDriverHandler.setPitch(oldPitch)

def speakText(text,wait=False,index=None):
	"""Speaks some given text.
This function will not speak if L{allowSpeech} is false.
@param text: the message to speak
@type text: string
@param wait: if true, the function will not return until the text has finished being spoken. If false, the function will return straight away.
@type wait: boolean
@param index: the index to mark this current text with, its best to use the character position of the text if you know it 
@type index: int
"""
	if not allowSpeech:
		return
	text=processText(text)
	if text and not text.isspace():
		synthDriverHandler.speakText(text,wait=wait,index=index)
