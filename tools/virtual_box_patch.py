"""Bounded GR maintenance-state prototype. No device access or boot claim."""
from pathlib import Path
import hashlib,struct
ROOT=Path(__file__).resolve().parents[1]
BASE=0x47c48000
SOURCE='73e74252536d2880799c66b5dbf186b06848bf51d1a5763e0b5e708f9e4b018b'

def branch(address,target,link=False):
 assert (target-address-8)%4==0
 return (0xeb000000 if link else 0xea000000)|(((target-address-8)//4)&0xffffff)

def patch(data):
 assert hashlib.sha256(data).hexdigest()==SOURCE
 changes={
  # r8 was set to zero at 0x47ca95e8. Preserve conditional store and dispatch.
  0x47ca9608:(0x05c5401e,0x05c5801e,'Only status API opcode 0x30 stores normal=0'),
  # Preserve register usage and original comparisons; return the normal state.
  0x47ca8080:(0xe5d0001e,0xe3a00000,'Maintenance status getter reports normal=0'),
 }
 # Existing function had stack frame and returned 0 for non-full. Replace the
 # first four instructions with a balanced wrapper of the stock empty helper.
 originals=struct.unpack_from('<4I',data,0x47c63e0c-BASE)
 assert originals==(0xe92d4038,0xe59f046c,0xe3a02002,0xe1a0100d)
 for n,word in enumerate((0xe92d4010,branch(0x47c63e10,0x47c68da8,True),0xe3a00000,0xe8bd8010)):
  changes[0x47c63e0c+4*n]=(originals[n],word,'Counter gate publishes stock normal/100% response and returns non-full')
 result=bytearray(data);report=[]
 for addr,(before,after,purpose) in sorted(changes.items()):
  assert struct.unpack_from('<I',data,addr-BASE)[0]==before,(hex(addr),hex(before))
  struct.pack_into('<I',result,addr-BASE,after)
  report.append(dict(address=hex(addr),before=hex(before),after=hex(after),purpose=purpose))
 assert len(result)==len(data)
 allowed={a-BASE+i for a in changes for i in range(4)}
 assert all(i in allowed for i,(a,b) in enumerate(zip(data,result)) if a!=b)
 return bytes(result),report
