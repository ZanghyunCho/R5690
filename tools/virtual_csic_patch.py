"""Virtual CSIC candidate plus existing MB patch and level-only presentation.

Does not suppress raw chip errors or alter IES, pump or Initial Charge state.
Offline checks are not a physical boot guarantee.
"""
import hashlib,struct
from keystone import Ks,KS_ARCH_ARM,KS_MODE_ARM
from prototype_virtual_csic_registration import build
from prototype_virtual_csic_transport import ROOT,BASE,branch
from virtual_box_patch import patch as maintenance

def patch(stock):
    virtual,layout=build(stock)
    mb,mbchanges=maintenance(stock)
    result=bytearray(virtual)
    for change in mbchanges:
        offset=int(change['address'],16)-BASE
        assert virtual[offset:offset+4]==stock[offset:offset+4]
        result[offset:offset+4]=mb[offset:offset+4]
    ks=Ks(KS_ARCH_ARM,KS_MODE_ARM)
    def put(address,payload):result[address-BASE:address-BASE+len(payload)]=payload
    # Preserve state/type in the three-byte native snapshot records.
    helper=0x47c63e20;entry=0x47cab5a4
    assert struct.unpack_from('<I',stock,entry-BASE)[0]==0xe92d40f0
    code=bytes(ks.asm(f'''push {{r1-r3,lr}}
        add r1,r0,#0x14
        mov r3,#4
        mov r2,#100
    level_loop:
        strb r2,[r1,#1]
        add r1,r1,#3
        subs r3,r3,#1
        bne level_loop
        pop {{r1-r3,lr}}
        .word 0xe92d40f0
        b {entry+4}''',addr=helper)[0])
    assert helper+len(code)<=0x47c63e60
    put(helper,code);put(entry,struct.pack('<I',branch(entry,helper)))
    # Original API opcode 0x26 retains its channel bounds and aggregation.
    helper=0x47c63e60;entry=0x47ca99dc
    assert struct.unpack_from('<I',stock,entry-BASE)[0]==0xe3560004
    code=bytes(ks.asm('''mov r4,#100
        cmp r6,#4
        strblo r4,[r2,#7]
        b 0x47caa478''',addr=helper)[0])
    put(helper,code);put(entry,struct.pack('<I',branch(entry,helper)))
    assert len(result)==len(stock)
    # Explicitly retain old raw-state/error paths that V1 had overwritten.
    for a,n in [(0x47ca99e8,8),(0x47ca99fc,4),(0x47ca9b98,0x60),
                (0x47ca8108,8)]:
        assert result[a-BASE:a-BASE+n]==stock[a-BASE:a-BASE+n]
    layout['maintenance_changes']=mbchanges
    layout['remaining_only_interfaces']=['0x47CAB5A4 snapshot level bytes','0x47CA99DC bounded scalar level setter']
    layout['old_v1_raw_state_and_error_overrides_absent']=True
    layout['controller_sha256']=hashlib.sha256(result).hexdigest()
    return bytes(result),layout
