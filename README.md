---
# SPDX-FileCopyrightText: 2025 DESY and the Constellation authors
# SPDX-License-Identifier: CC-BY-4.0 OR EUPL-1.2
title: "Template"
description: "Constellation Satellite for ALTAI (ported from eudaq2 ALPIDE producer)"
category: "Readout System"
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
git clone git@github.com:NipponSword/altai-satellite.git
cd altai-satellite
uv venv --python 3.12
source .venv/bin/activate
```
Then install satellite with `alpide-daq-software`
```shell
uv sync --extra alpidedaqboard
```

## 🚀 Usage
Start satellite with
```shell
SatelliteAltai -n <name_of_plane> -g <group_name>
```

## 🔩 Parameters

The following parameters are read and interpreted by this satellite. Parameters without a default value are required.

| Parameter | Description | Type | Default Value |
| --------- | ----------- | ---- | ------------- |
| `serial` | Serial number of the board | str | - |
| `plane` | Plane number in the telescope | int | - |
| `trigger_mode` | Trigger mode. `"primary"` or `"replica"` | str | - |
| `strobe_length` | Strobe length | int | - |
| `vcasn` | AFE voltage VCASN | int | - |
| `vcasn2` | AFE voltage VCASN2| int | - |
| `ithr` | AFE current ITHR | int | - |
| `vclip` | AFE voltage VCLIP | int | - |
| `idb` | AFE current IDB | int | - |
| `chip_id` | Chip ID | int | `0x10` |
| `min_spacing` | Minimum spacing to accept the next trigger | int | `0` |
| `fixed_busy` | Fixed time of busy once accepting trigger | int | `0` |
| `rdo_mode` | Readout mode. `"dataport"` or `"dctrl"` | int | `"dataport"` |
| `vresetd` | AFE voltage VRESETD | int | `147` |

### Configuration Example

An example configuration for this satellite which could be dropped into a Constellation configuration as a starting point

```toml
[Altai.plane_0]
ithr          = 61
vcasn         = 109
vcasn2        = 121
vclip         = 60
idb           = 29
strobe_length = 400

# plane_1, 2, 3, ...

[Altai.plane_5]
ithr          = 61
vcasn         = 106
vcasn2        = 118
vclip         = 60
idb           = 29
strobe_length = 400
```


## 📉 Metrics

The following metrics are distributed by this satellite and can be subscribed to.

| Metric | Description | Value Type | Interval |
| ------ | ----------- | ---------- | -------- |
| `idda` | Current IDDA  | Float | 5s |
| `iddd` | Current IDDD  | Float | 5s |
| `temperature` | Current temperature of chip board  | Float | 5s |
| `trigger_id` | Current trigger_id decoded from DAQ raw data | Int | 5s |
