// #![feature(abi_avr_interrupt)]
#![no_std]
#![no_main]

use panic_halt as _;
// use avr_device::interrupt;

#[arduino_hal::entry]
fn main() -> ! {
    let dp = arduino_hal::Peripherals::take().unwrap();
    let pins = arduino_hal::pins!(dp);

    let mut serial = arduino_hal::default_serial!(dp,pins,57600);
    /*
     * For examples (and inspiration), head to
     *
     *     https://github.com/Rahix/avr-hal/tree/main/examples
     *
     * NOTE: Not all examples were ported to all boards!  There is a good chance though, that code
     * for a different board can be adapted for yours.  The Arduino Uno currently has the most
     * examples available.
     */

    let mut led = pins.d13.into_output();

    // dp.TC1.tccr1a.write(|w|w.wgm1().bits(0b00));
    // dp.TC1.tccr1b.write(|w|
    //     w.cs1().prescale_8()
    //     .icnc1().set_bit()
    //     .ices1().set_bit()
    // );

    // dp.TC1.timsk1.write(|w|w.icie1().set_bit());
    // unsafe {avr_device::interrupt::enable()};

    loop {
        led.toggle();
        if led.is_set_high() {
            serial.write_byte(b'Y');
        }else{
            serial.write_byte(b'N');
        }
        arduino_hal::delay_ms(1000);
    }
}

// #[avr_device::interrupt(atmega328p)]
// fn TIMER1_CAPT() {
//     todo!()
// }