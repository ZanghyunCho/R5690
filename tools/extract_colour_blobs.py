"""Extract ROM colour blobs using the unmodified R5691 ARM decoder.

BA payloads remain in their stored planar layout; this does not perform the
runtime planar-to-interleaved transform. No firmware is modified.
"""
from pathlib import Path
import hashlib
import json
import struct
from unicorn import Uc, UC_ARCH_ARM, UC_MODE_ARM
from unicorn.arm_const import UC_ARM_REG_R0, UC_ARM_REG_R1, UC_ARM_REG_R2, UC_ARM_REG_R3, UC_ARM_REG_SP, UC_ARM_REG_LR, UC_ARM_REG_PC

ROOT = Path(__file__).resolve().parents[1]
MAGIC = bytes.fromhex('7acf865c7d903c')

def extract():
    main = (ROOT/'artifacts/maintenance-virtualization/decoded/107423412.crom.0.bin').read_bytes()
    cpu = Uc(UC_ARCH_ARM, UC_MODE_ARM)
    cpu.mem_map(0x4848f000, (len(main)+4095)//4096*4096)
    cpu.mem_write(0x4848f000, main)
    for addr, size in [(0x20000000, 0x200000), (0x21000000, 0x20000), (0x22000000, 0x800000)]:
        cpu.mem_map(addr, size)
    sources = {
        'r5691': ROOT/'artifacts/maintenance-virtualization/decoded/114880856.crom.1.bin',
        't3400': ROOT/'artifacts/t3400-lut/decoded/65809.crom.0.bin',
    }
    inventory = {}
    for model, source in sources.items():
        data = source.read_bytes()
        ids = {}
        if model == 'r5691':
            for i in range(87):
                key, ptr = struct.unpack_from('<II', data, 0x4821505c-0x4808f000+i*8)
                ids[ptr-0x4808f000] = key
        else:
            # Donor uses ID/start/end triples. Address-to-file delta checked
            # independently against five named PNG resource records.
            for i in range(180):
                key, ptr, end = struct.unpack_from('<III', data, 0x356e0+i*12)
                off = ptr-0x44294310
                assert 0 <= off < len(data) and end >= ptr
                ids[off] = key
        folder = ROOT/'artifacts/t3400-lut/colour-blobs'/model
        folder.mkdir(parents=True, exist_ok=True)
        records = []
        off = 0
        while True:
            off = data.find(MAGIC, off)
            if off < 0:
                break
            here, off = off, off+1
            if data[here+7] not in (0xb9, 0xba):
                continue
            n, size = struct.unpack_from('<II', data, here+8)
            if not (0 < n < 0x180000 and 0 < size <= 0x800000 and here+12+n <= len(data)):
                continue
            record = dict(offset=hex(here), id=ids.get(here), variant=hex(data[here+7]), compressed_size=n, decoded_size=size)
            cpu.mem_write(0x20001000, data[here+12:here+12+n])
            cpu.mem_write(0x22000000, bytes(size))
            cpu.mem_write(0x201ff000, struct.pack('<I', 0x21000000))
            for reg, val in [(UC_ARM_REG_R0,0x20001000),(UC_ARM_REG_R1,n),(UC_ARM_REG_R2,0x22000000),(UC_ARM_REG_R3,size),(UC_ARM_REG_SP,0x201ff000),(UC_ARM_REG_LR,0x20000100)]:
                cpu.reg_write(reg, val)
            try:
                cpu.emu_start(0x48ad4b04, 0x20000100, count=30000000)
                if cpu.reg_read(UC_ARM_REG_PC) != 0x20000100 or cpu.reg_read(UC_ARM_REG_R0) != size:
                    raise ValueError('decoder did not return the expected output size')
                output = bytes(cpu.mem_read(0x22000000, size))
                filename = f'{here:08x}.bin'
                (folder/filename).write_bytes(output)
                record.update(file=filename, sha256=hashlib.sha256(output).hexdigest(), header_hex=output[:96].hex())
            except Exception as error:
                record['error'] = str(error)
            records.append(record)
        inventory[model] = dict(source=str(source.relative_to(ROOT)), source_sha256=hashlib.sha256(data).hexdigest(), blobs=records)
        print(model, len(records), 'blobs,', sum('error' in r for r in records), 'errors', flush=True)
    out = ROOT/'artifacts/t3400-lut/colour-blobs/inventory.json'
    out.write_text(json.dumps(inventory, indent=2)+'\n')

if __name__ == '__main__':
    extract()
