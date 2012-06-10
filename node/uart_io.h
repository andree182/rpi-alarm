#ifndef __UART_IO_H_
#define __UART_IO_H_

void UART_init(unsigned int baud);
void UART_transmit(unsigned char c);
unsigned char UART_receive(void);
int UART_receive_is_ready(void);

#define UART_endl() \
	UART_transmit('\r'); \
	UART_transmit('\n')

#endif
