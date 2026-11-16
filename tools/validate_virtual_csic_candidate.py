"""Native ARM integration checks with explicit property/OS mocks; no printer."""
import hashlib,json,struct
from collections import deque
from unicorn import UC_HOOK_CODE
from unicorn.arm_const import *
from prototype_virtual_csic_transport import ROOT,BASE,BUFFERS,machine
from virtual_csic_patch import patch as build

REGS=[UC_ARM_REG_R0,UC_ARM_REG_R1,UC_ARM_REG_R2,UC_ARM_REG_R3]
FORBIDDEN=[0x47c554f4,0x47c555a0,0x47c55b28,0x47c55bec,0x47c55c98,0x47c5577c,
           0x47c556c8,0x47c513e0,0x47c51434,0x47c512b0,0x47c6e0d0,0x47caf4ec,0x47caf4dc]

def environment(image,sku,initial):
    cpu=machine(image,cpu_model=UC_CPU_ARM_926);cpu.mem_map(0x3fffc000,0x4000)
    # Original per-colour cumulative ink-use property IDs, not EEPROM offsets.
    word=lambda a:struct.unpack_from('<I',image,a-BASE)[0]
    ids=[word(a) for a in [0x47c5bc68,0x47c5bc6c,0x47c5bc70,0x47c5bc74]]
    props={0x2e6:bytes([sku])}
    for prop in ids:props[prop]=struct.pack('<I',initial)
    events=[];details=[];reads=[]
    recent=deque(maxlen=18)
    cpu.hook_add(UC_HOOK_CODE,lambda uc,a,size,ctx:recent.append(hex(a)))
    def hook(uc,a,size,ctx):
        r0,r1,r2=[uc.reg_read(r) for r in REGS[:3]]
        if a==0x47c4b0c8:
            assert r2<256
            value=props.get(r0,bytes(r2));assert len(value)>=r2,(hex(r0),r2)
            uc.mem_write(r1,value[:r2]);reads.append(r0)
        elif a==0x47c4afd8:
            assert r2<256
            props[r0]=bytes(uc.mem_read(r1,r2))
        elif a==0x47c6a4f8:events.append([r0,r1])
        elif a==0x47c5bbe8:details.append([r0,r1])
        elif a in FORBIDDEN:raise AssertionError(('hardware or fatal path',hex(a),hex(uc.reg_read(UC_ARM_REG_LR))))
        elif a in [0x47c5b984,0x47c5451c]:pass
        else:return
        uc.reg_write(UC_ARM_REG_R0,0);uc.reg_write(UC_ARM_REG_PC,uc.reg_read(UC_ARM_REG_LR))
    for a in [0x47c4afd8,0x47c4b0c8,0x47c6a4f8,0x47c5bbe8,0x47c5b984,0x47c5451c]+FORBIDDEN:
        cpu.hook_add(UC_HOOK_CODE,hook,begin=a,end=a)
    def run(address,args):
        for r,v in zip(REGS,args):cpu.reg_write(r,v)
        cpu.reg_write(UC_ARM_REG_SP,0x2001f000);cpu.reg_write(UC_ARM_REG_LR,0x20000100)
        try:cpu.emu_start(address,0x20000100,count=1000000)
        except Exception:
            print("stopped",hex(address),list(recent));raise
        assert cpu.reg_read(UC_ARM_REG_PC)==0x20000100,hex(cpu.reg_read(UC_ARM_REG_PC))
        assert cpu.reg_read(UC_ARM_REG_SP)==0x2001f000
        return cpu.reg_read(UC_ARM_REG_R0)
    return cpu,props,ids,events,details,run

