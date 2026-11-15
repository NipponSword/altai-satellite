"""
SPDX-FileCopyrightText: 2025 DESY and the Constellation authors
SPDX-License-Identifier: EUPL-1.2
"""

# pyright: reportAttributeAccessIssue=false

import threading
from alpidedaqboard import ALPIDEDAQBoard
from enum import StrEnum
from .registers import AltaiReg, AltaiCmd, dump_addresses

class TriggerMode(StrEnum):
    PRIMARY = "primary"
    REPLICA = "replica"

class RdoMode(StrEnum):
    DCTRL = "dctrl"
    DATAPORT = "dataport"

class AltaiDaqBoard:
    def __init__(self, conf) -> None:
        self.serial = conf["serial"] # ok = None
        self.chipid = conf["chip_id"] if conf["chip_id"] else 0x10
        self.plane  = conf["plane"]
        self.strblen = None
        self.rdomode = None
        self.triggermode = conf["trigger_mode"]

        self._daqboard = ALPIDEDAQBoard(self.serial)
        self._lock = threading.Lock()

    def power_on(self) -> None:
        with self._lock:
            self._daqboard.power_on()

    def power_off(self) -> None:
        with self._lock:
            self._daqboard.power_off()

    def reset(self) -> None:
        with self._lock:
            # just in case we got up on the wrong side of the fw...
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
        self._daqboard.rdopar.clr.issue()
        self._daqboard.trgmon.clr.issue()

    def configure(self, conf: dict) -> None:
        with self._lock:
            if "vcasn" in conf:
                self._daqboard.alpide_reg_write(
                    AltaiReg.VCASN,
                    int(conf["vcasn"]),
                    chipid=self.chipid
                )
            if "vcasn2" in conf:
                self._daqboard.alpide_reg_write(
                    AltaiReg.VCASN2,
                    int(conf["vcasn2"]),
                    chipid=self.chipid
                )
            if "ithr" in conf:
                self._daqboard.alpide_reg_write(
                    AltaiReg.ITHR,
                    int(conf["ithr"]),
                    chipid=self.chipid
                )
            if "vclip" in conf:
                self._daqboard.alpide_reg_write(
                    AltaiReg.VCLIP,
                    int(conf["vclip"]),
                    chipid=self.chipid
                )
            if "idb" in conf:
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

            self.chipid = int(conf["chip_id"])

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
                raise ValueError('rdo_mode "%s" not understood' % self.rdomode)

            self._daqboard.trg.minspacing.write(int(conf["min_spacing"]))
            self._daqboard.trg.fixedbusy.write(int(conf["fixed_busy"]))

    def stop_trigger(self) -> None:
        with self._lock:
            if self.triggermode == TriggerMode.PRIMARY:
                self._daqboard.trg.ctrl.write(0b1001)  # primary mode, no maskig of external trigger or busy, force busy
                # TODO: needs to go out:
                self._daqboard.trgseq.stop.issue()
            elif self.triggermode == TriggerMode.REPLICA:
                self._daqboard.trg.ctrl.write(0b0001)  # replica mode, no masking, force busy
        
    def arm_trigger(self) -> None:
        with self._lock:
            if self.triggermode == TriggerMode.PRIMARY:
                self._daqboard.trg.ctrl.write(0b1000)  # primary mode, no maskig of external trigger or busy, no forced busy (anymore)
                # TODO: needs to go out:
                self._daqboard.trgseq.dt_set.write(8000)  # 10 kHz
                self._daqboard.trgseq.ntrg_set.write(300)
            elif self.triggermode == TriggerMode.REPLICA:
                self._daqboard.trg.ctrl.write(0b0000)  # replica mode, no masking, no forced busy (anymore)
    
    def read_event(self) -> bytes | None:
        with self._lock:
            return self._daqboard.event_read() 
    
    def get_power_status(self) -> tuple[float, float, bool]:
        with self._lock:
            idda, iddd, status = self._daqboard.power_status()

        return idda, iddd, status

    def get_carrier_temp(self) -> float | None:
        with self._lock:
            temp = self._daqboard.carrier_temp()

        return temp

    def dump_registers(self) -> dict:
        with self._lock:
            return {"ALPIDE_%04x_%s" % (addr,name): self.daq.alpide_reg_read(addr,chipid=self.chipid) for name, addr in dump_addresses().items()}

    def get_firmware_info(self) -> dict:
        with self._lock():
            fpga_git = self._daqboard.get_fpga_git()
            fpga_compile = self._daqboard.get_fpga_tcompile()
            alpidedaq_git = self._daqboard.get_software_git()
            alpidedaq_diff = self._daqboard.get_software_diff()

        return {"FPGA_FIT": fpga_git, 
                "FPGA_COMPILE": fpga_compile.iso_format(),
                "ALPIDEDAQ_GIT": alpidedaq_git,
                "ALPIDEDAQ_DIFF": alpidedaq_diff}

    def read_trigger_monitor(self) -> dict[str, int]:
        """Latch and read the firmware trigger-monitor counters."""
        with self._lock:
            self._daqboard.trgmon.lat.issue()
            return {"TRGMON_ " + name.upper(): reg.read() for name, reg in self.daq.trgmon.regs.items()}