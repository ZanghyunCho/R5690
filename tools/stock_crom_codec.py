"""Repair a stock CROM using its EXACT original DHT and original tokens.
Only backreferences invalidated by edited bytes become literal runs. This is
not a new Huffman-tree generator. Reject undefined symbols and copy overflow.
"""
import struct

def marker(tag,payload):return struct.pack('>HH',tag,len(payload)+2)+payload

def parse(data,start=0):
 assert data[start:start+2]==b'\xff\xd8'
 end=start+struct.unpack_from('>I',data,start+2)[0];assert start<end<=len(data)
 pos=start+6
 def take(tag):
  nonlocal pos
  t,n=struct.unpack_from('>HH',data,pos);assert t==tag and n>=2 and pos+2+n<=end
  b=data[pos+4:pos+2+n];pos+=2+n;return b
 dht=take(0xffc4);info=take(0xffb1)
 assert info[0]==3 and info[10:13]==bytes.fromhex('001020')
 size,count=struct.unpack_from('>II',info,1)
 coded=data[pos:pos+size];pos+=size
 lit_size=struct.unpack('>I',take(0xffb2))[0]
 literals=data[pos:end];assert len(literals)==lit_size
 codes=[];lookups=[];p=0
 for channel in range(3):
  assert dht[p]==0xf0+channel
  counts=dht[p+1:p+17];p+=17;code=0;table=[None]*65536;enc={}
  for width,n in enumerate(counts,1):
   for _ in range(n):
    assert code<(1<<width)-1,'Reserved/oversubscribed Huffman code'
    symbol=dht[p];p+=1;assert symbol not in enc
    enc[symbol]=(code,width)
    table[code<<(16-width):(code+1)<<(16-width)]=[(symbol,width)]*(1<<(16-width));code+=1
   code<<=1
  codes.append(enc);lookups.append(table)
 assert p==len(dht)
 buffer=bits=offset=0;tokens=[]
 for _ in range(count):
  triple=[]
  for table in lookups:
   while bits<16:
    assert offset<len(coded)
    buffer=((buffer<<8)|coded[offset])&0xffffff;offset+=1;bits+=8
   pair=table[(buffer>>(bits-16))&65535];assert pair is not None
   symbol,width=pair;bits-=width;triple.append(symbol)
  tokens.append(tuple(triple))
 return dict(end=end,dht=dht,info=info,codes=codes,tokens=tokens,literals=literals)

def expand(tokens,literals):
 output=bytearray();lp=0
 for control,low,high in tokens:
  distance=low|high<<8
  if distance:
   assert control<=253 and distance<=len(output)
   for _ in range(control+2):output.append(output[-distance])
  elif control!=255:
   n=control+1;assert lp+n<=len(literals)
   output+=literals[lp:lp+n];lp+=n
 assert lp==len(literals)
 return bytes(output)

def repair(original,desired):
 old=parse(original);source=expand(old['tokens'],old['literals']);assert len(source)==len(desired)
 tokens=[];literals=bytearray();position=0;old_lp=0;replaced=0
 allowed=sorted((v+1 for v in old['codes'][0] if v<255),reverse=True)
 assert 1 in allowed and 0 in old['codes'][1] and 0 in old['codes'][2]
 def emit_literal(chunk):
  # Dynamic programming avoids assuming every literal-run length exists.
  ways={0:[]}
  for n in range(1,len(chunk)+1):
   for length in allowed:
    if n-length in ways:ways[n]=ways[n-length]+[length];break
  assert len(chunk) in ways
  p=0
  for length in ways[len(chunk)]:
   tokens.append((length-1,0,0));literals.extend(chunk[p:p+length]);p+=length
 for triple in old['tokens']:
  control,lo,hi=triple;distance=lo|hi<<8
  if distance:
   assert control<=253;n=control+2
   matches=all(desired[position+i]==desired[position+i-distance] for i in range(n))
   if matches:tokens.append(triple)
   else:emit_literal(desired[position:position+n]);replaced+=1
   position+=n
  elif control==255:tokens.append(triple)
  else:
   n=control+1;tokens.append(triple);literals.extend(desired[position:position+n]);position+=n;old_lp+=n
 assert position==len(desired) and old_lp==len(old['literals'])
 assert expand(tokens,literals)==desired
 pad=(-len(tokens))%16;coded=bytearray();buffer=bits=0
 for triple in tokens+[(0,0,0)]*pad:
  for channel,symbol in enumerate(triple):
   code,width=old['codes'][channel][symbol]
   buffer=buffer<<width|code;bits+=width
   while bits>=8:
    bits-=8;coded.append((buffer>>bits)&255)
   buffer&=(1<<bits)-1
 if bits:coded.append(buffer<<(8-bits))
 coded.extend(bytes((-len(coded))%16+16))
 dht=marker(0xffc4,old['dht'])
 info=b'\3'+struct.pack('>II',len(coded),len(tokens))+bytes([pad])+bytes.fromhex('001020')
 info+=bytes((-(6+len(dht)+4+len(info)))%4)
 body=dht+marker(0xffb1,info)+coded+marker(0xffb2,struct.pack('>I',len(literals)))+literals
 result=b'\xff\xd8'+struct.pack('>I',6+len(body))+body
 new=parse(result);assert new['end']==len(result) and new['dht']==old['dht']
 assert expand(new['tokens'],new['literals'])==desired
 return result,dict(stock_dht_byte_identical=True,original_tokens=len(old['tokens']),new_tokens=len(tokens),
                    invalidated_copies_replaced=replaced,original_bytes=len(original),new_bytes=len(result))
