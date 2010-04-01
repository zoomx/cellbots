# Licensed under the Apache License, Version 2.0 (the "License"); you may not
# use this file except in compliance with the License. You may obtain a copy of
# the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
# WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
# License for the specific language governing permissions and limitations under
# the License.
#
# See http://www.cellbots.com for more information

__author__ = 'Ryan Hickman <rhickman@gmail.com>'
__license__ = 'Apache License, Version 2.0'

import os
import time
import socket
import select
import sys
import android
import math
import shlex
import netip
import xmpp
import ConfigParser
import string
from threading import Thread

#This thread is not 100% stable. Reason unknown. 
class serialReader(Thread):
   def __init__ (self):
      Thread.__init__(self)
   def run(self):
     process = os.popen('cat /dev/ttyMSM2')
     while process:
       try:
         speak(" %s centimeters" % process.readline())
       except:
         print "errored"


# Command input via open telnet port
def commandByTelnet():
  rs = []

  print "Firing up telnet socket..."
  try:
    svr_sock.bind(('', telnetPort))
    svr_sock.listen(3)
    svr_sock.setblocking(0)
    print "Ready to accept telnet. Use %s on port %s\n" % (phoneIP, telnetPort)
  except socket.error, (value,message):
    print "Could not open socket: " + message
    print "You can try using %s on port %s\n" % (phoneIP, telnetPort)

  while 1:
    r,w,_ = select.select([svr_sock] + rs, [], [])

    for cli in r:
      if cli == svr_sock:
        new_cli,addr = svr_sock.accept()
        rs = [new_cli]
      else:   
        input = cli.recv(1024)
        input = input.replace('\r','')
        input = input.replace('\n','')
        if input != '': 
          print "Received: '%s'" % input
          commandParse(input)

# Command input via XMPP chat
def commandByXMPP():
  global xmppUsername
  global xmppPassword
  if not xmppUsername:
    xmppUsername = droid.getInput('Username')['result']
  if not xmppPassword:
    xmppPassword = droid.getInput('Password')['result']
  jid = xmpp.protocol.JID(xmppUsername)
  client = xmpp.Client(jid.getDomain(), debug=[])
  client.connect(server=(xmppServer, xmppPort))
  client.RegisterHandler('message', XMPP_message_cb)
  if not client:
    print 'Connection failed!'
    return
  auth = client.auth(jid.getNode(), xmppPassword, 'botty')
  if not auth:
    print 'Authentication failed!'
    return
  client.sendInitPresence()
  try:
    while True:
      client.Process(1)
  except KeyboardInterrupt:
    pass

# Handle XMPP messages coming from commandByXMPP
def XMPP_message_cb(session, message):
  jid = xmpp.protocol.JID(message.getFrom())
  command = message.getBody()
  commandParse(str(command))

# Command input via speech recognition
def commandByVoice(mode='continuous'):
  try:
    listen = droid.recognizeSpeech()
    voiceCommands = str(listen['result'])
  except:
    voiceCommands = ""
  print "Voice commands: %s" % voiceCommands
  commandParse(voiceCommands)
  if mode == 'continuous':
    commandByVoice()

# Speak using TTS or make toasts
def speak(msg,override=False):
  global previousMsg
  if (audioOn and msg != previousMsg) or override:
    droid.speak(msg)
  elif msg != previousMsg:
    droid.makeToast(msg)
  else:
    print msg
  previousMsg=msg

# Handle changing the speed setting  on the robot
def changeSpeed(newSpeed):
  global currentSpeed
  if newSpeed >=0 and newSpeed <=9:
    msg = "Changing speed to %s" % newSpeed
    commandOut(newSpeed)
    currentSpeed=newSpeed
  else:
    msg = "Speed %s is out of range [0-9]" % newSpeed
  speak(msg)
    
# Point towards a specific compass heading
def orientToAzimuth(azimuth):
  onTarget = False
  stopTime = time.time() + 5000
  while not onTarget and time.time() < stopTime:
    results = droid.readSensors()

    if results['result'] is not None:
      currentHeading = results['result']['azimuth']
      msg = "Azimuth: %d Heading: %d" % (azimuth,currentHeading)
      delta = azimuth - currentHeading
      if math.fabs(delta) > 180:
        if delta < 0:
          adjustment = math.fabs(delta) + 360
        else:
          adjustment = math.fabs(delta) - 360
      else:
        adjustment = delta
      adjustmentAbs = math.fabs(adjustment)
      if adjustmentAbs < cardinalMargin:
        msg = "Goal achieved! Facing %d degrees, which is within the %d degree margin of %d!" % (currentHeading, cardinalMargin, azimuth)
        print msg
        speak(msg)
        commandOut('s')
        onTarget = True
      else:
        if adjustment > cardinalMargin:
          print "Moving %d right." % adjustmentAbs
          commandOut('r')
        if adjustment < (cardinalMargin * -1):
          print "Moving %d left." % adjustmentAbs
          commandOut('l')
        time.sleep(adjustmentAbs/180)
        commandOut('s')
        time.sleep(1)
    else:
      msg = "Could not start sensors."


