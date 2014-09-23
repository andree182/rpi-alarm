rpi-alarm
=========

This is a not entirely naive implementation of RFID alarm.

Basically this is the connection used:



[RPI] --- [Webcam]

 |
 
[Comm. HUB] --- [Alarm]

 |
 
[Node]


[Comm. HUB] just a level converter
It converts a GPIO pin (using a MOSFET in my case) to 12V as a feed
for the alarm audio device.
It also converts UART from [Node] to 3V3 as to not burn RPI...

[Node] a Attiny2313 device
It aggregates the detectors (like movement detector, or a "magnetic detector"),
contains a piezo beeper to alert user and talks to a RFID scanner.
It talks to RPI via regular RS232 UART.

[Alarm] a 12V alarm device - just apply 12V/1A and it beeps real loud :)

[Webcam] a webcam to gater images and send them to email, to alert owner

[RPI] a RPI device. Ideally UPS-backed, obviously.
