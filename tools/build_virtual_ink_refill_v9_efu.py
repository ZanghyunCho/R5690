"""Package V9: V7 + refill-reset controller (virtual_ink_refill_patch); V8 change NOT included.

Only the GR controller CROM (slot 0x440000, segment 0) changes relative to V7.
Never executes an updater or accesses a printer. Physical boot unverified.
"""
from pathlib import Path
import copy,hashlib,json,struct,zipfile,subprocess,sys
from stock_crom_codec import parse,expand,repair
from validate_crom_native import validate
from build_virtual_csic_relocated_efu import verify
from virtual_ink_refill_patch import patch as refill_patch
from virtual_csic_relocated_patch import patch as build_v6
ROOT=Path(__file__).resolve().parents[1]
NAME='FWE642TL_GR_VIRTUAL_CSIC_MB_T3400_CLUT_MATTE_SML_REFILL_CANDIDATE_v9.EFU'
PARENT_SHA='5040470409309b63d070841cd3606858bf891e6a507c42ded7e589c805207859'
V7_CONTROLLER_SHA='4e75ad9b22d56eb21eb116b3fb1b3c2fd980dab9e6db172b3b292bd4da204ea4'
sha=lambda b:hashlib.sha256(b).hexdigest()

def main():
    parent=ROOT/'firmware/custom/matte-sml-candidate-v7/FWE642TL_GR_VIRTUAL_CSIC_MB_T3400_CLUT_MATTE_SML_CANDIDATE_v7.EFU'
    assert sha(parent.read_bytes())==PARENT_SHA,'V7 parent missing or not pulled from LFS'
    with zipfile.ZipFile(parent) as z:
        assert z.namelist()==['FWE642TL.rcx'];original=z.read('FWE642TL.rcx')
        info=copy.copy(z.getinfo('FWE642TL.rcx'));comment=z.comment
    blocks=verify(original);start,end=0x6d4f158,0x7d4f158;rom=original[start:end]
    assert rom[0x440000:0x440004]==b'CROM'
    seg=parse(rom,0x440004);controller=expand(seg['tokens'],seg['literals'])
    assert sha(controller)==V7_CONTROLLER_SHA
    stock=(ROOT/'artifacts/maintenance-virtualization/decoded/119075160.crom.0.bin').read_bytes()
    v6,_=build_v6(stock);assert v6==controller
    desired,layout=refill_patch(v6,stock)
    subprocess.run([sys.executable,str(ROOT/'tools/validate_virtual_ink_refill.py')],check=True,cwd=ROOT/'tools')
    check=json.loads((ROOT/'docs/virtual-ink-refill-v9.json').read_text())
    assert check['controller_v9_sha256']==sha(desired)
    encoded,codec=repair(rom[0x440004:seg['end']],desired)
    pos=seg['end'];tail=[]
    for _ in range(2):
        t=parse(rom,pos);tail.append(rom[pos:t['end']]);pos=t['end']
    assert pos<=0x4d0000 and rom[pos:0x4d0000]==b'\xff'*(0x4d0000-pos)
    replacement=b'CROM'+encoded+b''.join(tail)
    assert len(replacement)<=0x90000
    newrom=rom[:0x440000]+replacement+b'\xff'*(0x90000-len(replacement))+rom[0x4d0000:]
    assert len(newrom)==len(rom)
    native=validate(rom,newrom)
    assert native['segments'][2]['sha256']==sha(desired)
    old=[sha(expand(*(lambda s:(s['tokens'],s['literals']))(parse(rom,p)))) for p in
         [0x40004,parse(rom,0x40004)['end'],seg['end'],parse(rom,seg['end'])['end']]]
    assert [native['segments'][i]['sha256'] for i in (0,1,3,4)]==old
    result=bytearray(original);result[start:end]=newrom
    owner=next(b for b in blocks if any(r['start']==start for r in b['records']));assert owner['variant']=='GR'
    record=next(r['record'] for r in owner['records'] if r['start']==start)
    struct.pack_into('<H',result,record+2,sum(newrom)&65535)
    h=hashlib.sha1(newrom);h.update(hashlib.sha1(result[owner['start']:owner['start']+14]).digest())
    result[record+16:record+36]=h.digest();result=bytes(result);verify(result)
    allowed=sorted([(record+2,record+4),(record+16,record+36),(start+0x440000,start+0x4d0000)])
    cursor=0
    for a,b in allowed:assert original[cursor:a]==result[cursor:a];cursor=b
    assert original[cursor:]==result[cursor:]
    folder=ROOT/'firmware/custom/virtual-ink-refill-v9';folder.mkdir(exist_ok=True)
    output=folder/NAME;assert not output.exists(),'Refusing to overwrite an existing EFU'
    with zipfile.ZipFile(output,'x',compression=zipfile.ZIP_DEFLATED,compresslevel=9) as z:
        z.comment=comment;z.writestr(info,result)
    with zipfile.ZipFile(output) as z:assert z.testzip() is None and z.read('FWE642TL.rcx')==result
    manifest=dict(status='V9 CANDIDATE: V7 + real ink levels, stock ink-end stop, refill reset on pack re-check; physical boot unverified',
        file=NAME,bytes=output.stat().st_size,sha256=sha(output.read_bytes()),parent_efu_sha256=PARENT_SHA,
        rcx_sha256=sha(result),controller_before_sha256=V7_CONTROLLER_SHA,controller_after_sha256=sha(desired),
        patch=layout,native_checks='docs/virtual-ink-refill-v9.json',
        v6_integration_suite_on_v9='PASS: 72 scans, 144 commits, 144 re-registrations (MB counter mocked nonzero)',
        startup_checks_on_v9='PASS: 64 early setter cases, 36 pre-activation entry controls',
        native_crom=native,crom_repair=codec,all_14_records_verified=True,zip_readback_identical=True,
        allowed_rcx_ranges=allowed,library_main_boot_byte_identical_to_v7=True,v8_status_override_included=False,
        usage=['Levels drop with use; at ink end printing stops as stock.',
            'Refill, then open and close the ink cover (pack re-check): every colour in near-end or end state is reset to full.',
            'All colours at once: service program Maintenance Box counter Initialize, then power cycle.'],
        limits=['Which physical action triggers the stock full scan 0x47C58AB0 (cover close / replacement flow) is inferred from callers, not traced on hardware.',
            'Property 0x75B is read by the stock maintenance-box gate; its link to EEPROM 0x28-0x29 written by the service program is inferred, not proven.',
            'A colour that is merely near-end is also reset when the cover is closed, even without refilling.',
            'Synthetic properties, OS and GPIO mocks; no complete boot or printer test.',
            'Independent rcx_correct cross-check unavailable in this environment.'])
    (folder/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
    (folder/'SHA256SUMS').write_text(f"{manifest['sha256']}  {NAME}\n")
    print('Built',output,'SHA256',manifest['sha256'],flush=True)

if __name__=='__main__':main()
