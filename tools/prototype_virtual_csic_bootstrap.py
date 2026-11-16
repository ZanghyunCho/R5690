"""Unreleased cold-start register/UID bootstrap for the RAM CSIC adapter.

Component-only bootstrap. Discovery/registration integration is implemented
separately; this standalone experiment is not an EFU or physical boot test.
Requires keystone-engine 0.9.2 for ARM helper assembly.
"""
from pathlib import Path
import hashlib
import json
import struct
from keystone import Ks, KS_ARCH_ARM, KS_MODE_ARM
from unicorn import UC_HOOK_CODE
from unicorn.arm_const import *
from prototype_virtual_csic_transport import ROOT,BASE,ENTRIES,BUFFERS,machine,call,branch

CAVE=0x47d70000
SEED=CAVE+0x800
IS_READY=CAVE+0x700
SKUS=CAVE+0x1000
TEMPLATES=CAVE+0x2000
UIDS=CAVE+0x3000
UID_CACHE=0x47e032b8
PROPERTY_READY=0x47d5eb9c

def build(stock):
    assert hashlib.sha256(stock).hexdigest()=='73e74252536d2880799c66b5dbf186b06848bf51d1a5763e0b5e708f9e4b018b'
    report=json.loads((ROOT/'artifacts/virtual-csic-images/REPORT.json').read_text())
    rows=report['cases'];skus=list(dict.fromkeys(int(row['sku'],16) for row in rows))
    assert len(skus)==6
    raw=b''.join((ROOT/'artifacts/virtual-csic-images'/row['file']).read_bytes() for row in rows)
    assert len(raw)==6*4*168
    uids=b''.join(f'R5691-VIRTUAL-{slot:08d}'.encode('ascii') for slot in range(4))
    assert len(uids)==88
    ks=Ks(KS_ARCH_ARM,KS_MODE_ARM)
    def asm(code,address):return bytes(ks.asm(code,addr=address)[0])
    image=bytearray(stock)
    spans=[]
    def place(address,data):
        assert stock[address-BASE:address-BASE+len(data)]==bytes([255])*len(data)
        assert all(address+len(data)<=a or address>=b for a,b in spans)
        image[address-BASE:address-BASE+len(data)]=data;spans.append((address,address+len(data)))
    place(SKUS,bytes(skus));place(TEMPLATES,raw);place(UIDS,uids)
    seed=asm(f'''
        push {{r1-r9, lr}}
        sub sp, sp, #8
        mov r4, r0
        mov r6, #22
        mul r6, r4, r6
        ldr r5, ={UID_CACHE}
        add r5, r5, r6
        ldr r7, ={UIDS}
        add r7, r7, r6
        mov r8, #0
    check_uid:
        ldrb r6, [r5, r8]
        ldrb r9, [r7, r8]
        cmp r6, r9
        bne needs_seed
        add r8, r8, #1
        cmp r8, #22
        blo check_uid
        b ready
    needs_seed:
        ldr r6, ={PROPERTY_READY}
        ldr r6, [r6]
        cmp r6, #0
        moveq r0, #2
        beq exit
        mov r0, #255
        strb r0, [sp]
        ldr r0, =0x2e6
        mov r1, sp
        mov r2, #1
        bl 0x47c4b0c8
        ldrb r6, [sp]
        ldr r7, ={SKUS}
        mov r8, #0
    search:
        ldrb r9, [r7, r8]
        cmp r6, r9
        beq found
        add r8, r8, #1
        cmp r8, #6
        blt search
        mov r0, #1
        b exit
    found:
        add r8, r4, r8, lsl #2
        mov r6, #168
        mul r8, r6, r8
        ldr r7, ={TEMPLATES}
        add r7, r7, r8
        ldr r6, =bank_pointers
        ldr r6, [r6, r4, lsl #2]
        mov r8, #42
    copy_bank:
        ldr r9, [r7], #4
        str r9, [r6], #4
        subs r8, r8, #1
        bne copy_bank
        mov r6, #22
        mul r6, r4, r6
        ldr r7, ={UIDS}
        add r7, r7, r6
        ldr r8, =0x47e032b8
        add r8, r8, r6
        mov r6, #22
    copy_uid:
        ldrb r9, [r7], #1
        strb r9, [r8], #1
        subs r6, r6, #1
        bne copy_uid
    ready:
        mov r0, #0
    exit:
        add sp, sp, #8
        pop {{r1-r9, pc}}
    bank_pointers:
        .word {BUFFERS[0]}, {BUFFERS[1]}, {BUFFERS[2]}, {BUFFERS[3]}
    ''',SEED)
    assert len(seed)<0x800;place(SEED,seed)
    # Native field setters mark modified words with bit 15. Physical reload
    # returns clean data words; exposing these marks as chip flags breaks the
    # original registration write/readback self-test.
    clean=asm(f'''
        push {{r0-r4,lr}}
        bl 0x47c51b4c
        bl 0x47c51a60
        mov r1, #84
    clean_loop:
        ldrh r2, [r0]
        bic r2, r2, #0x8000
        strh r2, [r0], #2
        subs r1, r1, #1
        bne clean_loop
        pop {{r0-r4,pc}}
    ''',CAVE+0x600)
    place(CAVE+0x600,clean)
    ready=asm(f'''
        push {{r1-r4,lr}}
        mov r1,#22
        mul r1,r0,r1
        ldr r2,={UID_CACHE}
        add r2,r2,r1
        ldr r3,={UIDS}
        add r3,r3,r1
        mov r4,#0
    compare_uid:
        ldrb r0,[r2,r4]
        ldrb r1,[r3,r4]
        cmp r0,r1
        movne r0,#2
        bne ready_exit
        add r4,r4,#1
        cmp r4,#22
        blo compare_uid
        mov r0,#0
    ready_exit:
        pop {{r1-r4,pc}}
    ''',IS_READY)
    place(IS_READY,ready)
    changes=[]
    for i,(entry,name) in enumerate(ENTRIES.items()):
        helper=CAVE+64*i;prologue=struct.unpack_from('<I',stock,entry-BASE)[0]
        assert prologue==0xe92d47f0
        gate=asm(f'''
            cmp r0, #4
            bhs fallback
            push {{r0-r4, lr}}
            bl {IS_READY}
            cmp r0, #2
            beq deferred
            cmp r0, #0
            bne complete
            ldr r0, [sp]
            bl {CAVE+0x600}
            mov r0, #0
        complete:
            str r0, [sp]
            pop {{r0-r4, pc}}
        deferred:
            pop {{r0-r4, lr}}
        fallback:
            .word {prologue}
            b {entry+4}
        ''',helper)
        assert len(gate)<=64;place(helper,gate)
        struct.pack_into('<I',image,entry-BASE,branch(entry,helper))
        changes.append(dict(entry=hex(entry),helper=hex(helper),operation=name))
    return bytes(image),dict(entries=changes,cave_spans=[[hex(a),hex(b)] for a,b in spans],seed=hex(SEED),skus=skus)

