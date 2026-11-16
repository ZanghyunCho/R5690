"""Reproduce v4 defects; no EFU build or printer access.

Neither a reproduced ABI defect nor a cold property guard proves the user's
physical shutdown cause. Tests explicitly distinguish evidence from hypotheses.
"""
import json
from unicorn import UC_HOOK_CODE
from unicorn.arm_const import *
from prototype_virtual_csic_transport import ROOT,machine,call
from validate_virtual_csic_startup_regression import old_image

def main():
    stock=(ROOT/'artifacts/maintenance-virtualization/decoded/119075160.crom.0.bin').read_bytes()
    image=old_image()
    returns=[]
    for slot in range(4):
        cpu=machine(image,cpu_model=UC_CPU_ARM_926)
        def prop(uc,a,size,ctx):
            assert uc.reg_read(UC_ARM_REG_R0)==0x2e6
            uc.mem_write(uc.reg_read(UC_ARM_REG_R1),b'\x20')
            uc.reg_write(UC_ARM_REG_R0,0);uc.reg_write(UC_ARM_REG_PC,uc.reg_read(UC_ARM_REG_LR))
        cpu.hook_add(UC_HOOK_CODE,prop,begin=0x47c4b0c8,end=0x47c4b0c8)
        result=call(cpu,0x47c52674,[slot,0x17,0x1fff])
        returns.append(result)
    assert returns==[0,1,2,3],returns
    # Run a setter before property-manager readiness, without the old read
    # mock. Capture the original explicit initialization-error guard.
    guards=[]
    for name,program in [('stock',stock),('v4',image)]:
        cpu=machine(program,cpu_model=UC_CPU_ARM_926);hit=[]
        def guard(uc,a,size,ctx):hit.append(hex(a));uc.emu_stop()
        cpu.hook_add(UC_HOOK_CODE,guard,begin=0x47c4d30c,end=0x47c4d30c)
        for r,v in [(UC_ARM_REG_R0,0),(UC_ARM_REG_R1,0x52),(UC_ARM_REG_R2,100),
                    (UC_ARM_REG_SP,0x2001f000),(UC_ARM_REG_LR,0x20000100)]:cpu.reg_write(r,v)
        cpu.emu_start(0x47c52674,0x20000100,count=20000)
        guards.append(dict(program=name,property_manager_guard=hit,pc=hex(cpu.reg_read(UC_ARM_REG_PC))))
    assert not guards[0]['property_manager_guard']
    assert guards[1]['property_manager_guard']==['0x47c4d30c']
    report=dict(status='V4 WITHDRAWN; defects reproduced; physical shutdown root cause unconfirmed',
        protected_cell_setter_returns=returns,expected_success_return=0,
        property_uninitialized_setter_controls=guards,
        limits=['Cold property test deliberately leaves the property manager uninitialized; actual printer call ordering is unknown.',
               'Protected-cell setter nonzero return is a definite API defect, but its causal link to shutdown is unproved.',
               'Runtime executable/writable ownership of the FF padding was never established on hardware.',
               'CSIC initialization omissions and actual OS/watchdog behavior remain unverified.'])
    output=ROOT/'docs/virtual-csic-v4-boot-regression.json';output.write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(report,indent=2))

if __name__=='__main__':main()
