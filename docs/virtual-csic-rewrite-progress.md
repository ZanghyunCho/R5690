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

## Cold-start and registration follow-up

The user restored all three SPI ROMs with stock firmware when the earlier
problem disappeared. This does not isolate a single IC or a single flag.
The later IC3 dump contains a separate `1WAY0001` sector at `0xFC0000`
with objects `0x04400001` (853 records of 24 bytes) and `0x04400002`
(4080 bytes). Native routines link these objects to chip identity/counter
history, beyond the 2KB service EEPROM backup. No history is erased.

New unreleased scripts generate 24 SKU/slot metadata candidates using the
stock part table and native field packer/capacity parser. A cold-start ARM
adapter installs the appropriate candidate and four stable in-boot UIDs.
All 24 cold-load/write/reload cases pass with trapped physical bus calls
remaining unused. This is synthetic execution, not a printer boot test.

The integrated replay of stock registration `0x47C582B4` currently FAILS:
SKU 0x10, slot 0 returns 1 with detail 0x27. The original routine
`0x47C573CC` writes test fields and compares the readback. The current
RAM transport does not yet satisfy this protocol. Initializing fields
0x17/0x18 to the comparison constants instead fails the earlier reserved
flag check (detail 0x38); that attempted workaround was removed.
Do not bypass either failure or package this controller as an EFU.

`tools/prototype_virtual_csic_registration.py` is an intentionally failing
integration probe, not a passing validation or a released patch. Its virtual
acceptance adapters replace vendor-chip authentication with a virtual-slot
contract; they do not emulate real-chip cryptography. Discovery, reboot
persistence, unlimited remaining semantics and physical ink supply remain
unverified.
