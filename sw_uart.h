#ifndef __SW_UART_H__
#define __SW_UART_H__

/**
 * Initialize receiver - setup PCINT on PB4. 
 * 
 * NOTE: The following needs to be part of ISR(PCINT_vect):
 * if (!(PINB & _BV(PB3)))
 *      SW_UART_start_rx();
**/
void SW_UART_init_rx(void);

/**
 * After PCINT on PB4, this is called to start USI receiving data...
**/
void SW_UART_start_rx(void);

void SW_UART_flush(void);
unsigned char SW_UART_receive(void);
unsigned char SW_UART_receive_is_ready(void);

#endif // __SW_UART_H__
