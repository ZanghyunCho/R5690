"""Level-only API regression: preserve raw state/type/error handling."""
import json,hashlib
from unicorn import UC_HOOK_CODE
from unicorn.arm_const import *
from prototype_virtual_csic_transport import ROOT,machine as bare_machine
from virtual_box_patch import patch as mb_patch
from virtual_csic_patch import patch

def machine(image):
    cpu=bare_machine(image,cpu_model=UC_CPU_ARM_926)
    cpu.reg_write(UC_ARM_REG_SP,0x2001f000);cpu.reg_write(UC_ARM_REG_LR,0x20000100)
    return cpu

def execute(cpu,address):
    cpu.emu_start(address,0x20000100,count=10000)
    assert cpu.reg_read(UC_ARM_REG_PC)==0x20000100

def api(image,command,index,value,seed=None):
 c=machine(image);events=[];trace=[]
 if seed:
  for addr,b in seed.items():c.mem_write(addr,b)
 def transport(uc,address,size,context):
  r0,r1,r2=(uc.reg_read(r) for r in (UC_ARM_REG_R0,UC_ARM_REG_R1,UC_ARM_REG_R2))
  assert r2<=512
  if address==0x47cb6304:events.append(dict(event=hex(r0),data=bytes(uc.mem_read(r1,r2)).hex()))
  else:uc.reg_write(UC_ARM_REG_R0,0)
  uc.reg_write(UC_ARM_REG_PC,uc.reg_read(UC_ARM_REG_LR))
 for a in (0x47cb6304,0x47c4afd8):c.hook_add(UC_HOOK_CODE,transport,begin=a,end=a)
 def trace_code(uc,a,size,ctx):
  trace.append(hex(a))
  if len(trace)>100:trace.pop(0)
 c.hook_add(UC_HOOK_CODE,trace_code)
 for r,v in ((UC_ARM_REG_R0,command),(UC_ARM_REG_R1,index),(UC_ARM_REG_R2,value)):c.reg_write(r,v)
 try:execute(c,0x47ca9528)
 except Exception:
  print('API failure',hex(command),index,value,'pc',hex(c.reg_read(UC_ARM_REG_PC)),trace);raise
 assert c.reg_read(UC_ARM_REG_SP)==0x2001f000
 return bytes(c.mem_read(0x47e18688,0x80)),events

def snapshot(image,records):
 c=machine(image);packet=0x20001000;initial=bytearray(bytes([0xa5])*64)
 initial[0x14:0x20]=records;c.mem_write(packet,bytes(initial))
 # Start type cache with an unknown value so the stock routine sends its type
 # event on the first query; subsequent queries may legitimately omit it.
 c.mem_write(0x47e18697,b'\xff'*4)
 events=[];freed=[]
 def io(uc,address,size,context):
  r0,r1,r2=(uc.reg_read(r) for r in (UC_ARM_REG_R0,UC_ARM_REG_R1,UC_ARM_REG_R2))
  if address==0x47cb6304:
   assert r2<=512;events.append(dict(event=hex(r0),data=bytes(uc.mem_read(r1,r2)).hex()))
  elif address==0x47c4afd8:uc.reg_write(UC_ARM_REG_R0,0)
  else:freed.append(r0)
  uc.reg_write(UC_ARM_REG_PC,uc.reg_read(UC_ARM_REG_LR))
 for a in (0x47cb6304,0x47c4afd8,0x47d26760):c.hook_add(UC_HOOK_CODE,io,begin=a,end=a)
 c.reg_write(UC_ARM_REG_R0,packet)
 saved={r:0x10000000+i for i,r in enumerate((UC_ARM_REG_R4,UC_ARM_REG_R5,UC_ARM_REG_R6,UC_ARM_REG_R7,UC_ARM_REG_R8,UC_ARM_REG_R9,UC_ARM_REG_R10,UC_ARM_REG_R11))}
 for r,v in saved.items():c.reg_write(r,v)
 execute(c,0x47cab5a4)
 assert c.reg_read(UC_ARM_REG_SP)==0x2001f000
 assert all(c.reg_read(r)==v for r,v in saved.items())
 assert freed==[packet]
 actual=bytes(c.mem_read(packet,64))
 assert actual[:0x14]==initial[:0x14] and actual[0x20:]==initial[0x20:]
 return dict(events=events,records=actual[0x14:0x20].hex(),cache=bytes(c.mem_read(0x47e18688,0x40)).hex(),abi_preserved=True)

def main():
    stock=(ROOT/'artifacts/maintenance-virtualization/decoded/119075160.crom.0.bin').read_bytes()
    old,_=mb_patch(stock);new,_=patch(stock)
    scalar=0;errors=0;snapshots=0
    for command in [0x26,0x27,0x28]:
        for channel in range(6):
            for value in [0,1,2,100,128,133,255]:
                a,ea=api(old,command,channel,value);b,eb=api(new,command,channel,value)
                if command==0x26 and channel<4:
                    assert b[7+channel]==100
                    assert a[:7+channel]+a[8+channel:]==b[:7+channel]+b[8+channel:]
                else:assert (a,ea)==(b,eb)
                scalar+=1
    for selector in range(0x30,0xa4):
        for value in [0,1]:
            assert api(old,0x29,selector,value)==api(new,0x29,selector,value)
            errors+=1
    for state in [0,1,2,3,5,6,128,133,255]:
        for level in [0,1,50,100,255]:
            records=b''.join(bytes([state,level,i]) for i in range(4))
            a=snapshot(old,records);b=snapshot(new,records)
            expected=bytearray.fromhex(a['records'])
            for i in range(4):expected[3*i+1]=100
            assert b['records']==expected.hex()
            snapshots+=1
    report=dict(status='PASS; native API with event/property transport mocks',controller_sha256=hashlib.sha256(new).hexdigest(),cpu_model='ARM926',scalar_cases=scalar,
        error_api_cases_unchanged=errors,snapshot_cases=snapshots,
        raw_state_and_type_preserved=True,general_errors_not_suppressed=True)
    out=ROOT/'artifacts/virtual-csic-candidate/INTERFACES.json';out.write_text(json.dumps(report,indent=2)+'\n')
    print(report)

if __name__=='__main__':main()
