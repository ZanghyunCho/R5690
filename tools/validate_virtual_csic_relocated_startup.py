"""Differential startup regressions against the exact withdrawn v4 binary.

This does not emulate the complete printer OS or establish physical boot.
"""
import hashlib,json,struct,zipfile
from unicorn import UC_HOOK_CODE
from unicorn.arm_const import *
from prototype_virtual_csic_transport import ROOT,BASE,BUFFERS,ENTRIES,machine,call
from prototype_virtual_csic_bootstrap import SEED,PROPERTY_READY,UID_CACHE
from stock_crom_codec import parse,expand
from virtual_csic_relocated_patch import patch

def old_image():
    p=ROOT/'artifacts/virtual-csic-candidate/withdrawn-v4-224bdb64.EFU'
    assert hashlib.sha256(p.read_bytes()).hexdigest()=='224bdb64412e45de37a0fc14a8e5d29d088e3028d2348d1ab32d81478fbbf9d9'
    with zipfile.ZipFile(p) as z:rom=z.read('FWE642TL.rcx')[0x6d4f158:0x7d4f158]
    seg=parse(rom,0x440004)
    return expand(seg['tokens'],seg['literals'])

def run_guard(program,slot,ready=0,field=0x52):
    cpu=machine(program,cpu_model=UC_CPU_ARM_926);hits=[]
    cpu.mem_write(PROPERTY_READY,struct.pack('<I',ready))
    def guard(uc,a,size,ctx):hits.append(hex(a));uc.emu_stop()
    for a in [0x47c4b0c8,0x47c4d30c]:cpu.hook_add(UC_HOOK_CODE,guard,begin=a,end=a)
    for r,v in [(UC_ARM_REG_R0,slot),(UC_ARM_REG_R1,field),(UC_ARM_REG_R2,100),
                (UC_ARM_REG_SP,0x2001f000),(UC_ARM_REG_LR,0x20000100)]:cpu.reg_write(r,v)
    cpu.emu_start(0x47c52674,0x20000100,count=20000)
    return cpu,hits

def main():
    stock=(ROOT/'artifacts/maintenance-virtualization/decoded/119075160.crom.0.bin').read_bytes()
    old=old_image();new,layout=patch(stock);early=[];returns=[];fallback=[]
    relocated_seed=int(next(r['start'] for r in layout['allocations'] if r['label']=='compact metadata bootstrap'),16)
    for ready in [0,1]:
        for slot in range(4):
            for field in [1,3,0x16,0x17,0x18,0x52,0x53,0x59]:
                a,ha=run_guard(stock,slot,ready,field);b,hb=run_guard(new,slot,ready,field)
                assert not ha and not hb,(slot,ready,field,hb)
                assert b.reg_read(UC_ARM_REG_PC)==0x20000100
                assert a.reg_read(UC_ARM_REG_R0)==b.reg_read(UC_ARM_REG_R0)
                assert bytes(a.mem_read(BUFFERS[slot],168))==bytes(b.mem_read(BUFFERS[slot],168))
                early.append(dict(slot=slot,manager_ready=bool(ready),field=hex(field),stock_result_identical=True))
    _,old_hits=run_guard(old,0)
    assert old_hits==['0x47c4b0c8']
    for slot in range(4):
        for label,program in [('v4',old),('fixed',new)]:
            cpu=machine(program,cpu_model=UC_CPU_ARM_926)
            cpu.mem_write(PROPERTY_READY,struct.pack('<I',1))
            def prop(uc,a,size,ctx):
                assert uc.reg_read(UC_ARM_REG_R0)==0x2e6
                uc.mem_write(uc.reg_read(UC_ARM_REG_R1),b'\x20')
                uc.reg_write(UC_ARM_REG_R0,0);uc.reg_write(UC_ARM_REG_PC,uc.reg_read(UC_ARM_REG_LR))
            cpu.hook_add(UC_HOOK_CODE,prop,begin=0x47c4b0c8,end=0x47c4b0c8)
            if label=='fixed':assert call(cpu,relocated_seed,[slot])==0
            result=call(cpu,0x47c52674,[slot,0x17,0x1fff])
            assert result==(slot if label=='v4' else 0)
            returns.append(dict(version=label,slot=slot,return_value=result))
    for entry in list(ENTRIES)+[0x47c553cc,0x47c52450,0x47c51f78,0x47c520cc]:
        for slot in range(4):
            states=[]
            for program in [stock,new]:
                cpu=machine(program,cpu_model=UC_CPU_ARM_926)
                call(cpu,entry,[slot,17],end=entry+4)
                states.append([cpu.reg_read(r) for r in [UC_ARM_REG_R0,UC_ARM_REG_R1,UC_ARM_REG_SP,UC_ARM_REG_LR]])
            assert states[0]==states[1]
            fallback.append(dict(entry=hex(entry),slot=slot,original_entry_preserved_before_activation=True))
    for lo,hi in [(0x47c52c28,0x47c52c80),(0x47c53618,0x47c538b0)]:
        assert new[lo-BASE:hi-BASE]==stock[lo-BASE:hi-BASE]
    report=dict(status='STARTUP REGRESSIONS PASSED; physical boot unverified',
        controller_sha256=hashlib.sha256(new).hexdigest(),early_setter_cases=early,
        protected_field_return_cases=returns,preactivation_entry_cases=fallback,
        csic_hardware_initialization_restored=True,no_runtime_state_in_ff_padding=True,
        old_v4_new_property_dependency_reproduced=True,
        limitations=['Exact physical shutdown cause remains unconfirmed.',
            'No complete OS boot, task synchronization, live peripherals or physical printer.'])
    out=ROOT/'artifacts/virtual-csic-relocated';out.mkdir(exist_ok=True)
    (out/'STARTUP.json').write_text(json.dumps(report,indent=2)+'\n')
    print(f'PASS {len(early)} early setter cases, {len(returns)} protected-field return controls, {len(fallback)} preactivation entry controls.')

if __name__=='__main__':main()
