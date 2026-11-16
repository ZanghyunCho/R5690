# Halftone transplant: native tests and unresolved integration

The user reports successful update after power-cycling and improved colours
with the published CLUT candidate. That report does not establish that a
particular driver path, halftone algorithm or physical ink limit is active.

## Correction: ink-duty metadata is not a verified runtime limit

The preceding 135/120, 80/95 and 85/50 percent comparisons describe values in
the `inkd` tag. The **original R5691 colour parser at `0x48ABCAE4` does not
read those values in the tested path**. For CMM IDs 11/13/14, setting the
encoded total to 1 instead of its stock value yields the exact same parsed
context and output pointers. A native memory-read hook records no access to
the inkd value region in either run. Static tag comparisons also omit inkd.

Therefore neither “copying this number changes the enforced total limit” nor
“preserving this number preserves the actual limit” is established. No actual
pL/drop or mL/page measurement has been made. Other consumers and constraints
may exist. Ink limits may also interact with generated LUTs, drop conversion
and ink calibration; the exact enforcement path remains unresolved.

A locally constructed CLUT+inkd-metadata experiment was quarantined before
publication. It is not a recommended firmware or a device test. The build tool
now rejects that option. No new EFU is released with this investigation.

## Original R5691 code can read donor structures

With synthetic channel codes `[1,2,3,0]` and 2-bit output, the unmodified
R5691 SML wrapper `0x48ABF630` accepts all six tested donor conversion resources:
DB 217/226/225 and HYBRID-labelled 244/245/246. The resulting allocated tables
have distinct hashes. R5691 resources 211/220/214 are successful controls.
Allocator results are mocked; the original format dispatch, parser and table
generation execute. This is not execution of raster hardware or physical
drop-volume validation.

The R5691 binary also includes readers for both donor dither signatures:
`fc f9 2e b8` selectors and `cf f9 2e 47` matrices. In original ARM execution:

| Selector | Resource IDs returned for the synthetic four-channel input |
| --- | --- |
| 706 | 686, 666, 686, 666 |
| 705 | 685, 665, 685, 665 |
| 702 | 682, 662, 682, 662 |

All six referenced matrices pass the native header validator `0x48ADDAC0`
and full unpacker `0x48ADDFE8` with a synthetic 12-bit input representation.
Decoded widths/heights are 512×512, 512×1024 and 1024×1024. This corrects the
earlier uncertainty about whether R5691 has a reader for these data formats.
It does **not** establish the caller's live parameters or HYBRID engine support.

## Storage and integration still needed

The 1200×1200 selector refers to two 1,572,896-byte stored matrices, which
unpack to 2,097,156 bytes each. The old library module is 2,995,828 bytes at
`0x4808F000`, with the main code beginning at `0x4848F000`: the address interval
between them has only 1,198,476 bytes beyond the old library end. It is not
established that this interval is unused at runtime.

The custom colour compressor produces 1,592,954 bytes for donor 662, verified
exact by the original decoder. For 666/686 it produces 398,365 / 398,278 bytes.
These matrices do not become small enough simply by applying the existing
compression. Appending the high-resolution pair to the existing loaded
library would overlap the main-code address range. This is a limit of that
placement strategy, not proof that the printer lacks enough total RAM.

Before an integrated EFU is justified, determine safe backing storage and
loading, the actual runtime resource-selection fields and caller parameters,
and actual ink-limit enforcement. Do not change an offline catalogue label
and claim that the live engine switches to HYBRID. DPI, passes, waveforms,
service flags and cartridge patches have not been changed here.

Evidence JSON files accompany this report. Reproduction script in the working
tree: `tools/validate_t3400_halftone.py`. All emulation is isolated from any
printer, with no live USB, updater, NVRAM or peripheral access.
