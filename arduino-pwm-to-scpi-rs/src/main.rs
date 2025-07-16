#![feature(abi_avr_interrupt)]
#![feature(f16)]
#![allow(static_mut_refs)]
#![no_std]
#![no_main]

mod pulse_meter;
mod ring_buffer;
use arduino_hal::simple_pwm::Prescaler;
use pulse_meter::PulseMeter;


use panic_halt as _;
use avr_device::interrupt;


// Global variables for interrupt handler (need to be atomic/volatile)
static mut PULSE_METER:PulseMeter = PulseMeter::new(Prescaler::Prescale8);

#[arduino_hal::entry]
fn main() -> ! {
    let dp = arduino_hal::Peripherals::take().unwrap();
    unsafe{PULSE_METER.configure_clock(&dp)};
    
    let pins = arduino_hal::pins!(dp);
    let mut serial = arduino_hal::default_serial!(dp, pins, 57600);

    // ICP1 is physical pin 12 which is pin 8 on th Arduino Pro Mini board
    // Configure pin 8 (ICP1) as input
    pins.d8.into_floating_input();

    loop {
        if let Some(duty_cycle) = unsafe{PULSE_METER.duty_cycle_2()} {
             ufmt::uwriteln!(
                &mut serial,
                "duty_cycle {}", 
                duty_cycle
            ).unwrap();
        }
        arduino_hal::delay_ms(100);
    }
}

#[interrupt(atmega328p)]
fn TIMER1_CAPT() {
    unsafe {PULSE_METER.handle_capture();}
}
