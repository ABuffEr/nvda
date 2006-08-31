import struct
import re
import win32api
import win32com
import win32con
import win32gui
import pyAA
import debug
from api import *
import keyEventHandler
from config import conf

re_multiSpacing=re.compile(r' +')

def makeNVDAObject(accObject):
	return NVDAObject(accObject)

class NVDAObject(object):

	def __new__(cls,*args):
		if (len(args)!=1) or not isinstance(args[0],pyAA.AA.AccessibleObject):
			raise TypeError("class takes an object of type pyAA.AA.AccessibleObject as its only parameter")
		accObject=args[0]
		try:
			window=accObject.Window
		except:
			return None
		if not win32gui.IsWindow(window):
			return None
		className=win32gui.GetClassName(window)
		try:
			role=accObject.GetRole()
		except:
			return None
		NVDAClass=classMap.get("%s_%s"%(className,role),None)
		if not NVDAClass:
			NVDAClass=classMap.get("%s"%className,None)
			if not NVDAClass:
				NVDAClass=cls
		return object.__new__(NVDAClass,*args)

	def __init__(self,accObject):
		self.accObject=accObject
		self.lines=[]
		self.keyMap={}
		self.lastStates=self.getStates()

	def __eq__(self,other):
		if (self.getProcessID()==other.getProcessID()) and (self.getWindowHandle()==other.getWindowHandle()) and (self.getRole()==other.getRole()) and (self.getChildID()==other.getChildID()) and (self.getLocation()==other.getLocation()):
			return True
		else:
			return False

	def __ne__(self,other):
		if (self.getProcessID()!=other.getProcessID()) or (self.getWindowHandle()!=other.getWindowHandle()) or (self.getRole()!=other.getRole()) or (self.getChildID()!=other.getChildID()) or (self.getLocation()!=other.getLocation()):
			return True
		else:
			return False

	def getBufferText(self):
		thisLine=""
		if conf["presentation"]["reportKeyboardShortcuts"]:
			thisLine+=" %s"%self.getKeyboardShortcut()
		thisLine+=" %s"%self.getName()
		if conf["presentation"]["reportClassOfAllObjects"] or (conf["presentation"]["reportClassOfClientObjects"] and (self.getRole()==ROLE_SYSTEM_CLIENT)):
			thisLine+=" %s"%self.getClassName()
		thisLine+=" %s"%getRoleName(self.getRole())
		thisLine+=" %s"%self.getValue()
		thisLine+=" %s"%getStateNames(self.getStates())
		text=[]
		children=self.getChildren()
		for child in children:
			text+=child.getBufferText()
		if len(children)>0:
			text.append("end of %s %s"%(self.getName(),getRoleName(self.getRole())))
			thisLine="%s (contains %s items):"%(thisLine,len(children))
		thisLine=thisLine.strip()
		thisLine=re_multiSpacing.sub(" ",thisLine)
		text.insert(0,thisLine)
		return text

	def updateBuffer(self):
		if len(self.lines)==0: 
			self.lines=self.getBufferText()

	def speakObject(obj):
		window=obj.getWindowHandle()
		name=obj.getName()
		role=obj.getRole()
		if conf["presentation"]["reportClassOfAllObjects"] or (conf["presentation"]["reportClassOfClientObjects"] and (role==ROLE_SYSTEM_CLIENT)):
			className=obj.getClassName()
		else:
			className=None
		roleName=getRoleName(role)
		states=obj.getStates()
		stateNames=""
		if states is not None:
			states=filterStates(states)
			stateNames=""
			for state in createStateList(states):
				stateNames="%s %s"%(stateNames,getStateName(state))
		value=obj.getValue()
		description=obj.getDescription()
		if description==name:
			description=None
		help=obj.getHelp()
		if conf["presentation"]["reportKeyboardShortcuts"]:
			keyboardShortcut=obj.getKeyboardShortcut()
		else:
			keyboardShortcut=None
		position=None
		childID=obj.getChildID()
		if childID>0:
			parent=obj.getParent()
			if parent:
				parentChildCount=parent.getChildCount()
				position="%s of %s"%(childID,parentChildCount)
		#if role!=ROLE_SYSTEM_GROUPING:
		#	groupName=getObjectGroupName(accObject)
		#else:
		#	groupName=None
		groupName=None
		audio.speakObjectProperties(groupName=groupName,name=name,className=className,roleName=roleName,stateNames=stateNames,value=value,description=description,help=help,keyboardShortcut=keyboardShortcut,position=position)

	def getWindowHandle(self):
		try:
			window=self.accObject.Window
		except:
			return None
		return window

	def getName(self):
		try:
			name=self.accObject.GetName()
		except:
			name=""
		if not name:
			window=self.getWindowHandle()
			if not window:
				return ""
			name=win32gui.GetWindowText(window)
		return name

	def getValue(self):
		value=None
		try:
			value=self.accObject.GetValue()
		except:
			pass
		if value:
			return value
		else:
			return ""

	def getRole(self):
		try:
			return self.accObject.GetRole()
		except:
			return ""

	def getStates(self):
		states=0
		try:
			states=self.accObject.GetState()
		except:
			pass
		states-=(states&STATE_SYSTEM_FOCUSED)
		states-=(states&STATE_SYSTEM_FOCUSABLE)
		states-=(states&STATE_SYSTEM_SELECTABLE)
		states-=(states&STATE_SYSTEM_MULTISELECTABLE)
		return states

	def getDescription(self):
		try:
			return self.accObject.GetDescription()
		except:
			return ""

	def getHelp(self):
		try:
			return self.accObject.GetHelp()
		except:
			return ""

	def getKeyboardShortcut(self):
		keyboardShortcut=None
		try:
			keyboardShortcut=self.accObject.GetKeyboardShortcut()
		except:
			return ""
		if not keyboardShortcut:
			return ""
		else:
			return keyboardShortcut

	def getChildID(self):
		try:
			return self.accObject.ChildID
		except:
			return None

	def getChildCount(self):
		return len(self.getChildren())

	def getProcessID(self):
		try:
			return self.accObject.ProcessID
		except:
			debug.writeException("NVDAObjects.NVDAObject.getProcessID")
			return None

	def getLocation(self):
		try:
			return self.accObject.GetLocation()
		except:
			return None

	def getClassName(self):
		return win32gui.GetClassName(self.getWindowHandle())

	def getParent(self):
		try:
			accObject=self.accObject.GetParent()
		except:
			return None
		if accObject.GetRole()==pyAA.Constants.ROLE_SYSTEM_WINDOW:
			try:
				return makeNVDAObject(accObject.GetParent())
			except:
				return None
		else:
			return makeNVDAObject(accObject)

	def getNext(self):
		try:
			parentObject=NVDAObject(self.accObject.GetParent())
			parentRole=parentObject.getRole()
		except:
			parentObject=None
			parentRole=None
		if parentObject and (parentRole==ROLE_SYSTEM_WINDOW):
			try:
				nextObject=NVDAObject(parentObject.accObject.Navigate(pyAA.Constants.NAVDIR_NEXT))
				testObject=NVDAObject(nextObject.accObject.Navigate(pyAA.Constants.NAVDIR_PREVIOUS))
				if nextObject and testObject and (testObject==parentObject) and (nextObject!=parentObject):  
					return makeNVDAObject(pyAA.AccessibleObjectFromWindow(nextObject.getWindowHandle(),pyAA.Constants.OBJID_CLIENT))
			except:
				debug.writeException("next object using window")
				return None
		else:
			try:
				nextObject=NVDAObject(self.accObject.Navigate(pyAA.Constants.NAVDIR_NEXT))
				testObject=NVDAObject(nextObject.accObject.Navigate(pyAA.Constants.NAVDIR_PREVIOUS))
				if nextObject and testObject and (self==testObject) and (nextObject!=self):
					return nextObject
				else:
					return None
			except:
				return None

	def getPrevious(self):
		try:
			parentObject=self.accObject.GetParent()
			parentRole=parentObject.GetRole()
		except:
			return None
		if parentRole==pyAA.Constants.ROLE_SYSTEM_WINDOW:
			try:
				prevObject=parentObject.Navigate(pyAA.Constants.NAVDIR_PREVIOUS)
				testObject=prevObject.Navigate(pyAA.Constants.NAVDIR_NEXT)
				if prevObject and testObject and ((prevObject.Window!=testObject.Window) or (prevObject.GetRole()!=testObject.GetRole()) or (prevObject.ChildID!=testObject.ChildID)):
					return makeNVDAObject(pyAA.AccessibleObjectFromWindow(prevObject.Window,pyAA.Constants.OBJID_CLIENT))
				else:
					return None
			except:
				return None
		else:
			try:
				prevObject=self.accObject.Navigate(pyAA.Constants.NAVDIR_PREVIOUS)
				testObject=prevObject.Navigate(pyAA.Constants.NAVDIR_NEXT)
				if prevObject and testObject and ((prevObject.Window!=testObject.Window) or (prevObject.GetRole()!=testObject.GetRole()) or (prevObject.ChildID!=testObject.ChildID)):
					return makeNVDAObject(prevObject)
				else:
					return None
			except:
				return None

	def getFirstChild(self):
		try:
			childObject=self.accObject.Navigate(pyAA.Constants.NAVDIR_FIRSTCHILD)
			if childObject.GetRole()==pyAA.Constants.ROLE_SYSTEM_WINDOW:
				childObject=pyAA.AccessibleObjectFromWindow(childObject.Window,pyAA.Constants.OBJID_CLIENT)
			testObject=self.accObject
			if childObject and ((childObject.Window!=testObject.Window) or (childObject.GetRole()!=testObject.GetRole()) or (childObject.ChildID!=testObject.ChildID)):
				return makeNVDAObject(childObject)
			else:
				return None
		except:
			return None

	def doDefaultAction(self):
		try:
			self.accObject.DoDefaultAction()
		except:
			pass

	def getChildren(self):
		children=[]
		obj=self.getFirstChild()
		if obj:
			children.append(obj)
			next=obj.getNext()
			while next:
				children.append(next)
				next=next.getNext()
		return children

	def getActiveChild(self):
		try:
			child=self.accObject.GetFocus()
		except:
			return None
		return makeNVDAObject(child)

	def hasFocus(self):
		states=0
		try:
			states=self.accObject.GetState()
		except:
			pass
		if states&pyAA.Constants.STATE_SYSTEM_FOCUSED:
			return True
		else:
			return False

	def getCaretIndecies():
		return [[0,0],[0,0]]

	def getCaretIndex(self):
		return [0,0]

	def getNextCharacterIndex(self,index,crossLines=True):
		lineLength=self.getLineLength(index=index)
		lineCount=self.getLineCount()
		if index[1]==lineLength:
			if (index[0]==lineCount-1) or not crossLines:
				return None
			else:
				newIndex=[index[0]+1,0]
		else:
			newIndex=[index[0],index[1]+1]
		return newIndex

	def getPreviousCharacterIndex(self,index,crossLines=True):
		lineLength=self.getLineLength(index=index)
		lineCount=self.getLineCount()
		if index[1]==0:
			if (index[0]==0) or not crossLines:
				return None
			else:
				newIndex=[index[0]-1,self.getLineLength(index[0]-1)-1]
		else:
			newIndex=[index[0],index[1]-1]
		return newIndex

	def getWordEndIndex(self,index):
		whitespace=['\n','\r','\t',' ','\0']
		if not index:
			raise TypeError("function takes a character index as its ownly argument")
		curIndex=index
		while self.getCharacter(index=curIndex) not in whitespace:
			prevIndex=curIndex
			curIndex=self.getNextCharacterIndex(curIndex,crossLines=False)
			if not curIndex:
				return prevIndex
		return curIndex

	def getNextLineIndex(self,index):
		lineCount=self.getLineCount()
		if index[0]>=lineCount-1:
			return None
		else:
			return [index[0]+1,0]

	def getPreviousLineIndex(self,index):
		lineCount=self.getLineCount()
		if index[0]<=0:
			return None
		else:
			return [index[0]-1,0]
 
	def getLineCount(self):
		self.updateBuffer()
		return len(self.lines)

	def getLineLength(self,index=None):
		self.updateBuffer()
		if index is None:
			index=getCaretIndex()
		return len(self.lines[index[0]])

	def getLineNumber(self,index=None):
		if index is None:
			index=self.getCaretIndex()
		if index is None:
			debug.writeError("window.getLineNumber: failed to get index")
			return None
		return index[0]

	def getLine(self,index=None):
		self.updateBuffer()
		if index is None:
			index=self.getCaretIndex()
		return self.lines[index[0]]

	def getCharacter(self,index=None):
		self.updateBuffer()
		if index is None:
			index=self.getCaretIndex()
		if index[1]>=self.getLineLength(index=index):
			return None
		return self.getLine(index=index)[index[1]]

	def getWord(self,index=None):
		if not index:
			index=self.getCaretIndex()
		end=self.getWordEndIndex(index)
		if not end or (end==index):
			text=self.getCharacter(index=index)
		else:
			text=self.getTextRange(index,end)
		return text



	def getSelection(self):
		return None

	def getText(self):
		text=""
		index=[0,0]
		while index:
			text+="%s "%self.getLine(index=index)
			index=self.getNextLineIndex(index)
		return text

	def getTextRange(self,start,end):
		if start[0]==end[0]:
			if start[1]>end[1]:
				raise TypeError("Start and end indexes are invalid (%s, %s)"%(start,end))
			line=self.getLine(index=start)
			if not line:
				return None
			return line[start[1]:end[1]]
		else:
			if start[0]>end[0]:
				raise TypeError("Start and end indexes are invalid (%s, %s)"%(start,end))
			lines=[]
			for lineNum in range(end[0])[start[1]+1:]:
				lines.append(self.getLine(index=[lineNum,0]))
			lines.insert(0,self.getLine(index=start)[start[1]:])
			lines.append(self.getLine(index=end)[:end[1]])
			text=""
			for line in lines:
				text+="%s "%line
			return text

	def event_foreground(self):
		self.speakObject()

	def event_focusObject(self):
		if self.hasFocus():
			self.speakObject()

	def event_objectValueChange(self):
		audio.speakObjectProperties(value=self.getValue())

	def event_objectStateChange(self):
		states=self.getStates()
		if states is None:
			return None
		states_on=states-(states&self.lastStates)
		audio.speakObjectProperties(stateNames=getStateNames(states_on))
		states_off=self.lastStates-(states&self.lastStates)
		audio.speakObjectProperties(stateNames=getStateNames(states_off,opposite=True))
		self.lastStates=states


