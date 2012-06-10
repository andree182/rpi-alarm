#ifndef __USI_UART_H__
#define __USI_UART_H__

extern unsigned char initial_timer0_seed;
extern unsigned char usi_counter_seed_receive;
extern unsigned char timer0_seed;

void USI_UART_init(void);

/**
 * Initialize receiver - setup PCINT on PB5, disable USI. 
 * 
 * NOTE: The following needs to be part of ISR(PCINT_vect):
 * if (!(PINB & _BV(PB5)))
 *      USI_UART_start_rx();
**/
void USI_UART_init_rx(void);

/**
 * After PCINT on PB5, this is called to start USI receiving data...
**/
void USI_UART_start_rx(void);

void USI_UART_flush(void);
unsigned char USI_UART_receive(void);
unsigned char USI_UART_receive_is_ready(void);

#endif // __USI_UART_H__
