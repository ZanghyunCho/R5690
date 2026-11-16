# Virtual ink rewrite: unreleased RAM transport core

The old V1 and its T3400 CLUT derivative do not implement a complete virtual
ink cartridge. Actual chip reads/writes and validation are still present.
The user reports actual chip depletion and failure without chips, and requests
a rewrite. No new EFU is released with the following adapter experiment.

## Implemented and executed

`tools/prototype_virtual_csic_transport.py` creates an isolated modified ARM
image in memory, based on the stock GR controller, without V1's cache overrides.
It routes four ink slot indices through their existing RAM chip buffers:

| Slot | Existing bank |
| --- | --- |
| 0 | 0x47E02B68 |
| 1 | 0x47E02EB0 |
| 2 | 0x47E02E08 |
| 3 | 0x47E02D60 |

The adapter handles read, alternate read, readback, write and alternate write
at `0x47C51B78`, `0x47C51C50`, `0x47C51CF4`, `0x47C51D84`, `0x47C51E28`.
It retains the RAM contents across emulated reads/writes, so the native field
setter's changes remain visible when the original field getter reads back.
It does not generate a fake all-success report while issuing physical writes.
Indices outside 0..3 retain the displaced prologue and original continuation.

The prototype helpers occupy known FF-filled padding at `0x47D70000`; no
module extension or extra runtime state buffer is needed for this experiment.
This placement and bounded helpers alone do not establish a boot-safe image.

Original ARM execution passes:

- 20 counter packing → virtual write → virtual reload → field readback cases.
- Per-colour bank independence in every roundtrip.
- 20 supported-slot stack/callee-saved register checks.
- 10 unsupported-slot original-prologue/argument controls.
- 12 calls through the original consumption commit `0x47C561B4`, covering
  native packing, virtual write/reload, native readback comparison and ack.
- No execution of the trapped physical bus helpers in these cases.
- A stock-image positive control reaches the physical write helper.

The consumption tests use synthetic branch mode 3. Clock-derived consumption
calculation and final bookkeeping are mocked; the original commit executes.
The raw RAM buffers are seeded by the test. No printer, chip, pump or service
program is accessed, and no physical EEPROM/NVRAM write occurs.

## Still required before a complete virtual cartridge

The adapter is not a valid new firmware or a complete chip emulator. It still
requires valid cold-start data and identity, no-chip discovery/authentication
integration, stable reboot behavior, always-available ink semantics that do
not corrupt consumption readback, and verification against real supply/IES
state transitions. In particular, suppressing actual chip writes is not proof
that M ink physically reaches the head or that ordinary ink supply will run.

Do not package this partial controller as an EFU or describe the user request
as completed. No new identity or Initial Charge flag has been written. The
working colour LUT is retained as a separate existing artifact.

Evidence: `virtual-csic-transport-validation.json`. The script asserts every
described test and writes its report to `artifacts/virtual-csic-adapter/`.
