"""
SPDX-FileCopyrightText: 2025 DESY and the Constellation authors
SPDX-License-Identifier: EUPL-1.2
"""

from constellation.core.transmitter_satellite import TransmitterSatellite
from constellation.core.configuration import Configuration, enum_type
from constellation.core.monitoring import schedule_metric
from constellation.core.protocol.cscp1 import SatelliteState

from . import __version__
from .daq import AltaiDaqBoard
from datetime import datetime
from time import sleep
import subprocess
import threading


class Altai(TransmitterSatellite, version=__version__):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.daq = None
        self.conf = None
        self._lock = threading.RLock()

    def do_initializing(self, config: Configuration) -> str:
        conf = self._read_config()
        self.daq = AltaiDaqBoard(conf["serial"], conf["chipid"])
        self.plane = int(conf["plane"])
        self.stoptrigger()

        return "Do initializing complete"

    def do_launching(self) -> str:
        self.stoptrigger()
        self.daq.power_on()
        self.daq.reset()
        self.daq.configure(self.conf if self.conf else self._read_config)

        return "Do launching complete"

    def do_starting(self) -> str:
        self.idev = 0
        self.isev = 0
        self.send_status_event(datetime.now(), bore=True)
        self.isev += 1
        self.arm_trigger()

        return "Do starting complete"

    # ==============================

    def do_stopping(self) -> str:
        self.stoptrigger()

        return "Do stopping complete"

    #
    # TODO: which one ↑↓ ???
    #

    def do_landing(self):
        self.stoptrigger()
        
        return "Do landing complete"

    # ==============================

    def DoStatus(self): # TODO: this should be replaced to ??
        self.SetStatusTag("StatusEventN", "%d" % self.isev)
        self.SetStatusTag("DataEventN", "%d" % self.idev)

    def do_run(self) -> str:
        # status events: roughly every 10s (time checked at least every 1000 events or at receive timeout)

        while self.stop_requested:
            self.read_and_send_event()
        
        while self.read_and_send_event():
            self.log.info("Reading remining events...")

        return "Do running complete"

    def send_status_event(self, time, bore=False, eore=False):
        ev = pyeudaq.Event("RawEvent", self.name + "_status")
        idda, iddd, status = self.daq.get_power_status()
        temp = self.daq.get_carrier_temp()
        ev.SetTag("IDDA", "%.2f mA" % idda)
        ev.SetTag("IDDD", "%.2f mA" % iddd)
        ev.SetTag("Temperature", "%.2f C" % temp if temp else "Invalid temperature read!")
        ev.SetTag("Event", "%d" % self.idev)
        ev.SetTag("Time", time.isoformat())
        if bore:
            ev.SetBORE()
            ev.SetTag("FPGA_GIT", self.daq.get_fpga_git())
            ev.SetTag("FPGA_COMPILE", self.daq.get_fpga_tcompile().isoformat())
            # ev.SetTag('FX3_GIT'     ,self.daq.get_fx3_git())
            # ev.SetTag('FX3_COMPILE' ,self.daq.get_fx3_tcompile().isoformat())
            git = subprocess.check_output(["git", "rev-parse", "HEAD"]).strip()
            diff = subprocess.check_output(["git", "diff"])
            ev.SetTag("EUDAQ_GIT", git)
            ev.SetTag("EUDAQ_DIFF", diff)
            ev.SetTag("ALPIDEDAQ_GIT", self.daq.get_software_git())
            ev.SetTag("ALPIDEDAQ_DIFF", self.daq.get_software_diff())
        if eore:
            ev.SetEORE()
        if bore or eore:
            dumpe_result = self.daq.dump_registers()
            for regs in dump_result:
                ev.SetTag("ALPIDE_%s" % reg.key(), "%d" % regs.value())
            self.daq.trgmon.lat.issue()
            for reg in self.daq.trgmon.regs:
                ev.SetTag("TRGMON_" + reg.upper(), "%d" % self.daq.trgmon.regs[reg].read())
        self.SendEvent(ev)

    def read_and_send_event(self):
        raw = self.daq.read_event()
        if raw:
            raw = bytes(raw)
            assert len(raw) >= 20
            assert list(raw[:4]) == [0xAA] * 4
            assert list(raw[-4:]) == [0xBB] * 4
            itrg = sum(b << (j * 8) for j, b in enumerate(raw[4:8]))
            tev = sum(b << (j * 8) for j, b in enumerate(raw[8:16]))
            ev = pyeudaq.Event("RawEvent", self.name)
            ev.SetTriggerN(itrg)  # clarification: itrg is the event number form the DAQ board
            ev.SetTimestamp(begin=tev, end=tev)
            ev.SetDeviceN(self.plane)
            ev.AddBlock(0, raw)
            self.SendEvent(ev)
            self.idev += 1
            return True
        else:
            return False

    def _read_config(self, config: Configuration) -> dict[str, Any]:
        
        config.set_default(key="status_interval", value=1.0)
        config.set_default(key="CHIPID", value=0x10)
        config.set_default(key="VRESETD", value=147)
        config.set_default(key="RDOMODE", value="DATAPORT")

        configuration = {
            "serial": config.get_str(key="serial",),
            "plane": config.get_int(key="plane"),
            "triggermode": config.get_str(key="triggermode"),
            "minspacing": config.get_int(key="minspacing"),
            "fixedbusy": config.get_int(key="fixedbusy"),
            "CHIPID": config.get_int(key="CHIPID"),
            "VCASN": config.get_int(key="VCASN"),
            "VCASN2": config.get_int(key="VCASN2"),
            "ITHR": config.get_int(key="ITHR"),
            "VCLIP": config.get_int(key="VCLIP"),
            "IDB": config.get_int(key="IDB"),
            "VRESETD": config.get_int(key="VRESETD"),
            "STROBE_LENGTH": config.get_int(key="STROBE_LENGTH"),
            "RDOMODE": config.get_str(key="RDOMODE")
        }

        self.status_interval = config.get_float("status_interval")
        self.log.debug("Calculating status every %.3f s" % self.status_interval)
        
        return configuration

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description="ALPIDE EUDAQ2 Producer", formatter_class=argparse.ArgumentDefaultsHelpFormatter
    )
    parser.add_argument("--run-control", "-r", default="tcp://localhost:44000")
    parser.add_argument("--name", "-n", default="ALPIDE_XXX")
    args = parser.parse_args()

    myproducer = ALPIDEProducer(args.name, args.run_control)
    myproducer.Connect()
    while myproducer.IsConnected():
        sleep(1)
