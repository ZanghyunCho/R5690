"""Package an offline-validated virtual CSIC candidate, retaining CLUT v1.

Never executes an updater or accesses a printer. Physical boot is unverified.
"""
from pathlib import Path
import copy,hashlib,json,struct,subprocess,sys,zipfile
from stock_crom_codec import parse,expand,repair
from validate_crom_native import validate
from virtual_csic_patch import patch
ROOT=Path(__file__).resolve().parents[1]
NAME='FWE642TL_GR_VIRTUAL_CSIC_MB_T3400_CLUT_CANDIDATE_v5.EFU'
sha=lambda b:hashlib.sha256(b).hexdigest()

def verify(data):
    p=data.index(b'\x0c')+1;blocks=[]
    assert p==344
    while p<len(data):
        start=p;magic=data[p:p+9];assert magic in (b'EPSON IPL',b'EPSONMIPL')
        hh=hashlib.sha1(data[p:p+14]).digest();p+=4096;records=[]
        for i in range(3):
            r=start+16+36*i;n=struct.unpack_from('<I',data,r+12)[0]
            if not n:continue
            assert p+n<=len(data);payload=memoryview(data)[p:p+n]
            assert sum(payload)&65535==struct.unpack_from('<H',data,r+2)[0]
            h=data[r+16:r+36]
            if any(h):
                d=hashlib.sha1(payload);d.update(hh);assert d.digest()==h
            records.append(dict(record=r,start=p,bytes=n));p+=n
        blocks.append(dict(start=start,end=p,magic=magic.decode(),variant=data[start+11:start+13].decode(),records=records))
    assert p==len(data) and len(blocks)==8 and sum(len(b['records']) for b in blocks)==14
    return blocks

def main():
    parent=ROOT/'firmware/custom/t3400-colour-lut-v1/FWE642TL_GR_VIRTUAL_INK_MB_T3400_CLUT_PROTOTYPE_v1.EFU'
    assert sha(parent.read_bytes())=='42e3630b8be35d8cd6dc469bff4c84528b27e7256b069cdb2e0e003fd5b2a62d'
    with zipfile.ZipFile(parent) as z:
        assert z.namelist()==['FWE642TL.rcx'];original=z.read('FWE642TL.rcx')
        info=copy.copy(z.getinfo('FWE642TL.rcx'));comment=z.comment
    stock=(ROOT/'artifacts/maintenance-virtualization/decoded/119075160.crom.0.bin').read_bytes()
    desired,layout=patch(stock)
    validation=json.loads((ROOT/'artifacts/virtual-csic-boot-fix/REPORT.json').read_text())
    assert validation['controller_sha256']==sha(desired)
    startup=json.loads((ROOT/'artifacts/virtual-csic-boot-fix/STARTUP.json').read_text())
    assert startup['controller_sha256']==sha(desired)
    assert startup['csic_hardware_initialization_restored'] and startup['no_runtime_state_in_ff_padding']
    interfaces=json.loads((ROOT/'artifacts/virtual-csic-boot-fix/INTERFACES.json').read_text())
    assert interfaces['general_errors_not_suppressed']
    assert interfaces['controller_sha256']==sha(desired)
    blocks=verify(original);start,end=0x6d4f158,0x7d4f158;rom=original[start:end]
    seg=parse(rom,0x440004);encoded,codec=repair(rom[0x440004:seg['end']],desired)
    # Preserve all trailing CROM modules, all memory addresses and boot code.
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
    assert all(native['segments'][i]['sha256']==sha(expand(parse(rom,p)['tokens'],parse(rom,p)['literals']))
        for i,p in [(3,seg['end']),(4,parse(rom,seg['end'])['end'])])
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
    work=ROOT/'artifacts/virtual-csic-boot-fix';rcx=work/'virtual-csic-v5.rcx';rcx.write_bytes(result)
    ref=Path('/workspace/development-tools/epson-reversing')
    assert subprocess.check_output(['git','-C',str(ref),'rev-parse','HEAD'],text=True).strip()=='2ed0a54a4ba98c9a860bf2e0efbfc4d53c0e4a16'
    subprocess.run(['git','-C',str(ref),'diff','--exit-code','HEAD','--','rcx_correct','rcx.py'],check=True)
    wrapper="""import runpy,sys
from pathlib import Path
script,infile,outfile,*offsets=sys.argv[1:]
sys.path.insert(0,str(Path(script).parent));sys.argv=[script,infile,outfile]
n=runpy.run_path(script)
for offset in offsets:n['correct_ipl'](int(offset))
n['fp'].flush();n['fp'].close()
"""
    checked=work/'independent-v5.rcx'
    subprocess.run([sys.executable,'-c',wrapper,str(ref/'rcx_correct'),str(rcx),str(checked),
        *[str(b['start']) for b in blocks if b['magic']=='EPSON IPL']],check=True)
    assert checked.read_bytes()==result
    folder=ROOT/'firmware/custom/virtual-csic-t3400-candidate-v5';folder.mkdir(exist_ok=True)
    output=folder/NAME;assert not output.exists(),'Refusing to overwrite an existing EFU'
    with zipfile.ZipFile(output,'x',compression=zipfile.ZIP_DEFLATED,compresslevel=9) as z:
        z.comment=comment;z.writestr(info,result)
    with zipfile.ZipFile(output) as z:assert z.testzip() is None and z.read('FWE642TL.rcx')==result
    manifest=dict(status='V5 OFFLINE STARTUP-REGRESSION CANDIDATE; physical boot unverified; exact V4 shutdown cause unconfirmed',
        file=NAME,bytes=output.stat().st_size,sha256=sha(output.read_bytes()),
        parent_efu_sha256=sha(parent.read_bytes()),controller_sha256=sha(desired),rcx_sha256=sha(result),
        layout=layout,native_crom=native,crom_repair=codec,all_14_records_verified=True,
        independent_6_IPL_correction_identical=True,zip_readback_identical=True,
        allowed_rcx_ranges=allowed,existing_T3400_CLUT_library_byte_identical=True,
        all_IC3_IC5_and_GH_records_byte_identical_to_parent=True,
        validation=validation,interfaces=interfaces,startup_regressions=startup,
        limits=['V4 was withdrawn after a physical boot-time shutdown; the exact cause is still unconfirmed.',
            'Known setter return and eager-property-read defects are corrected, but physical boot success has not been demonstrated.',
            'Synthetic runtime properties, GPIO APIs and OS event/publication mocks; no complete boot.',
            'Physical printer update acceptance, no-chip operation, automatic supply and print output have not been tested.',
            'No IES/leak sensor, pump branch, Initial Charge flag or NVRAM history erasure patch.',
            'Original hardware Huffman tables retained; hardware peripheral decoding untested.',
            'Only existing common-mode T3400 CLUTs retained; no new halftone, total-ink, waveform or resolution transplant.'])
    (folder/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
    print('Built',output,'SHA256',manifest['sha256'],flush=True)

if __name__=='__main__':main()
