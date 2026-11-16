"""Execute stock display setup/clear against exact withdrawn v4/v5 images."""
import hashlib,json,struct,zipfile
from unicorn import UC_HOOK_MEM_WRITE
from unicorn.arm_const import *
from prototype_virtual_csic_transport import ROOT,BASE,machine
from stock_crom_codec import parse,expand

FILES=[('v4','artifacts/virtual-csic-candidate/withdrawn-v4-224bdb64.EFU','224bdb64412e45de37a0fc14a8e5d29d088e3028d2348d1ab32d81478fbbf9d9'),
       ('v5','artifacts/virtual-csic-boot-fix/withdrawn-v5-64888576.EFU','64888576dccd59f25c704af1383b6273ede8e8fcbf5502276b193b16418620e3')]

def main():
    stock=(ROOT/'artifacts/maintenance-virtualization/decoded/119075160.crom.0.bin').read_bytes()
    word=lambda a:struct.unpack_from('<I',stock,a-BASE)[0]
    fb=word(0x47c4a1b0);pointer=word(0x47c4a1b4);pixels=word(0x47c49ce8);end=fb+pixels*4
    assert (fb,pointer,pixels,end)==(0x47d69594,0x47d57d98,480*272,0x47de8d94)
    cases=[]
    for version,name,expected in FILES:
        file=ROOT/name;assert hashlib.sha256(file.read_bytes()).hexdigest()==expected
        with zipfile.ZipFile(file) as z:rom=z.read('FWE642TL.rcx')[0x6d4f158:0x7d4f158]
        seg=parse(rom,0x440004);image=expand(seg['tokens'],seg['literals'])
        cpu=machine(image,cpu_model=UC_CPU_ARM_926)
        cpu.reg_write(UC_ARM_REG_SP,0x2001f000);cpu.reg_write(UC_ARM_REG_LR,0x20000100)
        # Execute original pointer initialization up to its hardware call.
        cpu.emu_start(0x47c4a0fc,0x47c4a10c,count=20)
        assert struct.unpack('<I',cpu.mem_read(pointer,4))[0]==fb
        addresses=[0x47d70000,0x47d70600,0x47d70800,0x47d72000,0x47d73000]
        before={hex(a):bytes(cpu.mem_read(a,32)).hex() for a in addresses}
        writes=[]
        def observe(uc,access,address,size,value,ctx):
            if 0x47d70000<=address<0x47d73100 and len(writes)<8:writes.append(hex(address))
        cpu.hook_add(UC_HOOK_MEM_WRITE,observe)
        for r in [UC_ARM_REG_R0,UC_ARM_REG_R1,UC_ARM_REG_R2,UC_ARM_REG_R3]:cpu.reg_write(r,0)
        cpu.reg_write(UC_ARM_REG_SP,0x2001f000);cpu.reg_write(UC_ARM_REG_LR,0x20000100)
        cpu.emu_start(0x47c49b40,0x20000100,count=1000000)
        assert cpu.reg_read(UC_ARM_REG_PC)==0x20000100
        after={hex(a):bytes(cpu.mem_read(a,32)).hex() for a in addresses}
        assert all(bytes.fromhex(v)==bytes(32) for v in after.values())
        assert before['0x47d70000']!=after['0x47d70000'] and writes
        cases.append(dict(version=version,efu_sha256=expected,helper_and_table_bytes_before=before,
                          after_stock_framebuffer_clear=after,observed_framebuffer_writes_into_helpers=writes))
    report=dict(status='CONFIRMED FRAMEBUFFER/CODE OVERLAP IN BOTH WITHDRAWN IMAGES',
        framebuffer_start=hex(fb),framebuffer_end_exclusive=hex(end),pixels=pixels,width=480,height=272,bytes_per_pixel=4,
        native_pointer_setup='0x47C4A0FC..0x47C4A10C',native_display_clear='0x47C49B40',cases=cases,
        conclusion='The supposed FF code cave is inside the stock display framebuffer. A stock display clear destroys the injected helpers and metadata in both v4 and v5.',
        limit='Actual shutdown instruction/watchdog timing is not captured from the printer; the destructive overlap itself is directly reproduced.')
    (ROOT/'docs/virtual-csic-framebuffer-collision.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps({k:v for k,v in report.items() if k!='cases'},indent=2))

if __name__=='__main__':main()
