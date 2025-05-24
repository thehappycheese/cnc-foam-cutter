from math import pi
from .serial import CNC


def configure(cnc:CNC|None=None):

    if cnc is None:
        cnc = CNC()

    micro_steps                         = 8
    motor_steps_per_circle              = 200
    belt_axes_pulley_diameter_mm        = 12
    acme_screw_axes_advance_per_turn_mm = 8
    belt_axes_steps_per_mm              = motor_steps_per_circle * micro_steps / ( pi * belt_axes_pulley_diameter_mm )
    acme_screw_axes_steps_per_mm        = motor_steps_per_circle * micro_steps / acme_screw_axes_advance_per_turn_mm

    cnc.set_or_raise("X/Microsteps",f"{micro_steps}")
    cnc.set_or_raise("Y/Microsteps",f"{micro_steps}")
    cnc.set_or_raise("Z/Microsteps",f"{micro_steps}")
    cnc.set_or_raise("A/Microsteps",f"{micro_steps}")

    cnc.set_or_raise("X/StepsPerMm",f"{acme_screw_axes_steps_per_mm:.3f}")
    cnc.set_or_raise("Z/StepsPerMm",f"{acme_screw_axes_steps_per_mm:.3f}")

    cnc.set_or_raise("Y/StepsPerMm",f"{belt_axes_steps_per_mm:.3f}")
    cnc.set_or_raise("A/StepsPerMm",f"{belt_axes_steps_per_mm:.3f}")

    # cant do this without first installing all limit switches
    # write("$Limits/Invert=On\n")

    cnc.set_or_raise("X/Current/Run","0.8")
    cnc.set_or_raise("Y/Current/Run","0.8")
    cnc.set_or_raise("Z/Current/Run","0.8")
    cnc.set_or_raise("A/Current/Run","0.8")

    cnc.set_or_raise("X/Current/Hold","0.1")
    cnc.set_or_raise("Y/Current/Hold","0.1")
    cnc.set_or_raise("Z/Current/Hold","0.1")
    cnc.set_or_raise("A/Current/Hold","0.1")

    cnc.set_or_raise("Homing/Cycle0","YXAZ")
    cnc.set_or_raise("Homing/Cycle1","")
    cnc.set_or_raise("Homing/Cycle2","")
    cnc.set_or_raise("Homing/Cycle3","")
    cnc.set_or_raise("Homing/Cycle4","")
    cnc.set_or_raise("Homing/Cycle5","")


    cnc.set_or_raise("Homing/Enable","On")
    cnc.set_or_raise("Homing/DirInvert","YXZ")

    cnc.set_or_raise("Stepper/DirInvert","XZ")
    cnc.set_or_raise("Stepper/EnableInvert","On")