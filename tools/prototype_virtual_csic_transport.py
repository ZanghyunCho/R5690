"""Unreleased ARM RAM-backed CSIC transport adapter, NOT flashable firmware.

Proves an emulated write/read roundtrip on PRESEEDED buffers. Cold-start chip
image construction, authentication, identity lifetime, no-chip detection and
ink-supply sequencing remain unresolved. Never call this a complete virtual
cartridge and never package this controller as an EFU.
"""
from pathlib import Path
import hashlib
import json
import struct
from unicorn import Uc, UC_ARCH_ARM, UC_MODE_ARM, UC_HOOK_CODE
from unicorn.arm_const import *

ROOT=Path(__file__).resolve().parents[1]
BASE=0x47c48000
CAVE=0x47d70000
# Boundaries take a colour SLOT in r0, unlike the shared bus helpers, whose
# address spaces can include devices other than ink cartridges.
ENTRIES={0x47c51b78:'read',0x47c51c50:'alternate_read',0x47c51cf4:'readback',
         0x47c51d84:'write',0x47c51e28:'alternate_write'}
BUFFERS=[0x47e02b68,0x47e02eb0,0x47e02e08,0x47e02d60]

def branch(source,target):
    assert (target-source-8)%4==0
    return 0xea000000|(((target-source-8)//4)&0xffffff)

def staged_adapter(stock):
    assert hashlib.sha256(stock).hexdigest()=='73e74252536d2880799c66b5dbf186b06848bf51d1a5763e0b5e708f9e4b018b'
    image=bytearray(stock);edits=[]
    for i,(entry,name) in enumerate(ENTRIES.items()):
        helper=CAVE+i*32
        prologue=struct.unpack_from('<I',stock,entry-BASE)[0]
        assert prologue==0xe92d47f0
        # r0 < 4: retain existing RAM chip image and return success, without
        # calling hardware. Otherwise execute displaced prologue + stock body.
        words=[0xe3500004,0x33a00000,0x312fff1e,prologue,branch(helper+16,entry+4)]
        payload=struct.pack('<5I',*words)
        assert stock[helper-BASE:helper-BASE+len(payload)]==bytes([255])*len(payload)
        image[helper-BASE:helper-BASE+len(payload)]=payload
        struct.pack_into('<I',image,entry-BASE,branch(entry,helper))
        edits.append(dict(entry=hex(entry),helper=hex(helper),operation=name))
    return bytes(image),edits

def machine(image,cpu_model=None):
    cpu=Uc(UC_ARCH_ARM,UC_MODE_ARM)
    if cpu_model is not None:cpu.ctl_set_cpu_model(cpu_model)
    cpu.mem_map(BASE,0x3b8000);cpu.mem_write(BASE,image)
    cpu.mem_map(0x20000000,0x20000)
    return cpu

def call(cpu,address,args,end=0x20000100):
    for reg,value in zip([UC_ARM_REG_R0,UC_ARM_REG_R1,UC_ARM_REG_R2,UC_ARM_REG_R3],args):
        cpu.reg_write(reg,value)
    cpu.reg_write(UC_ARM_REG_SP,0x2001f000);cpu.reg_write(UC_ARM_REG_LR,0x20000100)
    cpu.emu_start(address,end,count=10000)
    assert cpu.reg_read(UC_ARM_REG_PC)==end
    return cpu.reg_read(UC_ARM_REG_R0)

def main():
    stock=(ROOT/'artifacts/maintenance-virtualization/decoded/119075160.crom.0.bin').read_bytes()
    image,edits=staged_adapter(stock);cpu=machine(image)
    reached=[]
    def forbidden(uc,address,size,context):
        reached.append(hex(address));raise AssertionError('Physical CSIC bus reached')
    for address in [0x47c554f4,0x47c555a0,0x47c55b28,0x47c55bec,0x47c55c98]:
        cpu.hook_add(UC_HOOK_CODE,forbidden,begin=address,end=address)
    for p in BUFFERS:cpu.mem_write(p,bytes(168))
    cases=[]
    for slot in range(4):
        for value in [0,1,4,0x1234,0x3fff]:
            before=[bytes(cpu.mem_read(p,168)) for p in BUFFERS]
            # Original logical counter setter updates both counter copies in
            # the existing colour-specific RAM bank.
            assert call(cpu,0x47c526c4,[slot,value])==0
            assert call(cpu,0x47c51d84,[slot,1])==0
            assert call(cpu,0x47c51b78,[slot,4])==0
            assert call(cpu,0x47c5256c,[slot,0x20001000])==0
            result=struct.unpack('<H',cpu.mem_read(0x20001000,2))[0]
            assert result==value
            after=[bytes(cpu.mem_read(p,168)) for p in BUFFERS]
            assert all(after[i]==before[i] for i in range(4) if i!=slot)
            cases.append(dict(slot=slot,counter_written=value,counter_read=result,other_banks_preserved=True))
        for entry in ENTRIES:
            for reg in [UC_ARM_REG_R4,UC_ARM_REG_R5,UC_ARM_REG_R6,UC_ARM_REG_R7,UC_ARM_REG_R8,UC_ARM_REG_R9,UC_ARM_REG_R10,UC_ARM_REG_R11]:
                cpu.reg_write(reg,0x12345678)
            assert call(cpu,entry,[slot,1])==0
            assert cpu.reg_read(UC_ARM_REG_SP)==0x2001f000
            assert all(cpu.reg_read(r)==0x12345678 for r in [UC_ARM_REG_R4,UC_ARM_REG_R5,UC_ARM_REG_R6,UC_ARM_REG_R7,UC_ARM_REG_R8,UC_ARM_REG_R9,UC_ARM_REG_R10,UC_ARM_REG_R11])
    fallback=[]
    for entry in ENTRIES:
        for slot in [4,255]:
            states=[]
            for program in [stock,image]:
                m=machine(program);call(m,entry,[slot,17],end=entry+4)
                states.append((m.reg_read(UC_ARM_REG_SP),bytes(m.mem_read(0x2001efc0,64)),m.reg_read(UC_ARM_REG_R0),m.reg_read(UC_ARM_REG_R1)))
            assert states[0]==states[1]
            fallback.append(dict(entry=hex(entry),slot=slot,original_prologue_and_arguments_preserved=True))
    # Execute the original higher-level consumption commit, including native
    # field packing, RAM-backed write, reload, readback comparison and ack.
    # Clock-to-counter calculation and bookkeeping callback are substituted;
    # mode 3 is a synthetic selected branch, not the current printer's mode.
    commit=[]
    word=lambda address:struct.unpack_from('<I',stock,address-BASE)[0]
    last_counts=word(0x47c565b0)
    requested_counts=word(0x47c565ac)
    for slot in range(4):
        for value in [0,1,0x1234]:
            m=machine(image);acks=[]
            m.mem_write(last_counts-0x14,b'\x03')
            m.mem_write(0x20002000,b'\x01')
            def clock(uc,address,size,context):
                selected=uc.reg_read(UC_ARM_REG_R0)
                assert selected==slot
                uc.mem_write(requested_counts+2*selected,struct.pack('<H',value))
                uc.reg_write(UC_ARM_REG_R0,0);uc.reg_write(UC_ARM_REG_PC,uc.reg_read(UC_ARM_REG_LR))
            def ack(uc,address,size,context):
                acks.append(uc.reg_read(UC_ARM_REG_R0))
                uc.reg_write(UC_ARM_REG_R0,0);uc.reg_write(UC_ARM_REG_PC,uc.reg_read(UC_ARM_REG_LR))
            m.hook_add(UC_HOOK_CODE,clock,begin=0x47c56184,end=0x47c56184)
            m.hook_add(UC_HOOK_CODE,ack,begin=0x47c550d8,end=0x47c550d8)
            for address in [0x47c554f4,0x47c555a0,0x47c55b28,0x47c55bec,0x47c55c98]:
                m.hook_add(UC_HOOK_CODE,forbidden,begin=address,end=address)
            assert call(m,0x47c561b4,[1<<slot,0x20002000])==0
            assert acks==[slot]
            assert struct.unpack('<H',m.mem_read(last_counts+2*slot,2))[0]==value
            assert call(m,0x47c5256c,[slot,0x20001000])==0
            assert struct.unpack('<H',m.mem_read(0x20001000,2))[0]==value
            commit.append(dict(slot=slot,counter=value,native_commit_return=0,readback_verified=True,acknowledgement_observed=True))
    # Positive control: the unchanged stock write really reaches a bus helper.
    control=machine(stock);hit=[]
    def stop(uc,a,size,context):hit.append(hex(a));uc.emu_stop()
    control.hook_add(UC_HOOK_CODE,stop,begin=0x47c555a0,end=0x47c555a0)
    for r,v in [(UC_ARM_REG_R0,0),(UC_ARM_REG_R1,1),(UC_ARM_REG_SP,0x2001f000),(UC_ARM_REG_LR,0x20000100)]:control.reg_write(r,v)
    control.emu_start(0x47c51d84,0x20000100,count=10000)
    assert hit==['0x47c555a0'] and not reached
    report=dict(status='UNRELEASED ADAPTER EXPERIMENT; NOT A COMPLETE VIRTUAL CHIP OR EFU',
        changes=edits,roundtrips=cases,consumption_commit_cases=commit,unsupported_slot_controls=fallback,physical_bus_calls=reached,
        stock_positive_control=hit,scope='No V1 state-cache overrides. Original field packing and per-slot RAM banks remain active.',
        missing=['Cold-start valid chip data and stable identity','No-chip discovery and authentication integration',
            'Persistence and reboot consistency','Always-available ink semantics without breaking write verification',
            'Actual automatic supply/IES and actuator behavior','Physical boot and print validation'])
    folder=ROOT/'artifacts/virtual-csic-adapter';folder.mkdir(exist_ok=True)
    (folder/'REPORT.json').write_text(json.dumps(report,indent=2)+'\n')
    print('20 native counter roundtrips, 12 native consumption commits, 20 ABI checks, 10 fallback controls; zero physical chip calls. Stock control reaches hardware.')

if __name__=='__main__':main()
