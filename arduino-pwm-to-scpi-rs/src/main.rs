#![feature(abi_avr_interrupt)]
#![feature(f16)]
#![allow(static_mut_refs)]
#![no_std]
#![no_main]

mod pulse_meter;
use pulse_meter::{
    PulseMeter,
    PulseData
};

// ICP1 is physical pin 12 which is pin 8 on th Arduino Pro Mini board
use panic_halt as _;
//use arduino_hal::prelude::*;
use avr_device::interrupt;


// Global variables for interrupt handler (need to be atomic/volatile)
static mut PULSE_METER:PulseMeter = PulseMeter::new();

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

    loop {
        // Check for new pulse data
        if let Some(PulseData{width, period}) = interrupt::free(|_| {
            unsafe{PULSE_METER.latest_data.clone()}
        }) {
            let duty_cycle = width as f16 / period as f16;
            ufmt::uwriteln!(
                &mut serial,
                "duty_cycle {}", 
                (duty_cycle * 1000f16) as u16
            ).unwrap();
        }
        
        arduino_hal::delay_ms(100);
    }
}

// This is the Rust equivalent of ISR(TIMER1_CAPT_vect)
#[interrupt(atmega328p)]
fn TIMER1_CAPT() {
    unsafe {PULSE_METER.handle_capture();}// the reference in the main loop must be made inside
}