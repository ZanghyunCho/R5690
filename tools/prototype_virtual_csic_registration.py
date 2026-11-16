"""Virtual acceptance adapters; original ink registration replay.

Virtual devices do not claim to implement Epson chip cryptography. These
adapters bind a supported virtual slot to its generated metadata instead.
The standalone replay is not an EFU; the separate v4 builder adds level-only
presentation and the existing MB patch. Physical supply remains unverified.
"""
import hashlib
import json
import struct
from keystone import Ks,KS_ARCH_ARM,KS_MODE_ARM
from unicorn import UC_HOOK_CODE
from unicorn.arm_const import *
from prototype_virtual_csic_bootstrap import build as bootstrap,CAVE,SEED,STATES
from prototype_virtual_csic_transport import ROOT,BASE,machine,branch,BUFFERS

def build(stock):
    image,layout=bootstrap(stock);image=bytearray(image)
    ks=Ks(KS_ARCH_ARM,KS_MODE_ARM)
    edits=[]
    def place(entry,helper,body):
        prologue=struct.unpack_from('<I',stock,entry-BASE)[0]
        assert prologue&0xffff0000==0xe92d0000
        payload=bytes(ks.asm(body.format(prologue=prologue,continuation=entry+4),addr=helper)[0])
        assert len(payload)<=0x100
        assert image[helper-BASE:helper-BASE+len(payload)]==bytes([255])*len(payload)
        image[helper-BASE:helper-BASE+len(payload)]=payload
        struct.pack_into('<I',image,entry-BASE,branch(entry,helper))
        edits.append(dict(entry=hex(entry),helper=hex(helper),bytes=len(payload)))
    for n,entry in enumerate([0x47c553cc,0x47c52450,0x47c51f78,0x47c520cc]):
        place(entry,CAVE+0x180+n*64,f'''
            cmp r0, #4
            bhs fallback
            push {{{{r0-r4,lr}}}}
            bl {SEED}
            str r0, [sp]
            pop {{{{r0-r4,pc}}}}
        fallback:
            .word {{prologue}}
            b {{continuation}}
        ''')
    for n,(entry,product) in enumerate([(0x47c57e4c,True),(0x47c57a04,False),(0x47c8d8d8,False)]):
        body=f'''
            cmp r0, #1
            beq slot0
            cmp r0, #2
            beq slot1
            cmp r0, #4
            beq slot2
            cmp r0, #8
            beq slot3
            .word {{prologue}}
            b {{continuation}}
        slot0: mov r0, #0
            b selected
        slot1: mov r0, #1
            b selected
        slot2: mov r0, #2
            b selected
        slot3: mov r0, #3
        selected:
            push {{{{r4,lr}}}}
            mov r4, r0
            bl {SEED}
        '''
        if product:body+='cmp r0, #0\n moveq r0, #1\n movne r0, #0\n'
        if entry==0x47c57a04:
            requested=struct.unpack_from('<I',stock,0x47c565ac-BASE)[0]
            verified=struct.unpack_from('<I',stock,0x47c56594-BASE)[0]
            body+=f'''cmp r0,#0
                bne finish
                mov r0,r4
                bl 0x47c56184
                ldr r1,={requested}
                add r1,r1,r4,lsl #1
                ldrh r1,[r1]
                mov r0,r4
                bl 0x47c526c4
                cmp r0,#0
                bne finish
                mov r0,r4
                bl {CAVE+0x600}
                ldr r1,={requested}
                add r1,r1,r4,lsl #1
                ldrh r2,[r1]
                ldr r1,={verified}
                add r1,r1,r4,lsl #1
                strh r2,[r1]
                mov r0,#0
            finish:
            '''
        body+='pop {{r4,pc}}'
        place(entry,CAVE+0x300+n*0x100,body)
    # Read-only diagnostic cells and monotonic write cells must behave like
    # chip data, not arbitrary RAM. Keep the stock bit packer for other fields.
    entry=0x47c52674;helper=CAVE+0xc00
    place(entry,helper,f'''
        cmp r0, #4
        bhs fallback
        push {{{{r0-r4,lr}}}}
        bl {SEED}
        cmp r0, #0
        bne done
        ldr r0, [sp]
        ldr r1, [sp, #4]
        cmp r1, #0x17
        beq done
        cmp r1, #0x18
        beq done
        cmp r1, #1
        beq monotonic
        cmp r1, #3
        beq monotonic
        cmp r1, #0x16
        bne proceed
    monotonic:
        sub sp, sp, #8
        mov r2, sp
        bl 0x47c522f0
        ldrh r0, [sp]
        add sp, sp, #8
        ldr r2, [sp, #8]
        cmp r2, r0
        blo ignore
    proceed:
        pop {{{{r0-r4,lr}}}}
    fallback:
        .word {{prologue}}
        b {{continuation}}
    ignore:
        mov r0, #0
    done:
        str r0, [sp]
        pop {{{{r0-r4,pc}}}}
    ''')
    # Virtual slots use the stock 'no physical history record' sentinel.
    # The physical IC3 history is neither edited nor erased.
    entry=0x47c54c98;helper=CAVE+0xd00
    prologue=struct.unpack_from('<I',stock,entry-BASE)[0]
    assert prologue==0xe52de004
    payload=bytes(ks.asm(f'''cmp r0,#4
        ldrlo r0,=0x3ff
        bxlo lr
        .word {prologue}
        b {entry+4}''',addr=helper)[0])
    assert image[helper-BASE:helper-BASE+len(payload)]==b'\xff'*len(payload)
    image[helper-BASE:helper-BASE+len(payload)]=payload
    struct.pack_into('<I',image,entry-BASE,branch(entry,helper))
    edits.append(dict(entry=hex(entry),helper=hex(helper),bytes=len(payload),role='virtual history sentinel'))
    # These are ink CSIC GPIO selection/probing interfaces, not the pump,
    # IES or maintenance-box driver. With all four slots virtual there is
    # no physical CSIC transaction to prepare or finish.
    for entry in [0x47c53618,0x47c537f4,0x47c536e8,0x47c53870,
                  0x47c52c28,0x47c58778]:
        before=bytes(image[entry-BASE:entry-BASE+8])
        image[entry-BASE:entry-BASE+8]=struct.pack('<II',0xe3a00000,0xe12fff1e)
        edits.append(dict(entry=hex(entry),role='virtual CSIC bus lifecycle / zero missing-slot mask',before=before.hex()))
    # Stock rescan clears every chip bank. Invalidate the per-slot seed
    # markers before executing the original clear, so data is restored on
    # the next virtual read instead of falsely treating empty RAM as valid.
    entry=0x47c52b74;helper=CAVE+0xe00
    place(entry,helper,f'''push {{{{r0-r3,lr}}}}
        ldr r0,={STATES}
        mov r1,#0
        mov r2,#8
    clear_marker:
        str r1,[r0],#4
        subs r2,r2,#1
        bne clear_marker
        pop {{{{r0-r3,lr}}}}
        .word {{prologue}}
        b {{continuation}}
    ''')
    layout['virtual_acceptance_adapters']=edits
    return bytes(image),layout

