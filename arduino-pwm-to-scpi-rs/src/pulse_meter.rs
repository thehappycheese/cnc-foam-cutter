#[derive(Clone, Copy)]
pub struct PulseData {
    pub width: u16,
    pub period: u16,
}

enum PulseState {
    WaitingForRisingEdge,
    WaitingForFallingEdge { rising_edge_timestamp: u16 },
    WaitForEndOfPeriod { rising_edge_timestamp: u16, width:u16 },
}

pub struct PulseMeter {
    state: PulseState,
    pub latest_data: Option<PulseData>,
}

impl PulseMeter {

    #[inline(always)]
    pub const fn new() -> Self {
        Self {
            state: PulseState::WaitingForRisingEdge,
            latest_data: None
        }
    }

    #[inline(always)]
    pub unsafe fn handle_capture(&mut self) {
        let tc1 = unsafe { &(*arduino_hal::pac::TC1::ptr()) };
        let current_timestamp = tc1.icr1.read().bits();

        macro_rules! switch_to_rising_edge_detection {($tc1:expr) => { $tc1.tccr1b.modify(|_, w| w.ices1().set_bit()) }}
        macro_rules! switch_to_falling_edge_detection {($tc1:expr) => { $tc1.tccr1b.modify(|_, w| w.ices1().clear_bit()) }}
        // macro_rules! is_rising_edge_detection {($tc1:expr) => {$tc1.tccr1b.read().ices1().bit_is_set()}}
        // macro_rules! is_falling_edge_detection {($tc1:expr) => {$tc1.tccr1b.read().ices1().bit_is_clear()}}

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
                self.latest_data = Some(PulseData { width, period });
                self.state = PulseState::WaitingForFallingEdge { rising_edge_timestamp: current_timestamp }
            }
        }
    }

}