#!/usr/bin/env python

import serial
import os, time
import subprocess
import sys

def enum(**enums):
    return type('Enum', (), enums)

# socat PTY,link=$HOME/testpty,echo=0,raw -
for f in ["/dev/ttyAMA0", "/dev/ttyUSB0", "/home/andree/testpty"]:
    if os.path.exists(f):
        NODE_TTY=f
        break

sys.stdout = os.fdopen(sys.stdout.fileno(), 'w', 0)

CMD_START = '!'
CMD_MOVEMENT_BEGIN = '{'
CMD_MOVEMENT_END = '}'
CMD_START_BEEP = 'B'
CMD_STOP_BEEP = 'b'
CMD_PING = '?'
CMD_PONG = '!'
CMD_STATUS_REQUEST = 'd'

SENSOR_MOVEMENT = '0'
SENSOR_DOOR = '1'

BEEP_FOB = 'ZQ'
BEEP_LOCK_WARNING = 'qm'
BEEP_LOCK_WARNING_HI = 'QM'
BEEP_ALARM_WARNING = ':1'

### robustness settings
# delay between pings
PING_DELAY = 5
# delay until the pong is expected
PONG_DELAY = PING_DELAY * 2
# delay between safety status requests
STATUS_REQUEST_DELAY = 5

### timeouts settings
# number of seconds between two fob-induced actions
FOB_DELAY = 5
# maximum time between movement and alarm warning trigger
ALARM_WARNING_TIMEOUT = 0
# maximum time between movement and alarm trigger
ALARM_TIMEOUT = 15
# time after fob movement ends after which the lock warning ends
ALARM_ARM_WARNING_TIMEOUT = 3
# length of silence/beep during lock warning
ALARM_LOCK_WARNING_INTERVAL = 1 # should be the smallest non-0 value around

# time after which the automatic unlock happens (to prevent too whole day of alarm sirene buzzing)
ALARM_DISABLE_TIMEOUT = 2 * 60

FOBS = [
    "00002DCB28C>",
    "00002E44CFE7",
    "00002E9454>E",
    "00002E88359H"
    ]

def detectFob(buf):
    for f in FOBS:
        if buf.find(f) != -1:
            buf = ""
            return True
    return False

def genBeepCmd(pitch):
    return CMD_START_BEEP + pitch + "|!"

# safety to workaround missing characters and left out beeping/beep stop
def ttyMultiWrite(cmd):
    for i in range(0, 3):
        time.sleep(0.05)
        tty.write(cmd)

tty = serial.Serial(NODE_TTY, baudrate = 9600, timeout = ALARM_LOCK_WARNING_INTERVAL * 0.5) # NOTE: timeout here specifies the granularity of events

buf = ""
AlarmStatus = enum(UNLOCKED = 0, LOCKING = 1, LOCKED = 2, TRIGGERED = 3)
status = AlarmStatus.UNLOCKED

def logmessage(s):
    print(time.asctime() + ": " + s)

class NodePing:
    def run(self):
        global actions, tty
        tty.write(CMD_PING)
        actions += [Action(time.time() + PONG_DELAY, NodePong())]

class NodePong:
    @staticmethod
    def handlePong():
        global actions, tty
        actions = [a for a in actions if (not isinstance(a.action, NodePing) and not isinstance(a.action, NodePong))]
        actions += [Action(time.time() + PING_DELAY, NodePing())]
    
    def run(self):
        NodePong.handlePong()
        logmessage("Pong timeout")

class NodeStatusRequest:
    def run(self):
        global actions, tty
        tty.write(CMD_STATUS_REQUEST)
        actions += [Action(time.time() + STATUS_REQUEST_DELAY, NodeStatusRequest())]

class AlarmWarning:
    def __init__(self, pitch):
        self.pitch = pitch

    def run(self):
        global actions, tty
        ttyMultiWrite(genBeepCmd(self.pitch))

    @staticmethod
    def disarm(stepBeeping = True):
        global actions, tty
        if stepBeeping:
            ttyMultiWrite(CMD_STOP_BEEP)
        actions = [a for a in actions if (not isinstance(a.action, AlarmWarning))]
        # logmessage("AlarmWarning disable")
        
    @staticmethod
    def notifyFob():
        for i in range(0,3):
            tty.write(genBeepCmd(BEEP_FOB))
            time.sleep(0.05)
            tty.write(CMD_STOP_BEEP)
            time.sleep(0.05)
        ttyMultiWrite(CMD_STOP_BEEP)

class AlarmLockedWarningDisable:
    def run(self):
        global actions
        global AlarmStatus, status
        AlarmWarning.disarm()
        
class AlarmLockedWarning:
    def run(self):
        global actions, tty
        AlarmWarning.disarm(False)
        actions += [Action(time.time(), AlarmWarning(BEEP_LOCK_WARNING_HI))]
        actions += [Action(time.time() + ALARM_ARM_WARNING_TIMEOUT, AlarmLockedWarningDisable())]
        
    @staticmethod
    def disarm():
        global actions
        actions = [a for a in actions if (not isinstance(a.action, AlarmLockedWarning))]
        
def subcall(path):
    subprocess.call(path, shell = False)

