# V4 WITHDRAWN — reported power-off during boot

The user reports that the printer shuts off during boot after installing v4.
The EFU has been removed from the current branch. Offline results below did
not validate physical boot and must not be treated as evidence of usability.
No replacement EFU is authorized by these results alone. Root cause pending.

# Virtual CSIC rewrite: v4 offline candidate

The old ink/maintenance V1 and T3400 CLUT v1 only overrode status/level
interfaces; real-chip reads, consumption writes and validation remained.
The user confirmed chip depletion and failure without chips. V4 replaces
that approach with virtual-slot transport and registration adapters.
Physical printer operation has not yet been verified.

## Corrected registration protocol

The native field setter marks modified words with bit 15. A RAM-only reload
exposed those marks as chip flags. The virtual reload now returns clean data
words. The native registration self-test also attempts decrements of monotonic
cells and writes protected diagnostic cells. The virtual field policy rejects
decrements and preserves protected cells, while retaining the native packer
for normal writes. This resolves the earlier 0x27/0x38 failures without
skipping the original write/readback comparison in 0x47C573CC.

The virtual authentication adapter synchronizes the chip consumption and
verified counter cache from the original cumulative-use calculation. Omitting
the verified cache caused native mode 1 to reject re-registration with 0xAE;
that was fixed. The native 0x47C57320 comparison remains active.

The stock chip-bank clear invalidates seed markers, allowing a later read to
restore consistent metadata. Four stable virtual UIDs are reconstructed from
six supported SKU/part tables. Virtual slots use the stock no-physical-history
sentinel rather than erasing IC3 records. Virtual authentication is an explicit
virtual-device contract, not emulation of Epson chip cryptography.

## Evidence

`tools/validate_virtual_csic_candidate.py` executes the combined MB/virtual-CSIC
controller, with synthetic property reads/writes, event delivery, delay and OS
status publication. It covers six SKUs and six cumulative-use inputs through
4,000,000,000, exercising configured generation modes 1–4 across the cases.

- 72 original four-slot scan/registration calls at 0x47C58AB0.
- 144 original consumption commits at 0x47C561B4, including bookkeeping.
- 144 original per-slot re-registrations at 0x47C58508.
- Four fresh CPU/RAM reconstruction cases with stable virtual identities.
- No trapped physical CSIC, fatal, chip-history object write or format calls.
- An unsupported SKU fails; unmodified stock reaches a physical CSIC call.

`tools/validate_virtual_csic_interfaces.py` covers 126 scalar cases, 45 snapshot
cases and 232 unchanged error API cases. Only level values become 100%; raw
state, cartridge type and general error handling retain stock behavior.

Reports: `docs/virtual-csic-v4-arm-validation.json` and
`docs/virtual-csic-v4-interface-validation.json`.

The native integration and API checks also pass with Unicorn configured as
ARM926. Added helpers avoid MOVW/MOVT instructions. This is a compatibility
check, not identification of the physical printer CPU.

## Packaging and limits

`firmware/custom/virtual-csic-t3400-candidate-v4/` contains the EFU, checksum and
manifest. The working MB patch and existing T3400 CLUT library are retained;
old V1 raw-state/error overrides are absent. The builder checks all 14 records,
native ARM reconstruction of five CROM modules, an independent IPL correction
and ZIP readback. Only the GR controller storage and its integrity fields differ
from the T3400 CLUT v1 parent. IC3, IC5, boot code and the library are unchanged.

This is offline evidence, not a complete OS boot or physical printer test.
Update acceptance, no-chip operation, automatic ink supply, IES behavior,
long-duration operation and printing remain unverified. There is no pump,
Initial Charge flag, leak-sensor or physical NVRAM-history erasure patch.
The separate earlier transport-only experiment is still not a usable firmware
on its own; v4 includes additional bootstrap, discovery and registration code.

## User recovery observation

The user restored all three SPI ROMs with stock when the previous problem
cleared; that does not isolate one IC, one flag or a specific code patch.
The later authorized IC3 dump has a separate `1WAY0001` sector at `0xFC0000`,
containing identity/counter history objects `0x04400001` (853 x 24-byte records)
and `0x04400002` (4080 bytes), beyond the 2KB service EEPROM backup. The native
link is documented by `tools/trace_ink_history_storage.py`. It does not prove
that this history was the live cause of the user's M ink supply fault.

## Physical failure follow-up

The user confirmed that v4 displays the Epson logo and advances the boot
progress before powering off. Normal USB is unavailable at that stage, but
firmware update mode remains accessible. The user restored stock themselves
and explicitly confirmed normal boot with stock. Treat this as a v4 regression;
there is no basis to ask for board disassembly or NVRAM erasure.

`tools/diagnose_virtual_csic_boot_regression.py` reproduces two findings:

1. The protected-field setter returns the slot index (0,1,2,3), not success 0,
   for field 0x17. This is an actual API defect missed by the earlier tests.
2. With property-manager readiness deliberately unset, a stock field setter
   returns, but the v4 setter enters the original initialization-error guard
   at 0x47C4D30C because it newly invokes property reads through SEED. The old
   integration tests replaced that entire read API with a success mock.

Neither finding proves the physical shutdown cause. Actual startup ordering,
FF-padding execution/write ownership, omitted CSIC initialization, and OS
watchdog behavior remain unverified. The v4 builder is disabled and no revised
EFU has been built. Results are in `virtual-csic-v4-boot-regression.json`.

## V5 follow-up

A separate V5 offline startup-regression candidate corrects the reproduced
setter/dependency defects and restores stock CSIC initialization. Physical boot
and the exact V4 shutdown cause remain unconfirmed. See `virtual-csic-v5-boot-fix.md`.
V4 remains withdrawn and its builder remains disabled.

## V5 failure and confirmed framebuffer collision

V5 also shut down during boot and has been withdrawn. Both versions placed
helpers inside the stock LCD framebuffer. Original display clear destroys
them and the patched call fails to return. See `virtual-csic-framebuffer-collision.md`
and the native reproduction JSON. V6 relocates helpers into retired auth code
and passes the new display regressions; physical boot remains unverified.
