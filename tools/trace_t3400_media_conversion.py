"""Execute donor media-code helpers; preserve distinct input namespaces.

This probes distinct job-setting fields and catalogue selection independently.
The +0x48 conversion is NOT established as a CMM media conversion.
"""
from pathlib import Path
import hashlib,json,struct
from unicorn import Uc,UC_ARCH_ARM,UC_MODE_ARM
from unicorn.arm_const import *
from colour_blob_codec import Codec
ROOT=Path(__file__).resolve().parents[1]
BASE=0x43696000

def main():
    path=ROOT/'artifacts/t3400-lut/decoded/71459089.crom.0.bin';data=path.read_bytes()
    # Base is independently constrained by absolute jump-table targets landing
    # exactly on their MOV/BX return stubs, not just guessed from a nearby image.
    table=0x23b12c
    for key,target in [(6,0x438d140c),(178,0x438d16a4)]:
        assert struct.unpack_from('<I',data,table+key*4)[0]==target
        assert struct.unpack_from('<I',data,target-BASE+4)[0]==0xe12fff1e
    assert struct.unpack_from('<I',data,0x23b40c)[0]==0xe3a00066
    # Caller consumes a virtual method and stores conversion result at +0xE.
    caller=data[0x438c69d8-BASE:0x438c69f4-BASE]
    assert struct.unpack_from('<I',caller,4)[0]==0xe5901048
    assert struct.unpack_from('<I',caller,24)[0]==0xe5c1000e
    cpu=Uc(UC_ARCH_ARM,UC_MODE_ARM);cpu.mem_map(BASE,(len(data)+4095)//4096*4096);cpu.mem_write(BASE,data)
    cpu.mem_map(0x20000000,0x20000)
    def run(address,value):
        cpu.reg_write(UC_ARM_REG_R0,value);cpu.reg_write(UC_ARM_REG_SP,0x2001f000);cpu.reg_write(UC_ARM_REG_LR,0x20000100)
        cpu.emu_start(address,0x20000100,count=1000)
        assert cpu.reg_read(UC_ARM_REG_PC)==0x20000100
        return cpu.reg_read(UC_ARM_REG_R0)
    # Concrete vtable 0x441610FC: +0x40 reads object+0x7C;
    # +0x48 reads object+0x80. Never merge these input namespaces.
    assert struct.unpack_from('<I',data,0x441610fc-BASE+0x40)[0]==0x436f013c
    assert struct.unpack_from('<I',data,0x441610fc-BASE+0x48)[0]==0x436f014c
    field_cases=[]
    for key in [0,8,36,178]:
        cpu.reg_write(UC_ARM_REG_R1,0x20001000)
        run(0x43725694,key)
        field_cases.append(dict(config_key=key,object_field_7c=struct.unpack('<I',cpu.mem_read(0x20001000,4))[0]))
    assert field_cases[1]['object_field_7c']==13
    def word(address):
        return struct.unpack_from('<I',data,address-BASE)[0]
    def cstring(address):
        return data[address-BASE:].split(b'\0',1)[0].decode('utf-8')
    # Independent name and IPP media tables use the SAME input code 215.
    assert [word(0x44018d7c+i*4) for i in range(3)]==[215,0x44019efc,0x1037]
    assert cstring(word(0x44019efc+4))=='Enhanced Matte Paper'
    assert word(0x4405b69c)==215
    assert cstring(word(0x4405b6a0))=='com.epson-matte-enhanced'
    association=dict(input_code=215,name_record='0x44018D7C',name_pointer_table='0x44019EFC',
        english_name=cstring(word(0x44019efc+4)),ipp_record='0x4405B69C',
        ipp_name=cstring(word(0x4405b6a0)),cmm_paper_type=102)
    # Actual CMM PaperType producer: consumes raster object u16 +0x44.
    paper_cases=[]
    for key in [144,215,178,6,205,65535]:
        cpu.mem_write(0x20002044,struct.pack('<H',key))
        paper_cases.append(dict(input_code=key,paper_type=run(0x43835cf0,0x20002000)))
    assert [r['paper_type'] for r in paper_cases[:2]]==[102,102]
    cases=[dict(input=i,result=run(0x438d1118,i)) for i in [0,6,15,36,178,183,184]]
    assert next(x['result'] for x in cases if x['input']==6)==102
    assert run(0x438d0e70,36)==178
    # Independently run the recipient catalogue selector on the donor catalogue
    # using its large-format media enum. No driver/job routing is inferred.
    inv=json.loads((ROOT/'artifacts/t3400-lut/colour-blobs/inventory.json').read_text())
    item=next(r for r in inv['t3400']['blobs'] if r['id']==0)
    cat=(ROOT/'artifacts/t3400-lut/colour-blobs/t3400'/item['file']).read_bytes()
    c=Codec();c.cpu.mem_write(0x22000000,cat)
    c.cpu.mem_write(0x20030000,struct.pack('<8I',0,102,4,3,1,1200,1200,2))
    c.cpu.mem_write(0x20031000,bytes(256))
    result=c.call(0x48abe280,[0x20031000,0x20030000,0x22000000])
    words=struct.unpack('<64i',c.cpu.mem_read(0x20031000,256))
    assert result==0 and (words[0],words[3],words[14])==(14,213,702),(result,words)
    report=dict(status='ENHANCED MATTE IDENTITY CONFIRMED IN NAME/IPP TABLES; NATIVE CMM CONVERSION AND SELECTION PASSED',
        source=str(path.relative_to(ROOT)),source_sha256=hashlib.sha256(data).hexdigest(),main_base=hex(BASE),
        unclassified_setting_conversion='0x438D1118',
        correction='Earlier CMM-media interpretation withdrawn: no dataflow links this result to the CMM PaperType field.',
        enhanced_matte_association=association,
        concrete_vtable='0x441610FC',getter_40_field='0x7C',getter_48_field='0x80',
        config_to_field_7c=dict(function='0x43725694',cases=field_cases),
        actual_cmm_trace=dict(debug_function='0x4398591C',paper_type_field='u16 +0x8',cmm_type_field='u16 +0xA',
            copy_function='0x43836254',copy_source_offset='0xD8',copy_length='0x9C',producer='0x43835CF0',producer_input='raster object u16 +0x44',
            producer_table='0x43D4DFDC',producer_cases=paper_cases,
            debug_callers=['0x43836640','0x43836E98']),caller='0x438C69E8',caller_input_virtual_method_offset='0x48',caller_output_byte_offset='0xE',
        conversion_cases=cases,other_media_helper=dict(function='0x438D0E70',input=36,output=178),
        donor_catalogue_selection=dict(function='recipient 0x48ABE280',media_enum=102,media_label='L_APMP_MK',
            resolution=[1200,1200],doc_type='BASE',halftone='DB',output_bits=2,cmm_id=words[0],sml_id=words[3],dither_id=words[14]),
        limits=['Numeric codes in UI labels, the 0x438D0E70 helper and the +0x48 setting conversion are different namespaces.',
            'Enhanced Matte code 215 is tied to CMM PaperType 102 by table identity and native execution, not a live captured print job.',
            'Large dither storage/loading and complete raster processing remain unverified.',
            'No EFU or printer access; native catalogue selection uses synthetic inputs.'])
    (ROOT/'docs/t3400-native-media-conversion.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(report,indent=2))

if __name__=='__main__':main()
