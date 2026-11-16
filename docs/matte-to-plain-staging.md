# Matte donor data → R5691 Plain Paper: offline staging

The user confirmed the direction: select **Plain Paper in the PC driver**, and
use T3400 Enhanced Matte data internally. Existing working V6 controller,
virtual cartridges, maintenance patch and current CLUT are the baseline.

## Verified recipient scope

The stock resource catalogue references SML ID 214 only from PLAIN 1200×1200,
2-bit rows 14 (BASE), 414 (E-RGB) and 574 (E-BIZ-COLOR). Native catalogue
selection 0x48ABE280 confirms those IDs with synthetic settings. Rebinding this
resource does not require changing the paper selector or other paper modes.
There is no proposed DPI/pass/waveform change.

## Candidate donor, not yet a proven UI mapping

The T3400 catalogue has L_APMP_MK BASE 1200×1200, OUT_BIT 2, DB, SML 213/213,
dither selector 702. Its 2400×1200 row instead uses OUT_BIT 1 and SML 211:
that is not interchangeable with the recipient's 2-bit mode. L_APMP_MK has no
600×600 or 600×1200 BASE rows, so lower recipient modes cannot be called an
exact corresponding-resolution transplant.

The donor main image contains separate labels Enhanced Matte (preceding ID
0xB2) and Archival Matte (0x0F). The connection from the Enhanced Matte UI
selection to L_APMP_MK has not been established by native execution. Do not
present this candidate as a confirmed Enhanced Matte profile merely from its
abbreviated name. Source offsets and hashes are recorded in the JSON report.

## Implemented offline probe

`tools/stage_matte_to_plain_sml.py` stages donor SML 213 under recipient ID 214.
It does not produce an EFU. The 658-byte encoded resource fits in the existing
1872-byte unused compressed tail of V6 CLUT resource 13. That host resource's
live header and bounded compressed stream remain byte-identical. Only the
resource-214 pointer and the inserted bytes change in the staged library.
No framebuffer, code cave, ROM extension or guessed RAM address is used.

The original resource lookup 0x480994C0 resolves the new pointer and leaves
selected control IDs unchanged. Original ARM decoding reproduces the donor
payload exactly. The stock SML parser 0x48ABF630 accepts it using synthetic
four-channel CMYK/2-bit settings and a mocked allocation callback. The report
also records allocation requests. This is reader compatibility, not complete
raster execution, physical dot-size identification or print-quality evidence.

## Remaining work

- Prove the donor Enhanced Matte UI-to-catalogue association.
- Install dither selector 702 together with matrices 662/682 using an owned,
  bounded storage/loading path. The large matrices do not fit the original
  652 slot; a selector-only patch would leave missing dependencies.
- Verify actual raster processing with the donor thresholds/dither and
  preserve correct output-plane/channel semantics.

No firmware has been released for this staging. V6 remains the working
baseline. The user reports pumps operating and M nozzle dropout no longer
occurring under their present conditions; this does not establish long-duration
reliability or operation with physical chips removed.

## Native donor media conversion follow-up

`tools/trace_t3400_media_conversion.py` identifies donor main base 0x43696000
using absolute jump-table targets that land exactly on ARM return stubs.
It executes conversion 0x438D1118: input 6 returns media enum 102. The caller
0x438C69E8 passes the result of the settings object's virtual method +0x48,
then stores the converted byte at output offset +0xE.

The original recipient catalogue selector also accepts the donor catalogue
with synthetic media 102 / BASE / DB / 1200×1200 / OUT_BIT 2 and selects
CMM 14, SML 213 and dither 702. This confirms the native catalogue relationship
of enum 102 to L_APMP_MK and the exact data dependencies.

A separate helper 0x438D0E70 converts input 36 to 178 (0xB2), but feeding 178
to the CMM conversion returns 166, not 102. These are different namespaces.
The actual Enhanced Matte job-settings object and its +0x48 result still need
to be traced; a display-name code must not be substituted directly.

The decoded dither header is version 3, 1024×1024, with stored bit width 12
(header bytes 0x16=1 and 0x17=4). The native unpacker computes the bit width as
8*byte[0x16]+byte[0x17]. Merely truncating thresholds to 8 bits is not a lossless
transplant and has not been staged. Complete raster input/comparison semantics
would need proof before any such representation change.

Results are recorded in `t3400-native-media-conversion.json`. No new EFU is
produced and the working V6 image is unchanged.
