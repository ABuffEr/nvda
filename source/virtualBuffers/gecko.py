import time
import ctypes
import comtypesClient
import comtypes.automation
import debug
import winUser
import MSAAHandler
import audio
import api
import NVDAObjects
from baseType import *

NAVRELATION_EMBEDS=0x1009 

class virtualBuffer_gecko(virtualBuffer):

	def __init__(self,NVDAObject):
		virtualBuffer.__init__(self,NVDAObject)
		#(pacc,child)=MSAAHandler.accessibleObjectFromEvent(self.NVDAObject.windowHandle,0,0)
		#(pacc,child)=MSAAHandler.accNavigate(pacc,child,NAVRELATION_EMBEDS)
		#self.NVDAObject=NVDAObjects.MSAA.NVDAObject_MSAA(pacc,child)
		audio.speakMessage("gecko virtualBuffer %s %s"%(self.NVDAObject.name,self.NVDAObject.typeString))
		if self.isDocumentComplete():
			self.loadDocument()

	def event_MSAA_gainFocus(self,hwnd,objectID,childID):
		obj=NVDAObjects.MSAA.getNVDAObjectFromEvent(hwnd,objectID,childID)
		if not obj:
			return False
		role=obj.role
		states=obj.states
		if (role==MSAAHandler.ROLE_SYSTEM_DOCUMENT) and (states&MSAAHandler.STATE_SYSTEM_READONLY):
			if (states&MSAAHandler.STATE_SYSTEM_BUSY):
				audio.speakMessage(MSAAHandler.getStateName(MSAAHandler.STATE_SYSTEM_BUSY))
			elif self.getNVDAObjectID(obj)!=self.getNVDAObjectID(self.NVDAObject): 
				self.NVDAObject=obj
				self.loadDocument()
			return True
		if (role not in [MSAAHandler.ROLE_SYSTEM_TEXT,MSAAHandler.ROLE_SYSTEM_CHECKBUTTON,MSAAHandler.ROLE_SYSTEM_RADIOBUTTON,MSAAHandler.ROLE_SYSTEM_COMBOBOX,MSAAHandler.ROLE_SYSTEM_PUSHBUTTON]) and api.isVirtualBufferPassThrough():
  			api.toggleVirtualBufferPassThrough()
		if not self._allowCaretMovement:
			return False
		ID=self.getNVDAObjectID(obj)
		r=self.getRangeFromID(ID)
		if (r is not None) and (len(r)==2) and ((self.caretPosition<r[0]) or (self.caretPosition>=r[1])):
			self.caretPosition=r[0]
			if conf["virtualBuffers"]["reportVirtualPresentationOnFocusChanges"]:
				self.reportCaretIDMessages()
				audio.speakText(self.getTextRange(r[0],r[1]))
				api.setFocusObject(obj)
				api.setNavigatorObject(obj)
				return True
		return False

	def event_MSAA_scrollingStart(self,hwnd,objectID,childID):
		audio.speakMessage("scroll")
		obj=NVDAObjects.MSAA.getNVDAObjectFromEvent(hwnd,objectID,childID)
		if not obj:
			return False
		role=obj.role
		states=obj.states
		if not self._allowCaretMovement:
			return False
		ID=self.getNVDAObjectID(obj)
		audio.speakMessage("ID: %s, obj: %s"%(ID,obj.role))
		r=self.getRangeFromID(ID)
		if (r is not None) and (len(r)==2) and ((self.caretPosition<r[0]) or (self.caretPosition>=r[1])):
			self.caretPosition=r[0]
			self.reportCaretIDMessages()
			audio.speakText(self.getTextRange(r[0],r[1]))

	def event_MSAA_stateChange(self,hwnd,objectID,childID):
		obj=NVDAObjects.MSAA.getNVDAObjectFromEvent(hwnd,objectID,childID)
		role=obj.role
		states=obj.states
		if (role==MSAAHandler.ROLE_SYSTEM_DOCUMENT) and (states&MSAAHandler.STATE_SYSTEM_READONLY):
			if states&MSAAHandler.STATE_SYSTEM_BUSY:
				audio.speakMessage(MSAAHandler.getStateName(MSAAHandler.STATE_SYSTEM_BUSY))
				return True
			elif self.getNVDAObjectID(obj)!=self.getNVDAObjectID(self.NVDAObject):
				self.NVDAObject=obj
				self.loadDocument()
				return True
		return False

	def event_MSAA_valueChange(self,hwnd,objectID,childID):
		audio.speakMessage('value')
		return False

	def activatePosition(self,pos):
		IDs=self.getIDsFromPosition(pos)
		if (IDs is None) or (len(IDs)<1):
			return
		obj=self._IDs[IDs[-1]]["node"]
		if obj is None:
			return
		role=obj.role
		states=obj.states
		nodeInfo=self.getNVDAObjectInfo(obj)
		if role in [MSAAHandler.ROLE_SYSTEM_TEXT,MSAAHandler.ROLE_SYSTEM_COMBOBOX]:
			if not api.isVirtualBufferPassThrough():
				api.toggleVirtualBufferPassThrough()
			obj.setFocus()
		if role in [MSAAHandler.ROLE_SYSTEM_CHECKBUTTON,MSAAHandler.ROLE_SYSTEM_RADIOBUTTON]:
			obj.doDefaultAction()
		elif role==MSAAHandler.ROLE_SYSTEM_PUSHBUTTON:
			obj.doDefaultAction()
		elif role in [MSAAHandler.ROLE_SYSTEM_LINK,MSAAHandler.ROLE_SYSTEM_GRAPHIC]:
			obj.doDefaultAction()
			obj.setFocus()

	def isDocumentComplete(self):
		role=self.NVDAObject.role
		states=self.NVDAObject.states
		if (role==MSAAHandler.ROLE_SYSTEM_DOCUMENT) and not (states&MSAAHandler.STATE_SYSTEM_BUSY) and (states&MSAAHandler.STATE_SYSTEM_READONLY):
			return True
		else:
			return False

	def loadDocument(self):
		if winUser.getAncestor(self.NVDAObject.windowHandle,winUser.GA_ROOT)==winUser.getForegroundWindow():
			audio.cancel()
			if api.isVirtualBufferPassThrough():
				api.toggleVirtualBufferPassThrough()
			audio.speakMessage(_("loading document %s")%self.NVDAObject.name+"...")
		self.resetBuffer()
		self.fillBuffer(self.NVDAObject)
		self.caretPosition=0
		if winUser.getAncestor(self.NVDAObject.windowHandle,winUser.GA_ROOT)==winUser.getForegroundWindow():
			audio.cancel()
			self.caretPosition=0
			self._allowCaretMovement=False #sayAllGenerator will set this back to true when done
			time.sleep(0.01)
			audio.speakMessage(_("done"))
			core.newThread(self.sayAllGenerator())

	def fillBuffer(self,obj,IDAncestors=(),position=None):
		debug.writeMessage("virtualBuffers.gecko.fillBuffer: %s %s %s %s with %s children"%(obj.name,MSAAHandler.getRoleName(obj.role),obj.value,obj.description,obj.childCount))
		info=self.getNVDAObjectInfo(obj)
		ID=self.getNVDAObjectID(obj)
		if ID and ID not in IDAncestors:
			IDAncestors=tuple(list(IDAncestors)+[ID])
		if ID and not self._IDs.has_key(ID):
			self.addID(ID,**info)
		text=self.getNVDAObjectText(obj)
		if text:
			position=self.addText(IDAncestors,text,position=position)
		#We don't want to render objects inside comboboxes
		if obj.role==MSAAHandler.ROLE_SYSTEM_COMBOBOX:
			return position
		#For everything else we keep walking the tree
		else:
			for child in obj.children:
				position=self.fillBuffer(child,IDAncestors,position=position)
			if obj.role==MSAAHandler.ROLE_SYSTEM_DOCUMENT:
				position=self.addText(IDAncestors," ",position)
			return position

	def getNVDAObjectID(self,obj):
		if obj.role!=MSAAHandler.ROLE_SYSTEM_STATICTEXT:
			return ctypes.cast(obj._pacc,ctypes.c_void_p).value

	def getNVDAObjectText(self,obj):
		role=obj.role
		states=obj.states
		if role==MSAAHandler.ROLE_SYSTEM_STATICTEXT:
			data=obj.value
			if data and not data.isspace():
				return "%s "%data
		if role==MSAAHandler.ROLE_SYSTEM_DOCUMENT:
			return "%s\n "%obj.name
		elif role==MSAAHandler.ROLE_SYSTEM_GRAPHIC:
			return obj.name+" " 
		elif role==MSAAHandler.ROLE_SYSTEM_COMBOBOX:
			return obj.value+" "
		elif role==MSAAHandler.ROLE_SYSTEM_CHECKBUTTON:
			return obj.name+" "
		elif role==MSAAHandler.ROLE_SYSTEM_RADIOBUTTON:
			return obj.name+" "
		elif role==MSAAHandler.ROLE_SYSTEM_TEXT:
			return obj.value+"\0"
		elif role==MSAAHandler.ROLE_SYSTEM_PUSHBUTTON:
			return obj.name+" "
		elif role=="white space":
			return obj.name.replace('\r\n','\n')

	def getNVDAObjectInfo(self,obj):
		info=fieldInfo.copy()
		info["node"]=obj
		role=obj.role
		states=obj.states
		if role=="frame":
			info["fieldType"]=fieldType_frame
			info["typeString"]=fieldNames[fieldType_frame]
		if role=="iframe":
			info["fieldType"]=fieldType_frame
			info["typeString"]=fieldNames[fieldType_frame]
		elif role==MSAAHandler.ROLE_SYSTEM_DOCUMENT:
			info["fieldType"]=fieldType_document
			info["typeString"]=fieldNames[fieldType_document]
		elif role==MSAAHandler.ROLE_SYSTEM_LINK:
			info["fieldType"]=fieldType_link
			info["typeString"]=obj.typeString
		elif role=="p":
			info["fieldType"]=fieldType_paragraph
			info["typeString"]=fieldNames[fieldType_paragraph]
		elif role==MSAAHandler.ROLE_SYSTEM_CELL:
			info["fieldType"]=fieldType_cell
			info["typeString"]=fieldNames[fieldType_cell]
		elif role==MSAAHandler.ROLE_SYSTEM_TABLE:
			info["fieldType"]=fieldType_table
			info["typeString"]=fieldNames[fieldType_table]
		elif role==MSAAHandler.ROLE_SYSTEM_ROW:
			info["fieldType"]=fieldType_row
			info["typeString"]=fieldNames[fieldType_row]
		elif role=="thead":
			info["fieldType"]=fieldType_tableHeader
			info["typeString"]=fieldNames[fieldType_tableHeader]
		elif role=="tfoot":
			info["fieldType"]=fieldType_tableFooter
			info["typeString"]=fieldNames[fieldType_tableFooter]
		elif role=="tbody":
			info["fieldType"]=fieldType_tableBody
			info["typeString"]=fieldNames[fieldType_tableBody]
		elif role==MSAAHandler.ROLE_SYSTEM_LIST:
			info["fieldType"]=fieldType_list
			info["typeString"]=fieldNames[fieldType_list]
			info["descriptionFunc"]=lambda x: "with %s items"%x.childCount
		elif role==MSAAHandler.ROLE_SYSTEM_LISTITEM:
			info["fieldType"]=fieldType_listItem
			bullet=obj.name.rstrip()
			if not bullet:
				bullet=_("bullet")
			elif bullet.endswith('.'):
				bullet=bullet[0:-1]
			info["typeString"]=bullet
		elif role=="dl":
			info["fieldType"]=fieldType_list
			info["typeString"]=_("definition")+" "+fieldNames[fieldType_list]
			info["descriptionFunc"]=lambda x: _("with %s items")%x.childCount
		elif role=="dt":
			info["fieldType"]=fieldType_listItem
			bullet=obj.name.rstrip()
			if not bullet:
				bullet=_("bullet")
			elif bullet.endswith('.'):
				bullet=bullet[0:-1]
			info["typeString"]=bullet
		elif role=="dd":
			info["fieldType"]=fieldType_listItem
			info["typeString"]=_("definition")
		elif role==MSAAHandler.ROLE_SYSTEM_GRAPHIC:
			info["fieldType"]=fieldType_graphic
			info["typeString"]=fieldNames[fieldType_graphic]
		elif role in ["h1","h2","h3","h4","h5","h6"]:
			info["fieldType"]=fieldType_heading
			info["typeString"]=fieldNames[fieldType_heading]+" %s"%role[1]
		elif role=="blockquote":
			info["fieldType"]=fieldType_blockQuote
			info["typeString"]=fieldNames[fieldType_blockQuote]
		elif role=="q":
			info["fieldType"]=fieldType_blockQuote
			info["typeString"]=fieldNames[fieldType_blockQuote]
		elif role==MSAAHandler.ROLE_SYSTEM_PUSHBUTTON:
			info["fieldType"]=fieldType_button
			info["typeString"]=fieldNames[fieldType_button]
		elif role=="form":
			info["fieldType"]=fieldType_form
			info["typeString"]=fieldNames[fieldType_form]
		elif role==MSAAHandler.ROLE_SYSTEM_RADIOBUTTON:
			info["fieldType"]=fieldType_radioButton
			info["typeString"]=fieldNames[fieldType_radioButton]
			info["stateTextFunc"]=lambda x: MSAAHandler.getStateName(MSAAHandler.STATE_SYSTEM_CHECKED) if x.states&MSAAHandler.STATE_SYSTEM_CHECKED else _("not %s")%MSAAHandler.getStateName(MSAAHandler.STATE_SYSTEM_CHECKED)
		elif role==MSAAHandler.ROLE_SYSTEM_CHECKBUTTON:
			info["fieldType"]=fieldType_checkBox
			info["typeString"]=fieldNames[fieldType_checkBox]
			info["stateTextFunc"]=lambda x: MSAAHandler.getStateName(MSAAHandler.STATE_SYSTEM_CHECKED) if x.states&MSAAHandler.STATE_SYSTEM_CHECKED else _("not %s")%MSAAHandler.getStateName(MSAAHandler.STATE_SYSTEM_CHECKED)
		elif role==MSAAHandler.ROLE_SYSTEM_TEXT:
			info["fieldType"]=fieldType_edit
			info["typeString"]=fieldNames[fieldType_edit]
		elif role==MSAAHandler.ROLE_SYSTEM_COMBOBOX:
			info["fieldType"]=fieldType_comboBox
			info["typeString"]=fieldNames[fieldType_comboBox]
		else:
			info["typeString"]=MSAAHandler.getRoleName(role) if isinstance(role,int) else role
		accessKey=obj.keyboardShortcut
		if accessKey:
			info["accessKey"]=accessKey
		return info
 
