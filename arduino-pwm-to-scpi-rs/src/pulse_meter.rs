use crate::ring_buffer::RingBuffer;
use arduino_hal::simple_pwm::Prescaler;


enum PulseState {
    WaitingForRisingEdge,
    WaitingForFallingEdge { rising_edge_timestamp: u16 },
    WaitForEndOfPeriod { rising_edge_timestamp: u16, width:u16 },
}

pub struct PulseMeter {
    state: PulseState,
    prescaler:Prescaler,
    ring_buffer: RingBuffer<32>
}

impl PulseMeter {

    #[inline(always)]
    pub const fn new(prescaler:Prescaler) -> Self {
        Self {
            state: PulseState::WaitingForRisingEdge,
            prescaler,
            ring_buffer:RingBuffer::new()
        }
    }

    pub unsafe fn configure_clock(&self, dp:&arduino_hal::Peripherals){
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
            match self.prescaler {
                Prescaler::Direct   =>w.cs1().direct(),
                Prescaler::Prescale8=>w.cs1().prescale_8(),
                Prescaler::Prescale64=>w.cs1().prescale_64(),
                Prescaler::Prescale256=>w.cs1().prescale_256(),
                Prescaler::Prescale1024=>w.cs1().prescale_1024()
            }
            .icnc1().set_bit()
            .ices1().set_bit()
        });
        
        // Enable Input Capture interrupt
        dp.TC1.timsk1.write(|w| w.icie1().set_bit());
    
        // Enable global interrupts
        unsafe { avr_device::interrupt::enable() };
    }

    #[inline(always)]
    pub unsafe fn handle_capture(&mut self) {
        let tc1 = unsafe { &(*arduino_hal::pac::TC1::ptr()) };
        let current_timestamp = tc1.icr1.read().bits();

        macro_rules! switch_to_rising_edge_detection {($tc1:expr) => { $tc1.tccr1b.modify(|_, w| w.ices1().set_bit()) }}
        macro_rules! switch_to_falling_edge_detection {($tc1:expr) => { $tc1.tccr1b.modify(|_, w| w.ices1().clear_bit()) }}

        match self.state {
            PulseState::WaitingForRisingEdge => {
                switch_to_falling_edge_detection!(tc1);
                self.state = PulseState::WaitingForFallingEdge { rising_edge_timestamp: current_timestamp };
            }
            PulseState::WaitingForFallingEdge { rising_edge_timestamp } => {
                switch_to_rising_edge_detection!(tc1);
                let width = current_timestamp.wrapping_sub(rising_edge_timestamp);
                self.state = PulseState::WaitForEndOfPeriod { rising_edge_timestamp, width };
            }
            PulseState::WaitForEndOfPeriod { rising_edge_timestamp, width } => {
                switch_to_falling_edge_detection!(tc1);
                let period = current_timestamp.wrapping_sub(rising_edge_timestamp);
                self.ring_buffer.push(((width as u32*100)/period as u32) as u16);
                self.state = PulseState::WaitingForFallingEdge { rising_edge_timestamp: current_timestamp }
            }
        }
    }

    pub fn duty_cycle_2(&self) -> Option<u16>{
        let result = self.ring_buffer.average().map(|v|v+1);
        return result;
    }
}
