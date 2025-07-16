
pub enum PSUCommand{
    OutputOn,
    OutputOff,
    SetVoltage(f32),
    SetCurrent(f32),
}
