"""Package V7: V6 + donor T3400 Enhanced Matte SML 213 bound to R5691 SML ID 214.

Data-only change to the GR library CROM (slot 0x40000, segment 1). The
controller, main program, boot code, dither resources and all other records
are byte-identical to V6. Never executes an updater or accesses a printer.
Physical boot and print output are unverified.

Requires the offline staging output of stage_matte_to_plain_sml.py:
artifacts/t3400-lut/matte-to-plain/staged-library.bin.offline-only
"""
from pathlib import Path
import copy,hashlib,json,struct,zipfile
from stock_crom_codec import parse,expand,repair
from validate_crom_native import validate
from build_virtual_csic_relocated_efu import verify
from colour_blob_codec import Codec
ROOT=Path(__file__).resolve().parents[1]
NAME='FWE642TL_GR_VIRTUAL_CSIC_MB_T3400_CLUT_MATTE_SML_CANDIDATE_v7.EFU'
PARENT_SHA='290efca81c5a061c819a1bea03c11a676bd5eee1847e823393ae850ade008e26'
STAGED_SHA='b9e4308e3a25c1adefe9e4b37e9992e084c47151618996d101178c09ecc3328f'
DONOR_SML_SHA='ae4dd99102cf032358ee35b0cb79f79ac0fff71fc7393d4cd3e408f8ee1fa964'
LIB_BASE=0x4808f000;TABLE=0x4821505c
sha=lambda b:hashlib.sha256(b).hexdigest()

def resources(codec,lib):
    """Decode every library resource with the original ARM decoder."""
    out={}
    for i in range(87):
        key,ptr=struct.unpack_from('<II',lib,TABLE-LIB_BASE+8*i);off=ptr-LIB_BASE
        assert lib[off:off+7]==bytes.fromhex('7acf865c7d903c')
        n,size=struct.unpack_from('<II',lib,off+8)
        out[key]=sha(codec.decode(lib[off+12:off+12+n],size))
    return out

