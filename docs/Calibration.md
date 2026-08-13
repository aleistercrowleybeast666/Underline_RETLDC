# Calibration

Calibration converts raw sensor values into an engineering quantity. Baseline compensation is a
later Processor stage and is not calibration.

## Identity

`builtin.calibration.identity` computes `y = x`. The user still declares output `quantity` and
`unit`; no unit is inferred from raw syntax.

## Linear

`builtin.calibration.linear` computes:

```text
y = K × x + B
```

`K` and `B` are finite user/configuration values. No historical coefficient is built into TR_F or
the model. Evaluation returns a fresh read-only Channel through the workflow.

The Project workspace builds parameter controls from each plugin's `parameter_schema()`. Linear
therefore contributes `K` and `B` dynamically; Identity contributes no model parameters. The
workflow appends user-declared `quantity` and output `unit` for both models. Adding another scalar
Calibration model does not require an ID-specific GUI branch.

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
  "sensor": {"id": "LC-01"},
  "notes": ""
}
```

`schema`, quantity, units, model ID/version, and parameters are persisted. Optional metadata
includes name, sensor, notes, creation time, operator, and source. Loading rejects other schema IDs,
missing required fields, non-finite coefficients, or unsupported model IDs.

Loading a Calibration JSON selects its stable model ID and repopulates the same schema-generated
form. Saving serializes the active model version, parameter values, quantity, and units; neither
operation stores a localized model name.
