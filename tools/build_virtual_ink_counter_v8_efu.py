"""Package V8: V7 + ink-use status fix (virtual_ink_counter_patch).

Only the GR controller CROM (slot 0x440000, segment 0) changes relative to V7.
Never executes an updater or accesses a printer. Physical boot unverified.
"""
from pathlib import Path
import copy,hashlib,json,struct,zipfile,subprocess,sys
from stock_crom_codec import parse,expand,repair
from validate_crom_native import validate
from build_virtual_csic_relocated_efu import verify
from virtual_ink_counter_patch import patch
ROOT=Path(__file__).resolve().parents[1]
NAME='FWE642TL_GR_VIRTUAL_CSIC_MB_T3400_CLUT_MATTE_SML_INKCOUNT_CANDIDATE_v8.EFU'
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
    desired,layout=patch(controller)
    work=ROOT/'artifacts/v8';work.mkdir(parents=True,exist_ok=True)
    (work/'controller-v7.bin').write_bytes(controller)
    subprocess.run([sys.executable,str(ROOT/'tools/validate_virtual_ink_counter.py'),str(work/'controller-v7.bin')],check=True,cwd=ROOT/'tools')
    check=json.loads((ROOT/'docs/virtual-ink-counter-fix.json').read_text())
    assert check['controller_after_sha256']==sha(desired)
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
    folder=ROOT/'firmware/custom/virtual-ink-counter-v8';folder.mkdir(exist_ok=True)
    output=folder/NAME;assert not output.exists(),'Refusing to overwrite an existing EFU'
    with zipfile.ZipFile(output,'x',compression=zipfile.ZIP_DEFLATED,compresslevel=9) as z:
        z.comment=comment;z.writestr(info,result)
    with zipfile.ZipFile(output) as z:assert z.testzip() is None and z.read('FWE642TL.rcx')==result
    manifest=dict(status='V8 CANDIDATE: V7 + virtual-cartridge ink-use status fix; physical boot unverified',
        file=NAME,bytes=output.stat().st_size,sha256=sha(output.read_bytes()),parent_efu_sha256=PARENT_SHA,
        rcx_sha256=sha(result),controller_before_sha256=V7_CONTROLLER_SHA,controller_after_sha256=sha(desired),
        patch=layout,native_status_check='docs/virtual-ink-counter-fix.json',
        native_crom=native,crom_repair=codec,all_14_records_verified=True,zip_readback_identical=True,
        allowed_rcx_ranges=allowed,library_main_boot_byte_identical_to_v7=True,
        cause='Virtual identities never change, so the stock new-pack reset of cumulative ink use (0x47C58B5C -> 0x47C5BB68) never runs; the counters reach near-end (0x83) and then ink end.',
        limits=['Only status evaluator 0x47C61B24 ignores the cumulative counters. Counters still accumulate in NVRAM; virtual chip synchronisation is unchanged.',
            'Other consumers of the counters (e.g. 0x47C5A488 level cache, 0x47D10C88) are unchanged; their user-visible effect is unverified.',
            'Physical ink-end sensor flag path (0x47D5EE1C set by 0x47C62038) is retained; its sensor identity is inferred from debounced sampling, not a hardware trace.',
            'Ink level is no longer estimated from usage. Watch the packs physically; empty packs rely on the sensor path only.',
            'Synthetic capacity thresholds and mocked helpers in the native check; no complete boot or printer test.',
            'Independent rcx_correct cross-check unavailable in this environment.'])
    (folder/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
    (folder/'SHA256SUMS').write_text(f"{manifest['sha256']}  {NAME}\n")
    print('Built',output,'SHA256',manifest['sha256'],flush=True)

if __name__=='__main__':main()
