"""
SPDX-FileCopyrightText: 2025 DESY and the Constellation authors
SPDX-License-Identifier: EUPL-1.2
"""

# pyright: reportAttributeAccessIssue=false

from constellation.core.transmitter_satellite import TransmitterSatellite
from constellation.core.configuration import Configuration, enum_type
from constellation.core.monitoring import schedule_metric
from constellation.core.protocol.cscp1 import SatelliteState

from . import __version__
from .daq import AltaiDaqBoard, TriggerMode, RdoMode
from datetime import datetime
from time import sleep
import subprocess
import threading




class Altai(TransmitterSatellite, version=__version__):

    daq: AltaiDaqBoard
    conf: dict

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.daq = None
        self.conf = None

    def do_initializing(self, config: Configuration) -> str:
        conf = self._read_config(config)
        self.daq = AltaiDaqBoard(conf)
        self.daq.stop_trigger()

        return "Do initializing complete"

    def do_launching(self) -> str:
        self.daq.stop_trigger()
        self.daq.power_on()
        self.daq.reset()
        self.daq.configure(self.conf)

        return "Do launching complete"

    def do_landing(self):
        self.daq.power_off()
        return "Do landing complete"

    def do_starting(self, run_identifer: str) -> str:
        self.send_status_event(datetime.now(), bore=True)
        self.daq.arm_trigger()

        for key, value in self.daq.get_info4bor().items():
            self.bor[key] = value

        for key, value in self.daq.dump_registers().items():
            self.bor[key] = value

        for key, value in self.daq.read_trigger_monitor().items():
            self.bor[key] = value

        return "Do starting complete"

    def do_run(self) -> str:
        # status events: roughly every 10s (time checked at least every 1000 events or at receive timeout)

        while not self.stop_requested:
            self._read_and_send_event()

        return "Do running complete"

    def do_stopping(self) -> str:
                
        self.daq.stop_trigger()

        while self.read_and_send_event():
            self.log.info("Reading remining events...")

        for key, value in self.daq.dump_registers().items():
            self.eor[key] = value

        for key, value in self.daq.read_trigger_monitor().items():
            self.eor[key] = value
        
        return "Do stopping complete"


    # TODO : replace to metrics
    # def send_status_event(self, time, bore=False, eore=False):
    #     ev = pyeudaq.Event("RawEvent", self.name + "_status")
    #     idda, iddd, status = self.daq.get_power_status()
    #     temp = self.daq.get_carrier_temp()
    #     ev.SetTag("IDDA", "%.2f mA" % idda)
    #     ev.SetTag("IDDD", "%.2f mA" % iddd)
    #     ev.SetTag("Temperature", "%.2f C" % temp if temp else "Invalid temperature read!")
    #     ev.SetTag("Event", "%d" % self.idev)
    #     ev.SetTag("Time", time.isoformat())
    #     self.SendEvent(ev)

    def _read_and_send_event(self) -> bool:

        raw = self.daq.read_event()
        if raw:
            raw = bytes(raw)
            assert len(raw) >= 20
            assert list(raw[:4]) == [0xAA] * 4
            assert list(raw[-4:]) == [0xBB] * 4
            itrg = sum(b << (j * 8) for j, b in enumerate(raw[4:8]))
            tev = sum(b << (j * 8) for j, b in enumerate(raw[8:16]))
            data_record = self.new_data_record(
                {
                    "RawEvent" : "ALPIDE", # TODO: Is this correct??
                    "TriggerN" : itrg,
                    "Timestamp": tev,       # TODO: check Corry or EUDAQ 
                    "DeviceN"  : self.daq.plane
                }
            )

            data_record.AddBlock(0, raw)
            self.semd_data_record(data_record)
            self.n_sent += 1
            return True
        else:
            return False

    def _read_config(self, config: Configuration) -> dict:
        
        config.set_default(key="status_interval", value=1.0)
        config.set_default(key="minspacing", value=0)
        config.set_default(key="fixedbusy", value=0)
        config.set_default(key="CHIPID", value=0x10)
        config.set_default(key="VRESETD", value=147)
        config.set_default(key="RDOMODE", value="DATAPORT")

        configuration = {
            "serial": config.get_str(key="serial",),
            "plane": config.get_int(key="plane"),
            "triggermode": config.get_enum(TriggerMode, key="triggermode"),
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
            "RDOMODE": config.get_enum(RdoMode, key="RDOMODE")
        }

        self.status_interval = config.get_float("status_interval")
        self.log.debug("Calculating status every %.3f s" % self.status_interval)
        
        return configuration