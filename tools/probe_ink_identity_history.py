"""Read-only original-code identity/counter comparisons with synthetic records.

This does not assert that a different identity constitutes a new ink pack or
that passing this comparison starts a pump. No chip or NVRAM is written.
"""
from pathlib import Path
import hashlib
import json
import struct
from unicorn import Uc, UC_ARCH_ARM, UC_MODE_ARM
from unicorn.arm_const import *

ROOT=Path(__file__).resolve().parents[1]

def main():
    data=(ROOT/'artifacts/maintenance-virtualization/decoded/119075160.crom.0.bin').read_bytes()
    assert hashlib.sha256(data).hexdigest()=='73e74252536d2880799c66b5dbf186b06848bf51d1a5763e0b5e708f9e4b018b'
    cpu=Uc(UC_ARCH_ARM,UC_MODE_ARM)
    cpu.mem_map(0x47c48000,(len(data)+4095)//4096*4096);cpu.mem_write(0x47c48000,data)
    cpu.mem_map(0x20000000,0x20000)
    def record(uid,counter):
        assert len(uid)==22
        return uid+struct.pack('<H',counter)
    uid=bytes(range(22));other=bytes([0x70])+uid[1:]
    cases=[]
    for label,history,current,expected in [
        ('same identity, same counter',record(uid,10),record(uid,10),0),
        ('same identity, lower current counter',record(uid,10),record(uid,9),1),
        ('same identity, higher current counter',record(uid,10),record(uid,11),0),
        ('different identity, lower current counter',record(uid,10),record(other,0),0),
        ('empty history sentinel',bytes([255])*24,record(uid,0),0),
    ]:
        cpu.mem_write(0x20001000,history+bytes([255])*24)
        cpu.mem_write(0x20004000,current);cpu.mem_write(0x20005000,b'\0')
        for r,v in [(UC_ARM_REG_R0,0x20001000),(UC_ARM_REG_R1,0x20004000),(UC_ARM_REG_R2,1),
                    (UC_ARM_REG_R3,0x20005000),(UC_ARM_REG_SP,0x2001f000),(UC_ARM_REG_LR,0x20000100)]:
            cpu.reg_write(r,v)
        cpu.emu_start(0x47d11918,0x20000100,count=10000)
        assert cpu.reg_read(UC_ARM_REG_PC)==0x20000100
        flag=cpu.mem_read(0x20005000,1)[0];assert flag==expected
        cases.append(dict(case=label,history_comparison_flag=flag))
    result=dict(function='0x47D11918',controller_sha256=hashlib.sha256(data).hexdigest(),cases=cases,
        observed='Compares 21 identity bytes, the low nibble of byte 21 and a 16-bit counter. A matched historical counter greater than the incoming counter sets flag 1.',
        upstream='0x47C8D4F8 obtains chip data and invokes identity/history helpers after earlier chip validation.',
        limits=['Synthetic identity records, not real serials or printer data.',
            'Changing the identity bypasses this one comparison only; it does not prove a new-pack event or ink-supply recovery.',
            'Handshake and field checks in 0x47C582B4 occur before this path; a new identity does not repair those failures.',
            'No physical pump, print test, chip write or NVRAM reset performed.'])
    folder=ROOT/'artifacts/ink-status-pipeline';folder.mkdir(exist_ok=True)
    (folder/'identity-history.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(result,indent=2))

if __name__=='__main__':main()
