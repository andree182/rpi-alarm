# AVR-GCC Makefile
PROJECT=name
SOURCES=main.c uart_io.c usi_uart.c
# SOURCES=main.c uart_io.c sw_uart.c
CC=avr-gcc
OBJCOPY=avr-objcopy
MMCU=attiny2313
OBJCOPY_FLAGS=--strip-all

CFLAGS=-mmcu=$(MMCU) -Wall -Wstrict-prototypes -Os -mcall-prologues -DSTRIPPED_USI -DF_CPU=1000000UL

$(PROJECT).hex: $(PROJECT).out
	$(OBJCOPY) $(OBJCOPY_FLAGS) -j .text -O ihex $(PROJECT).out $(PROJECT).hex

$(PROJECT).out: $(SOURCES)
	$(CC) $(CFLAGS) -I./ -o $(PROJECT).out $(SOURCES)

program: $(PROJECT).hex
	avrdude -v -p t2313 -c usbasp -e -U flash:w:$(PROJECT).hex

fuses:
	# enable watchdog and brown-out for 2.7V
	avrdude -v -p t2313 -c usbasp -y -U hfuse:w:0xcb:m

clean:
	rm -f $(PROJECT).out
	rm -f $(PROJECT).hex
