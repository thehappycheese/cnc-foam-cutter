import serial

class KORAD_KD3005P:
    """Based on the user manual for the KD3000/6000 series, so might be suitable for other models"""
    pss:serial.Serial
    
    def __init__(self, port:str|None=None) -> None:
        self.pss = serial.Serial(port,timeout=0.05)
        print(self.send_read("*IDN?"))

    def send_read(self, msg:str):
        self.pss.write(msg.encode("ascii"))
        return self.pss.read_until()
    
    def send(self, msg:str):
        self.pss.write(msg.encode("ascii"))

    def status(self):
        """> Note: The state of over-current protection (OCP) cannot be reported, but it can be toggled using over_current_protection_disable and over_current_protection_enable."""
        res = self.send_read("STATUS?")[0]
        vset = float(self.send_read("VSET1?").decode("ascii"))
        iset = float(self.send_read("ISET1?").decode("ascii"))
        vout = float(self.send_read("VOUT1?").decode("ascii"))
        iout = float(self.send_read("IOUT1?").decode("ascii"))
        return {
            "mode": "Constant Voltage" if bool(res & 0b0000_0001) else "Constant Current",
            "output_on": bool(res & 0b0100_0000),
            "voltage_set":vset,
            "current_set":iset,
            "voltage_out":vout,
            "current_out":iout,
        }
    
    def read_current(self):
        return float(self.send_read("IOUT1?").decode("ascii"))
    
    def read_voltage(self):
        return float(self.send_read("VOUT1?").decode("ascii"))

    def over_current_protection_enable(self):
        self.send("OCP1")
    
    def over_current_protection_disable(self):
        self.send("OCP0")

    def output_on(self):
        self.send("OUT1")
    
    def output_off(self):
        self.send("OUT0")
    
    def set_voltage(self, value:float):
        self.send(f"VSET1:{value:.3f}")

    def set_current(self, value:float):
        self.send(f"ISET1:{value:.3f}")