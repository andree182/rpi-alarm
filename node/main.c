/*
 * rfid (usi uart) - PB5
 * piezo - PB4
 * door magnet - PB3 (down on closed, up on open - using pull-up)
 * motion detector PB2 (no pull-up)
 * yellow led - PB0
 * red led    - PD6
 */

#ifndef __AVR_ATtiny2313__
#define __AVR_ATtiny2313__
#endif

#include <avr/io.h>
#include <avr/interrupt.h>
#include <util/delay.h>
#include <avr/wdt.h>
#include "uart_io.h"
#include "usi_uart.h"

static int movement, doorOpen;

static void delay_ms(uint16_t ms)
{
    while (ms) {
        _delay_ms(1);
        ms--;
    }
}

enum {
    LED_RED = 0,
    LED_RED_FAST,
    LED_YELLOW,
};

#ifdef USI_DEBUG
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
#endif

static void blink_led(int which)
{
    switch (which) {
    case LED_RED:
        PORTD |= _BV(PD6);
        delay_ms(10);
        PORTD &= ~_BV(PD6);
        break;
    case LED_RED_FAST:
        PORTD |= _BV(PD6);
        _delay_us(100);
        PORTD &= ~_BV(PD6);
        break;
        break;
    case LED_YELLOW:
        PORTB |= _BV(PB0);
        delay_ms(10);
        PORTB &= ~_BV(PB0);
        break;
    }
}

static void msg(char c)
{
    UART_transmit('!');
    UART_transmit(c);
}

#define READ_MOVEMENT() \
    movement = PINB & _BV(PB2)

#define READ_DOORS_OPEN() \
    doorOpen = PINB & _BV(PB3)

static void status_msg_one(int which, int status)
{
    msg(which + '0');

    if (status) {
        msg('{');
    } else {
        msg('}');
    }
}

static void status_msg(void)
{
    READ_MOVEMENT();        
    READ_DOORS_OPEN();
    
#ifdef LED_SIGNALLING
    if (movement) 
        PORTD |= _BV(PD6);
    else
        PORTD &= ~_BV(PD6);

    if (doorOpen)
        PORTB |= _BV(PB0);
    else
        PORTB &= ~_BV(PB0);
#endif

    status_msg_one(0, movement);
    status_msg_one(1, doorOpen);
}

ISR(PCINT_vect)
{
    if (!(PINB & _BV(PB5))) {
        USI_UART_start_rx();
    } else {
        status_msg();
    }
}

#ifdef USI_DEBUG

static void print_usi_settings(void)
{
    UART_print_ci('I', initial_timer0_seed);
    UART_print_ci('S', usi_counter_seed_receive);
    UART_print_ci('T', timer0_seed);
    UART_transmit('\n');
}

#endif

static void wdg_init(void)
{    
#if 0
    WDTCSR |= (_BV(WDCE) | _BV(WDE));
    WDTCSR = _BV(WDE) | /* (0 << WDIF) | (0 << WDIE) |*/ (/* 8s timeout */_BV(WDP3) | _BV(WDP0));
#else
    wdt_enable(WDTO_8S);
#endif
}

int main (void)
{
    int ocr1a, ocr1b;

    wdg_init();

    /* 9600 baud with 8MHz div 8 */
    UART_init(12);
    
    _delay_ms(20);

    /* enable outputs */
    DDRB = _BV(PB0) | _BV(PB4);
    DDRD = _BV(PD6);
    
    /* Set input without pull-up */
    DDRB &= ~_BV(PB2); // set input, no pullup
    PORTB &= ~_BV(PB2);
    
    DDRB &= ~_BV(PB3); // set input + pullup
    PORTB |= _BV(PB3);
    
    GIMSK |= _BV(PCIE);
    PCMSK |= _BV(PCINT3) | _BV(PCINT2); // interrupt on doors/movement
    
    USI_UART_init();
    USI_UART_flush();
    USI_UART_init_rx();

    /* Private flags */
    READ_MOVEMENT();
    READ_DOORS_OPEN();

    sei();

	msg('#');
    msg('!');
    
    /* loop forever */
    while (1) {
        if (UART_receive_is_ready()) {
            unsigned char c = UART_receive();
            
            switch (c) {
            case '?':
                wdt_reset();
                blink_led(LED_RED);
                msg('!');
                break;
            case 'n':
                UART_transmit('\n');
                UART_transmit('\r');
                break;
            case 'Y':
                PORTB |= _BV(PB0);
                break;
            case 'y':
                PORTB &= ~_BV(PB0);
                break;
            case 'R':
                PORTD |= _BV(PD6);
                break;
            case 'r':
                PORTD &= ~_BV(PD6);
                break;
            case 'B':
                // setup beep using PWM on PB4
                // 5kHz (piezo resonance frequency) is 200|100
                ocr1a = (UART_receive() - '0') * 20;
                ocr1b = (UART_receive() - '0') * 20;
                if (UART_receive() != '|')
                    break;
                if (UART_receive() != '!')
                    break;

                TCCR1A = 0b00100011;
                TCCR1B = 0b00011001;
                OCR1A = ocr1a;
                OCR1B = ocr1b;
                break;
            case 'b':
                TCCR1A = 0;
                TCCR1B = 0; //just for sure...
                break;
            case 'd':
                status_msg();
                break;
#ifdef USI_DEBUG
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
#endif
            }
        } else if (USI_UART_receive_is_ready()) {
            /* route USI->UART */
            blink_led(LED_RED_FAST);
            UART_transmit(USI_UART_receive());
        }
    }
}