def main():
    stock=(ROOT/'artifacts/maintenance-virtualization/decoded/119075160.crom.0.bin').read_bytes()
    image,layout=build(stock);cases=[]
    for sku in layout['skus']:
        cpu=machine(image);properties=[];notifications=[];details=[]
        # Shared flag read by 47C606F0/47C60190: synthetic clear state.
        # Map the data and execute both original accessors unchanged.
        cpu.mem_map(0x3fffc000,0x4000)
        def hook(uc,a,size,ctx):
            if a==0x47c4b0c8:
                prop,dest,length=(uc.reg_read(r) for r in [UC_ARM_REG_R0,UC_ARM_REG_R1,UC_ARM_REG_R2])
                assert length<256
                uc.mem_write(dest,bytes([sku] if prop==0x2e6 else [0]*length));properties.append(prop)
            elif a==0x47c6a4f8:notifications.append([uc.reg_read(UC_ARM_REG_R0),uc.reg_read(UC_ARM_REG_R1)])
            elif a==0x47c5bbe8:details.append([uc.reg_read(UC_ARM_REG_R0),uc.reg_read(UC_ARM_REG_R1)])
            elif a in [0x47c554f4,0x47c555a0,0x47c55b28,0x47c55bec,0x47c55c98,0x47c5577c]:raise AssertionError('Physical CSIC transport reached')
            elif a in [0x47c5b984,0x47c5451c]:pass
            else:return
            uc.reg_write(UC_ARM_REG_R0,0);uc.reg_write(UC_ARM_REG_PC,uc.reg_read(UC_ARM_REG_LR))
        for a in [0x47c4b0c8,0x47c6a4f8,0x47c5bbe8,0x47c554f4,0x47c555a0,0x47c55b28,0x47c55bec,0x47c55c98,0x47c5577c,0x47c5b984,0x47c5451c]:cpu.hook_add(UC_HOOK_CODE,hook,begin=a,end=a)
        # Seed through the same native read adapter before stock registration,
        # as the preceding chip-data load must do. Cold buffers start empty.
        for slot in range(4):
            def run(address,args):
                for r,v in zip([UC_ARM_REG_R0,UC_ARM_REG_R1,UC_ARM_REG_R2,UC_ARM_REG_R3],args):cpu.reg_write(r,v)
                cpu.reg_write(UC_ARM_REG_SP,0x2001f000);cpu.reg_write(UC_ARM_REG_LR,0x20000100)
                cpu.emu_start(address,0x20000100,count=500000)
                assert cpu.reg_read(UC_ARM_REG_PC)==0x20000100,hex(cpu.reg_read(UC_ARM_REG_PC))
                return cpu.reg_read(UC_ARM_REG_R0)
            assert run(0x47c51b78,[slot,12])==0
            try:result=run(0x47c582b4,[1<<slot])
            except Exception as error:
                print('Registration stopped',hex(sku),slot,type(error).__name__,str(error),'PC',hex(cpu.reg_read(UC_ARM_REG_PC)),flush=True)
                raise
            assert result==0,(hex(sku),slot,result,details)
            assert not details,(hex(sku),slot,details)
            cases.append(dict(sku=hex(sku),slot=slot,stock_registration_return=result,no_detail_errors=True))
    out=ROOT/'artifacts/virtual-csic-registration';out.mkdir(exist_ok=True)
    (out/'REPORT.json').write_text(json.dumps(dict(status='UNRELEASED SYNTHETIC REGISTRATION REPLAY; NOT EFU',layout=layout,cases=cases,
        limits=['Virtual adapters replace vendor-chip authentication; they do not emulate real-chip crypto.',
            'Property/configuration, event delivery and the OS status-publication callback are mocked; no complete cold boot or hardware discovery.',
            'Unlimited remaining ink, persistence, automatic supply, IES and physical printing are not verified.']),indent=2)+'\n')
    print('24 original registration cases pass through virtual adapters without physical chip transport.')

if __name__=='__main__':main()
