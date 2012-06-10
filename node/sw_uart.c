#include <avr/io.h>
#include <avr/interrupt.h>
#include <util/delay.h>
#include "sw_uart.h"

#define US_PER_BIT 104

static char start_bit;
uint8_t rfid_data[16];
uint8_t rfid_nbytes = 0;
uint8_t buf = 0;

void SW_UART_init_rx(void)
{
    // Enable pull up
    PORTB |= _BV(PB4);
    DDRB &= ~(_BV(PB4));
    
    // Clear pin change interrupt flag.
    EIFR = _BV(PCIF);
    // Enable pin change interrupt for PORTB
    GIMSK |= _BV(PCIE);
    // Enable pin change interrupt for PB4
    PCMSK |= _BV(PCINT4);
    
    start_bit = 0;
}

void SW_UART_start_rx(void)
{
    start_bit = 1;
}

void SW_UART_flush(void)
{
}

static void wait_for_start_bit(void)
{
    // Wait for Start bit (low)
    while (PINB & _BV(PB4))
        ;

    // Wait until end of start bit
    _delay_us(US_PER_BIT);

    // Wait until 1/3 into the first data bit
    _delay_us(US_PER_BIT / 3);
}

static void read_byte(void)
{
    uint8_t i;

    for (i = 0; i < 8; ++i) {
        if (PINB & _BV(PB4))
            buf |= 1 << i;

        // A bit too long, but not enough to worry
        // (i.e., we can drift almost 8 us per bit)
        _delay_us(US_PER_BIT);
    }
}
  
unsigned char SW_UART_receive(void)
{
    start_bit = 0;
    
    PCMSK &= ~_BV(PCINT4);
    
    PORTB |= _BV(PB0);
    wait_for_start_bit();
    PORTB |= _BV(PB1);
    read_byte();
    PORTB &= ~_BV(PB0);
    PORTB &= ~_BV(PB1);
    PCMSK |= _BV(PCINT4);
    
    return buf;
}

unsigned char SW_UART_receive_is_ready(void)
{
    return start_bit;
}
