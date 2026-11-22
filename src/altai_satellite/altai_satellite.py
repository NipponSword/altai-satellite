"""
SPDX-FileCopyrightText: 2025 DESY and the Constellation authors
SPDX-License-Identifier: EUPL-1.2
"""
from time import sleep, monotonic

from constellation.core.configuration import Configuration
from constellation.core.monitoring import schedule_metric
from constellation.core.protocol.cscp1 import SatelliteState
from constellation.core.transmitter_satellite import TransmitterSatellite

from . import __version__
from .daqboard import AltaiDaqBoard, RdoMode, TriggerMode

POWER_CHECK_INTERVAL = 5.0 #s


class Altai(TransmitterSatellite, version=__version__):
    """ALTAI satellite class

    Raises:
        RuntimeError: ALTAI power tripped
    """

    daq: AltaiDaqBoard
    conf: dict

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._last_trigger_id = 0
    
    # =========================================
    # Constellation methods
    # =========================================

    def do_initializing(self, config: Configuration) -> str:
        """ initialize

        Args:
            config (Configuration): toml configuration
        """
        if hasattr(self, "daq"):
            self.daq.close()
        self.conf = self._read_config(config)
        self.daq = AltaiDaqBoard(self.conf)
        self.daq.stop_trigger()

        return "Do initializing complete"

    def do_launching(self) -> str:
        """launch

        Raises:
            RuntimeError: ALTAI power did not come up
        """
        self.daq.stop_trigger()
        self.daq.power_on()

        sleep(0.1)
        if not self.daq.is_powered():
            raise RuntimeError("ALTAI power did not come up (over-current?)")
        
        self.daq.reset()
        self.daq.configure(self.conf)

        return "Do launching complete"

    def do_landing(self) -> str:
        """land, power off
        """
        self.daq.power_off()

        return "Do landing complete"

    def do_starting(self, run_identifer: str) -> str:
        """start, set bor
        """
        self.bor = (
            {"eudaq_event": f"ALPIDE_plane_{self.daq.plane}"} |
            {"write_as_blocks": True} |
            self.daq.get_firmware_info() |
            self.daq.dump_registers() |
            self.daq.read_trigger_monitor()
        )

        self.daq.arm_trigger()

        return "Do starting complete"

    def do_run(self) -> str:
        """run, check power

        Raises:
            RuntimeError: ALTAI power latch-up
        """
        next_power_check = monotonic()
        while not self.stop_requested():
            self._read_and_send_event()
            if monotonic() >= next_power_check:
                if not self.daq.is_powered():
                    raise RuntimeError("ALTAI power tripped during run")
                next_power_check += POWER_CHECK_INTERVAL

        return "Do running complete"

    def do_stopping(self) -> str:
        """stop, read all data before power off
        """        
        self.daq.stop_trigger()

        self.log.info("Reading remaining events...")
        while self._read_and_send_event():
            pass

        self.eor = (
            self.daq.dump_registers() |
            self.daq.read_trigger_monitor()
        )
        
        return "Do stopping complete"

    def fail_gracefully(self) -> str:
        """gracefull stop
        """
        if not hasattr(self, "daq"):
            return "Failed before board was opend"
        try:
            self.daq.stop_trigger()
            self.daq.power_off()
        except Exception as err:
            self.log.error(f"Cleanup after failure failed: {err}")
        
        return "Trigger blocked, power off..."

    # =========================================
    # Metrics
    # =========================================

    @schedule_metric("mA", 5)
    def idda(self) -> float | None:
        return self.daq.get_power_status()[0]

    @schedule_metric("mA", 5)
    def iddd(self) -> float | None:
        return self.daq.get_power_status()[1]
    
    @schedule_metric("C", 5, [SatelliteState.RUN])
    def temperature(self) -> float | None:
        return self.daq.get_carrier_temp()

    @schedule_metric("", 5, [SatelliteState.RUN])
    def trigger_id(self) -> int | None:
        return self._last_trigger_id

    # =========================================
    # Utils
    # =========================================

    def _read_and_send_event(self) -> bool:
        """read event and sent to recv satellite

        Returns:
            bool: if cannot read, return False
        """

        raw = self.daq.read_event()

        if not raw:
            return False
        try:
            trigger_id, timestamp = parse_header(raw)
        except ValueError as err:
            self.log.warning(f"Dropping malformed event: {err}")
            self.mark_run_tainted()
            return True

        # ---
        timestamp *= 1000
        # EudaqNativeWriter divides by 1000 (ps -> ns); 
        # x1000 keeps the raw timestamp in the file, as the EUDAQ2 producer did.
        # ---
        data_record = self.new_data_record(
            {
                "trigger_number" : trigger_id,
                "timestamp_begin": timestamp,
                "timestamp_end"  : timestamp,
                "device_number"  : self.daq.plane
            }
        )
        data_record.add_block(raw)
        self.send_data_record(data_record)
        self._last_trigger_id = trigger_id

        return True

    def _read_config(self, config: Configuration) -> dict:
        """dump config to dict

        Args:
            config (Configuration): toml config

        Returns:
            dict: conf
        """
        
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
        
        return configuration

def parse_header(raw: bytes) -> tuple[int, int]:
    """get trigger_id and ts, check header

    Args:
        raw (bytes): event byte array from ALTAI

    Raises:
        ValueError: malformed event

    Returns:
        tuple[int, int]: trigger_id, timestamp
    """
    
    header_is_correct = (
        len(raw) >= 20 and
        list(raw[:4]) == [0xAA] * 4 and
        list(raw[-4:]) == [0xBB] * 4
    )

    if not header_is_correct :
        raise ValueError(f"malformed event ({len(raw)} bytes)")
    
    trigger_id = int.from_bytes(raw[4:8], "little")
    timestamp = int.from_bytes(raw[8:16], "little")

    return trigger_id, timestamp