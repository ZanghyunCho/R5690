"""Native ARM check of the ink-use status fix on the V7 controller.

Executes the ORIGINAL status evaluator 0x47C61B24 (patched vs unpatched).
Mocks: property reads, slot/mask helpers, chip-type read, notifications.
Integer division helper and threshold helper 0x47C692EC run natively.
Capacity thresholds are synthetic; no printer or complete boot.
"""
import hashlib,json,struct,sys
from pathlib import Path
from unicorn import Uc,UC_ARCH_ARM,UC_MODE_ARM,UC_HOOK_CODE
from unicorn.arm_const import *
from virtual_ink_counter_patch import patch,BASE
ROOT=Path(__file__).resolve().parents[1]
V7_CONTROLLER_SHA='4e75ad9b22d56eb21eb116b3fb1b3c2fd980dab9e6db172b3b292bd4da204ea4'
CAP=0x47e03490;STATE=0x47d5ee18;RECORD=0x47e03484;IES=0x47d5ee1c
MOCK_ZERO=[0x47c539c8,0x47c52ab4,0x47c5188c,0x47c5bbe8,0x47c59560,0x47c59d70,0x47c619a4,0x47c6d08c]

def run(image,used,ies=0,threshold=0):
    cpu=Uc(UC_ARCH_ARM,UC_MODE_ARM)
    cpu.mem_map(BASE,0x3b8000);cpu.mem_write(BASE,image);cpu.mem_map(0x20000000,0x20000)
    for slot in range(4):
        # +4 end, +0x10/+0x14 display buckets, +0x30 level base, +0x34 near-end
        s=CAP+56*slot;cpu.mem_write(s,bytes(56))
        cpu.mem_write(s+2,struct.pack('<H',10));cpu.mem_write(s+4,struct.pack('<I',1000000))
        cpu.mem_write(s+0x10,struct.pack('<I',500000));cpu.mem_write(s+0x14,struct.pack('<I',200000))
        cpu.mem_write(s+0x30,struct.pack('<I',1000000));cpu.mem_write(s+0x34,struct.pack('<I',900000))
    cpu.mem_write(STATE-4,bytes(8));cpu.mem_write(RECORD,bytes(12));cpu.mem_write(IES,bytes([ies]*4))
    props={0x808:used[0],0x809:used[1],0x80d:used[2],0x80e:used[3]}
    reads=[]
    def hook(uc,a,size,ctx):
        r0,r1,r2=[uc.reg_read(r) for r in (UC_ARM_REG_R0,UC_ARM_REG_R1,UC_ARM_REG_R2)]
        ret=0
        if a==0x47c4b0c8:
            reads.append(r0)
            if r0 in props:uc.mem_write(r1,struct.pack('<I',props[r0]))
            elif r0==0x329:uc.mem_write(r1,bytes([threshold]))
            else:uc.mem_write(r1,bytes(r2))
        elif a==0x47c61af0:ret=r0
        elif a==0x47c5241c:ret=1<<r0
        elif a==0x47c53ba4:ret=1
        elif a in MOCK_ZERO:
            if a==0x47c52ab4:uc.mem_write(r1,bytes(2))
        else:return
        uc.reg_write(UC_ARM_REG_R0,ret);uc.reg_write(UC_ARM_REG_PC,uc.reg_read(UC_ARM_REG_LR))
    for a in [0x47c4b0c8,0x47c61af0,0x47c5241c,0x47c53ba4]+MOCK_ZERO:cpu.hook_add(UC_HOOK_CODE,hook,begin=a,end=a)
    cpu.reg_write(UC_ARM_REG_R0,1);cpu.reg_write(UC_ARM_REG_SP,0x2001f000);cpu.reg_write(UC_ARM_REG_LR,0x20000100)
    cpu.emu_start(0x47c61b24,0x20000100,count=200000)
    assert cpu.reg_read(UC_ARM_REG_PC)==0x20000100 and cpu.reg_read(UC_ARM_REG_SP)==0x2001f000
    rec=bytes(cpu.mem_read(RECORD,12))
    return dict(state=list(cpu.mem_read(STATE,4)),record=[rec[i*3] for i in range(4)],
        level=[rec[i*3+1] for i in range(4)],usage_property_reads=sorted({hex(r) for r in reads if r in props}))

def main():
    src=Path(sys.argv[1]) if len(sys.argv)>1 else ROOT/'artifacts/v7/controller.bin'
    stock=src.read_bytes();assert hashlib.sha256(stock).hexdigest()==V7_CONTROLLER_SHA
    fixed,info=patch(stock)
    cases=[]
    scenarios=[('all fresh',[0,0,0,0],0),('C near end (photo)',[100000,950000,0,0],0),
        ('C past end',[0,1200000,0,0],0),('sensor flag set, counters fresh',[0,0,0,0],1),
        ('sensor flag set, counters high',[0,1200000,0,0],1)]
    for name,used,ies in scenarios:
        before,after=run(stock,used,ies),run(fixed,used,ies)
        cases.append(dict(scenario=name,used=used,sensor_flag=ies,v7=before,patched=after))
        print(name,'| V7 state',before['state'],'rec',[hex(x) for x in before['record']],'| patched state',after['state'],'rec',[hex(x) for x in after['record']],'lvl',after['level'])
    near=next(c for c in cases if c['scenario']=='C near end (photo)')
    assert 0x83 in near['v7']['record'] and near['patched']['record']==[0x80]*4 and near['patched']['level']==[100]*4
    past=next(c for c in cases if c['scenario']=='C past end')
    assert 6 in past['v7']['state'] and past['patched']['state']==[0]*4
    for c in cases:
        if c['sensor_flag']:
            # The sensor-driven end state must be identical to unpatched behavior with fresh counters.
            fresh=next(x for x in cases if x['scenario']=='sensor flag set, counters fresh')
            assert c['patched']['state']==fresh['v7']['state'] and c['patched']['record']==fresh['v7']['record']
    assert all(not c['patched']['usage_property_reads'] for c in cases)
    report=dict(status='NATIVE STATUS-EVALUATOR CHECK; synthetic thresholds and mocks; no printer',
        controller_before_sha256=V7_CONTROLLER_SHA,controller_after_sha256=hashlib.sha256(fixed).hexdigest(),patch=info,cases=cases)
    (ROOT/'docs/virtual-ink-counter-fix.json').write_text(json.dumps(report,indent=2)+'\n')
    print('PASS')

if __name__=='__main__':main()
