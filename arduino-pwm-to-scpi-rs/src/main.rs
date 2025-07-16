#![feature(abi_avr_interrupt)]
#![feature(f16)]
#![allow(static_mut_refs)]
#![no_std]
#![no_main]

mod pulse_meter;
use pulse_meter::PulseMeter;

mod ring_buffer;
use crate::{messaging::PSUCommand, queue::FixedQueue, ring_buffer::RingBuffer};

mod messaging;
mod queue;
mod float_format;
use float_format::format_float_2dp;

use arduino_hal::simple_pwm::Prescaler;
use panic_halt as _;

const TICK_INTERVAL_MS:u16 = 10;
const MAX_TICKS_BETWEEN_UPDATE:u16   = 1000/TICK_INTERVAL_MS; // 1 second
const MIN_TICKS_BETWEEN_UPDATE:usize = (20/TICK_INTERVAL_MS) as usize;
const MIN_TICKS_BETWEEN_SEND:u16     = 50/TICK_INTERVAL_MS;
const CURRENT_MAX:f32 = 4.0;
const VOLTAGE_SET:f32 = 20.0;

static mut PULSE_METER:PulseMeter = PulseMeter::new(Prescaler::Prescale8);



#[arduino_hal::entry]
fn main() -> ! {
    let dp = arduino_hal::Peripherals::take().unwrap();
    unsafe{PULSE_METER.configure_clock(&dp)};
    
    let pins = arduino_hal::pins!(dp);
    let mut serial = arduino_hal::default_serial!(dp, pins, 9600);
    
    // ICP1 is physical pin 12 which is pin 8 on th Arduino Pro Mini board
    // Configure pin 8 (ICP1) as input
    pins.d8.into_floating_input();
    
    let mut debouncer:RingBuffer<MIN_TICKS_BETWEEN_UPDATE> = RingBuffer::new();
    let mut output_enabled = false;
    let mut set_value:u16 = 0;
    let mut ticks_since_last_update:u16 = 0;
    
    let mut ticks_since_last_send:u16 = 0;
    let mut message_queue:FixedQueue<PSUCommand, 5> = FixedQueue::new();

    loop {
        ticks_since_last_update +=1;
        ticks_since_last_send +=1;


        

        if let Some(duty_cycle) = unsafe{PULSE_METER.duty_cycle_2()} {
            let overdue_for_set = ticks_since_last_update>=MAX_TICKS_BETWEEN_UPDATE;
            if overdue_for_set{
                ticks_since_last_update = MAX_TICKS_BETWEEN_UPDATE; // try prevent idle overflow
            }
            debouncer.push(duty_cycle);
            if debouncer.all_same() || overdue_for_set {
                if set_value!=duty_cycle || overdue_for_set {
                    set_value = duty_cycle;
                    ticks_since_last_update = 0;
                    if message_queue.space()>=2 {
                        if set_value<10{
                            output_enabled = false;
                            message_queue.enqueue(PSUCommand::OutputOff);
                            message_queue.enqueue(PSUCommand::SetVoltage(VOLTAGE_SET));
                        }else if set_value<90{
                            let current = (set_value as f32 - 10.0)/80.0 * CURRENT_MAX;
                            if !output_enabled{
                                output_enabled = true; // technically only when the message is sent...
                                message_queue.enqueue(PSUCommand::OutputOn);
                            }
                            message_queue.enqueue(PSUCommand::SetCurrent(current));
                        }else {
                            if !output_enabled{
                                output_enabled = true; // technically only when the message is sent...
                                message_queue.enqueue(PSUCommand::OutputOn);
                            }
                            message_queue.enqueue(PSUCommand::SetCurrent(CURRENT_MAX));
                        }
                    }
                    
                }
            }
        }

        if ticks_since_last_send >= MIN_TICKS_BETWEEN_SEND {
            ticks_since_last_send = MIN_TICKS_BETWEEN_SEND; // try prevent idle overflow
            message_queue.dequeue().map(|message|{
                ticks_since_last_send=0;
                match message {
                    PSUCommand::OutputOff=>{
                        ufmt::uwrite!(
                            &mut serial,
                            "OUT0"
                        ).unwrap();
                    },
                    PSUCommand::OutputOn=>{
                        ufmt::uwrite!(
                            &mut serial,
                            "OUT1"
                        ).unwrap();
                    },
                    PSUCommand::SetCurrent(current)=>{
                        let printed = format_float_2dp(current);
                        
                        ufmt::uwrite!(
                            &mut serial,
                            "ISET1:{}",
                            printed.as_str()
                        ).unwrap();
                    }
                    PSUCommand::SetVoltage(voltage)=>{
                        let printed = format_float_2dp(voltage);
                        ufmt::uwrite!(
                            &mut serial,
                            "VSET1:{}",
                            printed.as_str()
                        ).unwrap();
                    }
                }
            });
        }

        arduino_hal::delay_ms(TICK_INTERVAL_MS as u32);
    }
}

#[avr_device::interrupt(atmega328p)]
fn TIMER1_CAPT() {
    unsafe {PULSE_METER.handle_capture();}
}
