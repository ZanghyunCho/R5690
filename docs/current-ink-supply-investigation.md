# Current ink supply and recognition investigation

The user reports better colours with T3400 CLUT v1 but later poor M ink supply
during ordinary use. They switched to maintenance-only firmware to expose the
pack error; that firmware then displayed an ink-pack recognition/install error.
Do not describe this latter observation as the same message on LUT v1. The
user subsequently reports that the old aggregate-error v3 candidate also
displays “다음 잉크팩을 인식할 수 없습니다”. No repair is established by v3.

The user suggests a changed ink serial/new-pack recognition may be needed.
That is a hypothesis, not a verified cause of the M supply issue. No current
chip detail response or pump-state trace is available. A read-only request for
Adjustment Program “Printer information check” fatal error history is pending.
Such history may be useful but is not guaranteed to expose a nonfatal current
cartridge error.

## Evidence from original firmware

V1's controller patch writes normal/100% into snapshot inputs and scalar
state caches, zeroes per-colour status/error cache updates, and overrides the
supported-colour status getter. These changes affect internal state, not only
display formatting. They can discard state distinctions needed elsewhere;
their role in this M supply issue remains unproven. The LUT v1 EFU retained
that controller exactly. MB-only retains original ink behavior. The v3
candidate preserves more raw state but modifies outgoing A80 reports and the
derived 0x104 error value; it does not implement a coherent virtual chip.

Controller function `0x47C582B4` validates handshake/readback and fields 0x59
and 0x72 before calling subsequent identity-related code. Therefore changing
an identity alone cannot fix a failure in one of those preceding checks.
Existing validated details include 0x10/0x11 for those field checks and 0x31
for a readback mismatch, but none is established as the current device's value.

`0x47C8D4F8` obtains per-slot chip data and invokes history/identity helpers.
`0x47D11918` compares the first 21 bytes, the low nibble of byte 21, and a
16-bit value at +22. With matching identity and a larger historical counter,
it sets a flag. Original ARM execution on five synthetic cases confirms this:
equal/higher incoming counters leave the flag clear; a lower incoming counter
sets it; a different identity leaves it clear. See
`tools/probe_ink_identity_history.py` and
`artifacts/ink-status-pipeline/identity-history.json`.

This is one identity/counter check, not proof that any particular bytes form
the displayed serial or that changing them creates a valid new-pack event.
It does not start a pump or prove physical ink supply. No identity, chip,
NVRAM, service flag or firmware change was made in response to this report.
Do not generate a new identity on every boot and claim it fixes supply.

## Halftone work retained, not cancelled

Original catalogue selector `0x48ABE280` was executed with synthetic settings
`[subtype=0, media=0, doc=4, halftone=3, channel_type=1, H, V, out_bits=2]`.
It selects stock BASE CMM IDs 11/13/14, SML 211/220/214 and dither 650/651/652
for 600×600 / 600×1200 / 1200×1200. Retargeting the catalogue rows to deliberately
uninstalled experimental IDs changes the returned SML/dither IDs; E-RGB
control rows remain unchanged. Twelve original-code checks pass, recorded in
`artifacts/t3400-lut/halftone-transplant/native-mode-selection.json` and
`tools/trace_colour_mode_selection.py`. These are selection checks, not an EFU.

The CMM allocator routes via `0x4860FE08` into `0x4860FD1C`, which tries pool
0x68 and falls back to 0x805A via `0x48919F94`. The named `jfklut` table entry
alone must not be treated as a proven hard limit for these allocations.
Actual free space and safe backing storage still require verification.
