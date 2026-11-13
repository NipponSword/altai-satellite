import threading
from alpidedaqboard import ALPIDEBoard
from .registers import AltaiReg, AltaiCmd, dump_addresses

class AltaiDaqBoard:
    def __init__(self, conf) -> None:
        self.serial = conf["serial"] # ok = None
        self.chipid = conf["chipid"] if conf["chipid"] else 0x10
        self.strblen = None
        self.rdomode = None
        self.triggermode = conf["triggermode"]
        if self.triggermode not in ["primary", "replica"]:
            raise ValueError('need to specify trigger mode to be either "primary" or "replica"')

        self._daqboard = ALPIDEBoard(serial)
        self._lock = threading.Lock()

    def power_on(self) -> None:
        with self._lock:
            self._daqboard.power_on()

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
            self._daqboard.alpide_cmd_issue(0xD2)  # GRST

            # now for monitoring, also start clean
            self._clear_minitors()

    def _clear_monitors(self) -> None:
        self._daqboard.rdopar.clr.issue()
        self._daqboard.trgmon.clr.issue()

    def configure(self, conf: dict) -> None:
        with self._lock:
            if "VCASN" in conf:
                self._daqboard.alpide_reg_write(0x604, int(conf["VCASN"]), chipid=self.chipid)
            if "VCASN2" in conf:
                self._daqboard.alpide_reg_write(0x607, int(conf["VCASN2"]), chipid=self.chipid)
            if "ITHR" in conf:
                self._daqboard.alpide_reg_write(0x60E, int(conf["ITHR"]), chipid=self.chipid)
            if "VCLIP" in conf:
                self._daqboard.alpide_reg_write(0x608, int(conf["VCLIP"]), chipid=self.chipid)
            if "IDB" in conf:
                self._daqboard.alpide_reg_write(0x60C, int(conf["IDB"]), chipid=self.chipid)
            self._daqboard.alpide_reg_write(0x602, int(conf["VRESETD"]), chipid=self.chipid)

            self.chipid = int(conf["CHIPID"])

            self.strblen = int(conf["STROBE_LENGTH"])
            self.rdomode = conf["RDOMODE"]

            self._daqboard.alpide_cmd_issue(0xE4)  # PRST
            self._daqboard.alpide_reg_write(
                0x0004, 0x0060, chipid=self.chipid
            )  # disable busy monitoring, analog test pulse, enable test strobe
            self._daqboard.alpide_reg_write(0x0005, self.strblen, chipid=self.chipid)  # strobe length
            self._daqboard.alpide_reg_write(
                0x0010, 0x0030, chipid=self.chipid
            )  # initial token, SDR, disable manchester, previous token == self!!!
            self._daqboard.alpide_cmd_issue(0x63)  # RORST (needed!!!)

            if self.rdomode == "DCTRL":
                self._daqboard.alpide_reg_write(0x0001, 0x020D, chipid=self.chipid)  # normal readout, TRG mode, CMU RDO
                self._daqboard.rdoctrl.delay_set.write(
                    2 * self.strblen + 100
                )  # when to start reading (@80MHz, i.e. at least strobe-time x2 + sth.) ... TODO
                self._daqboard.rdoctrl.chipid.write(self.chipid)
                self._daqboard.rdoctrl.ctrl.write(1)  # enable DCTRL RDO
                self._daqboard.rdomux.ctrl.write(2)  # select DCTRL RDO
            elif self.rdomode == "DATAPORT":
                self._daqboard.alpide_reg_write(0x0001, 0x000D, chipid=self.chipid)  # normal readout, TRG mode
                self._daqboard.rdopar.ctrl.write(1)  # enable parallel port RDO
                self._daqboard.rdomux.ctrl.write(1)  # select parallel port RDO
                self._daqboard.xonxoff.ctrl.write(1)  # enable XON XOFF
            else:
                raise ValueError('RDOMODE "%s" not understood' % self.rdomode)

            self._daqboard.trg.minspacing.write(int(conf["minspacing"]) if "minspacing" in conf else 0)
            self._daqboard.trg.fixedbusy.write(int(conf["fixedbusy"]) if "fixedbusy" in conf else 0)

    def stop_trigger(self) -> None:
        with self._lock:
            if self.triggermode == "primary":
                self._daqboard.trg.ctrl.write(0b1001)  # primary mode, no maskig of external trigger or busy, force busy
                # TODO: needs to go out:
                self._daqboard.trgseq.stop.issue()
            elif self.triggermode == "replica":
                self._daqboard.trg.ctrl.write(0b0001)  # replica mode, no masking, force busy
        
    def arm_trigger(self) -> None:
        with self._lock:
            if self.triggermode == "primary":
                self._daqboard.trg.ctrl.write(0b1000)  # primary mode, no maskig of external trigger or busy, no forced busy (anymore)
                # TODO: needs to go out:
                self._daqboard.trgseq.dt_set.write(8000)  # 10 kHz
                self._daqboard.trgseq.ntrg_set.write(300)
            elif self.triggermode == "replica":
                self._daqboard.trg.ctrl.write(0b0000)  # replica mode, no masking, no forced busy (anymore)
    
    def read_event(self) -> int:
        with self._lock:
            self._daqboard.event_read()

    def get_power_status(self) -> tuple[float, float, bool]:
        with self._lock:
            idda, iddd, status = self._daqboard.power_status()
        return idda, iddd, status

    def get_carrier_temp(self) -> float:
        with self._lock:
            temp = self._daqboard.carrier_temp()
        return temp

    def dump_registers(self) -> dict:
        with self._lock:
            return {reg.name : self._daqboard.alpide_reg_read(addr, chipid=self.chipid) for reg, addr in dump_addresses().items()}