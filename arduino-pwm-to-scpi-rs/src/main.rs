#![feature(abi_avr_interrupt)]
#![no_std]
#![no_main]

mod pulse_meter;

// ICP1 is physical pin 12 which is pin 8 on th Arduino Pro Mini board
use panic_halt as _;
//use arduino_hal::prelude::*;
use avr_device::interrupt;

// Global variables for interrupt handler (need to be atomic/volatile)
static mut PULSE_START: u16 = 0;
static mut PULSE_WIDTH: u16 = 0;
static mut PULSE_PERIOD: u16 = 0;
static mut NEW_PULSE_DATA: bool = false;

struct PulseInfo{
    period:u16,
    width:u16,
}

#[arduino_hal::entry]
fn main() -> ! {
    let dp = arduino_hal::Peripherals::take().unwrap();
    let pins = arduino_hal::pins!(dp);
    let mut serial = arduino_hal::default_serial!(dp, pins, 57600);

    // Configure pin 8 (ICP1) as input
    pins.d8.into_floating_input();
    
    // Configure Timer1 for Input Capture
    dp.CPU.prr.write(|w|w.prtim1().clear_bit()); // Disable power reduction for timer 1
    
    // Set Timer1 to normal mode (Count upward to MAX then overflow)
    dp.TC1.tccr1a.write(|w| w.wgm1().bits(0b000));
    dp.TC1.tccr1b.write(|w| w.wgm1().bits(0b00));

    // CS1   Clock source (slow down from 16MHz to 200 kHz (this should be plenty resolution for our pwm at 1kHz)
    // ICNC1 1 - Enable noise canceller
    // ICES  Initially Search for Rising Edge (this will be changed to wait for a falling edge and back again)
    //       0 - (Default) Trigger on Falling Edge
    //       1 -           Trigger on Rising Edge
    dp.TC1.tccr1b.write(|w| {
        w.cs1().prescale_64()
        .icnc1().set_bit()
        .ices1().set_bit()
    });
    
    // Enable Input Capture interrupt
    dp.TC1.timsk1.write(|w| w.icie1().set_bit());
    
    // Enable global interrupts
    unsafe { interrupt::enable() };

    let mut pulse_info:Option<PulseInfo>;
    loop {
        // Check for new pulse data
        pulse_info = interrupt::free(|_| {
            unsafe {
                if NEW_PULSE_DATA {
                    NEW_PULSE_DATA = false;
                    Some(PulseInfo{period:PULSE_PERIOD, width:PULSE_WIDTH})
                }else{
                    None
                }
            }
        });
        if let Some(pulse_info)=pulse_info {
            //let frequency = (16_000_000u32 / 64u32) / pulse_info.period as u32;
            //let duty_cycle = (pulse_info.width as u32 * 100) / pulse_info.period as u32;
            ufmt::uwriteln!(
                &mut serial,
                "period {} width {}", 
                pulse_info.period,
                pulse_info.width
            ).unwrap();
        }
        
        arduino_hal::delay_ms(100);
    }
}

// This is the Rust equivalent of ISR(TIMER1_CAPT_vect)
#[interrupt(atmega328p)]
fn TIMER1_CAPT() {
    let tc1 = unsafe { &(*arduino_hal::pac::TC1::ptr()) };
    
    unsafe {
        static mut LAST_CAPTURE: u16 = 0;
        static mut MEASURING: bool = false;
        
        let current_capture = tc1.icr1.read().bits();
        
        if !MEASURING {
            // Switch to falling edge detection
            tc1.tccr1b.modify(|_, w| w.ices1().clear_bit());
            // First rising edge - start measurement
            PULSE_START = current_capture;
            MEASURING = true;
        } else {
            if tc1.tccr1b.read().ices1().bit_is_clear() {
                // Falling edge - end of pulse
                // Switch back to rising edge detection
                tc1.tccr1b.modify(|_, w| w.ices1().set_bit());
                PULSE_WIDTH = current_capture.wrapping_sub(PULSE_START);
            } else {
                // Rising edge - end of period
                PULSE_PERIOD = current_capture.wrapping_sub(LAST_CAPTURE);
                MEASURING = false;
                NEW_PULSE_DATA = true;
            }
        }
        
        LAST_CAPTURE = current_capture;
    }
}