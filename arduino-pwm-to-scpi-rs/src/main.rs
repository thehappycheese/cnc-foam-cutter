#![feature(abi_avr_interrupt)]
#![feature(f16)]
#![allow(static_mut_refs)]
#![no_std]
#![no_main]

mod pulse_meter;
mod ring_buffer;
use pulse_meter::PulseMeter;
use crate::ring_buffer::RingBuffer;

use arduino_hal::simple_pwm::Prescaler;
use panic_halt as _;

const TICK_INTERVAL_MS:u16 = 10;
const MAX_TICKS_BETWEEN_SENDS:u16 = 1000/TICK_INTERVAL_MS; // 1 second
const MIN_TICKS_BETWEEN_SENDS:usize = (50/TICK_INTERVAL_MS) as usize;
// Global variables for interrupt handler (need to be atomic/volatile)
static mut PULSE_METER:PulseMeter = PulseMeter::new(Prescaler::Prescale8);
static mut DEBOUNCER:RingBuffer<MIN_TICKS_BETWEEN_SENDS> = RingBuffer::new();


#[arduino_hal::entry]
fn main() -> ! {
    let dp = arduino_hal::Peripherals::take().unwrap();
    unsafe{PULSE_METER.configure_clock(&dp)};
    
    let pins = arduino_hal::pins!(dp);
    let mut serial = arduino_hal::default_serial!(dp, pins, 57600);
    
    // ICP1 is physical pin 12 which is pin 8 on th Arduino Pro Mini board
    // Configure pin 8 (ICP1) as input
    pins.d8.into_floating_input();
    
    let mut set_value:u16 = 0;
    let mut ticks_since_last_send:u16 = 0;
    loop {
        ticks_since_last_send +=1;
        if let Some(duty_cycle) = unsafe{PULSE_METER.duty_cycle_2()} {
            let overdue_for_set = ticks_since_last_send>MAX_TICKS_BETWEEN_SENDS;
            if unsafe{
                DEBOUNCER.push(duty_cycle);
                DEBOUNCER.all_same()
            } || overdue_for_set {
                if set_value!=duty_cycle || overdue_for_set {
                    set_value = duty_cycle;
                    ticks_since_last_send = 0;
                    ufmt::uwriteln!(
                        &mut serial,
                        "set_value {}", 
                        set_value
                    ).unwrap();
                }
            }
            
        }
        arduino_hal::delay_ms(TICK_INTERVAL_MS as u32);
    }
}

#[avr_device::interrupt(atmega328p)]
fn TIMER1_CAPT() {
    unsafe {PULSE_METER.handle_capture();}
}
