"""Manages NVDA configuration.
@var configFileName: file where the configuration should be read from, and written to
@type configFileName: string
@var confspec: a template that defines all the sections and values for the configuration.
@type confspec: string
""" 
# NVDA Configuration Support

configFileName = "nvda.ini"

import os
from StringIO import StringIO
from configobj import ConfigObj
from validate import Validator
val = Validator()

### The configuration specification
confspec = StringIO("""# NVDA Configuration File

#Language settings
[language]
	language = string(default="enu")

# Speech settings
[speech]
	# The synthesiser to use
	synth = string(default=auto)

	[[__many__]]
		rate = integer(default=60)
		pitch = integer(default=50)
		volume = integer(default=100)
		voice = integer(default=1)
		speakPunctuation = boolean(default=False)
		relativeUppercasePitch = integer(default=20)

# Presentation settings
[presentation]
		reportClassOfClientObjects = boolean(default=false)
		reportKeyboardShortcuts = boolean(default=true)
		reportTooltips = boolean(default=true)
		reportHelpBalloons = boolean(default=true)
		reportObjectGroupNames = boolean(default=True)
		sayStateFirst = boolean(default=False)
		beepOnProgressBarUpdates = boolean(default=true)

[mouse]
	reportObjectUnderMouse = boolean(default=true)

#Keyboard settings
[keyboard]
	speakTypedCharacters = boolean(default=true)
	speakTypedWords = boolean(default=false)
	speakCommandKeys = boolean(default=false)

[virtualBuffers]
	maxLineLength = integer(default=100)
	linesPerPage = integer(default=25)
	ignoreUnlinkedImagesWithNoAltAttribute = boolean(default=true)
	reportHeadings = boolean(default=true)
	reportLinks = boolean(default=true)
	reportDataTables = boolean(default=true)
	reportStructureTables = boolean(default=false)
	reportBlockQuotes = boolean(default=true)

#Settings for document reading (such as MS Word and wordpad)
[documentFormatting]
	#These settings affect what information is reported when you navigate to text where the formatting  or placement has changed
	reportFontName = boolean(default=false)
	reportFontSize = boolean(default=false)
	reportFontAttributes = boolean(default=false)
	reportStyle = boolean(default=false)
	reportPage = boolean(default=true)
	reportTables = boolean(default=true)
	reportAlignment = boolean(default=false)

""".replace("\n", "\r\n"))

### Globals
conf = None
mtime = 0

def load():
	"""Loads the configuration from the configFile. It also takes note of the file's modification time so that L{save} won't loose any changes made to the file while NVDA is running. 
"""
	global conf, mtime
	# If the config file exists, store its mtime.
	if os.path.isfile(configFileName):
		mtime = os.path.getmtime(configFileName)
	conf = ConfigObj(configFileName, configspec = confspec, indent_type = "\t")
	# Python converts \r\n to \n when reading files in Windows, so ConfigObj can't determine the true line ending.
	conf.newlines = "\r\n"
	conf.validate(val)

def updateSynthConfig(name):
	"""Makes sure that the config contains a specific synth section for the given synth name.
@param name: the synth name
@type name: string
""" 
	"Validate the configuration for the selected synth."
	speech = conf["speech"]
	# If there are no settings for this synth, make sure there are defaults.
	if not speech.has_key(name):
		speech[name] = {}
		conf.validate(val, copy = True, section = speech)

def save(force = False):
	"""Saves the configuration to the config file. However it does not if the file's modification time has changed and L{force} is not true.
@param force: if true then the modification time of the file will be ignored.
@type force: boolean
"""
	global conf, mtime
	# If the file has changed since it was read, don't save over the top of it.
	if not force and os.path.isfile(configFileName) and os.path.getmtime(configFileName) != mtime:
		return
	# Copy default settings and formatting.
	conf.validate(val, copy = True)
	conf.write()
	mtime = os.path.getmtime(configFileName)

### Main
load()