# Send command out of the device (currently serial but other protocals could be added)
def commandOut(msg):
  os.system("echo '%s\n' > /dev/ttyMSM2" % msg)

# Parse the first character of incoming commands to determine what action to take
def commandParse(input):
  try:
    commandList = shlex.split(input)
  except:
    commandList = []
    print "Could not parse command"
  try:
    command = commandList[0].lower()
  except IndexError:
    command = ""
  try:
    commandValue = commandList[1]
  except IndexError:
    commandValue = ""

  if command in ["a", "audio", "record"]:
    global audioRecordingOn
    audioRecordingOn = not audioRecordingOn
    fileName=time.strftime("/sdcard/cellbot_%Y-%m-%d_%H-%M-%S.3gp")
    if audioRecordingOn:
      speak("Starting audio recording")
      droid.startAudioRecording(fileName)
    else:
      droid.stopAudioRecording()
      speak("Stopping audio recording")
      print "Audio file located at %s" % fileName
  elif command  in ["b", "back", "backward", "backwards"]:
    speak("Moving backward")
    commandOut('b')
  elif command == 'c':
    orientToAzimuth(int(commandValue[:3]))
  elif command in ["d", "date"]:
    speak(time.strftime("Current time is %_I %M %p on %A, %B %_e, %Y"))
  elif command in ["f", "forward", "forwards", "scoot"]:
    speak("Moving forward")
    commandOut('f')
  elif command in ["h", "hi", "hello"]:
    speak("Hello. Let's play.")
  elif command in ["l", "left"]:
    speak("Moving left")
    commandOut('l')
  elif command in ["m", "mute", "silence"]:
    global audioOn
    audioOn = not audioOn
    speak("Audio mute toggled")
  elif command in ["p", "point", "pointe", "face", "facing"]:
    msg = "Orienting %s" % cardinals[commandValue[:1]][0]
    speak(msg)
    try:
      orientToAzimuth(int(cardinals[commandValue[:1]][1]))
    except:
      print "Could not orient towards " + commandValue
  elif command in ["q", "quit", "exit"]:
    speak("Bye bye!")
    svr_sock.close()
    droid.stopSensing()
    droid.stopLocating()
    global readerThread
    readerThread.join()
    sys.exit("Exiting program after receiving 'q' command.")
  elif command in ["r", "right"]:
    speak("Moving right")
    commandOut('r')
  elif command in ["s", "stop"]:
    commandOut('s')
  elif command in ["t", "talk", "speak", "say"]:
    speak(input.replace(command, ''),True)
  elif command in ["v", "voice", "listen", "speech"]:
    droid.makeToast("Launching voice recognition")
    commandByVoice("onceOnly")
  elif command in ["x", "location", "gps"]:
    try:
      location = droid.readLocation()['result']
      addresses = droid.geocode(location['latitude'], location['longitude'])
      firstAddr = addresses['result']['result'][0]
      msg = 'You are in %(locality)s, %(admin_area)s' % firstAddr
    except:
      msg = "Failed to find location."
    speak(msg)
  elif command == "speed":
    if commandValue in ["0","1","2","3","4","5","6","7","8","9"]:
      changeSpeed(commandValue)
    else:
      print "Invalid speed setting: '%s'" % command
  elif command in ["faster", "hurry", "fast", "quicker"]:
    changeSpeed(currentSpeed + 1)
  elif command in ["slower", "slow", "chill"]:
    changeSpeed(currentSpeed - 1)
  elif command in ["move", "go", "turn"]:
    commandParse(commandValue)
  elif command in ["send", "pass"]:
    commandOut(commandValue)
  elif command in ["range", "distance", "z"]: 
    global serialIn
    commandOut("z")
    #A thread will handle the response.
  else:
    print "Unknown command: '%s'" % command

#Non-configurable settings
droid = android.Android()
cardinals = {}
cardinals['n']=('North','0')
cardinals['e']=('East','90')
cardinals['w']=('West','270')
cardinals['s']=('South','180')
previousMsg = ""
audioRecordingOn = False
phoneIP = netip.displayNoLo()
svr_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
serialIn = os.popen('cat /dev/ttyMSM2')
readerThread = serialReader()


# Get configurable options from the ini file
config = ConfigParser.ConfigParser()
config.read("/sdcard/ase/scripts/cellbotConfig.ini")
audioOn = config.getboolean("basics", "audioOn")
currentSpeed = config.getint("basics", "currentSpeed")
cardinalMargin = config.getint("basics", "cardinalMargin")
telnetPort = config.getint("control", "port")
inputMethod = config.get("control", "inputMethod")
xmppServer = config.get("xmpp", "server")
xmppPort = config.getint("xmpp", "port")
xmppUsername = config.get("xmpp", "username")
xmppPassword = config.get("xmpp", "password")
print "username is: " + xmppUsername

# The main loop that fires up a telnet socket and processes inputs
def main():
  readerThread.start()
  print "Send the letter 'q' or say 'quit' to exit the program.\n"
  droid.startSensing()
  droid.startLocating()
  global currentSpeed
  commandOut(currentSpeed)
  droid.makeToast("Initiating input method...")
  globals()[inputMethod]()

if __name__ == '__main__':
    main()