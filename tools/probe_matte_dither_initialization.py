"""Offline native two-matrix initialization through stock resource handles.

Synthetic emulator resource table and allocator are NOT a firmware storage
implementation. No EFU, device access, boot or physical raster emulation.
"""
from pathlib import Path
import json,struct,hashlib
from colour_blob_codec import Codec
from unicorn import UC_HOOK_CODE
from unicorn.arm_const import *
ROOT=Path(__file__).resolve().parents[1]
sha=lambda d:hashlib.sha256(d).hexdigest()

def main():
    inv=json.loads((ROOT/'artifacts/t3400-lut/colour-blobs/inventory.json').read_text())
    raw=(ROOT/inv['t3400']['source']).read_bytes();resources={}
    for i in range(180):
        key,start,end=struct.unpack_from('<III',raw,0x356e0+i*12)
        resources[key]=raw[start-0x44294310:end-0x44294310]
    c=Codec();u=c.cpu
    lib=(ROOT/'artifacts/maintenance-virtualization/decoded/114880856.crom.1.bin').read_bytes()
    u.mem_map(0x4808f000,(len(lib)+4095)//4096*4096);u.mem_write(0x4808f000,lib)
    u.mem_map(0x23100000,0x700000)
    # Repoint only the table literals in THIS emulator. Scratch addresses below
    # are host test fixtures, never proposed persistent printer addresses.
    assert struct.unpack_from('<II',lib,0x4809950c-0x4808f000)==(0x48215314,0x4821505c)
    u.mem_write(0x4809950c,struct.pack('<II',0x20070000,0x20071000))
    u.mem_write(0x20070000,struct.pack('<I',3))
    for i,key in enumerate([662,682,702]):
        addr=0x22000000+i*0x200000;u.mem_write(addr,resources[key])
        u.mem_write(0x20071000+8*i,struct.pack('<II',key,addr))
    handle=0x20060000
    u.mem_write(handle,struct.pack('<4I',0x20080000,0x20050000,0,0))
    allocations=[];release_ids=[];cursor=[0x23000000]
    def alloc(cpu,address,size,ctx):
        n=cpu.reg_read(UC_ARM_REG_R1);assert n in (0x234,1024*1024*2+4)
        ptr=cursor[0];cursor[0]+=(n+15)&~15
        assert cursor[0]<=0x23800000
        err=cpu.reg_read(UC_ARM_REG_R3);cpu.mem_write(err,struct.pack('<I',0))
        allocations.append(dict(bytes=n,pointer=hex(ptr)))
        cpu.reg_write(UC_ARM_REG_R0,ptr);cpu.reg_write(UC_ARM_REG_PC,cpu.reg_read(UC_ARM_REG_LR))
    def release(cpu,address,size,ctx):
        release_ids.append(dict(cached_pointer=hex(struct.unpack('<I',cpu.mem_read(handle+12,4))[0])))
    u.hook_add(UC_HOOK_CODE,alloc,begin=0x48aab300,end=0x48aab300)
    u.hook_add(UC_HOOK_CODE,release,begin=0x48099508,end=0x48099508)
    u.mem_write(0x201ff000,struct.pack('<3I',handle,0x20075000,1))
    context=c.call(0x48ade564,[702,4,0,0x20050000],instruction_limit=400000000)
    assert context!=0
    assert struct.unpack('<I',u.mem_read(0x20075000,4))[0]==0
    desc=[struct.unpack('<11I',u.mem_read(context+44*i,44)) for i in range(2)]
    assert len(allocations)==3 and len(release_ids)==3
    assert all(d[1:3]==(1024,1024) for d in desc)
    expected=json.loads((ROOT/'artifacts/t3400-lut/halftone-transplant/native-matrix-validation.json').read_text())
    outputs=[]
    for key,d in zip([682,662],desc):
        data=bytes(u.mem_read(d[0],d[1]*d[2]*2+4));digest=sha(data)
        assert digest==next(x['decoded_sha256'] for x in expected if x['id']==key)
        outputs.append(dict(id=key,descriptor=list(d),sha256=digest))
    channel_aux=[list(struct.unpack('<2I',u.mem_read(context+0x1e4+8*i,8))) for i in range(4)]
    assert channel_aux[0]==channel_aux[2] and channel_aux[1]==channel_aux[3]
    assert struct.unpack('<I',u.mem_read(handle+12,4))[0]==0
    assert struct.unpack('<4I',u.mem_read(context+0x1b8,16))==(0,1,0,1)
    frees=[]
    def free(cpu,address,size,ctx):
        ptr=cpu.reg_read(UC_ARM_REG_R1);frees.append(ptr)
        assert ptr in [int(a['pointer'],16) for a in allocations] or ptr==0
        cpu.reg_write(UC_ARM_REG_R0,0);cpu.reg_write(UC_ARM_REG_PC,cpu.reg_read(UC_ARM_REG_LR))
    u.hook_add(UC_HOOK_CODE,free,begin=0x48aab3e0,end=0x48aab3e0)
    assert c.call(0x48ade6f0,[context,0x20050000])==0
    assert sorted(p for p in frees if p)==sorted(int(a['pointer'],16) for a in allocations)
    report=dict(status='NATIVE TWO-MATRIX RESOURCE INITIALIZATION PASSED; SYNTHETIC STORAGE/ALLOCATOR',
        function='0x48ADE564',cleanup_function='0x48ADE6F0',freed_all_allocations=True,
        raw_native_parameter=0,parameter_semantics_unresolved=True,resource_ids=[682,662],channel_resource_mapping=[682,662,682,662],
        matrix_outputs=outputs,native_allocations=allocations,total_matrix_allocation_bytes=sum(a['bytes'] for a in allocations if a['bytes']!=0x234),
        resource_release_calls=release_ids,resource_handle_cache_cleared=True,channel_aux=channel_aux,
        limits=['The resource table is redirected to host-provided emulator memory; this is not a deployable storage or flash loader.',
            'Allocator and free mocked with distinct bounded buffers; physical heap capacity/fragmentation unverified.',
            'The native release API clears its cached resource pointer, but the library release callback is a no-op for static resources; an external loader would need explicit ownership/free handling.',
            'No complete halftone raster execution, print quality or boot validation; no EFU produced.'])
    (ROOT/'docs/matte-dither-initialization.json').write_text(json.dumps(report,indent=2)+'\n')
    print(report['status']);print('Matrix allocation bytes:',report['total_matrix_allocation_bytes'])
if __name__=='__main__':main()
