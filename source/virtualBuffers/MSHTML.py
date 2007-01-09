import time
import ctypes
import comtypesClient
import comtypes.automation
import core
import IAccessibleHandler
import debug
import winUser
import api
import audio
import config
import NVDAObjects
from baseType import *

class virtualBuffer_MSHTML(virtualBuffer):

	class domEventsType(object):

		def __init__(self,virtualBufferObject):
			self.virtualBufferObject=virtualBufferObject

		def ondeactivate(self,arg,event):
			try:
				domNode=event.srcElement
				if domNode.nodeName not in ["INPUT","SELECT","TEXTAREA"]:
					return
				ID=self.virtualBufferObject.getDomNodeID(domNode)
				if not self.virtualBufferObject._IDs.has_key(ID):
					return
				parentID=self.virtualBufferObject._IDs[ID]['parent']
				(start,end)=self.virtualBufferObject.getFullRangeFromID(ID)
				self.virtualBufferObject.removeID(ID)
				self.virtualBufferObject.fillBuffer(domNode,parentID,position=start)
			except:
				debug.writeException("onchange")

		def onreadystatechange(self,arg,event):
			if self.virtualBufferObject.isDocumentComplete():
				self.virtualBufferObject.loadDocument()

	def __init__(self,NVDAObject):
		#We sometimes need to cast com interfaces to another type so we need access directly to the MSHTML typelib
		self.MSHTMLLib=comtypesClient.GetModule('mshtml.tlb')
		#Create a html document com pointer and point it to the com object we receive from the internet explorer_server window
		#domPointer=ctypes.POINTER(self.MSHTMLLib.DispHTMLDocument)()
		domPointer=ctypes.POINTER(comtypes.automation.IDispatch)()
		wm=winUser.registerWindowMessage(u'WM_HTML_GETOBJECT')
		lresult=winUser.sendMessage(NVDAObject.windowHandle,wm,0,0)
		ctypes.windll.oleacc.ObjectFromLresult(lresult,ctypes.byref(domPointer._iid_),0,ctypes.byref(domPointer))
		self.dom=comtypesClient.wrap(domPointer)
		virtualBuffer.__init__(self,NVDAObject)
		#Set up events for the document, plus any sub frames
		self.domEventsObject=self.domEventsType(self)
		comtypesClient.GetEvents(self.dom,self.domEventsObject,interface=self.MSHTMLLib.HTMLDocumentEvents2)
		if self.isDocumentComplete():
			self.loadDocument()

	def event_IAccessible_gainFocus(self,hwnd,objectID,childID):
		try:
			nodeName=self.dom.activeElement.nodeName
		except:
			return False
		if (self.dom.body.isContentEditable is False) and (nodeName not in ["INPUT","SELECT","TEXTAREA"]) and api.isVirtualBufferPassThrough():
			api.toggleVirtualBufferPassThrough()
		if not self._allowCaretMovement:
			return False
		domNode=self.dom.activeElement
		ID=self.getDomNodeID(domNode)
		r=self.getFullRangeFromID(ID)
		if ((self.caretPosition<r[0]) or (self.caretPosition>=r[1])):
			self.caretPosition=r[0]
			obj=NVDAObjects.IAccessible.getNVDAObjectFromEvent(hwnd,objectID,childID)
			if obj and config.conf["virtualBuffers"]["reportVirtualPresentationOnFocusChanges"]:
				self.reportCaretIDMessages()
				audio.speakText(self.getTextRange(r[0],r[1]))
				api.setFocusObject(obj)
				api.setNavigatorObject(obj)
				return True
		return False

	def activatePosition(self,pos):
		ID=self.getIDFromPosition(pos)
		if ID is None:
			return
		domNode=self._IDs[ID]["node"]
		if domNode is None:
			return
		nodeName=domNode.nodeName
		if nodeName in ["SELECT","TEXTAREA"]:
			if not api.isVirtualBufferPassThrough():
				api.toggleVirtualBufferPassThrough()
			domNode.focus()
		elif nodeName =="INPUT":
			inputType=domNode.getAttribute('type')
			if inputType in ["checkbox","radio"]:
				domNode.click()
				audio.speakMessage("%s"%(IAccessibleHandler.getStateName(IAccessibleHandler.STATE_SYSTEM_CHECKED) if domNode.checked else _("not %s")%IAccessibleHandler.getStateName(IAccessibleHandler.STATE_SYSTEM_CHECKED)))
			elif inputType in ["file","text","password"]:
				if not api.isVirtualBufferPassThrough() and not ((nodeName=="INPUT") and (domNode.getAttribute('type') in["checkbox","radio"])): 
					api.toggleVirtualBufferPassThrough()
				domNode.focus()
			elif inputType in ["button","image","reset","submit"]:
				domNode.click()
		elif (nodeName in ["A","IMG"]) or domNode.onclick:
			domNode.click()
			try:
				domNode.focus()
			except:
				pass

	def loadDocument(self):
		if self.dom.body.isContentEditable is True: #This is an editable document and will not be managed by this virtualBuffer
			return
		if winUser.getAncestor(self.NVDAObject.windowHandle,winUser.GA_ROOT)==winUser.getForegroundWindow():
			audio.cancel()
			if api.isVirtualBufferPassThrough():
				api.toggleVirtualBufferPassThrough()
			audio.speakMessage(_("loading document %s")%self.dom.title+"...")
		self.resetBuffer()
		self.fillBuffer(self.dom)
		self.caretPosition=0
		if winUser.getAncestor(self.NVDAObject.windowHandle,winUser.GA_ROOT)==winUser.getForegroundWindow():
			audio.cancel()
			self.caretPosition=0
			self._allowCaretMovement=False #sayAllGenerator will set this back to true when done
			time.sleep(0.01)
			audio.speakMessage(_("done"))
			core.newThread(self.sayAllGenerator())

	def isDocumentComplete(self):
		documentComplete=True
		if self.dom.readyState!="complete":
			audio.cancel()
			audio.speakMessage(str(self.dom.readyState))
			documentComplete=False
		for frameNum in range(self.dom.frames.length):
			try:
				if self.dom.frames.item(frameNum).document.readyState!="complete":
					audio.cancel()
					audio.speakMessage(str(self.dom.frames.item(frameNum).document.readyState))
					documentComplete=False
			except:
				pass
		return documentComplete

	def fillBuffer(self,domNode,parentID=None,position=None):
		#We don't want comments in the buffer
		if isinstance(domNode,ctypes.POINTER(self.MSHTMLLib.DispHTMLCommentElement)):
			return position
		#We don't want non-displayed elements in the buffer 
		try:
			display=domNode.currentStyle.display
		except:
			display=None
		if display==u'none':
			return position
		#We don't want option elements in the buffer
		if domNode.nodeName=="OPTION":
			return position
		#Register proper events
		if domNode.nodeName=='INPUT' and domNode.getAttribute('type')=="text":
			debug.writeMessage("virtualBuffer.MSHTML.fillBuffer: adding events for text control")
			comtypesClient.GetEvents(domNode,self.domEventsObject,interface=self.MSHTMLLib.HTMLInputTextElementEvents2)
		if position is None:
			position=len(self.text)
		info=self.getDomNodeInfo(domNode)
		ID=self.getDomNodeID(domNode)
		info['parent']=parentID
		info['range']=[position,position]
		children=[]
		if isinstance(domNode,self.MSHTMLLib.DispHTMLFrameElement):
			try:
				children.append(domNode.contentWindow.document)
			except:
				pass
		elif isinstance(domNode,self.MSHTMLLib.DispHTMLDocument):
			try:
				comtypesClient.ReleaseEvents(domNode,self.domEventsObject,interface=self.MSHTMLLib.HTMLDocumentEvents2)
			except:
				pass
			comtypesClient.GetEvents(domNode,self.domEventsObject,interface=self.MSHTMLLib.HTMLDocumentEvents2)
			children.append(domNode.body)
		else:
			child=domNode.firstChild
			while child:
				children.append(child)
				try:
					child=child.nextSibling
				except:
					child=None
		info['children']=filter(lambda x: x,[self.getDomNodeID(x) for x in children])
		if ID and not self._IDs.has_key(ID):
			self.addID(ID,info)
		if not ID:
			ID=parentID
		text=self.getDomNodeText(domNode)
		if text:
			position=self.addText(ID,text,position=position)
		for child in children:
			position=self.fillBuffer(child,ID,position=position)
		return position

	def getDomNodeID(self,domNode):
		#We don't want certain inline nodes like span, font etc to have their own IDs
		while domNode:
			if (domNode.nodeName not in ["B","BR","CENTER","EM","FONT","I","SPAN","STRONG","SUP","U"]) or domNode.onclick:
				break
			domNode=domNode.parentNode
		#document nodes have broken uniqueIDs so we use its html node's uniqueID
		if isinstance(domNode,self.MSHTMLLib.DispHTMLDocument):
			try:
				domNode=domNode.firstChild
			except:
				pass
		#We return the uniqueID for the node if it has one
		try:
			return domNode.uniqueID
		except:
			return None

	def getDomNodeText(self,domNode):
		nodeName=domNode.nodeName
		if nodeName=="#text":
			data=domNode.data
			if data and not data.isspace():
				return data
		elif isinstance(domNode,self.MSHTMLLib.DispHTMLDocument):
			return domNode.title+"\n "
		elif nodeName=="IMG":
			label=domNode.getAttribute('alt')
			if not label:
				label=domNode.getAttribute('title')
			if not label:
				label=domNode.getAttribute('name')
			if not label:
				label=domNode.getAttribute('src').split('/')[-1]
			return label
		elif nodeName=="SELECT":
			itemText=comtypesClient.wrap(domNode.item(domNode.selectedIndex)).text
			return itemText
		elif (nodeName=="TEXTAREA") and (domNode.children.length==0):
			return " "
		elif nodeName=="INPUT":
			inputType=domNode.getAttribute('type')
			if inputType in ["text","file"]:
				return domNode.getAttribute('value')+" "
			if inputType=="password":
				return "*"*len(domNode.getAttribute('value'))+" "
			elif inputType in ["button","image","reset","submit"]:
				return domNode.getAttribute('value')
			elif inputType in ["checkbox","radio"]:
				return " "
		elif (nodeName=="BR") and (domNode.previousSibling and domNode.previousSibling.nodeName=="#text"):
			return "\n"

	def getDomNodeInfo(self,domNode):
		info=fieldInfo.copy()
		info["node"]=domNode
		if not domNode:
			return info
		nodeName=domNode.nodeName
		if isinstance(domNode,self.MSHTMLLib.DispHTMLFrameElement):
			info["fieldType"]=fieldType_frame
			info["typeString"]=fieldNames[fieldType_frame]
		elif isinstance(domNode,self.MSHTMLLib.DispHTMLDocument):
			info["fieldType"]=fieldType_document
			info["typeString"]=fieldNames[fieldType_document]
		elif nodeName=="A":
			info["fieldType"]=fieldType_link
			info["typeString"]=fieldNames[fieldType_link]
		elif nodeName=="TABLE":
			info["fieldType"]=fieldType_table
			info["typeString"]=fieldNames[fieldType_table]
		elif nodeName=="THEAD":
			info["fieldType"]=fieldType_tableHeader
			info["typeString"]=fieldNames[fieldType_tableHeader]
		elif nodeName=="TBODY":
			info["fieldType"]=fieldType_tableBody
			info["typeString"]=fieldNames[fieldType_tableBody]
		elif nodeName=="TFOOT":
			info["fieldType"]=fieldType_tableFooter
			info["typeString"]=fieldNames[fieldType_tableFooter]
		elif nodeName=="TR":
			info["fieldType"]=fieldType_row
			info["typeString"]=fieldNames[fieldType_row]
		elif nodeName=="TD":
			info["fieldType"]=fieldType_cell
			info["typeString"]=fieldNames[fieldType_cell]
		elif nodeName=="P":
			info["fieldType"]=fieldType_paragraph
			info["typeString"]=fieldNames[fieldType_paragraph]
		elif nodeName=="UL":
			info["fieldType"]=fieldType_list
			info["typeString"]=fieldNames[fieldType_list]
			info["descriptionFunc"]=lambda x: _("with %s items")%x.children.length
		elif nodeName=="OL":
			info["fieldType"]=fieldType_list
			info["typeString"]=fieldNames[fieldType_list]
			info["descriptionFunc"]=lambda x: _("with %s items")%x.children.length
		elif nodeName=="LI":
			info["fieldType"]=fieldType_listItem
			info["typeString"]=_("bullet")
		elif nodeName=="DL":
			info["fieldType"]=fieldType_list
			info["typeString"]=_("definition")+" "+fieldNames[fieldType_list]
			info["descriptionFunc"]=lambda x: _("with %s items")%x.children.length
		elif nodeName=="DT":
			info["fieldType"]=fieldType_listItem
			info["typeString"]=_("bullet")
		elif nodeName=="DD":
			info["fieldType"]=fieldType_listItem
			info["typeString"]=_("definition")
		elif nodeName=="TEXTAREA":
			info["fieldType"]=fieldType_editArea
			info["typeString"]=fieldNames[fieldType_editArea]
		elif nodeName=="IMG":
			info["fieldType"]=fieldType_graphic
			info["typeString"]=fieldNames[fieldType_graphic]
		elif nodeName in ["H1","H2","H3","H4","H5","H6"]:
			info["fieldType"]=fieldType_heading
			info["typeString"]=fieldNames[fieldType_heading]+" %s"%nodeName[1]
		elif nodeName=="BLOCKQUOTE":
			info["fieldType"]=fieldType_blockQuote
			info["typeString"]=fieldNames[fieldType_blockQuote]
		elif nodeName=="FORM":
			info["fieldType"]=fieldType_form
			info["typeString"]=fieldNames[fieldType_form]
		elif nodeName=="INPUT":
			inputType=domNode.getAttribute("type")
			if inputType=="text":
				info["fieldType"]=fieldType_edit
				info["typeString"]=fieldNames[fieldType_edit]
			elif inputType=="file":
				info["fieldType"]=fieldType_edit
				info["typeString"]=_("file updload")+" "+fieldNames[fieldType_edit]
			elif inputType=="password":
				info["fieldType"]=fieldType_edit
				info["typeString"]=_("protected")+" "+fieldNames[fieldType_edit]
			elif inputType in ["button","image","reset","submit"]:
				info["fieldType"]=fieldType_button
				info["typeString"]=fieldNames[fieldType_button]
			elif inputType=="radio":
				info["fieldType"]=fieldType_radioButton
				info["typeString"]=fieldNames[fieldType_radioButton]
				info["stateTextFunc"]=lambda x: IAccessibleHandler.getStateName(IAccessibleHandler.STATE_SYSTEM_CHECKED) if x.checked else _("not %s")%IAccessibleHandler.getStateName(IAccessibleHandler.STATE_SYSTEM_CHECKED)
			elif inputType=="checkbox":
				info["fieldType"]=fieldType_checkBox
				info["typeString"]=fieldNames[fieldType_checkBox]
				info["stateTextFunc"]=lambda x: IAccessibleHandler.getStateName(IAccessibleHandler.STATE_SYSTEM_CHECKED) if x.checked else _("not %s")%IAccessibleHandler.getStateName(IAccessibleHandler.STATE_SYSTEM_CHECKED)
		elif nodeName=="SELECT":
			info["fieldType"]=fieldType_comboBox
			info["typeString"]=fieldNames[fieldType_comboBox]
		else:
			info["typeString"]=nodeName
		try:
			accessKey=domNode.accessKey
			if accessKey:
				info["accessKey"]="alt+%s"%accessKey
		except:
			pass
		try:
			if domNode.onclick and (nodeName not in ["INPUT","A"]):
				info["typeString"]=_("clickable")+" "+info["typeString"]
		except:
			pass
		return info
