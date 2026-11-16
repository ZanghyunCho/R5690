"""Execute original R5691 catalogue selection with explicit synthetic settings.

Candidate resource IDs are deliberately uninstalled. This proves selection
wiring, not resource loading, complete printing or an installable firmware.
"""
from pathlib import Path
import json
import struct
from colour_blob_codec import Codec
from unicorn.arm_const import UC_ARM_REG_C1_C0_2, UC_ARM_REG_FPEXC

ROOT=Path(__file__).resolve().parents[1]

def main():
    original=(ROOT/'artifacts/t3400-lut/colour-blobs/r5691/00186318.bin').read_bytes()
    lines=original.decode('ascii').splitlines(keepends=True)
    header=next(line.rstrip('\r\n').split('\t') for line in lines if line.startswith('CMM-ID\t'))
    indices={name:header.index(name) for name in ['CMM-ID','DocType','subType','cSMB-ID','mSMB-ID','ubec_dither']}
    pairs={11:(3001,3011),13:(3002,3012),14:(3003,3013)}
    edited=[]
    for line in lines:
        row=line.rstrip('\r\n').split('\t')
        if row[0] in ['11','13','14'] and row[indices['DocType']]=='BASE' and row[indices['subType']]=='0':
            cmm=int(row[0]);sml,dither=pairs[cmm]
            row[indices['cSMB-ID']]=str(sml);row[indices['mSMB-ID']]=str(sml)
            row[indices['ubec_dither']]=str(dither)
            line='\t'.join(row)+'\r\n'
        edited.append(line)
    candidate=''.join(edited).encode('ascii')
    codec=Codec();cpu=codec.cpu
    cpu.reg_write(UC_ARM_REG_C1_C0_2,0xf00000);cpu.reg_write(UC_ARM_REG_FPEXC,0x40000000)
    report=[]
    for label,blob in [('stock',original),('candidate',candidate)]:
        cpu.mem_write(0x22000000,bytes(0x20000));cpu.mem_write(0x22000000,blob)
        for h,v,cmm in [(600,600,11),(600,1200,13),(1200,1200,14)]:
            for doc in [4,6]:
                settings=[0,0,doc,3,1,h,v,2]
                cpu.mem_write(0x20030000,struct.pack('<8I',*settings));cpu.mem_write(0x20031000,bytes(256))
                ret=codec.call(0x48abe280,[0x20031000,0x20030000,0x22000000])
                assert ret==0
                words=struct.unpack('<64i',cpu.mem_read(0x20031000,256))
                expected_sml,expected_dither=pairs[cmm] if label=='candidate' and doc==4 else ({11:211,13:220,14:214}[cmm],{11:650,13:651,14:652}[cmm])
                assert words[3]==expected_sml and words[14]==expected_dither
                report.append(dict(input=label,settings=settings,resolution=[h,v],doc_type='BASE' if doc==4 else 'E-RGB',
                    native_return=ret,selected_cmm=words[0],selected_sml=words[3],selected_dither=words[14]))
    out=ROOT/'artifacts/t3400-lut/halftone-transplant'
    (out/'candidate-catalogue.txt').write_bytes(candidate)
    (out/'native-mode-selection.json').write_text(json.dumps(dict(function='0x48ABE280',cases=report,
        limit='Synthetic mode inputs. IDs 3001..3013 are not installed; no firmware or printer write.'),indent=2)+'\n')
    print('12 native mode-selection checks passed: BASE retargets; E-RGB stays unchanged.')

if __name__=='__main__':main()
