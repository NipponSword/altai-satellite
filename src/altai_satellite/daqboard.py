"""
SPDX-FileCopyrightText: 2025 DESY and the Constellation authors
SPDX-License-Identifier: EUPL-1.2
"""

# pyright: reportAttributeAccessIssue=false

import threading
from enum import StrEnum

from alpidedaqboard import ALPIDEDAQBoard

from .registers import AltaiCmd, AltaiReg, dump_addresses


class TriggerMode(StrEnum):
    """Trigger mode configuration
    """
    PRIMARY = "primary"
    REPLICA = "replica"

class RdoMode(StrEnum):
    """Readout mode configuration
    """
    DCTRL = "dctrl"
    DATAPORT = "dataport"

class AltaiDaqBoard:
    def __init__(self, conf: dict) -> None:
        """ini

        Args:
            conf (dict): dict configuration
        """
        self.serial = conf["serial"]
        self.chipid = conf["chip_id"]
        self.plane  = conf["plane"]
        self.strblen = None
        self.rdomode = None
        self.triggermode = conf["trigger_mode"]

        self._daqboard = ALPIDEDAQBoard(self.serial, verbose=False)
        self._lock = threading.Lock()

    def close(self) -> None:
        """close USB handle
        """
        with self._lock:
            self._daqboard.dispose()

    def power_on(self) -> None:
        """ALTAI power on
        """
        with self._lock:
            self._daqboard.power_on()

    def power_off(self) -> None:
        """ALTAI power off
        """
        with self._lock:
            self._daqboard.power_off()

    def reset(self) -> None:
        """reset settings
        """
        with self._lock:
            self._daqboard.trg.opcode.write(0x55)
            self._daqboard.rdoctrl.rst.issue()
            self._daqboard.rdopar.rst.issue()
            self._daqboard.evtpkr.rst.issue()
            self._daqboard.evtbld.rst.issue()
            self._daqboard.trg.rstrdobsy.issue()
            
            self._daqboard.purge_events()
            self._daqboard.xonxoff.rst.issue()

            # ...or the ALPIDE...
            self._daqboard.alpide_cmd_issue(AltaiCmd.GRST)

            # now for monitoring, also start clean
            self._clear_monitors()

    def _clear_monitors(self) -> None:
        """reset monitor
        """
        self._daqboard.rdopar.clr.issue()
        self._daqboard.trgmon.clr.issue()

    def configure(self, conf: dict) -> None:
        """lets configure

        Args:
            conf (dict): configuration

        Raises:
            ValueError: incorrect settings
        """
        with self._lock:
            self._daqboard.alpide_reg_write(
                AltaiReg.VCASN,
                int(conf["vcasn"]),
                chipid=self.chipid
            )
            self._daqboard.alpide_reg_write(
                AltaiReg.VCASN2,
                int(conf["vcasn2"]),
                chipid=self.chipid
            )
            self._daqboard.alpide_reg_write(
                AltaiReg.ITHR,
                int(conf["ithr"]),
                chipid=self.chipid
            )
            self._daqboard.alpide_reg_write(
                AltaiReg.VCLIP,
                int(conf["vclip"]),
                chipid=self.chipid
            )
            self._daqboard.alpide_reg_write(
                AltaiReg.IDB,
                int(conf["idb"]),
                chipid=self.chipid
            )
            self._daqboard.alpide_reg_write(
                AltaiReg.VRESETD,
                int(conf["vresetd"]),
                chipid=self.chipid
            )

            self.strblen = int(conf["strobe_length"])
            self.rdomode = conf["rdo_mode"]

            self._daqboard.alpide_cmd_issue(AltaiCmd.PRST)
            self._daqboard.alpide_reg_write(
                AltaiReg.FROMU_CONF1,
                0x0060,
                chipid=self.chipid
            )  # disable busy monitoring, analog test pulse, enable test strobe
            self._daqboard.alpide_reg_write(
                AltaiReg.FROMU_CONF2,
                self.strblen,
                chipid=self.chipid
                )
            self._daqboard.alpide_reg_write(
                AltaiReg.CMU_DUM_CONFIG,
                0x0030,
                chipid=self.chipid
            )  # initial token, SDR, disable manchester, previous token == self!!!

            self._daqboard.alpide_cmd_issue(AltaiCmd.RORST)  # (needed!!!)

            if self.rdomode == RdoMode.DCTRL:
                self._daqboard.alpide_reg_write(
                    AltaiReg.MODE_CTRL,
                    0x020D,
                    chipid=self.chipid
                    )  # normal readout, TRG mode, CMU RDO
                self._daqboard.rdoctrl.delay_set.write(
                    2 * self.strblen + 100
                )  # when to start reading (@80MHz, i.e. at least strobe-time x2 + sth.) ... TODO
                self._daqboard.rdoctrl.chipid.write(self.chipid)
                self._daqboard.rdoctrl.ctrl.write(1)  # enable DCTRL RDO
                self._daqboard.rdomux.ctrl.write(2)  # select DCTRL RDO
            elif self.rdomode == RdoMode.DATAPORT:
                self._daqboard.alpide_reg_write(
                    AltaiReg.MODE_CTRL,
                    0x000D,
                    chipid=self.chipid
                    )  # normal readout, TRG mode
                self._daqboard.rdopar.ctrl.write(1)  # enable parallel port RDO
                self._daqboard.rdomux.ctrl.write(1)  # select parallel port RDO
                self._daqboard.xonxoff.ctrl.write(1)  # enable XON XOFF
            else:
                raise ValueError(f"rdo_mode {self.rdomode} not understood")

            self._daqboard.trg.minspacing.write(int(conf["min_spacing"]))
            self._daqboard.trg.fixedbusy.write(int(conf["fixed_busy"]))

    def stop_trigger(self) -> None:
        """ stop trigger rcv
        """
        with self._lock:
            if self.triggermode == TriggerMode.PRIMARY:
                self._daqboard.trg.ctrl.write(0b1001)  # primary mode, no maskig of external trigger or busy, force busy
                # TODO: needs to go out:
                self._daqboard.trgseq.stop.issue()
            elif self.triggermode == TriggerMode.REPLICA:
                self._daqboard.trg.ctrl.write(0b0001)  # replica mode, no masking, force busy
        
    def arm_trigger(self) -> None:
        """start trigger
        """
        with self._lock:
            if self.triggermode == TriggerMode.PRIMARY:
                # primary mode, no maskig of external trigger or busy, no forced busy (anymore)
                self._daqboard.trg.ctrl.write(0b1000)
                # TODO: needs to go out:
                self._daqboard.trgseq.dt_set.write(8000)  # 10 kHz
                self._daqboard.trgseq.ntrg_set.write(300)
            elif self.triggermode == TriggerMode.REPLICA:
                self._daqboard.trg.ctrl.write(0b0000)  # replica mode, no masking, no forced busy (anymore)
    
    def read_event(self) -> bytes | None:
        """read a ALTAI hit event

        Returns:
            bytes | None: raw data
        """
        with self._lock:
            raw =  self._daqboard.event_read()

        return bytes(raw) if raw else None
    
    def get_power_status(self) -> tuple[float, float, bool]:
        """read register and get power status

        Returns:
            tuple[float, float, bool]: value of idda, iddd, status
        """
        with self._lock:
            idda, iddd, status = self._daqboard.power_status()

        return idda, iddd, status

    def is_powered(self) -> bool:
        """check if ALTAI is not latched up

        Returns:
            bool: if False, ALTAI powered off
        """
        return self.get_power_status()[2]

    def get_carrier_temp(self) -> float | None:
        """read register and get temperature

        Returns:
            float | None: value of temparature
        """
        with self._lock:
            temp = self._daqboard.carrier_temp()

        return temp

    def dump_registers(self) -> dict:
        """dump current registers to dictionary

        Returns:
            dict: register values
        """
        with self._lock:
            return {
                f"ALPIDE_{addr:04x}_{name}": self._daqboard.alpide_reg_read(
                    addr,chipid=self.chipid
                )
                for name, addr in dump_addresses().items()
            }

    def get_firmware_info(self) -> dict:
        """get firmware and software information

        Returns:
            dict: value of git and compile information
        """
        with self._lock:
            info = {
                "FPGA_GIT": self._daqboard.get_fpga_git(),
                "FPGA_COMPILE": self._daqboard.get_fpga_tcompile().isoformat()
            }
            try:
                info["ALPIDEDAQ_GIT"] = _as_text(self._daqboard.get_software_git())
                info["ALPIDEDAQ_DIFF"] = _as_text(self._daqboard.get_software_diff())
            except OSError:
                info["ALPIDEDAQ_GIT"] = "unknown"
        
        return info

    def read_trigger_monitor(self) -> dict[str, int]:
        """Latch and read the firmware trigger-monitor counters
        """
        with self._lock:
            self._daqboard.trgmon.lat.issue()
            return {f"TRGMON_{name.upper()}": reg.read() for name, reg in self._daqboard.trgmon.regs.items()}

# --- end module class 

def _as_text(value: bytes | str) -> str:
    return value.decode(errors="replace") if isinstance(value, bytes) else value