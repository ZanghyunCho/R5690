"""Construct unreleased virtual register images from stock supported-part data.

These are NOT authenticated physical-chip images or flashable firmware. Tests
cover logical metadata/capacity parsing only; authentication/discovery and
unlimited-ink/supply behavior remain unimplemented.
"""
from pathlib import Path
import hashlib
import json
import struct
from unicorn import UC_HOOK_CODE
from unicorn.arm_const import *
from prototype_virtual_csic_transport import machine,call,BUFFERS,ROOT,BASE

def main():
    stock=(ROOT/'artifacts/maintenance-virtualization/decoded/119075160.crom.0.bin').read_bytes()
    assert hashlib.sha256(stock).hexdigest()=='73e74252536d2880799c66b5dbf186b06848bf51d1a5763e0b5e708f9e4b018b'
    folder=ROOT/'artifacts/virtual-csic-images';folder.mkdir(exist_ok=True)
    reports=[]
    for row in range(6):
        offset=0x47d39134-BASE+12*row
        sku=stock[offset];parts=struct.unpack_from('<I',stock,offset+4)[0]
        for slot in range(4):
            code,kind,unused,upper,lower=struct.unpack_from('<HBBHH',stock,parts-BASE+8*slot)
            assert code!=65535 and kind==12 and 0<lower<upper
            scale=5 if upper-1>4095 else 1
            raw_capacity=(upper-1)//scale
            capacity=raw_capacity*scale
            assert lower<=capacity<upper and raw_capacity<=4095
            cpu=machine(stock)
            requests=[]
            def property_read(uc,address,size,context):
                prop=uc.reg_read(UC_ARM_REG_R0);dest=uc.reg_read(UC_ARM_REG_R1);length=uc.reg_read(UC_ARM_REG_R2)
                assert prop==0x2e6 and length==1
                requests.append(prop);uc.mem_write(dest,bytes([sku]));uc.reg_write(UC_ARM_REG_R0,0)
                uc.reg_write(UC_ARM_REG_PC,uc.reg_read(UC_ARM_REG_LR))
            cpu.hook_add(UC_HOOK_CODE,property_read,begin=0x47c4b0c8,end=0x47c4b0c8)
            cpu.mem_write(BUFFERS[slot],bytes(168))
            # Set logical fields through the ORIGINAL native bit packer. The
            # supported part code and range come from the stock SKU table.
            values={0x52:raw_capacity,0x53:code,0x57:int(scale==5),0x59:kind,0x72:0x40+slot,
                    0x48:0x3f,0x49:0xf,0x4a:0x1f,0x79:0x40}
            for field,value in values.items():
                assert call(cpu,0x47c52674,[slot,field,value])==0
                assert call(cpu,0x47c522f0,[slot,field,0x20001000])==0
                observed=struct.unpack('<H',cpu.mem_read(0x20001000,2))[0]
                assert observed==value,(hex(field),value,observed)
            call(cpu,0x47c55e94,[1<<slot])
            # 56-byte per-colour capacity structure used by stock CSIC code.
            result=bytes(cpu.mem_read(0x47e03490+56*slot,56))
            assert result[0]==kind
            assert struct.unpack_from('<H',result,2)[0]==capacity
            assert requests==[0x2e6]
            assert call(cpu,0x47c5256c,[slot,0x20001000])==0
            assert struct.unpack('<H',cpu.mem_read(0x20001000,2))[0]==0
            raw=bytes(cpu.mem_read(BUFFERS[slot],168))
            filename=f'sku-{sku:02x}-slot-{slot}.register-image.bin'
            (folder/filename).write_bytes(raw)
            reports.append(dict(sku=hex(sku),slot=slot,part_code=hex(code),kind=kind,
                capacity=capacity,raw_capacity=raw_capacity,native_capacity_scale=scale,stock_allowed_range=[lower,upper],fields={hex(k):v for k,v in values.items()},
                native_capacity_parser_matched=True,initial_counter=0,file=filename,sha256=hashlib.sha256(raw).hexdigest()))
    report=dict(status='UNRELEASED METADATA IMAGES; NOT A COMPLETE VIRTUAL CARTRIDGE OR EFU',
        factory_table='0x47D39134',native_field_packer='0x47C52674',native_capacity_parser='0x47C55E94',
        cases=reports,limits=['Synthetic runtime SKU property, not a read of the current printer.',
            'First four supported entries are selected as slot candidates; physical part/colour identity beyond the tested parser is unverified.',
            'Images have no authenticated UID/challenge data and do not implement no-chip discovery.',
            'No reboot, unlimited ink, physical pump, IES or print behavior is established.'])
    (folder/'REPORT.json').write_text(json.dumps(report,indent=2)+'\n')
    print('24 SKU/slot candidates: native field packing/readback and capacity parsing pass; not complete virtual chips.')

if __name__=='__main__':main()
