"""Read-only storage audit; native snippets demonstrate why append is unsafe.

No EFU construction or printer access. Synthetic register/stack inputs are
explicitly chosen to exercise original stores, not to emulate a full boot.
"""
from pathlib import Path
import hashlib,json,struct
from colour_blob_codec import Codec
from unicorn.arm_const import *
ROOT=Path(__file__).resolve().parents[1]
sha=lambda b:hashlib.sha256(b).hexdigest()

def main():
    folder=ROOT/'artifacts/maintenance-virtualization/decoded'
    main=(folder/'107423412.crom.0.bin').read_bytes()
    lib=(folder/'114880856.crom.1.bin').read_bytes()
    main_end=0x4848f000+len(main);lib_end=0x4808f000+len(lib)
    assert main_end==0x4934adfc and lib_end==0x4836a674
    assert struct.unpack_from('<I',main,0x484b9de0-0x4848f000)[0]==main_end
    assert struct.unpack_from('<I',main,0x4863c1e0-0x4848f000)[0]==lib_end
    codec=Codec();cpu=codec.cpu
    cpu.mem_map(0x4808f000,(len(lib)+4095)//4096*4096);cpu.mem_write(0x4808f000,lib)
    sentinel=bytes(range(32));cpu.mem_write(main_end,sentinel)
    cpu.mem_write(0x201fe004,struct.pack('<H',0x5aa5))
    cpu.reg_write(UC_ARM_REG_SP,0x201fe000);cpu.reg_write(UC_ARM_REG_R5,0xa55a)
    cpu.emu_start(0x484b95f8,0x484b960c,count=10)
    assert cpu.reg_read(UC_ARM_REG_PC)==0x484b960c
    main_after=bytes(cpu.mem_read(main_end,32))
    assert main_after[:4]==struct.pack('<HH',0xa55a,0x5aa5) and main_after[4:]==sentinel[4:]
    # Original caller 0x4863BA0C supplies exactly lib_end as strcpy destination.
    text=b'owned-runtime-string\0';cpu.mem_write(0x22000000,text);cpu.mem_write(lib_end,sentinel)
    assert codec.call(0x4891cac1,[lib_end,0x22000000])==lib_end
    lib_after=bytes(cpu.mem_read(lib_end,32));assert lib_after[:len(text)]==text
    inv=json.loads((ROOT/'artifacts/t3400-lut/colour-blobs/inventory.json').read_text())
    source=(ROOT/inv['t3400']['source']).read_bytes();table={}
    for i in range(180):
        key,start,end=struct.unpack_from('<III',source,0x356e0+12*i)
        table[key]=(start-0x44294310,end-0x44294310)
    resources=[]
    for key in [662,682,702]:
        a,b=table[key];data=source[a:b]
        resources.append(dict(id=key,bytes=len(data),sha256=sha(data)))
    report=dict(status='APPEND LOCATIONS REJECTED: ORIGINAL NATIVE WRITES REPRODUCED',
        source_sha256=dict(main=sha(main),library=sha(lib)),
        main_append=dict(address=hex(main_end),pointer_literal='0x484B9DE0',native_snippet=['0x484B95F8','0x484B960C'],
            synthetic_halfwords=[0xa55a,0x5aa5],before=sentinel.hex(),after=main_after.hex()),
        library_append=dict(address=hex(lib_end),pointer_literal='0x4863C1E0',caller='0x4863BA0C',
            native_copy='0x4891CAC1 (Thumb)',synthetic_string=text.decode(),before=sentinel.hex(),after=lib_after.hex()),
        donor_resources=resources,required_raw_bytes=sum(x['bytes'] for x in resources),
        nominal_library_to_main_gap=0x4848f000-lib_end,
        conclusions=['Decoded image EOF is not the end of runtime ownership; both exact EOF addresses are live mutable storage.',
            'Appending resources at either EOF would conflict with original stores; no such firmware was built.',
            'Even the nominal library-to-main gap is smaller than the exact donor resource set, and its start is already live storage.',
            'A separate owned storage/loading mechanism or proven bounded relocation is required.'],
        limits=['Native snippets and strcpy only; synthetic values, no complete boot, MMU or printer hardware emulation.',
            'No ROM window mapping or safe free flash partition has been established.'])
    (ROOT/'docs/dither-storage-audit.json').write_text(json.dumps(report,indent=2)+'\n')
    print(report['status']);print('Required raw resources:',report['required_raw_bytes'])
if __name__=='__main__':main()
