"""V9 controller: real ink levels, stock ink-end stop, refill reset on rescan.

Starts from the V6/V7 virtual-CSIC controller (NOT V8):
1. Removes V6's level-only 100% presentation hooks (0x47CAB5A4, 0x47CA99DC)
   and restores the stock bytes of the dead helper area 0x47C63E1C..0x47C63EA4.
   Levels, near-end and ink-end come from the stock status evaluator again.
2. Hooks the stock full pack scan 0x47C58AB0 (run on cover close / pack
   re-check and at start-up). Before the stock scan runs:
   - every slot whose stock state (0x47D5EE18[slot]) is near-end (4) or
     end (5/6) gets the stock new-pack reset 0x47C5BB68(slot, 0);
   - if maintenance-box counter property 0x75B reads 0 (service-program
     "Initialize"), all four slots are reset and 0x75B is set to 1 so the
     request is consumed once.
   Skipped while the property manager is not ready (0x47D5EB9C == 0).
The helper lives in retired chip-auth code (0x47C8D8DC..), which V6 already
verified has no live external interior entries. No framebuffer use.
"""
import struct,hashlib
from keystone import Ks,KS_ARCH_ARM,KS_MODE_ARM

BASE=0x47c48000
V6_CONTROLLER_SHA='4e75ad9b22d56eb21eb116b3fb1b3c2fd980dab9e6db172b3b292bd4da204ea4'
SCAN=0x47c58ab0
HELPER=0x47c8d8dc;HELPER_END=0x47c8da00
DEAD=(0x47c63e1c,0x47c63ea4)
LEVEL_HOOKS=[0x47cab5a4,0x47ca99dc]
PROPERTY_READY=0x47d5eb9c;STATE=0x47d5ee18;MB_COUNTER=0x75b
PROP_READ=0x47c4b0c8;PROP_WRITE=0x47c4afd8;NEW_PACK_RESET=0x47c5bb68

def branch(src,dst):
    return 0xea000000|(((dst-src-8)//4)&0xffffff)

def patch(v6,stock):
    assert hashlib.sha256(v6).hexdigest()==V6_CONTROLLER_SHA
    img=bytearray(v6)
    w=lambda b,a:struct.unpack_from('<I',b,a-BASE)[0]
    # 1. Remove level-only presentation; restore dead helper bytes to stock.
    for a in LEVEL_HOOKS:
        assert w(v6,a)&0xff000000==0xea000000
        struct.pack_into('<I',img,a-BASE,w(stock,a))
    lo,hi=DEAD;img[lo-BASE:hi-BASE]=stock[lo-BASE:hi-BASE]
    # 2. Refill helper.
    assert w(v6,SCAN)==0xe92d4ff0==w(stock,SCAN)
    src=f'''
     push {{r0-r5,lr}}
     sub sp,sp,#4
     ldr r4,lit_ready
     ldr r4,[r4]
     cmp r4,#0
     beq done
     mvn r5,#0
     str r5,[sp]
     ldr r0,lit_mb
     mov r1,sp
     mov r2,#2
     bl {PROP_READ}
     ldrh r0,[sp]
     cmp r0,#0
     moveq r5,#0xf
     movne r5,#0
     ldr r1,lit_state
     mov r4,#3
    states:
     ldrb r3,[r1,r4]
     cmp r3,#4
     movhs r3,#1
     orrhs r5,r5,r3,lsl r4
     subs r4,r4,#1
     bpl states
     mov r4,#0
    apply:
     mov r3,r5,lsr r4
     tst r3,#1
     movne r0,r4
     movne r1,#0
     blne {NEW_PACK_RESET}
     add r4,r4,#1
     cmp r4,#4
     blo apply
     ldrh r0,[sp]
     cmp r0,#0
     bne done
     mov r0,#1
     str r0,[sp]
     ldr r0,lit_mb
     mov r1,sp
     mov r2,#2
     mov r3,#0
     bl {PROP_WRITE}
    done:
     add sp,sp,#4
     pop {{r0-r5,lr}}
     push {{r4-r11,lr}}
     b {SCAN+4}
    lit_ready: .word {PROPERTY_READY}
    lit_mb: .word {MB_COUNTER}
    lit_state: .word {STATE}
    '''
    code=bytes(Ks(KS_ARCH_ARM,KS_MODE_ARM).asm(src,addr=HELPER)[0])
    assert HELPER+len(code)<=HELPER_END
    # Helper area must still hold retired stock code (unallocated by V6).
    assert v6[HELPER-BASE:HELPER-BASE+len(code)]==stock[HELPER-BASE:HELPER-BASE+len(code)]
    img[HELPER-BASE:HELPER-BASE+len(code)]=code
    struct.pack_into('<I',img,SCAN-BASE,branch(SCAN,HELPER))
    assert not (0x47d69594<=HELPER<0x47de8d94)
    return bytes(img),dict(helper=hex(HELPER),helper_bytes=len(code),scan_hook=hex(SCAN),
        level_hooks_restored=[hex(a) for a in LEVEL_HOOKS],dead_area_restored=[hex(lo),hex(hi)],
        reset_states='near-end 4, end 5/6 at 0x47D5EE18',manual_trigger='property 0x75B == 0 -> all slots, then 0x75B := 1',
        controller_sha256=hashlib.sha256(img).hexdigest())
