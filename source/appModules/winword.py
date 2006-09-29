import comtypes.client
import comtypes.automation
import ctypes
from default import *
import audio
from keyEventHandler import sendKey

#Word constants

#Indexing
wdActiveEndPageNumber=3
wdNumberOfPagesInDocument=4
wdFirstCharacterLineNumber=10
wdWithInTable=12
wdStartOfRangeRowNumber=13
wdMaximumNumberOfRows=15
wdStartOfRangeColumnNumber=16
wdMaximumNumberOfColumns=18
#Units
wdCharacter=1
wdWord=2
wdLine=5
wdStory=6
wdColumn=9
wdRow=10
wdWindow=11
wdCell=12
wdTable=15
#GoTo - direction
wdGoToAbsolute=1
wdGoToRelative=2
wdGoToNext=2
#GoTo - units
wdGoToPage=1
wdGoToLine=3

def event_moduleStart():
	NVDAObjects.registerNVDAObjectClass("_WwG",ROLE_SYSTEM_CLIENT,NVDAObject_wordDocument)

def event_moduleEnd():
	NVDAObjects.unregisterNVDAObjectClass("_WwG",ROLE_SYSTEM_CLIENT)

class NVDAObject_wordDocument(NVDAObjects.NVDAObject_edit):

	def __init__(self,accObject):
		NVDAObjects.NVDAObject_edit.__init__(self,accObject)
		ptr=ctypes.c_void_p()
		ctypes.windll.oleacc.AccessibleObjectFromWindow(self.getWindowHandle(),-16,ctypes.byref(comtypes.automation.IUnknown._iid_),ctypes.byref(ptr))
		ptr=ctypes.cast(ptr,ctypes.POINTER(comtypes.automation.IUnknown))
		self.documentWindow=comtypes.client.wrap(ptr).ActivePane
		self.lastStyle=self.lastFontName=self.lastFontSize=self.lastIsTable=self.lastRowNumber=self.lastColumnNumber=self.lastPageNumber=None
		self.keyMap.update({
key("insert+f"):self.script_formatInfo,
})

	def getRole(self):
		return ROLE_SYSTEM_TEXT

	def getCaretRange(self):
		start=self.documentWindow.Selection.Start
		end=self.documentWindow.Selection.End
		if start!=end:
			return (start,end)
		else:
			return None

	def getCaretPosition(self):
		return self.documentWindow.Selection.Start

	def getVisibleLineRange(self):
		range=self.documentWindow.Selection.Range
		range.Expand(wdWindow)
		return (self.getLineNumber(range.Start),self.getLineNumber(range.End))

	def getStartPosition(self):
		return 0

	def getEndPosition(self):
		range=self.documentWindow.Selection.Range
		range.Expand(wdStory)
		return range.End

	def getLineNumber(self,pos):
		range=self.documentWindow.Selection.Range
		range.Start=range.End=pos
		return range.Information(wdFirstCharacterLineNumber)-1

	def getCurrentLineNumber(self):
		return self.getLineNumber(self.getCaretPosition())

	def getLine(self,pos):
		saveSelection=self.documentWindow.Selection
		range=self.documentWindow.Selection
		range.Start=range.End=pos
		range.Expand(wdLine)
		text=range.Text
		self.documentWindow.Selection.Start=saveSelection.Start
		self.documentWindow.Selection.End=saveSelection.End
		if text!='\r':
			return text
		else:
			return None

	def getCurrentLine(self):
		return self.getLine(self.getCaretPosition())

	def nextWord(self,pos):
		range=self.documentWindow.Selection.Range
		range.Start=range.End=pos
		delta=range.Move(wdWord,1)
		if delta:
			return range.Start
		else:
			return None

	def previousWord(self,pos):
		range=self.documentWindow.Selection.Range
		range.Start=range.End=pos
		delta=range.Move(wdWord,-1)
		if delta:
			return range.Start
		else:
			return None

	def getTextRange(self,start,end):
		range=self.documentWindow.Selection.Range
		range.Start=start
		range.End=end
		return range.Text

	def getFontName(self,pos):
		range=self.documentWindow.Selection.Range
		range.Start=range.End=pos
		return range.Font.Name

	def getCurrentFontName(self):
		return self.getFontName(self.getCaretPosition())

	def getFontSize(self,pos):
		range=self.documentWindow.Selection.Range
		range.Start=range.End=pos
		return "%d"%range.Font.Size

	def getCurrentFontSize(self):
		return self.getFontSize(self.getCaretPosition())

	def getStyle(self,pos):
		range=self.documentWindow.Selection.Range
		range.Start=range.End=pos
		return range.Style.NameLocal

	def getCurrentStyle(self):
		return self.getStyle(self.getCaretPosition())

	def isTable(self,pos):
		range=self.documentWindow.Selection.Range
		range.Start=range.End=pos
		return range.Information(wdWithInTable)

	def isCurrentTable(self):
		return self.isTable(self.getCaretPosition())

	def getRowNumber(self,pos):
		range=self.documentWindow.Selection.Range
		range.Start=range.End=pos
		return range.Information(wdStartOfRangeRowNumber)

	def getCurrentRowNumber(self):
		return self.getRowNumber(self.getCaretPosition())

	def getRowCount(self,pos):
		range=self.documentWindow.Selection.Range
		range.Start=range.End=pos
		return range.Information(wdMaximumNumberOfRows)

	def getCurrentRowCount(self):
		return self.getRowCount(self.getCaretPosition())

	def getColumnNumber(self,pos):
		range=self.documentWindow.Selection.Range
		range.Start=range.End=pos
		return range.Information(wdStartOfRangeColumnNumber)

	def getCurrentColumnNumber(self):
		return self.getColumnNumber(self.getCaretPosition())

	def getColumnCount(self,pos):
		range=self.documentWindow.Selection.Range
		range.Start=range.End=pos
		return range.Information(wdMaximumNumberOfColumns)

	def getCurrentColumnCount(self):
		return self.getColumnCount(self.getCaretPosition())

	def getPageNumber(self,pos):
		range=self.documentWindow.Selection.Range
		range.Start=range.End=pos
		return range.Information(wdActiveEndPageNumber)

	def getCurrentPageNumber(self):
		return self.getPageNumber(self.getCaretPosition())

	def getPageCount(self):
		return self.documentWindow.Selection.Information(wdNumberOfPagesInDocument)

	def reportChanges(self):
		pageNumber=self.getCurrentPageNumber()
		if pageNumber!=self.lastPageNumber:
			audio.speakMessage("Page %d of %d"%(pageNumber,self.getPageCount()))
			self.lastPageNumber=pageNumber
		isTable=self.isCurrentTable()
		if isTable!=self.lastIsTable:
			if isTable:
				audio.speakMessage("Table with %d columns and %d rows"%(self.getCurrentColumnCount(),self.getCurrentRowCount()))
			elif self.lastIsTable: 
				audio.speakMessage("out of table")
				self.lastRowNumber=self.lastColumnNumber=None
			self.lastIsTable=isTable
		rowNumber=self.getCurrentRowNumber()
		columnNumber=self.getCurrentColumnNumber()
		if self.isCurrentTable() and ((rowNumber!=self.lastRowNumber) or (columnNumber!=self.lastColumnNumber)):
			audio.speakMessage("col %d row %d"%(columnNumber,rowNumber))
			self.lastRowNumber=rowNumber
			self.lastColumnNumber=columnNumber
		style=self.getCurrentStyle()
		if style!=self.lastStyle:
			audio.speakMessage("%s style"%style)
			self.lastStyle=style
		fontName=self.getCurrentFontName()
		if fontName!=self.lastFontName:
			audio.speakMessage("%s font"%fontName)
			self.lastFontName=fontName
		fontSize=self.getCurrentFontSize()
		if fontSize!=self.lastFontSize:
			audio.speakMessage("%s point"%fontSize)
			self.lastFontSize=fontSize

	def script_moveByLine(self,keyPress):
		sendKey(keyPress)
		self.reportChanges()
		audio.speakText(self.getCurrentLine())

	def script_moveByCharacter(self,keyPress):
		sendKey(keyPress)
		self.reportChanges()
		audio.speakSymbol(self.getCurrentCharacter())

	def script_moveByWord(self,keyPress):
		sendKey(keyPress)
		self.reportChanges()
		audio.speakText(self.getCurrentWord())

	def script_delete(self,keyPress):
		sendKey(keyPress)
		self.reportChanges()
		audio.speakSymbol(self.getCurrentCharacter())

	def script_formatInfo(self,keyPress):
		audio.speakMessage("%s: %s, %s point"%(self.getCurrentStyle(),self.getCurrentFontName(),self.getCurrentFontSize()))
