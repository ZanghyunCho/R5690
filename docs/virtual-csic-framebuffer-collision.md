# Confirmed framebuffer collision in V4 and V5

The stock framebuffer is 480 × 272 × 4 bytes at 0x47D69594..0x47DE8D94.
Native initialization at 0x47C4A0FC loads the address from 0x47C4A1B0 and
stores it through the pointer loaded from 0x47C4A1B4 (0x47D57D98).
Native display clear at 0x47C49B40 writes 0x1FE00 four-byte pixels.

The presumed FF code cave at 0x47D70000 is inside that framebuffer. Existing
references to the FF tail were not proof of free storage: the framebuffer base
is written into a runtime pointer. The previous synthetic tests omitted this
initialization/clear and wrongly mapped the area as helper memory.

`trace_virtual_csic_framebuffer_collision.py` verifies exact withdrawn V4/V5
hashes, executes original pointer setup and full display clear, and observes
helper/table destruction. `validate_virtual_csic_display_regression.py` then
calls the patched field setter: both old images fail to return within 2000
instructions and execute zeroed framebuffer words. The relocated candidate
retains every helper/table and returns normally after the same display clear.
This directly reproduces corruption and a non-returning execution mechanism;
the actual printer's watchdog/power-off instruction was not captured.

## Relocation

V6 reclaims only retired chip-authentication/compatibility bodies at
0x47C57A04..0x47C5824C and 0x47C8D8D8..0x47C8DA00. Public entry hooks remain.
Static checks reject live external interior branches and preserve external
PC-relative literals/absolute references. The boundary stops before 0x47C8DA00,
which is entered by a live outside branch. Unsupported authentication inputs
return explicit failure instead of entering overwritten retired bodies.

A compact per-slot part/capacity/scale table replaces 4032-byte register images.
Original native bit packing reconstructs the same fields, checked for all 24
SKU/slot combinations, including SKU 0x21's different colour scale flags.
No code, metadata, or runtime marker is allocated in the framebuffer. Helper
literal/branch checks reject framebuffer targets. The final controller restores
all original framebuffer bytes present in the decompressed image.

Integration executes 12 full original display clears before/after registration,
72 original full scans, 144 consumption commits, 144 re-registrations and four
fresh-RAM reconstruction cases. Retired code arenas are mapped read/execute
only. Properties, OS callbacks and GPIO driver responses remain mocked; this
is not a full OS or physical printer boot test.

V4 and V5 remain withdrawn with disabled builders. V6 is a separately labelled
candidate: physical update/boot, no-chip printing and automatic supply are not
verified. Existing MB and T3400 CLUT changes are retained; no actuator, IES,
Initial Charge or physical NVRAM erasure patch is added.
