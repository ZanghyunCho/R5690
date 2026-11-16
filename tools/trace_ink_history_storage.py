"""Read-only link of ink identity/counter comparison to uploaded IC3 storage.

All device/NV APIs are intercepted. No flash reset, chip write or live device
operation. Uploaded identities are not printed or included in the report.
"""
from pathlib import Path
import hashlib
import json
import struct
from unicorn import Uc, UC_ARCH_ARM, UC_MODE_ARM, UC_HOOK_CODE
from unicorn.arm_const import *

ROOT=Path(__file__).resolve().parents[1]
DUMP=Path('/workspace/attachments/48456062-91f8-4af4-add6-cf6ad08f96bd/IC3.bin')

def main():
    dump=DUMP.read_bytes()
    assert len(dump)==0x1000000 and hashlib.sha256(dump).hexdigest()=='ca3c42d3bfa512ae66f7fff3077c81feb2cb45db498f64ac07b098ee805d7d20'
    code=(ROOT/'artifacts/maintenance-virtualization/decoded/119075160.crom.0.bin').read_bytes()
    assert hashlib.sha256(code).hexdigest()=='73e74252536d2880799c66b5dbf186b06848bf51d1a5763e0b5e708f9e4b018b'
    assert dump[0xfc0000:0xfc0008]==b'1WAY0001'
    cpu=Uc(UC_ARCH_ARM,UC_MODE_ARM)
    cpu.mem_map(0x47c48000,0x3b8000);cpu.mem_write(0x47c48000,code)
    cpu.mem_map(0x20000000,0x20000)
    history=bytearray(bytes([255])*(854*24));populated=[]
    for slot in range(853):
        pos=0xfc0010+slot*36;header=dump[pos:pos+12]
        if header==bytes([255])*12:
            continue
        obj,size,index=struct.unpack_from('<IHH',header)
        assert obj==0x04400001 and size==24 and index==slot
        payload=dump[pos+12:pos+36]
        history[24*slot:24*(slot+1)]=payload
        populated.append(payload)
    assert struct.unpack_from('<IH',dump,0xfc7804)==(0x04400002,4080)
    second=dump[0xfc7810:0xfc7810+4080]
    calls=[]
    def api(uc,address,size,context):
        descriptor=uc.reg_read(UC_ARM_REG_R0);target=uc.reg_read(UC_ARM_REG_R1)
        raw=bytes(uc.mem_read(descriptor,20))
        obj,unit=struct.unpack_from('<II',raw)
        index,count=struct.unpack_from('<HH',raw,8)
        calls.append(dict(api=hex(address),object_id=hex(obj),unit_bytes=unit,index=index,count=count,
            buffer_address=hex(target),operation='read' if address==0x47caf4d4 else 'write-intercepted-no-I/O'))
        if address==0x47caf4d4:
            data=bytes(history[index*24:(index+max(count,1))*24]) if obj==0x04400001 else second
            uc.mem_write(target,data)
        uc.reg_write(UC_ARM_REG_R0,0);uc.reg_write(UC_ARM_REG_PC,uc.reg_read(UC_ARM_REG_LR))
    for address in [0x47caf4d4,0x47caf4ec]:cpu.hook_add(UC_HOOK_CODE,api,begin=address,end=address)
    def call(address,args):
        for r,v in zip([UC_ARM_REG_R0,UC_ARM_REG_R1,UC_ARM_REG_R2,UC_ARM_REG_R3],args):cpu.reg_write(r,v)
        cpu.reg_write(UC_ARM_REG_SP,0x2001f000);cpu.reg_write(UC_ARM_REG_LR,0x20000100)
        cpu.emu_start(address,0x20000100,count=200000)
        assert cpu.reg_read(UC_ARM_REG_PC)==0x20000100
        return cpu.reg_read(UC_ARM_REG_R0)
    pointers={}
    for key,expected in [(0xa3,0x47e04c62),(0xd6,0x47e09c72)]:
        assert call(0x47c8e4fc,[key,0x20003000])==1
        ptr=struct.unpack('<I',cpu.mem_read(0x20003000,4))[0];assert ptr==expected
        pointers[hex(key)]=hex(ptr)
        count=853 if key==0xa3 else 0
        assert call(0x47c8dcac,[key,0,count,0])==0
        expected_data=bytes(history[:853*24]) if key==0xa3 else second
        assert bytes(cpu.mem_read(ptr,len(expected_data)))==expected_data
        assert call(0x47c8df50,[key,0,1 if key==0xa3 else 0,0])==0
    assert len(calls)==4
    # A synthetic incoming counter uses an uploaded identity only inside the
    # emulator. Identities and payload bytes never leave this process.
    template=max(populated,key=lambda r:struct.unpack_from('<H',r,22)[0])
    maximum=struct.unpack_from('<H',template,22)[0]
    examples=[]
    for label,value,alter_identity,expected in [('same-record',maximum,False,0),('lower-counter',maximum-1,False,1),('new-identity',0,True,0)]:
        assert value>=0
        current=bytearray(template);struct.pack_into('<H',current,22,value)
        if alter_identity:
            current[0]^=0x80
            assert not any(r[:21]==current[:21] for r in populated)
        cpu.mem_write(0x20004000,bytes(current));cpu.mem_write(0x20005000,b'\0')
        call(0x47d11918,[0x47e04c62,0x20004000,1,0x20005000])
        flag=cpu.mem_read(0x20005000,1)[0];assert flag==expected
        examples.append(dict(case=label,comparison_flag=flag))
    report=dict(status='READ-ONLY OFFLINE EVIDENCE; current error cause UNCONFIRMED',
        source_ic3_sha256=hashlib.sha256(dump).hexdigest(),sector='0xFC0000',format='1WAY0001',
        objects=[dict(id='0x04400001',first_header='0xFC0010',unit_bytes=24,slots=853,populated_slots=len(populated)),
                 dict(id='0x04400002',header='0xFC7804',payload='0xFC7810',bytes=4080)],
        ram_pointer_api='0x47C8E4FC',ram_buffers=pointers,native_nv_api_calls=calls,
        identity_comparison='0x47D11918',comparison_examples=examples,
        limitations=['This is the earlier uploaded IC3, not a fresh dump from the current failure.',
            'Native read/write API boundaries are mocked; no actual flash write or clear occurs.',
            'Readback demonstrates object and cache plumbing, not full 1WAY header validity/active-sector selection.',
            'Three ROMs were restored to stock together, so persistence and code changes are not isolated.',
            'Cannot identify the current error as a counter/history rejection without current device evidence.',
            'No dump payloads, ink identities, printer serial or NVRAM contents are published.'])
    out=ROOT/'artifacts/ink-status-pipeline/history-storage.json'
    out.write_text(json.dumps(report,indent=2)+'\n')
    print('IC3 1WAY object mapping verified; native read/write descriptors and 3 history comparisons passed. No device write.')
    print('Populated 24-byte history slots:',len(populated))

if __name__=='__main__':main()
