# Calibration

Calibration converts raw sensor values into an engineering quantity. Baseline compensation is a
later Processor stage and is not calibration.

Unit and Calibration are independent dimensions. A Unit describes what Channel numbers mean; it
does not prove or disprove sensor calibration. Calibration is an explicit numeric transform and
does not become selected merely because a Unit is present or absent. Compatible engineering-unit
conversion for display is a third, separate operation.

## Identity

`builtin.calibration.identity` computes `y = x` and preserves input Quantity and Data Unit. It is
the factory default for every newly parsed Channel, whether the Unit is N, MPa, missing/default SI,
raw, count, or ADC. Its GUI name is “Already Calibrated,” but this only means “do not apply an
additional transform.” Underline RETLDC does not certify that the sensor was physically calibrated.

The selection priority is:

```text
Project explicit Calibration > matched user Calibration profile > factory Identity
```

No step consults the Unit to guess Calibration state. A user can replace Identity with Linear,
Polynomial, Lookup Table, or any compatible plugin at any time.

## Linear

`builtin.calibration.linear` computes:

```text
y = K × x + B
```

`K` and `B` are finite user/configuration values. No historical coefficient is built into TR_F or
the model. Linear exposes output Quantity and output Unit through its parameter schema. Evaluation
returns a fresh read-only Channel through the workflow. For example, a raw input remains an
immutable `raw` Channel while Linear creates a new calibrated force Channel in N.

The Project workspace builds parameter controls from each plugin's `parameter_schema()`. Linear
therefore contributes `K`, `B`, output Quantity, and output Unit dynamically; Identity contributes
no model parameters and advertises same-as-input behavior through `requirements()`. A Calibration
plugin declares input compatibility and output behavior; adding another scalar model does not
require an ID-specific GUI branch.

Calibration may validly map `raw→N`, `count→Pa`, or `V→N`. It must perform the mathematical
mapping, not only change a Unit label. The Unit Registry handles only same-dimension conversions
such as Pa→MPa and K→°C, and refuses direct conversion from raw/count/ADC.

## Calibration JSON v1

```json
{
  "schema": "underline-retldc-calibration/1",
  "name": "LoadCell_01_20260812",
  "quantity": "force",
  "input_unit": "raw",
  "output_unit": "N",
  "model": {
    "id": "builtin.calibration.linear",
    "version": "1.0.0",
    "parameters": {"K": 0.098, "B": 0.0}
  },
  "sensor": {"sensor_id": "LC-01"},
  "notes": ""
}
```

`schema`, quantity, units, model ID/version, and parameters are persisted. Optional metadata
includes name, sensor, notes, creation time, operator, and source. Loading rejects other schema IDs,
missing required fields, non-finite coefficients, or unsupported model IDs.

Loading a Calibration JSON selects its stable model ID and repopulates the same schema-generated
form. Saving serializes the active model version, parameter values, quantity, and units; neither
operation stores a localized model name.

`sensor.sensor_id` may be used to match a trusted user profile on a later import. A matched profile
overrides only factory Identity; an explicit Project selection always wins.
