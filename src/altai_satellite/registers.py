"""
SPDX-FileCopyrightText: 2025 DESY and the Constellation authors
SPDX-License-Identifier: EUPL-1.2
"""

from enum import IntEnum, unique

N_REGIONS = 32

@unique
class AltaiReg(IntEnum):
    #   NAME        =  addr
    COMMAND = 0x0000
    MODE_CTRL = 0x0001
    REGION_DISABLE1 = 0x0002
    REGION_DISABLE2 = 0x0003
    FROMU_CONF1 = 0x0004
    FROMU_CONF2 = 0x0005
    FROMU_CONF3 = 0x0006
    FROMU_PULSING1 = 0x0007
    FROMU_PULSING2 = 0x0008
    FROMU_STATUS1 = 0x0009
    FROMU_STATUS2 = 0x000A
    FROMU_STATUS3 = 0x000B
    FROMU_STATUS4 = 0x000C
    FROMU_STATUS5 = 0x000D
    DAC_CLK = 0x000E
    DAC_CMU = 0x000F
    CMU_DUM_CONFIG = 0x0010
    CMU_ERROR = 0x0011
    DMU_FIFO_LSB = 0x0012
    DMU_FIFO_MSB = 0x0013
    BUSY_MIN_WIDTH = 0x001B
    ANALOG_OVERRIDE = 0x0600
    VRESETP = 0x0601
    VRESETD = 0x0602
    VCASP = 0x0603
    VCASN = 0x0604
    VPULSEH = 0x0605
    VPULSEL = 0x0606
    VCASN2 = 0x0607
    VCLIP = 0x0608
    VTEMP = 0x0609
    IAUX2 = 0x060A
    IRESET = 0x060B
    IDB = 0x060C
    IBIAS = 0x060D
    ITHR = 0x060E
    BUFFER_BYPASS = 0x060F
    SEU_COUNTER = 0x0700
    TEST_CONTROL = 0x0701

@unique
class AltaiCmd(IntEnum):
    GRST = 0xD2
    PRST = 0xE4
    RORST = 0x63


def dc_disable(region: int) -> int:
    return region << 11 | 0x300


def region_status(region: int) -> int:
    return region << 11 | 0x301


# Reading the DMU FIFO pops data, so it must never be dumped.
_NOT_DUMPED = {AltaiReg.DMU_FIFO_LSB, AltaiReg.DMU_FIFO_MSB}


def dump_addresses() -> dict[str, int]:
    """Registers recorded in BOR/EOR (side-effect-free reads only)."""
    addresses = {reg.name: reg.value for reg in AltaiReg if reg not in _NOT_DUMPED}
    for region in range(N_REGIONS):
        addresses[f"DC_DISABLE_{region}"] = dc_disable(region)
        addresses[f"REGION_STATUS_{region}"] = region_status(region)
    return addresses