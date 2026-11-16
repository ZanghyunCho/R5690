# Halftone and ink-duty comparison

Read-only comparison of stock R5691 and user-supplied T3400 data. No additional
firmware is built or modified by this analysis. Reproduce with
`python tools/compare_halftone_ink.py`; raw values and resource hashes are in
`docs/halftone-ink-comparison.json`.

## Common-resolution plain-paper catalogue modes

| Resolution | R5691 CMM | T3400 CMM | R5691 halftone labels | T3400 halftone labels |
| --- | --- | --- | --- | --- |
| 600×600 | 11 | 30 | DB | DB and HYBRID |
| 600×1200 | 13 | 31 | DB | DB and HYBRID |
| 1200×1200 | 14 | 32 | DB | DB and HYBRID |

The two donor rows coexist. Their presence does not prove which one is selected
by a particular driver/job. Both families record HT-ID 200 and OUT_BIT 2 in
these rows. A shared numeric ID is not evidence that the implementation is
identical. OUT_BIT does not specify droplet volume in pL.

R5691 selects cSMB/mSMB resources 211/216 (also 215/217), 220/225 and 214/214.
The donor DB rows select 217/217, 226/226 and 225/225; donor HYBRID rows select
244/244, 245/245 and 246/246. R5691's selected resources include format version
3 and version 5; the donor examples are version 5. Their payloads differ.
R5691 ID 211 includes a `ConvertSML` label, supporting a small/medium/large
conversion lead; its precise input/output units and physical drop assignment
are not established. Comparing file sizes is not sufficient to infer larger
or smaller drops.

R5691 dither resources 650/651/652 are 131,144 / 131,144 / 262,216 bytes with
signature `e7 cb 0d 1e`. T3400 resources 706/705/702 are 24-byte indirection
records with signature `fc f9 2e b8`:

| Resolution | Donor selector | Four referenced IDs |
| --- | --- | --- |
| 600×600 | 706 | 666, 686, 666, 686 |
| 600×1200 | 705 | 665, 685, 665, 685 |
| 1200×1200 | 702 | 662, 682, 662, 682 |

The referenced donor resources use signature `cf f9 2e 47` and are respectively
393,248 / 786,464 / 1,572,896 bytes each. The header and payload layouts differ
from the R5691 resources. Whether the R5691 consumer can support this format
requires code-level verification; it cannot be assumed or rejected just from
these different headers. Resource 696 is byte-identical in both firmwares.

The donor print-engine diagnostic strings explicitly include
`hybrided_minimum_dot`, `dither_size_h`, `dither_size_v`, `dither_h_shift` and
`G_DITHER*_SMBSEL`. These are relevant control leads, not decoded settings or
proof that any particular mode uses exclusively small droplets.

## Encoded overall ink-duty limit

Each compared colour blob has `inkd` version 1 with nine channel codes. Code
20 is the last encoded value. Scaling it by 100/255 agrees, to quantization,
with R5691's catalogue `Total_Duty` in all three modes. Applying that same
interpretation to the matching donor structure gives:

| Resolution | R5691 raw / normalized limit | T3400 raw / normalized limit |
| --- | --- | --- |
| 600×600 | 344 / 134.9% | 306 / 120.0% |
| 600×1200 | 204 / 80.0% | 242 / 94.9% |
| 1200×1200 | 217 / 85.1% | 128 / 50.2% |

The donor is lower in two modes and **higher at 600×1200**. These are encoded
limit metadata, not measured discharge, media coverage or actual firmware
enforcement. Percent here is an ink-duty normalization, not cartridge level.
Some per-channel R5691 catalogue duty entries do not match the encoded values;
therefore use the exact `inkd` values and resolve their consumer rather than
treating the catalogue as authoritative final channel settings.

Physical consumption also depends on CLUT output, halftoning, drop selection,
waveform/drop volume and job coverage. No pL-per-drop or mL-per-page result can
be derived from this comparison. The published CLUT-only candidate retains all
R5691 ink-duty metadata and halftone resources.

## EFU rejection during this investigation

The user reports the published CLUT candidate fails **after transfer starts**;
the printer subsequently boots its previous firmware normally. Rejection cause
is unresolved. This rules out neither device-side integrity checks nor
transfer/programming conditions. It does not establish a faulty LUT format.
No speculative replacement EFU was issued.
