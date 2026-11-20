"""Native ARM checks for the V9 refill-reset controller (no printer).

Reuses the V6 integration environment (property/OS/GPIO mocks) and runs the
ORIGINAL full scan 0x47C58AB0, registration, consumption commit and status
evaluator 0x47C61B24 on the patched controller.
"""
import hashlib,json,struct
from unicorn.arm_const import *
from prototype_virtual_csic_transport import ROOT,BASE
from virtual_csic_relocated_patch import patch as build_v6
from virtual_ink_refill_patch import patch,STATE,PROPERTY_READY,HELPER
from validate_virtual_csic_relocated import environment
import validate_virtual_ink_counter as status

def main():
    stock=(ROOT/'artifacts/maintenance-virtualization/decoded/119075160.crom.0.bin').read_bytes()
    v6,layout=build_v6(stock);v9,info=patch(v6,stock)
    cases=[]
    def setup(image,sku,initial,mb=0x1234):
        cpu,props,ids,events,details,run=environment(image,sku,initial)
        props[0x75b]=struct.pack('<H',mb)
        assert run(0x47c58ab0,[0x20004000])==0 and not details
        return cpu,props,ids,details,run
    used=lambda props,ids:[struct.unpack('<I',props[i][:4])[0] for i in ids]
    def counts(run,cpu):
        out=[]
        for s in range(4):
            assert run(0x47c5256c,[s,0x20005000])==0
            out.append(struct.unpack('<H',cpu.mem_read(0x20005000,2))[0])
        return out
    for sku in layout['skus']:
        for initial in [10000000,100000000]:
            # Boot-like scan: no reset, identical to V6.
            cpu,props,ids,details,run=setup(v9,sku,initial)
            assert used(props,ids)==[initial]*4
            before=counts(run,cpu);assert all(c>0 for c in before)
            # Per-slot near-end (4) and end (6) resets on the next scan.
            for slot,state in [(1,4),(2,6)]:
                cpu.mem_write(STATE+slot,bytes([state]))
                assert run(0x47c58ab0,[0x20004000])==0 and not details,(sku,slot,details)
                cpu.mem_write(STATE+slot,b'\0')
            u=used(props,ids);c=counts(run,cpu)
            assert u==[initial,0,0,initial],u
            assert c[1]==0 and c[2]==0 and c[0]==before[0] and c[3]==before[3],(c,before)
            # Consumption after a reset commits and re-registers normally.
            props[ids[1]]=struct.pack('<I',10000)
            cpu.mem_write(0x20006000,b'\x01\x00\x00')
            assert run(0x47c561b4,[1<<1,0x20006000])==0
            assert run(0x47c58508,[1<<1,0x20004000])==0 and not details
            # Manual trigger: MB counter 0 -> all reset once, marker becomes 1.
            for i in ids:props[i]=struct.pack('<I',initial)
            props[0x75b]=b'\0\0'
            assert run(0x47c58ab0,[0x20004000])==0 and not details
            assert used(props,ids)==[0]*4 and props[0x75b][:2]==b'\x01\x00'
            for i in ids:props[i]=struct.pack('<I',initial)
            assert run(0x47c58ab0,[0x20004000])==0 and used(props,ids)==[initial]*4
            # Not ready: helper must do nothing.
            cpu.mem_write(PROPERTY_READY,b'\0\0\0\0');cpu.mem_write(STATE+3,b'\x06');props[0x75b]=b'\0\0'
            # V6 itself falls back to the stock (physical) path before readiness;
            # the harness stops there. Only the helper's side effects matter.
            try:run(0x47c58ab0,[0x20004000])
            except AssertionError as error:assert 'hardware or fatal path' in str(error)
            assert used(props,ids)==[initial]*4 and props[0x75b]==b'\0\0'
            cases.append(dict(sku=hex(sku),initial=initial,counts_before=before,counts_after_slot_resets=c))
            # Control: V6 never resets for the same state.
            cpu6,props6,ids6,d6,run6=setup(v6,sku,initial)
            cpu6.mem_write(STATE+1,b'\x06');assert run6(0x47c58ab0,[0x20004000])==0
            assert used(props6,ids6)==[initial]*4
    # Display clear must not touch the helper (outside the LCD framebuffer).
    cpu,props,ids,details,run=setup(v9,layout['skus'][0],0)
    snap=bytes(cpu.mem_read(HELPER,info['helper_bytes']))
    cpu.mem_write(0x47d57d98,struct.pack('<I',0x47d69594));run(0x47c49b40,[0,0,0,0])
    assert bytes(cpu.mem_read(HELPER,info['helper_bytes']))==snap
    # Stock status evaluator is active again (no V8 override, no 100% hooks).
    near=status.run(v9,[100000,950000,0,0]);fresh=status.run(v9,[0,0,0,0]);end=status.run(v9,[0,1200000,0,0])
    assert near['record'][1]==0x83 and end['state'][1]==6 and fresh['record']==[0x80]*4 and fresh['level']==[100]*4
    report=dict(status='V9 NATIVE REFILL-RESET CHECKS PASSED; synthetic properties/OS mocks; no printer',
        controller_v6_sha256=hashlib.sha256(v6).hexdigest(),controller_v9_sha256=hashlib.sha256(v9).hexdigest(),
        patch=info,cases=cases,display_clear_preserves_helper=True,
        status_evaluator=dict(near_end=near,end=end,fresh=fresh),
        checks=['boot-like scan does not reset','near-end(4)/end(6) slot resets on next scan, others unchanged',
            'virtual chip counter follows reset; commit and re-registration succeed afterwards',
            'MB counter 0x75B==0 resets all once and is consumed (set to 1)','property manager not ready -> no action',
            'V6 control never resets','stock near-end/end/level reporting active'])
    (ROOT/'docs/virtual-ink-refill-v9.json').write_text(json.dumps(report,indent=2)+'\n')
    print('PASS',len(cases),'cases; V9 controller',report['controller_v9_sha256'])

if __name__=='__main__':main()