def main():
    stock=(ROOT/'artifacts/maintenance-virtualization/decoded/119075160.crom.0.bin').read_bytes()
    image,layout=build(stock);tests=[]
    def trap(uc,address,size,context):raise AssertionError('Physical CSIC transport executed')
    for sku in layout['skus']:
        cpu=machine(image);reads=[]
        cpu.mem_write(PROPERTY_READY,struct.pack("<I",1))
        def prop(uc,address,size,context):
            assert uc.reg_read(UC_ARM_REG_R0)==0x2e6 and uc.reg_read(UC_ARM_REG_R2)==1
            reads.append(sku);uc.mem_write(uc.reg_read(UC_ARM_REG_R1),bytes([sku]));uc.reg_write(UC_ARM_REG_R0,0)
            uc.reg_write(UC_ARM_REG_PC,uc.reg_read(UC_ARM_REG_LR))
        cpu.hook_add(UC_HOOK_CODE,prop,begin=0x47c4b0c8,end=0x47c4b0c8)
        for address in [0x47c554f4,0x47c555a0,0x47c55b28,0x47c55bec,0x47c55c98]:cpu.hook_add(UC_HOOK_CODE,trap,begin=address,end=address)
        identities=[]
        for slot in range(4):
            assert call(cpu,SEED,[slot])==0
            assert call(cpu,0x47c51b78,[slot,12])==0
            identity=bytes(cpu.mem_read(0x47e032b8+slot*22,22));assert len(identity)==22
            identities.append(identity)
            assert call(cpu,0x47c522f0,[slot,0x72,0x20001000])==0
            assert struct.unpack('<H',cpu.mem_read(0x20001000,2))[0]==0x40+slot
            assert call(cpu,0x47c526c4,[slot,0x1234])==0
            assert call(cpu,0x47c51d84,[slot,1])==0
            assert call(cpu,0x47c51b78,[slot,4])==0
            assert call(cpu,0x47c5256c,[slot,0x20001000])==0
            assert struct.unpack('<H',cpu.mem_read(0x20001000,2))[0]==0x1234
            assert bytes(cpu.mem_read(0x47e032b8+slot*22,22))==identity
            tests.append(dict(sku=hex(sku),slot=slot,cold_start=True,write_reload_preserved=True,uid_stable_within_boot=True))
        assert len(set(identities))==4 and len(reads)==4
    result=dict(status='UNRELEASED BOOTSTRAP EXPERIMENT; NOT A COMPLETE CHIP EMULATOR OR EFU',layout=layout,cases=tests,
        limits=['No authenticated vendor-chip data/challenge protocol or no-chip discovery integration.',
            'No persistent counter/UID history handling across actual reboots.',
            'No always-available policy or IES/pump behavior verification.'])
    out=ROOT/'artifacts/virtual-csic-bootstrap';out.mkdir(exist_ok=True)
    (out/'REPORT.json').write_text(json.dumps(result,indent=2)+'\n')
    print('24 ARM cold-start/reload cases passed; four stable in-boot identities; no trapped chip bus calls.')

if __name__=='__main__':main()