class NVDAObject_Edit(NVDAObject):

	def __init__(self,accObject):
		NVDAObject.__init__(self,accObject)
		self.keyMap={
			key("ExtendedUp"):self.script_moveByLine,
			key("ExtendedDown"):self.script_moveByLine,
			key("ExtendedLeft"):self.script_moveByCharacter,
			key("ExtendedRight"):self.script_moveByCharacter,
			key("Control+ExtendedLeft"):self.script_moveByWord,
			key("Control+ExtendedRight"):self.script_moveByWord,
			key("Shift+ExtendedRight"):self.script_changeSelection,
			key("Shift+ExtendedLeft"):self.script_changeSelection,
			key("Shift+ExtendedHome"):self.script_changeSelection,
			key("Shift+ExtendedEnd"):self.script_changeSelection,
			key("Shift+ExtendedUp"):self.script_changeSelection,
			key("Shift+ExtendedDown"):self.script_changeSelection,
			key("Control+Shift+ExtendedLeft"):self.script_changeSelection,
			key("Control+Shift+ExtendedRight"):self.script_changeSelection,
			key("ExtendedHome"):self.script_moveByCharacter,
			key("ExtendedEnd"):self.script_moveByCharacter,
			key("ExtendedDelete"):self.script_delete,
			key("Back"):self.script_backspace,
		}

	def getCaretIndecies(self):
		word=win32gui.SendMessage(self.getWindowHandle(),win32con.EM_GETSEL,0,0)
		if word<0:
			debug.writeError("window.getCaretIndex: got invalid selection word from window")
			return None
		curPos=win32api.LOWORD(word)
		lineNum=win32gui.SendMessage(self.getWindowHandle(),win32con.EM_LINEFROMCHAR,curPos,0)
		linePos=win32gui.SendMessage(self.getWindowHandle(),win32con.EM_LINEINDEX,lineNum,0)
		startIndex=(lineNum,curPos-linePos)
		curPos=win32api.HIWORD(word)
		lineNum=win32gui.SendMessage(self.getWindowHandle(),win32con.EM_LINEFROMCHAR,curPos,0)
		linePos=win32gui.SendMessage(self.getWindowHandle(),win32con.EM_LINEINDEX,lineNum,0)
		endIndex=(lineNum,curPos-linePos)
		point=(startIndex,endIndex)
		return point

	def getCaretIndex(self):
		point=self.getCaretIndecies()
		return point[1]

	def getLineCount(self):
		lineCount=win32gui.SendMessage(self.getWindowHandle(),win32con.EM_GETLINECOUNT,0,0)
		if lineCount<0:
			debug.writeError("window.getLineCount: failed to get line count")
			return None
		return lineCount


	def getLineLength(self,index=None):
		if index is None:
			index=self.getCaretIndex()
		lineLength=win32gui.SendMessage(self.getWindowHandle(),win32con.EM_LINELENGTH,win32gui.SendMessage(self.getWindowHandle(),win32con.EM_LINEINDEX,index[0],0),0)
		if lineLength<0:
			debug.writeError("window.getLineLength: line length invalid or negative (line number %d, line position %d"%(lineNum,curPos))
			return None
		return lineLength

	def getLine(self,index=None):
		if index is None:
			index=self.getCaretIndex()
		lineNum=index[0]
		lineLength=self.getLineLength(index=index)
		if lineLength is None:
			debug.writeError("window.getLine: line length is not valid")
			return None
		if lineLength==0:
			return None
		lineBuf=struct.pack('i',lineLength+1)
		lineBuf=lineBuf+"".ljust(lineLength-2)
		res=win32gui.SendMessage(self.getWindowHandle(),win32con.EM_GETLINE,lineNum,lineBuf)
		line="%s"%lineBuf[0:lineLength]
		return line

	def getSelection(self,indecies=None):
		if indecies is None:
			indecies=self.getCaretIndecies()
		if indecies is None:
			debug.writeError("window.getCharacter: failed to get index")
			return None
		if indecies[0]==indecies[1]:
			debug.writeError("window.getSelection: no selection")
			return None
		selection=self.getTextRange(indecies[0],indecies[1])
		if selection is None:
			return None
		return selection

	def script_moveByLine(self,keyPress):
		keyEventHandler.sendKey(keyPress)
		audio.speakText(self.getLine())

	def script_moveByCharacter(self,keyPress):
		keyEventHandler.sendKey(keyPress)
		audio.speakSymbol(self.getCharacter())

	def script_moveByWord(self,keyPress):
		keyEventHandler.sendKey(keyPress)
		audio.speakText(self.getWord())

	def script_changeSelection(self,keyPress):
		selectionPoints=self.getCaretIndecies()
		if selectionPoints[0]==selectionPoints[1]:
			selectionPoints=None
		keyEventHandler.sendKey(keyPress)
		newSelectionPoints=self.getCaretIndecies()
		if newSelectionPoints[0]==newSelectionPoints[1]:
			newSelectionPoints=None
		if newSelectionPoints and not selectionPoints:
			audio.speakText("selected %s"%self.getTextRange(newSelectionPoints[0],newSelectionPoints[1]))
		elif not newSelectionPoints:
			audio.speakSymbol(self.getCharacter())
		elif selectionPoints and newSelectionPoints: 
			if newSelectionPoints[1]>selectionPoints[1]:
				audio.speakText("selected %s"%self.getTextRange(selectionPoints[1],newSelectionPoints[1]))
			elif newSelectionPoints[0]>selectionPoints[0]:
				audio.speakText("unselected %s"%self.getTextRange(selectionPoints[0],newSelectionPoints[0]))
			elif newSelectionPoints[1]<selectionPoints[1]:
				audio.speakText("unselected %s"%self.getTextRange(newSelectionPoints[1],selectionPoints[1]))
			elif newSelectionPoints[0]<selectionPoints[0]:
				audio.speakText("selected %s"%self.getTextRange(newSelectionPoints[0],selectionPoints[0]))

	def script_delete(self,keyPress):
		keyEventHandler.sendKey(keyPress)
		sayCharacter()

	def script_backspace(self,keyPress):
		point=self.getCaretIndex()
		if not point==[0,0]: 
			delChar=self.getCharacter(index=self.getPreviousCharacterIndex(point))
			keyEventHandler.sendKey(keyPress)
			newPoint=self.getCaretIndex()
			if newPoint<point:
				audio.speakSymbol(delChar)
		else:
			keyEventHandler.sendKey(keyPress)

	def event_objectValueChange(self):
		audio.speakMessage("edit")

