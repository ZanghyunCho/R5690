"""Original ARM header/setup and LZ replay. Huffman peripheral NOT emulated."""
import struct,hashlib
from unicorn import Uc,UC_ARCH_ARM,UC_MODE_ARM,UC_HOOK_CODE,UC_HOOK_MEM_WRITE
from unicorn.arm_const import *
from stock_crom_codec import parse,expand

def replay(code,tokens,literals):
 c=Uc(UC_ARCH_ARM,UC_MODE_ARM)
 for a,n in ((0x47f0a000,0x1000),(0x41000000,0x1000000),(0x42000000,0x1000000),
             (0x47ff0000,0x1100000),(0x20000000,0x20000)):c.mem_map(a,n)
 c.mem_write(0x47f0a000,code);c.mem_write(0x41000000,bytes(v for t in tokens for v in t));c.mem_write(0x42000000,literals)
 for reg,v in ((UC_ARM_REG_R4,0x41000000),(UC_ARM_REG_R5,0x48000000),(UC_ARM_REG_R8,0x42000000),
               (UC_ARM_REG_R6,0),(UC_ARM_REG_R9,len(tokens)),(UC_ARM_REG_SP,0x20010000)):c.reg_write(reg,v)
 def wait(uc,a,size,ctx):uc.reg_write(UC_ARM_REG_PC,uc.reg_read(UC_ARM_REG_LR))
 c.hook_add(UC_HOOK_CODE,wait,begin=0x47f0abd0,end=0x47f0abd0)
 c.emu_start(0x47f0a804,0x47f0a890,count=100000000)
 assert c.reg_read(UC_ARM_REG_PC)==0x47f0a890
 n=c.reg_read(UC_ARM_REG_R5)-0x48000000;assert 0<=n<=0x1000000
 assert c.reg_read(UC_ARM_REG_R8)-0x42000000==len(literals)
 return bytes(c.mem_read(0x48000000,n))

def setup(code,ic4,segment_start=0x440004):
 c=Uc(UC_ARCH_ARM,UC_MODE_ARM)
 for a,n in ((0x47f0a000,0x1000),(0x02000000,0x1000000),(0x20000000,0x20000),
             (0xf6051000,0x1000),(0xf6063000,0x1000)):c.mem_map(a,n)
 c.mem_write(0x47f0a000,code);c.mem_write(0x02000000,ic4)
 desc,stop=0x20001000,0x20000100
 for reg,v in ((UC_ARM_REG_R0,desc),(UC_ARM_REG_R1,0x02000000+segment_start),(UC_ARM_REG_SP,0x2001f000),(UC_ARM_REG_LR,stop)):c.reg_write(reg,v)
 c.emu_start(0x47f0a8b4,stop,count=1000);assert c.reg_read(UC_ARM_REG_PC)==stop
 descriptor=struct.unpack('<7I',c.mem_read(desc,28));banks={};selected=[None]
 def writes(uc,access,address,size,value,ctx):
  if address==0xf605148e:selected[0]=value;banks[value]=[]
  elif address==0xf6051490:banks[selected[0]].append(value)
 c.hook_add(UC_HOOK_MEM_WRITE,writes)
 for reg,v in ((UC_ARM_REG_R0,desc),(UC_ARM_REG_R1,0x80010000),(UC_ARM_REG_R2,0x80080000),(UC_ARM_REG_LR,stop)):c.reg_write(reg,v)
 c.emu_start(0x47f0a95c,stop,count=20000)
 assert c.reg_read(UC_ARM_REG_PC)==stop and c.reg_read(UC_ARM_REG_R0)==1
 return descriptor,banks

def validate(original,modified):
 code=original[0x34b5c:0x3584c]
 assert hashlib.sha256(code).hexdigest()=='f2186f08420f6cb9c4198ff872096cd9d742b70f35fceb127bf3f142bebacd58'
 assert code==modified[0x34b5c:0x3584c]
 a,b=setup(code,original),setup(code,modified)
 assert a[1]==b[1] and set(a[1])=={0,4,5,6} and a[1][0]==[]
 results=[];header_checks=[]
 for start,count in ((0x40004,2),(0x440004,3)):
  pos=start;original_pos=start
  for index in range(count):
   seg=parse(modified,pos);original_seg=parse(original,original_pos)
   old_setup=setup(code,original,original_pos);new_setup=setup(code,modified,pos)
   assert old_setup[1]==new_setup[1]
   assert new_setup[0][0]==0x02000000+pos+6
   header_checks.append(dict(slot=hex(start-4),segment=index,old_position=hex(original_pos),new_position=hex(pos),native_header_and_DHT_setup_pass=True))
   original_pos=original_seg['end']
   expect=expand(seg['tokens'],seg['literals'])
   actual=replay(code,seg['tokens'],seg['literals']);assert actual==expect
   results.append(dict(slot=hex(start-4),segment=index,bytes=len(actual),sha256=hashlib.sha256(actual).hexdigest(),native_arm_exact=True))
   print('Native expansion verified',hex(start-4),index,flush=True);pos=seg['end']
 return dict(segments=results,all_segment_header_checks=header_checks,stock_descriptor=[hex(v) for v in a[0]],modified_descriptor=[hex(v) for v in b[0]],
             original_arm_hardware_setup_passed=True,dht_bank_writes_byte_identical=True,
             limitation='Original header/setup and LZ loop execute; peripheral Huffman decoding and full boot are not emulated')
