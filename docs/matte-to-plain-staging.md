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

## Donor identity confirmed from independent name tables

The T3400 catalogue has L_APMP_MK BASE 1200×1200, OUT_BIT 2, DB, SML 213/213,
dither selector 702. Its 2400×1200 row instead uses OUT_BIT 1 and SML 211:
that is not interchangeable with the recipient's 2-bit mode. L_APMP_MK has no
600×600 or 600×1200 BASE rows, so lower recipient modes cannot be called an
exact corresponding-resolution transplant.

The donor name record at 0x44018D7C binds code 215 to a translation table
whose English entry is **Enhanced Matte Paper**. An independent IPP table
at 0x4405B69C binds the same code to `com.epson-matte-enhanced`.
Native function 0x43835CF0 maps 215 to CMM PaperType 102, whose catalogue
label is L_APMP_MK. This confirms the donor identity through actual firmware
records and execution, without relying on the older 0xB2 label namespace.
The probe is synthetic; it does not capture a live PC print job.

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
It executes conversion 0x438D1118: input 6 returns numeric value 102.
**Correction:** this has not been established as a CMM media conversion. The caller
0x438C69E8 passes the result of the settings object's virtual method +0x48,
then stores the converted byte at output offset +0xE.

The original recipient catalogue selector also accepts the donor catalogue
with synthetic media 102 / BASE / DB / 1200×1200 / OUT_BIT 2 and selects
CMM 14, SML 213 and dither 702. This confirms the native catalogue relationship
of enum 102 to L_APMP_MK and the exact data dependencies.

A separate helper 0x438D0E70 converts input 36 to 178 (0xB2), but feeding 178
to the +0x48 setting conversion returns 166, not 102. These are different namespaces.
The actual Enhanced Matte job-settings object and its +0x48 result still need
to be traced; a display-name code must not be substituted directly.

The decoded dither header is version 3, 1024×1024, with stored bit width 12
(header bytes 0x16=1 and 0x17=4). The native unpacker computes the bit width as
8*byte[0x16]+byte[0x17]. Merely truncating thresholds to 8 bits is not a lossless
transplant and has not been staged. Complete raster input/comparison semantics
would need proof before any such representation change.

Results are recorded in `t3400-native-media-conversion.json`. No new EFU is
produced and the working V6 image is unchanged.

## Settings-object trace correction

The concrete vtable at 0x441610FC separates getter +0x40 (object +0x7C)
from getter +0x48 (object +0x80). The conversion above consumes the latter;
the constructor loads these fields from separate configuration keys. The
0x43725694 table maps configuration key 8 to field value 13, not 36 or 6.
Neither the index of a translated UI label nor a matching numeric result
proves a colour-media association. The previous “CMM media conversion” label
is withdrawn; paper-size semantics remain a hypothesis pending named evidence.

A direct colour anchor is now available: debug function 0x4398591C prints
PaperType from u16 +0x8 and CmmType from u16 +0xA. Caller 0x43836640
copies 0x9C bytes from its source object +0xD8 via 0x43836254 into that
configuration. This gives an actual colour-settings source to trace, rather
than inferring colour routing from an unrelated converted byte. These are
static dataflow findings; the job's Enhanced Matte value is still unresolved.

### Actual PaperType producer

Function 0x43835820 builds this colour configuration at raster object +0xD8.
At 0x438358E8 it uses an existing media override from object +0x6C, or calls
0x43835CF0 when that override is -1. The latter maps raster object u16 +0x44
through 31 pairs at 0x43D4DFDC. Both input codes 144 and 215 map to PaperType
102 (the catalogue's L_APMP_MK); code 178 is absent and returns 0xFFFF.
The native function is executed in the probe, including its original table
copy. This is a real CMM producer, but neither 144 nor 215 is yet connected
to the Enhanced Matte user setting. No earlier numeric shortcut is retained.

## Name-table association resolved

The earlier unresolved-identity notes above describe the investigation before
finding code 215 in the independent UI-name and IPP-media tables. Those notes
are superseded by the confirmed identity section. Native assertions cover both
records, the CMM producer, and the catalogue selection. The large dither storage
and full raster-processing blockers remain; no new EFU is released.

## Storage audit update

`dither-storage-audit.md` records native overwrites at both decoded image EOFs.
Direct library/main append is rejected. Exact reversible bit-plane compression
also remains about 3.1 MB for the two matrices, so the tested codecs do not
resolve storage. V6 and the offline SML-only image are unchanged.
