import serial
from serial import Serial
import time

class CNC:
    serial:Serial

    def __init__(self, addr="socket://fluidnc.local:23", timeout:float|None=0.2):
        self.serial = serial.serial_for_url(addr, timeout=timeout)

    def read_all(self)->str:
        buff = b""
        while self.serial.in_waiting:
            resp = self.serial.read_all()
            if resp is not None:
                buff += resp
        return buff.decode("ascii")

    def write_read_all(self, message:str) -> str:
        self.serial.write(message.encode("ascii"))
        #time.sleep(0.200)
        return self.serial.read_until().decode("ascii")
    
    def write_read_line(self, message:str) -> str:
        self.serial.write(message.encode("ascii"))
        return self.serial.readline().decode("ascii").strip()

    def writeln(self, message:str) -> str:
        return self.write_read_all(message+"\n")

    def alarm_clear(self):
        return self.writeln("$X")
    
    def alarm_soft_reset(self):
        return self.writeln("\x18")
    
    def alarm_reset_clear(self):
        return self.writeln("\x18\r\n$X")
    
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
    
    def set_current(self, current:float):
        MAX = 4
        MIN = 0
        if current<MIN:
            print("M3 S5")
            return self.writeln("M3 S5")
        
        portion = (current-MIN)/(MAX-MIN)
        pwm_percent = (portion*0.8+0.1)*100
        print(f"M3 S{pwm_percent:.0f}")
        return self.writeln(f"M3 S{pwm_percent:.1f}")
    
    def home(self):
        return self.writeln("$H")
    
    def set_position(self, x:float, y:float, z:float, a:float):
        """set the postion without moving the machine."""
        return self.writeln(f"G92 X{x} Y{y} Z{z} A{a}")
    
    def travel(self, x:float, y:float, z:float, a:float):
        """G0"""
        return self.writeln(f"G0 X{x} Y{y} Z{z} A{a}")
    
    def feed(self, rate:float, x:float, y:float,z:float,a:float):
        """
        TODO: feedrate is not compensated 
        see .util.path_planning.compensate_feedrate
        """
        return self.writeln(f"G1 F{rate} X{x} Y{y} Z{z} A{a}")
    
    def dwel(self, time_seconds:float):
        """G4 Px.x"""
        return self.writeln(f"G4 P{time_seconds:.3f}")
    
    def metric(self):
        return self.writeln("G21")

    def send_g1_commands(self, command_list: list) -> bool:
        """
        Sends multiple G1 commands and waits for 'ok' response after each one.
        
        TODO: feedrate is not compensated 
        see .util.path_planning.compensate_feedrate

        Args:
            command_list: List of 5-element lists [feed, x, y, z, a] where:
                        - feed: Feed rate
                        - x: X coordinate
                        - y: Y coordinate  
                        - z: Z coordinate
                        - a: A coordinate
            
        Returns:
            bool: True if all commands were sent and acknowledged successfully
        """
        success = True

        for feed, x, y, z, a in command_list:
            # Format G1 command with all coordinates
            command = f"G1 F{feed} X{x} Y{y} Z{z} A{a}\n"
            
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

    def send_g1_xy_commands(self, xy_tuples: list, feed:int) -> bool:
        """
        Sends multiple G1 XY commands and waits for 'ok' response after each one.
        
        TODO: feedrate is not compensated 
        see .util.path_planning.compensate_feedrate

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

    def send_gcode_lines(self, gcode:list[str], timeout_seconds=20):
        """lines should not be terminated with `"\r\n"` as this will be automatically added"""
        log = ""
        time.sleep(0.1)
        self.read_all()
        time.sleep(0.1)
        self.read_all()
        time.sleep(0.1)
        success = True
        for gc in gcode:
            command = (gc+"\r\n").encode("ascii")
            self.serial.write(command)
            log += command.decode("ascii")

            response = ""
            start_time = time.time()
            while "ok\r\n" not in response:
                if self.serial.in_waiting:
                    new_data = self.serial.read(self.serial.in_waiting).decode("ascii")
                    response += new_data
                    log      += new_data
                
                # Check for timeout
                if time.time() - start_time > timeout_seconds:
                    print(f"Timeout waiting for 'ok' after command: {gc.strip()}")
                    success = False
                    #break
                    
                # Small delay to prevent CPU hogging
                time.sleep(0.01)
            # if not success:
            #     break
        if not success:
            # cnc.alarm_clear()
            # cnc.alarm_soft_reset()
            # cnc.alarm_clear()
            # cnc.alarm_soft_reset()
            log+="FAILED\r\n"
            self.serial.write("M3 S0\r\n".encode("ascii"))
        return log