def main():
    stock=(ROOT/'artifacts/maintenance-virtualization/decoded/119075160.crom.0.bin').read_bytes()
    image,layout=build(stock);cases=[]
    for sku in layout['skus']:
        for initial in [0,1,100000,10000000,100000000,4000000000]:
            cpu,props,ids,events,details,run=environment(image,sku,initial)
            # Configured stock chip generation modes; exercise both copies.
            mode=(len(cases)%4)+1
            cpu.mem_write(struct.unpack_from("<I",stock,0x47c565b0-BASE)[0]-0x14,bytes([mode]))
            # Original full four-slot discovery/registration orchestration.
            assert run(0x47c58ab0,[0x20004000])==0,(hex(sku),initial,details)
            assert not details,(hex(sku),initial,details)
            uid_before=bytes(cpu.mem_read(0x47e032b8,88))
            assert len({uid_before[i*22:(i+1)*22] for i in range(4)})==4
            counts=[]
            assert all(prop in [0x808,0x809,0x80d,0x80e] for prop in ids)
            for slot in range(4):
                assert run(0x47c5256c,[slot,0x20005000])==0
                old_count=struct.unpack('<H',cpu.mem_read(0x20005000,2))[0]
                if initial>=10000000:assert old_count>0
                # Advance original NVRAM/property consumption, then execute
                # original calculation, native packing, commit and bookkeeping.
                props[ids[slot]]=struct.pack('<I',initial+10000)
                cpu.mem_write(0x20006000,b'\x01\x00\x00')
                assert run(0x47c561b4,[1<<slot,0x20006000])==0,(sku,slot,initial,details)
                assert run(0x47c5256c,[slot,0x20005000])==0
                current=struct.unpack('<H',cpu.mem_read(0x20005000,2))[0]
                assert current>=old_count
                counts.append([old_count,current])
                # Re-registration includes the original decrement/protected
                # field write/readback self-test with nonzero consumption.
                assert run(0x47c58508,[1<<slot,0x20004000])==0,(sku,slot,initial,details)
            assert not details,(hex(sku),initial,details)
            # Stock scan clears chip banks; seed markers must invalidate and
            # restore the same virtual identities and current consumption.
            assert run(0x47c58ab0,[0x20004000])==0,(sku,initial,details)
            assert bytes(cpu.mem_read(0x47e032b8,88))==uid_before
            assert not details
            cases.append(dict(sku=hex(sku),initial_consumption=initial,counts=counts,mode=mode,
                full_scan=True,consumption_commits=4,individual_reregistrations=4,
                repeat_full_scan=True,identities_stable=True,no_detail_errors=True))
    # Fresh CPU/RAM instances retain synthetic property values, as a cold
    # start would. This tests reconstruction, not a physical power cycle.
    cold_starts=[]
    for mode in range(1,5):
        fresh,persistent,_,_,fresh_details,reboot=environment(image,0x20,100010000)
        fresh.mem_write(struct.unpack_from('<I',stock,0x47c565b0-BASE)[0]-0x14,bytes([mode]))
        assert reboot(0x47c58ab0,[0x20004000])==0
        assert not fresh_details
        assert bytes(fresh.mem_read(0x47e032b8,88))==uid_before
        cold_starts.append(dict(mode=mode,stable_identities=True,reconstructed_from_properties=True))
    # Negative controls distinguish virtual success from a universal stub.
    _,_,_,_,_,unknown=environment(image,0x77,0)
    assert unknown(0x47c51b78,[0,84])==1
    _,_,_,_,_,control=environment(stock,0x20,0)
    try:control(0x47c58ab0,[0x20004000])
    except AssertionError as error:
        assert 'hardware or fatal path' in str(error)
    else:raise AssertionError('Stock control unexpectedly avoided physical CSIC access')
    out=ROOT/'artifacts/virtual-csic-candidate';out.mkdir(exist_ok=True)
    report=dict(status='OFFLINE ARM INTEGRATION PASSED; physical boot/supply/printing unverified',
        controller_sha256=hashlib.sha256(image).hexdigest(),cpu_model='ARM926',cases=cases,layout=layout,
        original_scan_calls=len(cases)*2,original_consumption_commits=len(cases)*4,original_reregistrations=len(cases)*4,
        forbidden_hardware_or_fatal_calls=0,
        unknown_sku_rejected=True,stock_positive_control_reaches_hardware=True,
        physical_history_object_write_or_format_calls=0,cold_start_reconstruction_cases=cold_starts,
        mocks=['Runtime properties including cumulative ink use are synthetic in-memory values.',
            'Event delivery, delay and OS status-publication callback 0x47C5451C are mocked.',
            'No complete operating-system boot, actuator control, supply/IES or printing test.'])
    (out/'REPORT.json').write_text(json.dumps(report,indent=2)+'\n')
    print(f'PASS: {len(cases)*2} stock full scans, {len(cases)*4} consumption commits, {len(cases)*4} re-registrations; no trapped CSIC hardware or fatal calls.')

if __name__=='__main__':main()