def main():
    parent=ROOT/'firmware/custom/virtual-csic-t3400-candidate-v6/FWE642TL_GR_VIRTUAL_CSIC_MB_T3400_CLUT_CANDIDATE_v6.EFU'
    assert sha(parent.read_bytes())==PARENT_SHA,'V6 parent missing or not pulled from LFS'
    with zipfile.ZipFile(parent) as z:
        assert z.namelist()==['FWE642TL.rcx'];original=z.read('FWE642TL.rcx')
        info=copy.copy(z.getinfo('FWE642TL.rcx'));comment=z.comment
    blocks=verify(original);start,end=0x6d4f158,0x7d4f158;rom=original[start:end]
    assert rom[0x40000:0x40004]==b'CROM'
    seg0=parse(rom,0x40004);seg1=parse(rom,seg0['end'])
    library=expand(seg1['tokens'],seg1['literals'])
    staged=(ROOT/'artifacts/t3400-lut/matte-to-plain/staged-library.bin.offline-only').read_bytes()
    assert sha(staged)==STAGED_SHA and len(staged)==len(library)
    diff=[i for i in range(len(library)) if library[i]!=staged[i]]
    # Only resource 214's table pointer and the bytes inside resource 13's unused tail.
    ptr_field=next(TABLE-LIB_BASE+8*i+4 for i in range(87) if struct.unpack_from('<I',library,TABLE-LIB_BASE+8*i)[0]==214)
    tail=[i for i in diff if not ptr_field<=i<ptr_field+4]
    assert all(ptr_field<=i<ptr_field+4 for i in diff if i<min(tail))
    assert max(tail)-min(tail)<658

    codec=Codec()
    old_res,new_res=resources(codec,library),resources(codec,staged)
    changed=sorted(k for k in old_res if old_res[k]!=new_res[k])
    assert changed==[214] and new_res[214]==DONOR_SML_SHA

    encoded,crom=repair(rom[seg0['end']:seg1['end']],staged)
    pos=seg0['end']+len(encoded)
    assert pos<=0x440000 and rom[seg1['end']:0x440000]==b'\xff'*(0x440000-seg1['end'])
    newrom=rom[:seg0['end']]+encoded+b'\xff'*(0x440000-pos)+rom[0x440000:]
    assert len(newrom)==len(rom)
    native=validate(rom,newrom)
    assert native['segments'][1]['sha256']==sha(staged)
    assert all(native['segments'][i]['sha256']==native_ref for i,native_ref in
        [(0,sha(expand(seg0['tokens'],seg0['literals'])))]+
        [(2+j,sha(expand(*(lambda s:(s['tokens'],s['literals']))(parse(rom,p))))) for j,p in enumerate(
            [0x440004,parse(rom,0x440004)['end'],parse(rom,parse(rom,0x440004)['end'])['end']])])

    result=bytearray(original);result[start:end]=newrom
    owner=next(b for b in blocks if any(r['start']==start for r in b['records']));assert owner['variant']=='GR'
    record=next(r['record'] for r in owner['records'] if r['start']==start)
    struct.pack_into('<H',result,record+2,sum(newrom)&65535)
    h=hashlib.sha1(newrom);h.update(hashlib.sha1(result[owner['start']:owner['start']+14]).digest())
    result[record+16:record+36]=h.digest();result=bytes(result);verify(result)
    allowed=sorted([(record+2,record+4),(record+16,record+36),(start+seg0['end'],start+0x440000)])
    cursor=0
    for a,b in allowed:assert original[cursor:a]==result[cursor:a];cursor=b
    assert original[cursor:]==result[cursor:]

    folder=ROOT/'firmware/custom/matte-sml-candidate-v7';folder.mkdir(exist_ok=True)
    output=folder/NAME;assert not output.exists(),'Refusing to overwrite an existing EFU'
    with zipfile.ZipFile(output,'x',compression=zipfile.ZIP_DEFLATED,compresslevel=9) as z:
        z.comment=comment;z.writestr(info,result)
    with zipfile.ZipFile(output) as z:assert z.testzip() is None and z.read('FWE642TL.rcx')==result
    manifest=dict(status='V7 CANDIDATE: V6 + donor Enhanced Matte SML 213 as R5691 SML 214; physical boot and print unverified',
        file=NAME,bytes=output.stat().st_size,sha256=sha(output.read_bytes()),
        parent_efu_sha256=PARENT_SHA,rcx_sha256=sha(result),
        library_before_sha256=sha(library),library_after_sha256=sha(staged),
        changed_library_bytes=len(diff),table_pointer_field=hex(LIB_BASE+ptr_field),
        inserted_range=[hex(LIB_BASE+min(tail)),hex(LIB_BASE+max(tail)+1)],
        resources_decoded_with_original_arm=87,resources_changed=changed,
        resource_214_decoded_sha256=new_res[214],donor_sml_213_sha256=DONOR_SML_SHA,
        affected_catalogue_rows='PLAIN 1200x1200 OUT_BIT 2: CMM 14 (BASE), 414 (E-RGB), 574 (E-BIZ-COLOR)',
        native_crom=native,crom_repair=crom,all_14_records_verified=True,zip_readback_identical=True,
        allowed_rcx_ranges=allowed,controller_main_boot_dither_byte_identical_to_v6=True,
        donor_verified_against='FWF649TL_LN22Q1.efu (2026-01-21): SML 213 and dither 702/662/682 hashes equal earlier donor',
        limits=['Only the dot-size conversion (SML) changes. Stock R5691 dither 652 is retained; donor dither 702/662/682 is not installed.',
            'Donor SML was designed together with donor 12-bit 1024x1024 dither; combination with stock dither is untested on paper.',
            'Same print head reported by user; drive waveform equality not verified.',
            'Only plain paper 1200x1200 modes use SML 214. Other qualities/media are unchanged. Driver path selection unverified.',
            'Independent rcx_correct cross-check was unavailable in this environment; in-tool IPL checksum/SHA-1 verification passed.',
            'Physical update acceptance, boot, ink duty and print quality have not been tested.'])
    (folder/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
    (folder/'SHA256SUMS').write_text(f"{manifest['sha256']}  {NAME}\n")
    print('Built',output,'SHA256',manifest['sha256'],flush=True)

if __name__=='__main__':main()
