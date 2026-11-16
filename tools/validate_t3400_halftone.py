"""Execute stock ARM parsers on donor data; no printer or firmware writes.

Synthetic channel/bit inputs establish data-reader compatibility only.
They do not emulate the raster hardware or demonstrate print quality.
"""
from pathlib import Path
import hashlib
import json
import struct
from unicorn import UC_HOOK_CODE, UC_HOOK_MEM_READ
from unicorn.arm_const import *
from colour_blob_codec import Codec

ROOT=Path(__file__).resolve().parents[1]
FOLDER=ROOT/'artifacts/t3400-lut/colour-blobs'
OUT=ROOT/'artifacts/t3400-lut/halftone-transplant'

def main():
    OUT.mkdir(exist_ok=True)
    inventory=json.loads((FOLDER/'inventory.json').read_text())
    def decoded(model,key):
        record=next(r for r in inventory[model]['blobs'] if r['id']==key)
        blob=(FOLDER/model/record['file']).read_bytes()
        assert hashlib.sha256(blob).hexdigest()==record['sha256']
        return blob
    raw=(ROOT/inventory['t3400']['source']).read_bytes()
    assert hashlib.sha256(raw).hexdigest()==inventory['t3400']['source_sha256']
    donor={}
    for i in range(180):
        key,start,end=struct.unpack_from('<III',raw,0x356e0+i*12)
        donor[key]=raw[start-0x44294310:end-0x44294310]
    codec=Codec();cpu=codec.cpu
    cpu.reg_write(UC_ARM_REG_C1_C0_2,0xf00000)
    cpu.reg_write(UC_ARM_REG_FPEXC,0x40000000)
    cpu.mem_map(0x23100000,0x300000)
    def allocate(uc,address,size,context):
        assert 0<uc.reg_read(UC_ARM_REG_R1)<=0x400000
        uc.reg_write(UC_ARM_REG_R0,0x23000000)
        uc.reg_write(UC_ARM_REG_PC,uc.reg_read(UC_ARM_REG_LR))
    cpu.hook_add(UC_HOOK_CODE,allocate,begin=0x48aab300,end=0x48aab300)
    matrices=[]
    for key in [662,665,666,682,685,686,702,705,706]:
        data=donor[key];cpu.mem_write(0x22000000,data);cpu.mem_write(0x20030000,bytes(1024))
        if key>=700:
            ret=codec.call(0x48ade1e4,[0x20030000,4,0x22000000])
            item=dict(id=key,kind='selector',native_return=ret,
                resource_ids=list(struct.unpack('<4I',cpu.mem_read(0x20030000,16))))
        else:
            assert codec.call(0x48addac0,[0x22000000])==0
            cpu.mem_write(0x201ff000,struct.pack('<III',4,0x22000000,1))
            ret=codec.call(0x48addfe8,[0x20030000,0x20030100,0,12])
            assert ret==0
            desc=struct.unpack('<11I',cpu.mem_read(0x20030000,44))
            output=bytes(cpu.mem_read(desc[0],desc[1]*desc[2]*2+4))
            item=dict(id=key,kind='matrix',synthetic_input_bits=12,native_return=ret,
                descriptor=list(desc),decoded_sha256=hashlib.sha256(output).hexdigest(),decoded_bytes=len(output))
        assert ret==0
        matrices.append(item)
    (OUT/'native-matrix-validation.json').write_text(json.dumps(matrices,indent=2)+'\n')
    sml=[]
    for model,keys in [('r5691',[211,220,214]),('t3400',[217,226,225,244,245,246])]:
        for key in keys:
            blob=decoded(model,key);cpu.mem_write(0x22000000,blob)
            cpu.mem_write(0x20030000,bytes(0x4000));cpu.mem_write(0x23000000,bytes(0x10000))
            cpu.mem_write(0x20035000,struct.pack('<I4B',4,1,2,3,0))
            assert codec.call(0x48abf698,[0x2003285c,256,1])==0
            ret=codec.call(0x48abf630,[0x20030000,0x22000000,0x20035000,2])
            assert ret==0
            sml.append(dict(model=model,id=key,return_value=ret,synthetic_channel_codes=[1,2,3,0],
                synthetic_output_bits=2,context_sha256=hashlib.sha256(bytes(cpu.mem_read(0x20030000,0x29c4))).hexdigest(),
                allocated_table_sha256=hashlib.sha256(bytes(cpu.mem_read(0x23000000,61440))).hexdigest()))
    (OUT/'native-sml-validation.json').write_text(json.dumps(sml,indent=2)+'\n')
    checks=[]
    for key in [11,13,14]:
        blob=decoded('r5691',key);n=struct.unpack_from('<I',blob,20)[0]
        off=next(struct.unpack_from('<I',blob,28+8*i)[0] for i in range(n) if blob[24+8*i:28+8*i]==b'inkd')
        count=blob[off+5];pos=off+6+count+2*list(blob[off+6:off+6+count]).index(20)
        edited=bytearray(blob);struct.pack_into('<H',edited,pos,1)
        results=[];reads=[]
        for candidate in [blob,bytes(edited)]:
            cpu.mem_write(0x22000000,candidate);cpu.mem_write(0x20030000,bytes(0x5000))
            cpu.mem_write(0x20032000,struct.pack('<16I',*[0x20033000+4*i for i in range(16)]))
            cpu.mem_write(0x201ff000,struct.pack('<II',0x22000000,1));access=[]
            handle=cpu.hook_add(UC_HOOK_MEM_READ,lambda uc,a,addr,size,value,ctx:access.append([hex(addr-0x22000000),size]),
                begin=0x22000000+off+4,end=0x22000000+off+36-1)
            try: ret=codec.call(0x48abcae4,[0x20030000,0x20031000,0x20032000,1])
            finally: cpu.hook_del(handle)
            assert ret==0
            results.append(bytes(cpu.mem_read(0x20030000,0x5000)));reads.append(access)
        assert results[0]==results[1] and reads==[[],[]]
        checks.append(dict(id=key,parser='0x48ABCAE4',modified_total_field_offset=pos,
            context_outputs_identical=True,inkd_value_reads=reads))
    (OUT/'inkd-consumer-check.json').write_text(json.dumps(checks,indent=2)+'\n')
    print('Validated: 6 donor matrix readers, 3 selectors, 9 SML resources; inkd values unread in 3 paired parser tests.')

if __name__=='__main__':main()