class NVDAObject_checkBox(NVDAObject):

	def getStates(self):
		states=NVDAObject.getStates(self)
		states-=states&pyAA.Constants.STATE_SYSTEM_PRESSED
		return states

class NVDAObject_mozillaDocument(NVDAObject):

	def event_focusObject(self):
		audio.cancel()
		audio.speakText(self.getText())

class NVDAObject_mozillaLink(NVDAObject):

	def getValue(self):
		return ""

	def getStates(self):
		states=NVDAObject.getStates(self)
		states-=(states&pyAA.Constants.STATE_SYSTEM_LINKED)
		return states

	def getChildren(self):
		children=NVDAObject.getChildren(self)
		if (len(children)==1) and (children[0].getRole()==pyAA.Constants.ROLE_SYSTEM_TEXT):
			return []
		return children

class NVDAObject_mozillaListItem(NVDAObject):

	def getBufferText(self):
		lines=[]
		for child in self.getChildren():
			lines+=child.getBufferText()
		if len(lines)==0:
			lines.append(" ")
		lines[0]="%s %s"%(self.getName(),lines[0])
		return lines

	def getName(self):
		child=self.getFirstChild()
		if child and child.getRole()==ROLE_SYSTEM_STATICTEXT:
			name=child.getName()
		return name

	def getChildren(self):
		children=NVDAObject.getChildren(self)
		if (len(children)>=1) and (children[0].getRole()==ROLE_SYSTEM_STATICTEXT):
			del children[0]
		return children

 
classMap={
"Edit":NVDAObject_Edit,
"RICHEDIT50W":NVDAObject_Edit,
"Button_44":NVDAObject_checkBox,
"MozillaContentWindowClass_15":NVDAObject_mozillaDocument,
"MozillaContentWindowClass_30":NVDAObject_mozillaLink,
"MozillaWindowClass_30":NVDAObject_mozillaLink,
"MozillaContentWindowClass_34":NVDAObject_mozillaListItem,
"MozillaWindowClass_34":NVDAObject_mozillaListItem,
}
