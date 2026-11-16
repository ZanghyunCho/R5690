"""Show withdrawn hooks fail to return after stock display clear; fix survives."""
import hashlib,json,struct,zipfile
from unicorn.arm_const import *
from prototype_virtual_csic_transport import ROOT,BASE,machine
from stock_crom_codec import parse,expand
from trace_virtual_csic_framebuffer_collision import FILES
from virtual_csic_relocated_patch import patch

def clear(cpu):
    cpu.reg_write(UC_ARM_REG_SP,0x2001f000);cpu.reg_write(UC_ARM_REG_LR,0x20000100)
    cpu.emu_start(0x47c4a0fc,0x47c4a10c,count=20)
    assert struct.unpack('<I',cpu.mem_read(0x47d57d98,4))[0]==0x47d69594
    for r in [UC_ARM_REG_R0,UC_ARM_REG_R1,UC_ARM_REG_R2,UC_ARM_REG_R3]:cpu.reg_write(r,0)
    cpu.reg_write(UC_ARM_REG_SP,0x2001f000);cpu.reg_write(UC_ARM_REG_LR,0x20000100)
    cpu.emu_start(0x47c49b40,0x20000100,count=1000000)
    assert cpu.reg_read(UC_ARM_REG_PC)==0x20000100

def attempt(cpu):
    for r,v in [(UC_ARM_REG_R0,0),(UC_ARM_REG_R1,0x52),(UC_ARM_REG_R2,100),
                (UC_ARM_REG_SP,0x2001f000),(UC_ARM_REG_LR,0x20000100)]:cpu.reg_write(r,v)
    cpu.emu_start(0x47c52674,0x20000100,count=2000)
    return dict(pc=hex(cpu.reg_read(UC_ARM_REG_PC)),returned=cpu.reg_read(UC_ARM_REG_PC)==0x20000100,
                return_value=cpu.reg_read(UC_ARM_REG_R0))

def main():
    cases=[]
    for name,path,expected in FILES:
        p=ROOT/path;assert hashlib.sha256(p.read_bytes()).hexdigest()==expected
        with zipfile.ZipFile(p) as z:rom=z.read('FWE642TL.rcx')[0x6d4f158:0x7d4f158]
        seg=parse(rom,0x440004);image=expand(seg['tokens'],seg['literals'])
        cpu=machine(image,cpu_model=UC_CPU_ARM_926);clear(cpu);result=attempt(cpu)
        assert not result['returned'] and 0x47d69594<=int(result['pc'],16)<0x47de8d94
        cases.append(dict(version=name,after_stock_display_clear=result))
    stock=(ROOT/'artifacts/maintenance-virtualization/decoded/119075160.crom.0.bin').read_bytes()
    fixed,layout=patch(stock);cpu=machine(fixed,cpu_model=UC_CPU_ARM_926);clear(cpu)
    for item in layout['allocations']:
        a=int(item['start'],16);n=item['bytes']
        assert bytes(cpu.mem_read(a,n))==fixed[a-BASE:a-BASE+n]
    result=attempt(cpu);assert result['returned'] and result['return_value']==0
    cases.append(dict(version='relocated',after_stock_display_clear=result,all_helpers_and_metadata_preserved=True))
    out=ROOT/'artifacts/virtual-csic-relocated';out.mkdir(exist_ok=True)
    report=dict(status='DISPLAY COLLISION REGRESSION PASSED',controller_sha256=layout['controller_sha256'],cases=cases,
        mechanism='Stock display clear erases V4/V5 hook targets; the hooked setter then fails to return within the instruction limit. Relocated helpers remain intact and the setter returns normally.',
        limitation='No physical watchdog trace or full OS boot; this directly reproduces the corrupt-code execution mechanism.')
    (out/'DISPLAY.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(report,indent=2))

if __name__=='__main__':main()
