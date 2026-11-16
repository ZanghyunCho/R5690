"""OFFLINE SML binding probe, not an EFU or confirmed Enhanced Matte mapping.

Only donor catalogue L_APMP_MK/1200x1200 is staged. The UI Enhanced Matte
association is not proven here. Dither/halftone engine are deliberately stock.
"""
from pathlib import Path
import hashlib,json,struct,zipfile
from unicorn import UC_HOOK_CODE
from unicorn.arm_const import *
from colour_blob_codec import Codec
from stock_crom_codec import parse,expand
ROOT=Path(__file__).resolve().parents[1]
FOLDER=ROOT/'artifacts/t3400-lut/colour-blobs'
sha=lambda b:hashlib.sha256(b).hexdigest()

def rows(blob):
    lines=blob.decode('ascii').splitlines()
    header=next(x.split('\t') for x in lines if x.startswith('CMM-ID\t'))
    return [dict(zip(header,x.split('\t'))) for x in lines if x.split('\t')[0].isdigit()]

def main():
    inv=json.loads((FOLDER/'inventory.json').read_text())
    def blob(model,key):
        record=next(x for x in inv[model]['blobs'] if x['id']==key)
        data=(FOLDER/model/record['file']).read_bytes();assert sha(data)==record['sha256']
        return data,record
    cat,_=blob('r5691',0);donor_cat,_=blob('t3400',0)
    target=[r for r in rows(cat) if r.get('cSMB-ID')=='214' or r.get('mSMB-ID')=='214']
    assert {r['CMM-ID'] for r in target}=={'14','414','574'}
    assert all(r['media']=='PLAIN' and r['H-RES']==r['V-RES']=='1200' and r['OUT_BIT']=='2' for r in target)
    donor=[r for r in rows(donor_cat) if r.get('media')=='L_APMP_MK' and r.get('DocType')=='BASE' and r.get('H-RES')=='1200' and r.get('V-RES')=='1200']
    assert len(donor)==1 and donor[0]['cSMB-ID']==donor[0]['mSMB-ID']=='213' and donor[0]['OUT_BIT']=='2'
    source,source_record=blob('t3400',213);codec=Codec();stream=codec.encode(source)
    assert codec.decode(stream,len(source))==source
    parent=ROOT/'firmware/custom/virtual-csic-t3400-candidate-v6/FWE642TL_GR_VIRTUAL_CSIC_MB_T3400_CLUT_CANDIDATE_v6.EFU'
    assert sha(parent.read_bytes())=='290efca81c5a061c819a1bea03c11a676bd5eee1847e823393ae850ade008e26'
    with zipfile.ZipFile(parent) as z:rom=z.read('FWE642TL.rcx')[0x6d4f158:0x7d4f158]
    first=parse(rom,0x40004);seg=parse(rom,first['end']);library=expand(seg['tokens'],seg['literals'])
    host=next(x for x in inv['r5691']['blobs'] if x['id']==13);start=int(host['offset'],16)
    used=struct.unpack_from('<I',library,start+8)[0];slack_start=start+12+used
    slack_end=start+12+host['compressed_size']
    payload=bytes.fromhex('7acf865c7d903cb9')+struct.pack('<I',len(stream))+stream
    assert len(payload)<=slack_end-slack_start
    staged=bytearray(library);staged[slack_start:slack_start+len(payload)]=payload
    table=0x4821505c-0x4808f000;matches=[]
    for i in range(87):
        key,ptr=struct.unpack_from('<II',library,table+8*i)
        if key==214:
            matches.append(table+8*i+4);struct.pack_into('<I',staged,matches[-1],0x4808f000+slack_start)
    assert len(matches)==1
    cpu=codec.cpu;cpu.mem_map(0x4808f000,(len(staged)+4095)//4096*4096);cpu.mem_write(0x4808f000,bytes(staged))
    assert codec.call(0x480994c0,[0,214])==0x4808f000+slack_start
    for key in [0,11,13,14,211,216,220,225,650,651,652]:
        old_ptr=struct.unpack_from('<I',library,next(table+8*i+4 for i in range(87) if struct.unpack_from('<I',library,table+8*i)[0]==key))[0]
        assert codec.call(0x480994c0,[0,key])==old_ptr
    # The host CLUT's length-bound compressed stream is byte-identical.
    assert staged[start:start+12+used]==library[start:start+12+used]
    selections=[]
    cpu.mem_write(0x22000000,cat)
    for doc,cmm in [(4,14),(6,414),(18,574)]:
        cpu.mem_write(0x20030000,struct.pack('<8I',0,0,doc,3,1,1200,1200,2))
        cpu.mem_write(0x20031000,bytes(256))
        assert codec.call(0x48abe280,[0x20031000,0x20030000,0x22000000])==0
        words=struct.unpack('<64i',cpu.mem_read(0x20031000,256))
        assert words[0]==cmm and words[3]==214 and words[14]==652
        selections.append(dict(doc_type_index=doc,cmm_id=cmm,sml_id=words[3],stock_dither_id=words[14]))
    allocations=[]
    cpu.reg_write(UC_ARM_REG_C1_C0_2,0xf00000);cpu.reg_write(UC_ARM_REG_FPEXC,0x40000000)
    def allocate(uc,a,size,ctx):
        assert uc.reg_read(UC_ARM_REG_R1)<=0x100000
        allocations.append(uc.reg_read(UC_ARM_REG_R1))
        uc.reg_write(UC_ARM_REG_R0,0x23000000);uc.reg_write(UC_ARM_REG_PC,uc.reg_read(UC_ARM_REG_LR))
    hook=cpu.hook_add(UC_HOOK_CODE,allocate,begin=0x48aab300,end=0x48aab300)
    try:
        cpu.mem_write(0x22000000,source);cpu.mem_write(0x20030000,bytes(0x4000))
        cpu.mem_write(0x20035000,struct.pack('<I4B',4,1,2,3,0))
        assert codec.call(0x48abf698,[0x2003285c,256,1])==0
        assert codec.call(0x48abf630,[0x20030000,0x22000000,0x20035000,2])==0
    finally:cpu.hook_del(hook)
    ui_file=ROOT/'artifacts/t3400-lut/decoded/71459089.crom.0.bin'
    ui=ui_file.read_bytes();label_evidence=[]
    for name in [b'Enhanced Matte\0',b'Archival Matte\0']:
        off=ui.index(name)
        label_evidence.append(dict(label=name[:-1].decode(),file_offset=hex(off),preceding_u32=hex(struct.unpack_from('<I',ui,off-4)[0])))
    report=dict(native_catalogue_selections=selections,native_allocation_requests=allocations,
        ui_label_evidence=dict(source=str(ui_file.relative_to(ROOT)),sha256=sha(ui),labels=label_evidence),status='OFFLINE PROBE ONLY; NO EFU RELEASE',parent_efu_sha256=sha(parent.read_bytes()),
        donor_catalogue_row=donor[0],recipient_rows=target,donor_sml=source_record,
        recipient_id=214,staged_library_sha256=sha(staged),storage=dict(existing_owner_id=13,
            unused_compressed_tail_start=hex(slack_start),unused_tail_bytes=slack_end-slack_start,
            inserted_bytes=len(payload),host_live_stream_unchanged=True),native_lookup_and_sml_parser_pass=True,
        dither_and_halftone_engine_unchanged=True,controller_unchanged=True,
        blockers=['Mapping donor UI Enhanced Matte (0xB2) to catalogue L_APMP_MK is not proven; Archival Matte (0x0F) is a separate UI label.',
            'Donor 1200x1200 dither 702 references two large matrices, 662 and 682. Full storage/loading integration remains unresolved.',
            'No donor L_APMP_MK rows exist at 600x600 or 600x1200; no resampling or implicit DPI change is staged.',
            'T3400 2400x1200 row uses OUT_BIT 1; cannot substitute it into the recipient 2-bit mode without further work.',
            'Synthetic allocator/channel settings; no complete raster pipeline or physical output validation.'])
    out=ROOT/'artifacts/t3400-lut/matte-to-plain';out.mkdir(exist_ok=True)
    (out/'staged-library.bin.offline-only').write_bytes(staged)
    (ROOT/'docs/matte-to-plain-staging.json').write_text(json.dumps(report,indent=2)+'\n')
    print('Native lookup, donor SML decode/parser and bounded storage pass; no EFU, dither or confirmed UI mapping.')

if __name__=='__main__':main()
