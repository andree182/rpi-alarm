#!/usr/bin/env python

import serial
import os, time

CMD_START = '!'
CMD_MOVEMENT_START = '{'
CMD_MOVEMENT_END = '}'
CMD_START_WARNING = 'X'
CMD_STOP_WARNING = 'x'
CMD_PING = '?'
CMD_PONG = '!'

# delay between pings
PING_DELAY = 5
# delay until the pong is expected
PONG_DELAY = PING_DELAY * 2

# number of seconds after which login/logout is done when a known fob is detected
FOB_DELAY = 5
# maximum time between movement and alarm warning trigger
ALARM_WARNING_TIMEOUT = 3
# maximum time between movement and alarm trigger
ALARM_TIMEOUT = 10

FOBS = [
    "00002DCB28C>",
    "00002E44CFE7",
    "00002E9454>E",
    "00002E88359H"
    ]

movement = False
movementTime = None
needLogin = False
lastFobTime = time.time() - FOB_DELAY
loggedIn = False
lastPingTime = time.time()
lastPongTime = time.time()

ser = serial.Serial("/dev/ttyUSB0", baudrate = 9600, timeout = 1)

buf = ""

def warnAlarm():
    ser.write(CMD_START_WARNING)

def triggerAlarm():
    print "ALARMA!"

def untriggerAlarm():
    ser.write(CMD_STOP_WARNING)

def warnAlarmStart():
    print "Alarm starting!"

def warnNoPong():
    print "No pong!"

def detectFob(buf):
    for f in FOBS:
        if buf.find(f) != -1:
            buf = ""
            return True
    return False

while True:
    c = ser.read()
    if c == CMD_START:
        c = ser.read()
        if c == CMD_MOVEMENT_START:
            print "Move"
            movement = True
            movementTime = time.time()
        elif c == CMD_MOVEMENT_END:
            print "NotMove"
            movement = False
        elif c == CMD_PONG:
            lastPongTime = time.time()
        else:
            buf += CMD_START + c
    elif c != '':
        buf += c
        if detectFob(buf):
            if lastFobTime + FOB_DELAY <= time.time():
                lastFobTime = time.time()
                loggedIn = not loggedIn
                print "Logged in: ", loggedIn
                if loggedIn:
                    needLogin = False
                    untriggerAlarm()
                else:
                    # give user time to clear the room
                    lastFobTime += ALARM_TIMEOUT
                    warnAlarmStart()

    if lastPongTime + PONG_DELAY < lastPingTime:
        warnNoPong()
        lastPongTime = time.time()
    if lastPingTime + PING_DELAY < time.time():
        ser.write(CMD_PING)
        lastPingTime = time.time()

    if movement:
        if not loggedIn:
            needLogin = True

    if needLogin and movementTime + ALARM_WARNING_TIMEOUT < time.time():
        warnAlarm()

    if needLogin and movementTime + ALARM_TIMEOUT < time.time():
        triggerAlarm()
