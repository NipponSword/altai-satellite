---
# SPDX-FileCopyrightText: 2025 DESY and the Constellation authors
# SPDX-License-Identifier: CC-BY-4.0 OR EUPL-1.2
title: "Template"
description: "Satellite of ALTAI (ported from eudaq2 ALPIDE producer)"
category: "External"
language: "Python"
parent_class: "TransmitterSatellite"
---

## 📌 Description

This is a detailed description of the satellite and its functionality.
Possible dependencies are described alongside its features, potential pitfalls and other information.

## 📝 Requirements

- Python >= 3.11 (tested: Python3.12, ConstellationDAQ 1.0.2
- uv (or plain python -m venv+pip)
- ALTAI DAQ board reachable over USB
- `alpide-daq-software` from [ALICE-ITS3-WP3-Gitlab](https://gitlab.cern.ch/alice-its3-wp3/alpide-daq-software) (Internal access)

## 🏢 Building
Before building, check you have already cloned `alpide-daq-software` as following
```shell
  projects
    ├── alpide-daq-software
    └── altai-satellite
``` 
Create virtual environment
```shell
git clone git@github.com:NipponSword/momiji-tlu-satellite.git
cd altai-satellite
uv venv --python 3.12
source .venv/bin/activate
```
Then install satellite with `alpide-daq-software`
```shell
uv sync --extra alpidedaqboard
```

## 🚀 Usage
Starting satellite with
```shell
SatelliteAltai -n <name_of_plane> -g <group_name>
```

## 🔩 Parameters

The following parameters are read and interpreted by this satellite. Parameters without a default value are required.

| Parameter | Description | Type | Default Value |
| --------- | ----------- | ---- | ------------- |
| `serial` | Serial number of the board | str |  |
| `plane` | Plane number in the telescope | int |  |
| `triggermode` | Trigger mode. `primary` or `replica` | str |  |
| `STROBE_LENGTH` | AFE bias | int |  |
| `minspacing` | Minimum spacing to accept the next trigger | int | `0` |
| `fixedbusy` | Fixed time of busy once accepting trigger | int | `0` |
| `status_interval` | Time to get next metrics | float | `1.0` |
| `RDOMODE` | Readout mode. `DATAPORT` or `DCTRL` | int | `DATA_PORT` |
| `CHIPID` | AFE bias | int | `0x10` |
| `VCASN` | AFE bias | int | `57` |
| `VCASN2` | AFE bias | int | `64` |
| `ITHR` | AFE bias | int | `51` |
| `VCLIP` | AFE bias | int | `0` |
| `IDB` | AFE bias | int | `64` |
| `VRESETD` | AFE bias | int | `147` |

> [!WARNING]
> The DAC values of AFE bias are set as an default value on the firmware. The software itself does not define the default value (except VRESETD), and if not defined in configuration file, the default reset value on firmware will be used.

### Configuration Example

An example configuration for this satellite which could be dropped into a Constellation configuration as a starting point

```toml
[Altai.plane_0]
ITHR          = 61
VCASN         = 109
VCASN2        = 121
VCLIP         = 60
IDB           = 29
STROBE_LENGTH = 400

# plane_1, 2, 3, ...

[Altai.plane_5]
ITHR          = 61
VCASN         = 106
VCASN2        = 118
VCLIP         = 60
IDB           = 29
STROBE_LENGTH = 400
```


## 📉 Metrics

The following metrics are distributed by this satellite and can be subscribed to.

| Metric | Description | Value Type | Interval |
| ------ | ----------- | ---------- | -------- |
| `TIME` | Time since launch in seconds | Float | 10s |

## Custom Commands

This section describes all custom commands the satellite exposes to the command interface.

| Command | Description | Arguments | Return Value | Allowed States |
| ------- | ----------- | --------- | ------------ | -------------- |
| `test` | This command always returns `true` | - | Boolean, always `true` | `NEW`, `INIT`, `ORBIT` |
