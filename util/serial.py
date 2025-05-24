import serial
from serial import Serial
import time

class CNC:
    serial:Serial

    def __init__(self, addr="socket://fluidnc.local:23"):
        self.serial = serial.serial_for_url(addr)
        time.sleep(0.100)
        print(self.read_all())

    def read_all(self)->str:
        buff = b""
        while self.serial.in_waiting:
            resp = self.serial.read_all()
            if resp is not None:
                buff += resp
        return buff.decode("ascii")

    def write_read_all(self, message:str) -> str:
        self.serial.write(message.encode("ascii"))
        time.sleep(0.200)
        return self.read_all()
    
    def write_read_line(self, message:str) -> str:
        self.serial.write(message.encode("ascii"))
        return self.serial.readline().decode("ascii").strip()

    def writeln(self, message:str) -> str:
        return self.write_read_all(message+"\n")

    def alarm_clear(self) -> bool:
        response = self.writeln("\x18")
        response_ok = response == "ok\r\n"
        return response_ok
    
    def status(self)->str:
        return self.writeln("?")[:-6]
    
    def config_get(self)->dict:
        response = self.writeln("$S")[:-6]
        return {(kv:=line.split("="))[0]:kv[1] for line in response.splitlines()}

    def relative_set(self, relative_positioning:bool)->str:
        if relative_positioning:
            return self.relative()
        else:
            return self.absolute()
        
    def feed_rate(self, rate:int) -> str:
        return self.writeln(f"F{rate}")
    
    def relative(self):
        """G91"""
        return self.writeln("G91")

    def absolute(self):
        """G90"""
        return self.writeln("G90")
    
    def home(self):
        return self.writeln("$H")
    

    def send_g1_xy_commands(self, xy_tuples: list, feed:int) -> bool:
        """
        Sends multiple G1 XY commands and waits for 'ok' response after each one.
        
        Args:
            xy_tuples: List of (x, y) coordinate tuples
            
        Returns:
            bool: True if all commands were sent and acknowledged successfully
        """
        success = True

        for x, y in xy_tuples:
            # Format G1 command with the XY coordinates
            command = f"G1 F{feed} X{x} Y{y} Z{x} A{y}\n"
            
            # Send the command
            self.serial.write(command.encode("ascii"))
            
            # Wait for and verify the 'ok' response
            response = ""
            start_time = time.time()
            timeout = 10  # 10-second timeout for safety
            
            while "ok" not in response:
                if self.serial.in_waiting:
                    new_data = self.serial.read(self.serial.in_waiting).decode("ascii")
                    response += new_data
                
                # Check for timeout
                if time.time() - start_time > timeout:
                    print(f"Timeout waiting for 'ok' after command: {command.strip()}")
                    success = False
                    break
                    
                # Small delay to prevent CPU hogging
                time.sleep(0.01)
            
            # Optional: Add a small delay between commands for stability
            time.sleep(0.01)
        
        return success
    
    def set_or_raise(self, setting:str, value:str):
        assert self.writeln(f"${setting}={value}").strip()=="ok", f"failed to set ${setting}={value}"
