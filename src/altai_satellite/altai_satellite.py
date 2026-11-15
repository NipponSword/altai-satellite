"""
SPDX-FileCopyrightText: 2025 DESY and the Constellation authors
SPDX-License-Identifier: EUPL-1.2
"""

from constellation.core.transmitter_satellite import TransmitterSatellite
from constellation.core.configuration import Configuration, enum_type
from constellation.core.monitoring import schedule_metric
from constellation.core.protocol.cscp1 import SatelliteState

from . import __version__
from .daq import AltaiDaqBoard, TriggerMode, RdoMode

class Altai(TransmitterSatellite, version=__version__):

    daq: AltaiDaqBoard
    conf: dict

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.trigger_id = 0
    
    # =========================================
    # Constellation methods
    # =========================================

    def do_initializing(self, config: Configuration) -> str:
        self.conf = self._read_config(config)
        self.daq = AltaiDaqBoard(self.conf)
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

        self.bor = (
            {"eudaq_evet": "ALPIDE"} |
            {"write_as_block": True} |
            self.daq.get_firmware_info() |
            self.daq.dump_registers() |
            self.daq.read_trigger_monitor()
        )

        self.daq.arm_trigger()

        return "Do starting complete"

    def do_run(self) -> str:
        # status events: roughly every 10s (time checked at least every 1000 events or at receive timeout)

        while not self.stop_requested():
            self._read_and_send_event()

        return "Do running complete"

    def do_stopping(self) -> str:
                
        self.daq.stop_trigger()

        while self._read_and_send_event():
            self.log.info("Reading remining events...")

        self.eor = (
            self.daq.dump_registers() |
            self.daq.read_trigger_monitor()
        )
        
        return "Do stopping complete"

    # =========================================
    # Metrics
    # =========================================

    @schedule_metric("mA", 5, [SatelliteState.RUN])
    def idda(self) -> float | None:
        return self.daq.get_power_status()[0]

    @schedule_metric("mA", 5, [SatelliteState.RUN])
    def iddd(self) -> float | None:
        return self.daq.get_power_status()[1]
    
    @schedule_metric("", 5, [SatelliteState.RUN])
    def temperature(self) -> float | None:
        return self.daq.get_carrier_temp()

    @schedule_metric("", 5, [SatelliteState.RUN])
    def trigger_id(self) -> int | None:
        return self.trigger_id

    # =========================================
    # Utils
    # =========================================

    def _read_and_send_event(self) -> bool:

        raw = self.daq.read_event()
        if raw:
            itrg, tev = self._parse_header(bytes(raw))
            
            data_record = self.new_data_record(
                {
                    "trigger_number" : itrg,
                    "timestamp_begin": tev * 1000, # ns -> ps
                    "timestamp_end"  : tev * 1000, # ns -> ps
                    "device_number"  : self.daq.plane
                }
            )
            data_record.add_block(0, raw)
            self.semd_data_record(data_record)
            self.trigger_id = int(itrg)

            return True
        else:
            return False

    def _parse_header(self, raw: bytes) -> tuple(int, int):
        
        header_is_correct = (
            len(raw) >= 20 and
            list(raw[:4]) == [0xAA] * 4 and
            list(raw[-4:]) == [0xBB] * 4
        )

        if not header_is_correct :
            raise ValueError("Invalid data format")

        itrg = sum(b << (j * 8) for j, b in enumerate(raw[4:8]))
        tev = sum(b << (j * 8) for j, b in enumerate(raw[8:16]))

        return itrg, tev

    def _read_config(self, config: Configuration) -> dict:
        
        config.set_default(key="status_interval", value=1.0)
        config.set_default(key="min_spacing", value=0)
        config.set_default(key="fixed_busy", value=0)
        config.set_default(key="chip_id", value=0x10)
        config.set_default(key="vresetd", value=147)
        config.set_default(key="rdo_mode", value=RdoMode.DATAPORT)

        configuration = {
            "serial": config.get_str(key="serial",),
            "plane": config.get_int(key="plane"),
            "trigger_mode": config.get_enum(TriggerMode, key="trigger_mode"),
            "min_spacing": config.get_int(key="min_spacing"),
            "fixed_busy": config.get_int(key="fixed_busy"),
            "chip_id": config.get_int(key="chip_id"),
            "vcasn": config.get_int(key="vcasn"),
            "vcasn2": config.get_int(key="vcasn2"),
            "ithr": config.get_int(key="ithr"),
            "vclip": config.get_int(key="vclip"),
            "idb": config.get_int(key="idb"),
            "vresetd": config.get_int(key="vresetd"),
            "strobe_length": config.get_int(key="strobe_length"),
            "rdo_mode": config.get_enum(RdoMode, key="rdo_mode")
        }

        self.status_interval = config.get_float("status_interval")
        self.log.debug("Calculating status every %.3f s" % self.status_interval)
        
        return configuration