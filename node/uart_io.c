#include <avr/io.h>
#include <avr/interrupt.h>
#include <util/delay.h>
#include "uart_io.h"

void UART_init(unsigned int baud)
{
    /*set baud rate*/
    UBRRH = (unsigned char)(baud >> 8);
    UBRRL = (unsigned char) baud;
    
    /*enable Receiver and Transmitter*/
    UCSRA = (1<<U2X);
    UCSRB = (1<<RXEN) | (1<<TXEN) |(1<<RXCIE);
    
    /* set frame format 8data, 2 stop bity*/
    UCSRC = (1<<USBS)|(3<<UCSZ0);
}

void UART_transmit(unsigned char data)
{
    /*wait for empty transmit buffer*/
    while (!(UCSRA & (1<<UDRE)))
        ;
    
    /*put dat into buffer, send data*/
    UDR = data;
}

static volatile int rx_ready;
static volatile unsigned char rx_ch;

ISR(SIG_USART0_RX)
{
    rx_ready = 1;
    rx_ch = UDR;
}

int UART_receive_is_ready(void)
{
    return rx_ready;
}

unsigned char UART_receive(void)
{
    while (!rx_ready) {
        _delay_ms(1);
    }
    
    rx_ready = 0;
    return rx_ch;
}
