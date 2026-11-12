---
# SPDX-FileCopyrightText: 2025 DESY and the Constellation authors
# SPDX-License-Identifier: CC-BY-4.0 OR EUPL-1.2
title: "Template"
description: "Satellite base structure serving as the basis for new developments"
category: "External"
language: "Python"
parent_class: "Satellite"
---

## First Steps

This is a template for new Constellation satellites, written in Python.
The following steps help in setting up the new satellite, rename the relevant classes and files, and run the satellite for the first time.
Additional information as well as detailed tutorials on how to implement a new satellite in Python can be found in the
[Constellation Application Developer Guide](https://constellation.pages.desy.de/application_development/index.html).

* Rename the satellite using the self-destructing script:

  ```sh
  rename-template.py MyName
  ```

* Adjust the satellite base class depending on the target functionality:
  * `TransmitterSatellite`: This satellite will generate and transmit data during the run
  * `ReceiverSatellite`: This satellite will receive data during the run
  * `Satellite`: This satellite will neither send nor receive data via CDTP during the run
* Implement the satellite code
* Install the Satellite:
  * From the template's base directory (where the `pyproject.toml` is located), run `pip install ./`
  * During development, you might want to add the `-e` switch to [install an editable install](https://setuptools.pypa.io/en/latest/userguide/development_mode.html), meaning changes in the source code of your satellite will directly modify the installed version.
* Run the satellite
* Update this `README.md`
  * Remove the "First Steps" section
  * Update the `parent_class` tag in the `README.md` to the satellite base class used in the code
  * Update the satellite description, parameter and metric list, custom commands of the `README.md` structure below
  * Add a configuration example for easy copy & paste
  * Add the satellite to the [Constellation Satellite Library](https://constellation.pages.desy.de/satellites/index.html) as
    described in the [Constellation Application Developer Guide](https://constellation.pages.desy.de/application_development/intro/listing.html)

---

## Description

This is a detailed description of the satellite and its functionality.
Possible dependencies are described alongside its features, potential pitfalls and other information.

## Parameters

The following parameters are read and interpreted by this satellite. Parameters without a default value are required.

| Parameter | Description | Type | Default Value |
| --------- | ----------- | ---- | ------------- |
| `example` | Description of the parameter | Boolean | `true` |

### Configuration Example

An example configuration for this satellite which could be dropped into a Constellation configuration as a starting point

```toml
[Template.One]
example = false
```

## Metrics

The following metrics are distributed by this satellite and can be subscribed to.

| Metric | Description | Value Type | Interval |
| ------ | ----------- | ---------- | -------- |
| `TIME` | Time since launch in seconds | Float | 10s |

## Custom Commands

This section describes all custom commands the satellite exposes to the command interface.

| Command | Description | Arguments | Return Value | Allowed States |
| ------- | ----------- | --------- | ------------ | -------------- |
| `test` | This command always returns `true` | - | Boolean, always `true` | `NEW`, `INIT`, `ORBIT` |
