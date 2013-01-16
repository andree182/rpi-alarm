#!/usr/bin/env python

import serial
import os, time
import subprocess
import sys

def enum(**enums):
    return type('Enum', (), enums)

if True:
    NODE_TTY = "/dev/ttyAMA0"
else:
    # socat PTY,link=$HOME/testpty,echo=0,raw -
    NODE_TTY = "/home/andree/testpty"

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
# time after fob entered after which the alarm is armed
ALARM_ARM_TIMEOUT = 15
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

tty = serial.Serial(NODE_TTY, baudrate = 9600, timeout = ALARM_LOCK_WARNING_INTERVAL * 0.5) # NOTE: timeout here specifies the granularity of events

buf = ""
AlarmStatus = enum(OPEN = 0, LOCKING = 1, LOCKED = 2, TRIGGERED = 3)
status = AlarmStatus.OPEN

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
        self.beep = False
        self.pitch = pitch

    def run(self):
        global actions, tty
        self.beep = not self.beep
        if self.beep:
            tty.write(CMD_START_BEEP + self.pitch)
        else:
            tty.write(CMD_STOP_BEEP)

    @staticmethod
    def disarm():
        global actions, tty
        tty.write(CMD_STOP_BEEP)
        actions = [a for a in actions if (not isinstance(a.action, AlarmWarning))]
        logmessage("AlarmWarning disable")
        
    @staticmethod
    def notifyFob():
        for i in range(0,3):
            tty.write(CMD_START_BEEP + BEEP_FOB)
            time.sleep(0.05)
            tty.write(CMD_STOP_BEEP)
            time.sleep(0.05)

class AlarmWarningIntensify:
    def run(self):
        global actions, tty
        AlarmWarning.disarm()
        actions += [Action(time.time() + ALARM_WARNING_TIMEOUT, AlarmWarning(BEEP_LOCK_WARNING_HI))]
        
    @staticmethod
    def disarm():
        global actions
        actions = [a for a in actions if (not isinstance(a.action, AlarmWarningIntensify))]
        logmessage("AlarmWarningIntensify disable")
        
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
        
        status = AlarmStatus.OPEN
        actions = []

        logmessage("Alarm disabled")
        subcall('./sirene-cancel')

class AlarmArm:
    def run(self):
        global AlarmStatus, status
        AlarmWarning.disarm()
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
        global actions, tty
        if [a for a in actions if (isinstance(a.action, AlarmDelayedTrigger))] != []:
            logmessage("False movement")
        actions = [a for a in actions if (not isinstance(a.action, AlarmDelayedTrigger))]
        
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
            status = AlarmStatus.OPEN
            logmessage("Open")
        elif (status == AlarmStatus.OPEN):
            actions += [Action(time.time() + ALARM_WARNING_TIMEOUT, AlarmWarning(BEEP_LOCK_WARNING))]
            actions += [Action(time.time() + ALARM_WARNING_TIMEOUT + ALARM_ARM_TIMEOUT * 0.75, AlarmWarningIntensify())]
            actions += [Action(time.time() + ALARM_ARM_TIMEOUT, AlarmArm())]
            status = AlarmStatus.LOCKING
            logmessage("Locking")
        elif (status == AlarmStatus.LOCKING):
            AlarmWarning.disarm()
            AlarmWarningIntensify.disarm()
            actions = [a for a in actions if not isinstance(a.action, AlarmArm)]
            status = AlarmStatus.OPEN
            logmessage("Locking cancel")

        AlarmWarning.notifyFob()

class Action:
    def __init__(self, time, action):
        self.time = time
        self.action = action

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
