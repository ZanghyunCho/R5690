# T3400 CLUT-only candidate for R5691

**Ink virtualisation correction:** this retains the old V1 ink-state overrides,
not a complete virtual cartridge. Physical chip reads/writes and validation
remain active. The user reports real chip depletion and failure without chips.
The colour LUT change does not fix that limitation. See
`../../../docs/virtual-csic-rewrite-progress.md` for the unreleased rewrite.

**User reports that the update succeeded after a power cycle and colours look
better. No controlled colour measurement or verified print-path trace exists.**

An initial transfer-stage failure was resolved by power-cycling, according to
the user. The cause is unknown; a USB fault has not been proven. Historical
offline checks are in `rejection-audit.json`.

Read-only halftone and encoded ink-duty comparisons are in
`halftone-ink-comparison.md` and `halftone-ink-comparison.json`. No additional
EFU has been released from those findings. Follow-up native tests and an
important correction about ink-limit metadata are in
`halftone-transplant-progress.md`.

Based on the first virtual ink + maintenance v1, SHA256
`8ab2a81dcc85717e26c476b19aad84378395b52c33835d76cf936cb6f06705de`.

Only three colour CLUT payloads change:

| R5691 mode | T3400 source | Resolution |
| --- | --- | --- |
| PLAIN / BASE / subtype 0 / CMM 11 | L_PP / CMM 30 | 600×600 |
| PLAIN / BASE / subtype 0 / CMM 13 | L_PP / CMM 31 | 600×1200 |
| PLAIN / BASE / subtype 0 / CMM 14 | L_PP / CMM 32 | 1200×1200 |

The two printers' numeric channel codes and grid layouts match. Physical
channel assignment and actual ink/media colour performance are unverified.
Existing virtual-cartridge patches, encoded ink-duty metadata, gamma, dot conversion,
monochrome settings, DPI and passes are retained. Other modes, including
E-RGB, retain stock LUTs. This is not a complete T3400 ink or mode transplant.
The parent's reported discharge/re-charge stall is not fixed by this change.

Verified offline: original ARM blob decoder, original ARM LUT parser and BA
array transform, original CROM DHT preservation, native CROM header/setup and
LZ replay, all 14 IPL records, independent IPL correction, ZIP readback and
unchanged bytes outside the documented ranges. No printer was accessed.

The existing firmware version is retained. This build does not bypass version
checks. The author has no live printer access; update acceptance is user-reported.

For a meaningful output comparison, use the same document, paper and driver
settings before/after. The installed Epson driver's active processing path is
unverified; it may not use these three device-side modes, so output may remain
unchanged. An unchanged result does not establish that the LUT data are equal.

EFU SHA256:
`42e3630b8be35d8cd6dc469bff4c84528b27e7256b069cdb2e0e003fd5b2a62d`.

See `manifest.json` for exact changed ranges, hashes, verification and limits.
