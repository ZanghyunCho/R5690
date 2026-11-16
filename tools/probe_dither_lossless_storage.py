"""Offline exact bit-plane compression feasibility; no firmware decoder or EFU.
Original matrix unpacker runs with a mocked allocator and synthetic 12-bit input.
"""
from pathlib import Path
import json,struct,zlib,lzma
import numpy as np
from colour_blob_codec import Codec
from unicorn import UC_HOOK_CODE
from unicorn.arm_const import *
r=Path(__file__).resolve().parents[1];inv=json.loads((r/'artifacts/t3400-lut/colour-blobs/inventory.json').read_text());d=(r/inv['t3400']['source']).read_bytes();resources={}
for i in range(180):
 k,a,b=struct.unpack_from('<III',d,0x356e0+12*i);resources[k]=d[a-0x44294310:b-0x44294310]
c=Codec();u=c.cpu;u.mem_map(0x23100000,0x300000)
def alloc(cpu,a,s,ctx):
 cpu.reg_write(UC_ARM_REG_R0,0x23000000);cpu.reg_write(UC_ARM_REG_PC,cpu.reg_read(UC_ARM_REG_LR))
u.hook_add(UC_HOOK_CODE,alloc,begin=0x48aab300,end=0x48aab300)
report=[];arrays=[]
for k in [662,682]:
 raw=resources[k];u.mem_write(0x22000000,raw);u.mem_write(0x20030000,bytes(1024));u.mem_write(0x201ff000,struct.pack('<III',4,0x22000000,1));assert c.call(0x48addfe8,[0x20030000,0x20030100,0,12])==0
 a=np.frombuffer(bytes(u.mem_read(0x23000000,1024*1024*2)),dtype='<u2').reshape(1024,1024);arrays.append(a)
 # Reversible bit-plane representation, no threshold quantization.
 planes=b''.join(np.packbits(((a>>bit)&1).astype('uint8'),bitorder='little').tobytes() for bit in range(12))
 assert np.array_equal(sum(np.unpackbits(np.frombuffer(planes[i*131072:(i+1)*131072],dtype='uint8'),bitorder='little').astype('uint16').reshape(1024,1024)<<i for i in range(12)),a)
 cases={'original':raw,'bitplanes':planes}
 report.append(dict(id=k,min=int(a.min()),max=int(a.max()),encodings={name:{'raw':len(v),'zlib':len(zlib.compress(v,9)),'lzma':len(lzma.compress(v))} for name,v in cases.items()}))
 print(report[-1],flush=True)
print('equal',np.array_equal(*arrays))
out=r/'docs/dither-lossless-compression-probe.json';out.write_text(json.dumps({'status':'OFFLINE COMPRESSION FEASIBILITY ONLY; NO FIRMWARE DECODER IMPLEMENTED','matrices':report},indent=2)+'\n')
