# WITHDRAWN — V5 repeats the boot-time shutdown

The framebuffer/code overlap common to V4/V5 is now reproduced. See
`virtual-csic-framebuffer-collision.md`. The following is historical test scope,
not evidence that V5 is usable.

# V5 startup-regression candidate

V4 was withdrawn after the user reported logo/progress followed by power-off.
Stock restored normal boot. V5 corrects reproduced source defects, but the exact
physical shutdown cause and physical V5 boot remain unconfirmed.

Changes against V4:

1. Protected-cell writes return success 0 for all virtual slots.
2. An unactivated setter uses the original field packer without SEED/property
   calls. Transport and handshake entries also retain their native entry until
   the UID cache identifies an activated virtual slot.
3. Activation occurs at original registration boundary 0x47C58508. SEED checks
   the native property-manager readiness guard before requesting SKU data.
4. The stock CSIC GPIO lifecycle and hardware initializer are restored. Only
   virtual presence selection is replaced. Low-level GPIO success is simulated
   in integration tests; actual GPIO/OS behavior has not been exercised.
5. Runtime markers in FF image padding are removed. The existing UID cache is
   compared against all 22 expected bytes. The native bank clear invalidates
   the UID cache before reconstruction at the next registration boundary.

`validate_virtual_csic_startup_regression.py` compares the exact withdrawn V4
EFU against the fixed source: 64 early-setter cases, 8 protected-return controls
and 36 native-entry controls. The early setter cases run without a property
read mock, with manager-ready both zero and nonzero. V4's new early property
request is a negative control. Source bytes for the CSIC hardware initializer
and GPIO lifecycle are asserted identical to stock.

`validate_virtual_csic_boot_fix.py` executes 72 original full scans, 144 original
consumption commits and 144 re-registrations, plus four fresh-RAM reconstruction
cases. The helper/table padding is mapped read/execute only. Stock GPIO setup
executes with mocked low-level APIs and is asserted observed in every case.
No physical chip transport or chip-history object writes/formats occur in the
candidate test paths. The stock positive control reaches physical transport.

The 126 scalar, 232 unchanged-error and 45 level-snapshot tests also pass. The
EFU's unpacked controller hash equals the exact tested source. The builder
checks all 14 records, original ARM reconstruction of five CROMs, independent
IPL correction and ZIP readback. Existing MB patch and T3400 CLUTs are retained.

These checks do not constitute a complete OS boot or actual watchdog/peripheral
validation. Executable ownership of the FF region on actual hardware remains
unconfirmed; removing runtime writes does not prove it. Physical update/boot,
no-chip printing and automatic ink supply remain unverified. V5 is explicitly
an offline candidate, not a confirmed repair. V4 and its disabled builder stay
withdrawn. No physical NVRAM erasure, pump, IES or Initial Charge patch is added.

Reports: `virtual-csic-v5-startup.json`, `virtual-csic-v5-integration.json`,
`virtual-csic-v5-interfaces.json`; full packaging record is in the V5 manifest.
