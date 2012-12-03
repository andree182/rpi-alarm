#!/usr/bin/env python

import serial
import os, time
import subprocess

def enum(**enums):
    return type('Enum', (), enums)

ARM_SIRENE = False

if True:
    NODE_TTY = "/dev/ttyAMA0"
else:
    # socat PTY,link=$HOME/testpty,echo=0,raw -
    NODE_TTY = "/home/andree/testpty"

CMD_START = '!'
CMD_MOVEMENT_BEGIN = '{'
CMD_MOVEMENT_END = '}'
CMD_START_WARNING = 'B'
CMD_STOP_WARNING = 'b'
CMD_PING = '?'
CMD_PONG = '!'
CMD_STATUS_REQUEST = 'd'

### robustness settings
# delay between pings
PING_DELAY = 5
# delay until the pong is expected
PONG_DELAY = PING_DELAY * 2
# delay between safety status requests
STATUS_REQUEST_DELAY = 5

### timeouts settings
# number of seconds after which login/logout is done when a known fob is detected
FOB_DELAY = 5
# maximum time between movement and alarm warning trigger
ALARM_WARNING_TIMEOUT = 0
# maximum time between movement and alarm trigger
ALARM_TIMEOUT = 10
# time after fob entered after which the alarm is armed
ALARM_ARM_TIMEOUT = 30
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
        print("Pong timeout @ " + time.asctime())

class NodeStatusRequest:
    def run(self):
        global actions, tty
        tty.write(CMD_STATUS_REQUEST)
        actions += [Action(time.time() + STATUS_REQUEST_DELAY, NodeStatusRequest())]

class AlarmWarning:
    def __init__(self, warnLock, length = 0):
        self.warnLock = warnLock
        self.beep = False
        self.length = length

    def run(self):
        global actions, tty
        self.beep = not self.beep
        if self.beep:
            tty.write(CMD_START_WARNING)
        else:
            tty.write(CMD_STOP_WARNING)
        
        if self.warnLock:
            # reschedule to beep in intervals
            aw = AlarmWarning(self.warnLock, self.length)
            aw.beep = self.beep
            actions += [Action(time.time() + self.length, aw)]

    @staticmethod
    def disarm():
        global actions, tty
        tty.write(CMD_STOP_WARNING)
        actions = [a for a in actions if (not isinstance(a.action, AlarmWarning))]
        print("AlarmWarning disable @ " + time.asctime())

class AlarmWarningIntensify:
    def run(self):
        global actions, tty
        AlarmWarning.disarm()
        actions += [Action(time.time() + ALARM_WARNING_TIMEOUT, AlarmWarning(True, ALARM_LOCK_WARNING_INTERVAL * 0.5))]
        
def subcall(path):
    if ARM_SIRENE:
        subprocess.call(path, shell = True)
    else:
        print path

class Alarm:
    def __init__(self):
        subcall("sudo su -c 'echo 23 > /sys/class/gpio/export'")
        subcall("sudo su -c 'echo out > /sys/class/gpio/gpio23/direction'")
        
    def run(self):
        global actions, tty
        global AlarmStatus, status
        actions += [Action(time.time() + ALARM_DISABLE_TIMEOUT, AlarmDisable())]
        subcall("sudo su -c 'echo 1 > /sys/class/gpio/gpio23/value'")
        status = AlarmStatus.TRIGGERED
        print("Alarm triggered @ " + time.asctime())

    @staticmethod
    def disarm():
        global actions, tty
        subcall("sudo su -c 'echo 0 > /sys/class/gpio/gpio23/value'")
        actions = [a for a in actions if (not isinstance(a.action, Alarm) and not isinstance(a.action, AlarmDisable))]
        print("Alarm disable @ " + time.asctime())

class AlarmDisable:
    def run(self):
        global actions
        global AlarmStatus, status
        
        # after 2 minutes, nothing happened - let's assume error and not bother neighbors anymore...
        AlarmWarning.disarm()
        Alarm.disarm()
        
        status = AlarmStatus.OPEN
        actions = []

        print("Alarm disabled @ " + time.asctime())
        # TODO: notify

class AlarmArm:
    def run(self):
        global AlarmStatus, status
        AlarmWarning.disarm()
        status = AlarmStatus.LOCKED
        print("Locked @ " + time.asctime())
        
class HandleMovement:
    lastMovementBegin = False

    @staticmethod
    def begin():
        global AlarmStatus, status
        global actions
        if status == AlarmStatus.LOCKED:
            actions += [Action(time.time() + ALARM_WARNING_TIMEOUT, AlarmWarning(False))]
            actions += [Action(time.time() + ALARM_TIMEOUT, Alarm())]

        if not HandleMovement.lastMovementBegin:
            print "Movement begin @ " + time.asctime()
            HandleMovement.lastMovementBegin = True
                
    @staticmethod
    def end():
        if HandleMovement.lastMovementBegin:
            print "Movement end @ " + time.asctime()
            HandleMovement.lastMovementBegin = False

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
            print("Open @ " + time.asctime())
        elif (status == AlarmStatus.OPEN):
            actions += [Action(time.time() + ALARM_WARNING_TIMEOUT, AlarmWarning(True, ALARM_LOCK_WARNING_INTERVAL))]
            actions += [Action(time.time() + ALARM_WARNING_TIMEOUT + ALARM_ARM_TIMEOUT * 0.75, AlarmWarningIntensify())]
            actions += [Action(time.time() + ALARM_ARM_TIMEOUT, AlarmArm())]
            status = AlarmStatus.LOCKING
            print("Locking @ " + time.asctime())
        elif (status == AlarmStatus.LOCKING):
            AlarmWarning.disarm()
            actions = [a for a in actions if not isinstance(a.action, AlarmArm)]
            status = AlarmStatus.OPEN
            print("Locking cancel @ " + time.asctime())

class Action:
    def __init__(self, time, action):
        self.time = time
        self.action = action

actions = [Action(time.time(), NodePing()), Action(time.time(), NodeStatusRequest())]

while True:
    c = tty.read()
    if c == CMD_START:
        c = tty.read()
        if c == CMD_MOVEMENT_BEGIN:
            HandleMovement.begin()
        elif c == CMD_MOVEMENT_END:
            HandleMovement.end()
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
