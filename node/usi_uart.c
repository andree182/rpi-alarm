#include <avr/io.h>
#include <avr/interrupt.h>
#include "usi_uart.h"

/////////////////// Settings

#define SYSTEM_CLOCK F_CPU

//#define BAUDRATE                   115200
//#define BAUDRATE                    57600
//#define BAUDRATE                    28800
//#define BAUDRATE                    19200
//#define BAUDRATE                    14400
#define BAUDRATE                     9600

// TCCR0B = _BV(CS00);
#define TIMER_PRESCALER           1
// TCCR0B = _BV(CS01);
// #define TIMER_PRESCALER           8     

#define TICKS_PER_SYMBOL ((SYSTEM_CLOCK / BAUDRATE) / TIMER_PRESCALER)

#define UART_RX_BUFFER_SIZE        32     /* 2,4,8,16,32,64,128 or 256 bytes */

// NOTE: This may contain bigger values if we were waking up CPU
// #define INTERRUPT_STARTUP_DELAY   (0x11 / TIMER_PRESCALER)
#define INTERRUPT_STARTUP_DELAY (TICKS_PER_SYMBOL / 4 * 3)

#define DATA_BITS                 8
#define START_BIT                 1
#define STOP_BIT                  1

/////////////////// (Calculated) Constants
#define USI_COUNTER_MAX_COUNT (16)
#define TIMER0_MAX (256) /* actually, the max value is of course (TIMER0_MAX - 1) */


#define TIMER0_SEED               (TIMER0_MAX - TICKS_PER_SYMBOL)
// #define TIMER0_SEED               (TIMER0_MAX - TICKS_PER_SYMBOL) + 5

#if ( (TICKS_PER_SYMBOL * 3/2) > (TIMER0_MAX - INTERRUPT_STARTUP_DELAY) )
    // delay between start and first bits is too long, so sample also start bit (but don't put it in the result)
    #define INITIAL_TIMER0_SEED       (TIMER0_MAX - (TICKS_PER_SYMBOL * 1/2))
    #define USI_COUNTER_SEED_RECEIVE  (USI_COUNTER_MAX_COUNT - (START_BIT + DATA_BITS))
#else
    // start with the bit after start bit
    #define INITIAL_TIMER0_SEED       (TIMER0_MAX - (TICKS_PER_SYMBOL * 3/2))
    #define USI_COUNTER_SEED_RECEIVE  (USI_COUNTER_MAX_COUNT - DATA_BITS)
#endif

#define UART_RX_BUFFER_MASK (UART_RX_BUFFER_SIZE - 1)
#if (UART_RX_BUFFER_SIZE & UART_RX_BUFFER_MASK)
    #error RX buffer size is not a power of 2
#endif

unsigned char initial_timer0_seed;
unsigned char usi_counter_seed_receive;
unsigned char timer0_seed;

static volatile unsigned char          UART_RxBuf[UART_RX_BUFFER_SIZE];
static volatile unsigned char UART_RxHead;
static volatile unsigned char UART_RxTail;
#if STOP_BIT > 1
static unsigned char          UART_RxPhase;
#endif

void USI_UART_init(void)
{
	initial_timer0_seed = INITIAL_TIMER0_SEED;
	usi_counter_seed_receive = USI_COUNTER_SEED_RECEIVE;
	timer0_seed = TIMER0_SEED;
}

void USI_UART_init_rx(void)
{
	// Enable pull up on USI DO and DI
    PORTB |= _BV(PB6) | _BV(PB5);
    // Set USI DI and DO
    DDRB &= ~(_BV(PB6) | _BV(PB5));
    
    // Disable USI
    USICR = 0;
    
    // Clear pin change interrupt flag.
    EIFR = _BV(PCIF);
    // Enable pin change interrupt for PORTB
    GIMSK |= _BV(PCIE);
    // Enable pin change interrupt for PB5
    PCMSK |= _BV(PCINT5);
}

#define nop()  __asm__ __volatile__("nop")

void USI_UART_start_rx(void)
{
    /* PB5 should be low now (start bit). */
    
    USIDR = 0;
    
    TCNT0 = INTERRUPT_STARTUP_DELAY + initial_timer0_seed;
    TCCR0B = _BV(CS00); // clk I/O (no prescaling)
    
    // Allow timer interrupt after overflow
    TIFR = _BV(TOV0);
    TIMSK |= _BV(TOIE0);

    USICR =
        // Enable USI Counter overflow interrupt
        _BV(USIOIE) |
        // Three Wire mode.
        _BV(USIWM0) |
        // Timer0 overflow as the USI Clock source.
        _BV(USICS0);

    USISR =
        // Clear all USI interrupt flags.
        0xF0 |
        // Preload the USI counter to generate interrupt
        usi_counter_seed_receive;

    PCMSK &= ~_BV(PCINT5); // Disable pin change interrupt for PB5
#if STOP_BIT > 1
    UART_RxPhase = 0;
#endif
}

ISR(USI_OVERFLOW_vect)
{	
    unsigned char tmphead;
    
    tmphead = (UART_RxHead + 1) & UART_RX_BUFFER_MASK;

    UART_RxBuf[tmphead] = USIDR;
    UART_RxHead = tmphead;

#if STOP_BIT == 1
    TCCR0B  = 0; // Stop Timer0.
    USI_UART_init_rx();
#elif STOP_BIT == 0
#error not implemented...
#else
#warning 2 bits should be supported
    UART_RxPhase = 1;
#endif
}

ISR(TIMER0_OVF_vect)
{	
#if STOP_BIT == 2
    if (UART_RxPhase == 1) {
        TCCR0B  = 0; // Stop Timer0.
        USI_UART_init_rx();
    }
#endif
    TCNT0 += timer0_seed;
}

static unsigned char Bit_Reverse(unsigned char x)
{
    x = ((x >> 1) & 0x55) | ((x << 1) & 0xaa);
    x = ((x >> 2) & 0x33) | ((x << 2) & 0xcc);
    x = ((x >> 4) & 0x0f) | ((x << 4) & 0xf0);
    return x;    
}

void USI_UART_flush(void)
{
    UART_RxHead = 0;
    UART_RxTail = 0;
}

unsigned char USI_UART_receive(void)
{
    unsigned char tmptail;
        
    while (UART_RxHead == UART_RxTail);
    
    tmptail = (UART_RxTail + 1) & UART_RX_BUFFER_MASK;
    UART_RxTail = tmptail;
    
    return Bit_Reverse(UART_RxBuf[tmptail]);
}

unsigned char USI_UART_receive_is_ready(void)
{
    return (UART_RxHead != UART_RxTail);
}
