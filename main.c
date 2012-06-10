#ifndef __AVR_ATtiny2313__
#define __AVR_ATtiny2313__
#endif

#include <avr/io.h>
#include <avr/interrupt.h>
#include <util/delay.h>
#include "uart_io.h"
#include "usi_uart.h"

static int movement;

static void delay_ms(uint16_t ms)
{
    while (ms) {
        _delay_ms(1);
        ms--;
    }
}

enum {
    LED_RED = 0,
    LED_YELLOW = 1,
    LED_GREEN = 2,
    LED_BLUE = 3,
};

// const unsigned char hex[] = "0123456789abcdef";
// 
// static void UART_print_ch(char c, uint8_t i)
// {
//     UART_transmit(c);
//     UART_transmit(' ');
//     UART_transmit(hex[i >> 4]);
//     UART_transmit(hex[i & 0x0f]);
//     UART_endl();
// }

static void UART_print_ci(char c, uint8_t i)
{
    UART_transmit(c);
    UART_transmit(' ');
    UART_transmit(i / 100 + '0');
    UART_transmit((i % 100) / 10 + '0');
    UART_transmit(i % 10 + '0');
    UART_endl();
}

static void blink_led(int which)
{
    switch (which) {
    case LED_RED:
        PORTB |= _BV(PB1);
        delay_ms(10);
        PORTB &= ~_BV(PB1);
        break;
    case LED_YELLOW:
        PORTB |= _BV(PB0);
        delay_ms(10);
        PORTB &= ~_BV(PB0);
        break;
    case LED_GREEN:
        PORTD |= _BV(PD6);
        delay_ms(10);
        PORTD &= ~_BV(PD6);
        break;
    case LED_BLUE:
        PORTB |= _BV(PB2);
        delay_ms(10);
        PORTB &= ~_BV(PB2);
        break;
    }
}

ISR(PCINT_vect)
{
    if (!(PINB & _BV(PB5))) {
        PORTD |= _BV(PD5);
        USI_UART_start_rx();
    }
    
    if (PINB & _BV(PB3)) {
        movement = 1;
        PORTB |= _BV(PB2);
        UART_transmit('M');
    } else if (movement) {
        movement = 0;
        PORTB &= ~_BV(PB2);
        UART_transmit('m');
        UART_transmit('\n');
    }
}

static void print_usi_settings(void)
{
    UART_print_ci('I', initial_timer0_seed);
    UART_print_ci('S', usi_counter_seed_receive);
    UART_print_ci('T', timer0_seed);
    UART_transmit('\n');
}

int main (void)
{
    /* 9600 baud with 8MHz div 8 */
    UART_init(12);
    
    _delay_ms(20);

    UART_transmit('h');
    UART_transmit('i');
    UART_endl();

    /* enable (led) outputs */
    DDRD = _BV(PD6) | _BV(PD5) | _BV(PD4);
    DDRB = _BV(PB0) | _BV(PB1) | _BV(PB2);
    
    /* Set input without pull-up */
    DDRB &= ~_BV(PB3); // set input
    PORTB &= ~_BV(PB3); // no pull-up
    GIMSK |= _BV(PCIE);
    PCMSK |= _BV(PCINT3);
    
    USI_UART_init();
    USI_UART_flush();
    USI_UART_init_rx();
    
    /* Private flags */
    movement = 0;

    sei();
    
    /* loop forever */
    while (1) {
        if (UART_receive_is_ready()) {
            unsigned char c = UART_receive();
            blink_led(LED_RED);
            
            switch (c) {
            case 'X':
                PORTB |= _BV(PB0);
                break;
            case 'x':
                PORTB &= ~_BV(PB0);
                break;
            case 'o':
                print_usi_settings();
                break;
            case 'I':
                initial_timer0_seed++;
                print_usi_settings();
                break;
            case 'i':
                initial_timer0_seed--;
                print_usi_settings();
                break;
            case 'S':
                usi_counter_seed_receive++;
                print_usi_settings();
                break;
            case 's':
                usi_counter_seed_receive--;
                print_usi_settings();
                break;
            case 'T':
                timer0_seed++;
                print_usi_settings();
                break;
            case 't':
                timer0_seed--;
                print_usi_settings();
                break;
            }
        } else if (USI_UART_receive_is_ready()) {
            blink_led(LED_GREEN);
            UART_transmit(USI_UART_receive());
        }
    }
}
