"""Read-only comparison of halftone resources and encoded ink-duty limits."""
from pathlib import Path
import hashlib
import json
import struct
import csv
import io

ROOT=Path(__file__).resolve().parents[1]
FOLDER=ROOT/'artifacts/t3400-lut/colour-blobs'

def main():
    inventory=json.loads((FOLDER/'inventory.json').read_text())
    resources={}
    tables={}
    for model, info in inventory.items():
        raw=(ROOT/info['source']).read_bytes()
        assert hashlib.sha256(raw).hexdigest()==info['source_sha256']
        blobs={r['id']:(FOLDER/model/r['file']).read_bytes() for r in info['blobs']}
        resources[model]=dict(blobs)
        if model=='t3400':
            for i in range(180):
                key,start,end=struct.unpack_from('<III',raw,0x356e0+i*12)
                if key not in blobs:
                    resources[model][key]=raw[start-0x44294310:end-0x44294310]
        rows=list(csv.reader(io.StringIO(blobs[0].decode('ascii')),delimiter='\t'))
        start=next(i for i,row in enumerate(rows) if row and row[0]=='CMM-ID')
        tables[model]=[dict(zip(rows[start],row)) for row in rows[start+1:]
            if row and row[0].isdigit() and len(row)>=len(rows[start])]
    def describe(model,key):
        data=resources[model].get(key)
        if data is None:return dict(id=key,available=False)
        result=dict(id=key,bytes=len(data),sha256=hashlib.sha256(data).hexdigest(),header_hex=data[:48].hex())
        if data[4:8]==bytes.fromhex('fcf92eb8') and len(data)==24:
            ids=struct.unpack_from('<4H',data,16)
            result['referenced_resource_ids']=list(ids)
            result['referenced_resources']=[describe(model,i) for i in dict.fromkeys(ids)]
        return result
    comparisons=[]
    for recipient, donor, resolution in [(11,30,[600,600]),(13,31,[600,1200]),(14,32,[1200,1200])]:
        pair=dict(resolution=resolution)
        for model,key in [('r5691',recipient),('t3400',donor)]:
            blob=resources[model][key]
            tags={blob[24+8*i:28+8*i]:struct.unpack_from('<I',blob,28+8*i)[0]
                for i in range(struct.unpack_from('<I',blob,20)[0])}
            off=tags[b'inkd'];version,count=blob[off+4:off+6]
            codes=list(blob[off+6:off+6+count])
            values=struct.unpack_from('<'+'H'*count,blob,off+6+count)
            limits={str(c):dict(raw=v,normalized_percent=v*100/255) for c,v in zip(codes,values)}
            rows=[r for r in tables[model] if r['CMM-ID']==str(key)]
            fields=['Halftone','HT-ID','OUT_BIT','Micro','mw_type','MW_Mode','INK-ID','cSMB-ID','mSMB-ID','ubec_dither','ubec_extbl','ubec_vinfo','ubec_tmp','C_Duty','M_Duty','Y_Duty','K_Duty','Total_Duty']
            used=sorted({int(row[f]) for row in rows for f in ['INK-ID','cSMB-ID','mSMB-ID','ubec_dither','ubec_vinfo'] if row.get(f,'-1')!='-1'})
            pair[model]=dict(cmm_id=key,rows=[{f:r[f] for f in fields if f in r} for r in rows],
                inkd_version=version,inkd_values_by_channel_code=limits,resources=[describe(model,i) for i in used])
        comparisons.append(pair)
    report=dict(status='Static comparison; no firmware modified and no physical ink volume measured',
        normalization='raw * 100 / 255; code 20 aligns with R5691 catalogue Total_Duty in the three compared modes',
        cautions=['The precise physical channel mapping is not independently verified.',
            'Some per-channel catalogue duty values differ from the encoded inkd fields; do not treat catalogue text as exact final settings.',
            'DB and HYBRID rows coexist in the donor catalogue. Which is selected for a particular print is unresolved.',
            'The 2-bit OUT_BIT field does not establish droplet volume or the physical meaning of each output state.',
            'Limits and thresholds do not determine actual pL, mL, or consumption without waveform/drop-volume and raster coverage information.'],
        comparisons=comparisons)
    output=ROOT/'docs/halftone-ink-comparison.json'
    output.write_text(json.dumps(report,indent=2)+'\n')
    for pair in comparisons:
        print(pair['resolution'],[(m,sorted({r['Halftone'] for r in pair[m]['rows']}),round(pair[m]['inkd_values_by_channel_code']['20']['normalized_percent'],2)) for m in ['r5691','t3400']])

if __name__=='__main__':main()
