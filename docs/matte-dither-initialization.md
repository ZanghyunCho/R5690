# Enhanced Matte selector and two-matrix initialization

`tools/probe_matte_dither_initialization.py` runs the stock top-level dither
initializer **0x48ADE564**, starting with donor selector 702. It does not
construct firmware. The resource table is redirected only in emulator memory
to host-supplied original donor bytes, and allocation/free are mocked.

Unlike the earlier individual-reader tests, this follows the original chain:

1. Fetch selector 702 through 0x48AAB60C and the original table lookup.
2. Decode its channel IDs, deduplicate them through 0x48ADE504, and retain
   channel mapping **[682, 662, 682, 662]**.
3. Initialize the two distinct 1024×1024 matrices through 0x48ADE388,
   0x48ADE294 and the original matrix parser/unpacker.
4. Verify both decoded matrices byte-for-byte by their established hashes.
5. Clear all three resource-handle caches through the original release path.
6. Run native cleanup **0x48ADE6F0** and verify every nonzero allocation is
   released exactly once via the mocked free callback.

Observed allocations are a 564-byte context and two 2,097,156-byte matrix
buffers: **4,194,876 bytes total**, excluding allocator bookkeeping, resource
source bytes, other colour resources and raster buffers. The matrix subtotal
is 4,194,312 bytes. No physical heap capacity/fragmentation test has occurred.

The raw native parameter propagated to the matrix loader is zero, matching
the earlier direct-reader calls. Its product meaning is not established.
The 12-bit stored threshold width comes from the data header; the fourth
argument `12` used as a mocked allocation context in earlier direct tests
must not be taken as proof of that parameter's semantic meaning.

Important ownership boundary: 0x48AAB588 calls library callback 0x48099508
and clears the resource-handle pointer. The callback is originally a no-op
because the source resources are static. A future external ROM/flash loader
cannot merely return newly allocated pointers here and assume they get freed;
it must implement matching resource ownership and release.

This verifies selector decoding, deduplication, two-matrix initialization,
channel associations and successful cleanup with synthetic memory. It does
not verify complete halftoning/raster output, an actual persistent resource
loader, print-mode runtime arguments, boot, or a deployable EFU. Storage
integration and sufficient physical heap are still unresolved.
