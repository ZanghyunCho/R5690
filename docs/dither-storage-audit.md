# Exact donor dither storage: verified exclusions

The confirmed Enhanced Matte 1200×1200 dependency is selector 702 (24 bytes)
and matrices 662 / 682 (1,572,896 bytes each): **3,145,816 bytes** total.
No new firmware is produced by these probes.

The apparent tail after the decoded library is not available storage.
Its EOF is 0x4836A674, and the main program has a pointer to that exact
address at 0x4863C1E0. Caller 0x4863BA0C passes it as a destination to the
original Thumb strcpy at 0x4891CAC1. The native copy overwrites a 32-byte
sentinel planted at that address. This is a live runtime string buffer.

Likewise, main EOF 0x4934ADFC is a live object. Literal 0x484B9DE0 supplies
this address; native snippet 0x484B95F8..0x484B960C writes two halfwords at
its start. Synthetic values 0xA55A and 0x5AA5 reproduce the overwrite exactly.
These probes demonstrate stores, not a complete boot. Neither ELF symbols
nor the full extent of these runtime allocations has been established.

The nominal library-to-main interval is only 1,198,476 bytes, already too
small for the exact dependency set even before accounting for this live data.
Thus neither padding nor a decoded file EOF authorizes an appended resource.
The earlier controller framebuffer collision makes this distinction essential.

An independent lossless-compression probe executed the original matrix
unpacker, then reversibly rearranged all 12 bits into bit planes. It did not
quantize thresholds. XZ/LZMA compresses the two bit-plane representations to
1,551,440 and 1,551,420 bytes; the raw packed matrices hardly compress at all.
This rules out those tested representations as a way to fit the nominal gap.
It does not claim no conceivable compression scheme could work, and no
LZMA decoder has been added to firmware.

Reproduce with the repository's Unicorn bindings:

- `python tools/audit_dither_storage.py`
- `python tools/probe_dither_lossless_storage.py`

The JSON reports record native overwrite evidence and compression sizes.
A usable integration still requires an independently established owned ROM
resource / loader path or a bounded relocation that preserves live state.
The emulator's 0x02000000 mapping in the CROM tests is not evidence that this
is a persistent, directly readable ROM window during printing. No such
assumption is used to construct a candidate.
