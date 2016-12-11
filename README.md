rpi-alarm
=========

This is a not-entirely-naive python implementation of a RFID alarm. The code architecture is event-oriented to make it clear what's happening and to avoid nasty corner cases (such as activating alarm because the doors were not shut quick-enough when leaving :-)). 2 years in permanent operation prove it's pretty stable.

Basically this is the connection used:

    [RPI] --- [Webcam]
      |
    [Comm. HUB] --- [Alarm]
      |
    [Node]

[**Comm. HUB**] is just a level converter
It converts a GPIO pin (using a MOSFET in my case) to 12V as a feed
for the alarm audio device.
It also converts UART from [Node] to 3V3 as to not burn RPI...

[**Node**] a Attiny2313 device
It aggregates the detectors (like movement detector, or a "magnetic detector"),
contains a piezo beeper to alert user and talks to a RFID scanner.
It talks to RPI via regular RS232 UART. Optionally some RS485 or similar could be used, to improve
robustness - but at the speeds of few kbauds, it's hardly needed.

[**Alarm**] a 12V alarm device - just apply 12V/1A and it beeps real loud :) Activated from RPI via GPIO.

[**Webcam**] an USB webcam to gater images and send them to email, to alert owner

[**RPI**] a RPI device. Ideally UPS-backed, obviously.
