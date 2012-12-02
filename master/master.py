#!/usr/bin/env python

import serial
import os, time
import subprocess

def enum(**enums):
    return type('Enum', (), enums)

REAL_HW = False

if REAL_HW:
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

# delay between pings
PING_DELAY = 5
# delay until the pong is expected
PONG_DELAY = PING_DELAY * 2

# number of seconds after which login/logout is done when a known fob is detected
FOB_DELAY = 5
# maximum time between movement and alarm warning trigger
ALARM_WARNING_TIMEOUT = 0
# maximum time between movement and alarm trigger
ALARM_TIMEOUT = 10
# time after fob entered after which the alarm is armed
ALARM_ARM_TIMEOUT = 30
# length of silence/beep during lock warning
ALARM_WARNING_LOCK_INTERVAL = 1

# time after which the automatic unlock happens
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

tty = serial.Serial(NODE_TTY, baudrate = 9600, timeout = 1)

buf = ""
AlarmStatus = enum(OPEN = 0, LOCKING = 1, LOCKED = 2, TRIGGERED = 3)
status = AlarmStatus.OPEN

class NodePing:
    def __init__(self):
        pass

    def run(self):
        global actions, tty
        tty.write(CMD_PING)
        actions += [Action(time.time() + PONG_DELAY, NodePong())]

class NodePong:
    def __init__(self):
        pass
    
    @staticmethod
    def handlePong():
        global actions, tty
        actions = [a for a in actions if (not isinstance(a.action, NodePing) and not isinstance(a.action, NodePong))]
        actions += [Action(time.time() + PING_DELAY, NodePing())]
    
    def run(self):
        NodePong.handlePong()
        print("Pong timeout @ " + time.asctime())

class AlarmWarning:
    def __init__(self, warnLock):
        self.warnLock = warnLock
        self.beep = False

    def run(self):
        global actions, tty
        self.beep = not self.beep
        if self.beep:
            tty.write(CMD_START_WARNING)
        else:
            tty.write(CMD_STOP_WARNING)
        
        if self.warnLock:
            # reschedule to beep in intervals
            aw = AlarmWarning(self.warnLock)
            aw.beep = self.beep
            actions += [Action(time.time() + 2 * ALARM_WARNING_LOCK_INTERVAL, aw)]

    @staticmethod
    def disarm():
        global actions, tty
        tty.write(CMD_STOP_WARNING)
        actions = [a for a in actions if (not isinstance(a.action, AlarmWarning))]
        print("AlarmWarning disable @ " + time.asctime())

def subcall(path):
    if REAL_HW:
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
    @staticmethod
    def begin():
        global AlarmStatus, status
        global actions
        if status == AlarmStatus.LOCKED:
            actions += [Action(time.time() + ALARM_WARNING_TIMEOUT, AlarmWarning(False))]
            actions += [Action(time.time() + ALARM_TIMEOUT, Alarm())]

    @staticmethod
    def end():
        pass

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
            actions += [Action(time.time() + ALARM_WARNING_TIMEOUT, AlarmWarning(True))]
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

actions = [Action(time.time(), NodePing())]

while True:
    c = tty.read()
    if c == CMD_START:
        c = tty.read()
        if c == CMD_MOVEMENT_BEGIN:
            handleMovement.begin()
        elif c == CMD_MOVEMENT_END:
            handleMovement.end()
        elif c == CMD_PONG:
            NodePong.handlePong()
        else:
            buf += CMD_START + c
    elif c != '':
        buf += c
        if detectFob(buf):
            HandleFob.entered()

    curTime = time.time()
    newActions = []
    for a in actions:
        if (a.time <= curTime):
            a.action.run()
        else:
            newActions += [a]
    actions = newActions