class Alarm:
    def run(self):
        global actions, tty
        global AlarmStatus, status
        actions += [Action(time.time() + ALARM_DISABLE_TIMEOUT, AlarmDisable())]
        subcall("./sirene-on")
        status = AlarmStatus.TRIGGERED
        logmessage("Alarm triggered")

    @staticmethod
    def disarm():
        global actions, tty
        subcall("./sirene-off")
        actions = [a for a in actions if (not isinstance(a.action, Alarm) and not isinstance(a.action, AlarmDisable))]
        logmessage("Alarm disable")

class AlarmDisable:
    def run(self):
        global actions
        global AlarmStatus, status
        
        # after a while, nothing happened - let's assume error and not bother neighbors anymore...
        AlarmWarning.disarm()
        Alarm.disarm()
        
        status = AlarmStatus.UNLOCKED
        actions = []

        logmessage("Alarm disabled")
        subcall('./sirene-cancel')

class AlarmArm:
    def run(self):
        global AlarmStatus, status
        status = AlarmStatus.LOCKED
        logmessage("Locked")
        
class AlarmDelayedTrigger:
    lastMovementBegin = False
    
    def run(self):
        global AlarmStatus, status
        global actions
        if status == AlarmStatus.LOCKED:
            actions += [Action(time.time() + ALARM_WARNING_TIMEOUT, AlarmWarning(BEEP_ALARM_WARNING))]
            actions += [Action(time.time() + ALARM_TIMEOUT, Alarm())]

        logmessage("Movement")

    @staticmethod
    def disarm():
        global actions, tty, status
        if [a for a in actions if (isinstance(a.action, AlarmDelayedTrigger))] != []:
            logmessage("False movement")
        actions = [a for a in actions if (not isinstance(a.action, AlarmDelayedTrigger))]
        
        if status == AlarmStatus.LOCKING:
            actions += [Action(time.time() + ALARM_LOCK_WARNING_INTERVAL, AlarmLockedWarning())]
            actions += [Action(time.time(), AlarmArm())]
        
class HandleMovement:
    @staticmethod
    def begin():
        global actions
        for a in actions:
            if isinstance(a.action, AlarmDelayedTrigger):
                return
        actions += [Action(time.time() + 0.5, AlarmDelayedTrigger())]
        
    @staticmethod
    def end():
        AlarmDelayedTrigger.disarm()

class HandleFob:
    lastFobTime = 0
    @classmethod
    def entered(cls):
        global AlarmStatus, status
        global actions
        
        if cls.lastFobTime + FOB_DELAY >= time.time():
            return
        cls.lastFobTime = time.time()
        
        if (status == AlarmStatus.LOCKED) or (status == AlarmStatus.TRIGGERED):
            Alarm.disarm()
            AlarmWarning.disarm()
            status = AlarmStatus.UNLOCKED
            logmessage("Unlocked")
        elif (status == AlarmStatus.UNLOCKED):
            actions += [Action(time.time() + ALARM_WARNING_TIMEOUT, AlarmWarning(BEEP_LOCK_WARNING))]
            status = AlarmStatus.LOCKING
            logmessage("Locking")
        elif (status == AlarmStatus.LOCKING):
            AlarmWarning.disarm()
            actions = [a for a in actions if not isinstance(a.action, AlarmArm)]
            status = AlarmStatus.UNLOCKED
            logmessage("Locking cancel")

        AlarmWarning.notifyFob()

class Action:
    def __init__(self, time, action):
        self.time = time
        self.action = action
    def __repr__(self):
        return str(self.time) + " => " + self.action.__class__.__name__

class MovementAggregator:
    movementStatuses = {SENSOR_MOVEMENT:0, SENSOR_DOOR:0}

    @classmethod
    def begin(cls, which):
        if which == SENSOR_MOVEMENT:
            # NOTE: ignore this sensor for now
            return
        
        cls.movementStatuses[which] = 1
        HandleMovement.begin()

    @classmethod
    def end(cls, which):
        cls.movementStatuses[which] = 0
        if max(cls.movementStatuses.values()) == 0:
            HandleMovement.end()

actions = [Action(time.time(), NodePing()), Action(time.time(), NodeStatusRequest())]
nextSensorStatus = None

while True:
    c = tty.read()
    if c == CMD_START:
        c = tty.read()
        if c >= '0' and c <= '9':
            nextSensorStatus = c
        elif c == CMD_MOVEMENT_BEGIN:
            MovementAggregator.begin(nextSensorStatus)
        elif c == CMD_MOVEMENT_END:
            MovementAggregator.end(nextSensorStatus)
        elif c == CMD_PONG:
            NodePong.handlePong()
        else:
            buf += CMD_START + c
    elif c != '':
        buf += c
        if detectFob(buf):
            HandleFob.entered()
            buf = ""

    curTime = time.time()
    
    needRescan = True
    while needRescan:
        needRescan = False
        # print str(curTime) + ":" + str(actions)
        for a in actions:
            if (a.time <= curTime):
                actionsOld = actions[:]
                a.action.run()
                try:
                    actions.remove(a)
                    if actions[:] != actionsOld[:]:
                        needRescan = True
                        break
                except:
                    needRescan = True
                    break;
