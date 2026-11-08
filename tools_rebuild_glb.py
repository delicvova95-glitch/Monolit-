# Regenerates the paver GLB from the original export:
# - EMBOSS=True: вдавливает «МОНОЛИТ» в геометрию верхней грани
# - MARKING=True: плоская матовая маркировка «МОНОЛИТ» в albedo верхней грани
#   (меш делится на два примитива: верхняя грань получает свою текстуру)
# - replaces textures with procedural natural concrete (mid-grey, matte, porous)
# - writes static/models/concrete-block-natural.glb
import json, struct, io, math, copy
import numpy as np
from PIL import Image, ImageDraw

SRC = "concrete block 3d model.glb"
DST = "tomsk-monolit/static/models/concrete-block-natural.glb"
EMBOSS = False          # True — вдавить надпись «МОНОЛИТ» в верхнюю грань
MARKING = True          # True — плоская тёмно-серая маркировка на верхней грани
DEPTH = -0.024          # emboss depth in original coords (~4.4 mm after scaling)
TOP_Y = 0.302           # top-face threshold

raw = open(SRC, 'rb').read()
jlen, jtype = struct.unpack('<II', raw[12:20])
gltf = json.loads(raw[20:20+jlen])
off = 20 + jlen
blen, btype = struct.unpack('<II', raw[off:off+8])
binbuf = bytearray(raw[off+8:off+8+blen])

CT = {5120:'b',5121:'B',5122:'h',5123:'H',5125:'I',5126:'f'}
NC = {'SCALAR':1,'VEC2':2,'VEC3':3,'VEC4':4}

def read_acc(idx):
    a = gltf['accessors'][idx]
    bv = gltf['bufferViews'][a['bufferView']]
    start = bv.get('byteOffset',0) + a.get('byteOffset',0)
    n = a['count'] * NC[a['type']]
    dt = np.dtype('<'+CT[a['componentType']])
    return np.frombuffer(binbuf, dtype=dt, count=n, offset=start), a, bv, start

prim = gltf['meshes'][0]['primitives'][0]
pos, posA, posBV, posOff = read_acc(prim['attributes']['POSITION'])
pos = pos.reshape(-1,3).copy()
nrm, _, _, _ = read_acc(prim['attributes']['NORMAL'])
uv, _, _, _ = read_acc(prim['attributes']['TEXCOORD_0'])
idx, _, _, _ = read_acc(prim['indices'])
idx = idx.reshape(-1,3)

# ---------- letter mask ----------
def M():  return [(0,0),(0,1),(.25,1),(.5,.54),(.75,1),(1,1),(1,0),(.76,0),(.76,.55),(.5,.21),(.24,.55),(.24,0)]
def O():
    out=[(.07,0),(.93,0),(1,.07),(1,.93),(.93,1),(.07,1),(0,.93),(0,.07)]
    hole=[[(.28,.24),(.28,.76),(.72,.76),(.72,.24)]]
    return out,hole
def N():  return [(0,0),(.25,0),(.25,.40),(.75,.40),(.75,0),(1,0),(1,1),(.75,1),(.75,.60),(.25,.60),(.25,1),(0,1)]
def L():  return [(0,0),(.24,0),(.43,.76),(.41,1),(1,1),(1,0),(.76,0),(.76,.78),(.55,.78),(.35,.23),(.25,0)]
def I():  return [(0,0),(.25,0),(.25,.58),(.75,0),(1,0),(1,1),(.75,1),(.75,.42),(.25,1),(0,1)]
def T():  return [(0,1),(1,1),(1,.74),(.63,.74),(.63,0),(.37,0),(.37,.74),(0,.74)]

letters=['М','О','Н','О','Л','И','Т']
shapes=[]
for ch in letters:
    if ch=='О': shapes.append(O())
    else: shapes.append({'М':M,'Н':N,'Л':L,'И':I,'Т':T}[ch]())

LETTER_W=.82; SPACING=.16; SCALE=.125; CENTER_Z=0.0; ZS=1.9
total = len(letters)*LETTER_W + (len(letters)-1)*SPACING
x0 = -total/2*SCALE

def px(poly, li):
    return [(x0 + (li*(LETTER_W+SPACING)+px_)*SCALE, CENTER_Z + (0.5-py_)*SCALE*ZS) for px_,py_ in poly]

def inside(pt, poly):
    x,z = pt; c=False; j=len(poly)-1
    for i in range(len(poly)):
        xi,zi=poly[i]; xj,zj=poly[j]
        if ((zi>z)!=(zj>z)) and (x < (xj-xi)*(z-zi)/(zj-zi)+xi): c=not c
        j=i
    return c

def in_letters(x,z):
    for li,s in enumerate(shapes):
        if isinstance(s,tuple):
            outer,hole=s
            if inside((x,z),px(outer,li)) and not any(inside((x,z),px(h,li)) for h in hole): return True
        else:
            if inside((x,z),px(s,li)): return True
    return False

top = pos[:,1] > TOP_Y
mask = np.zeros(len(pos), dtype=bool)
if EMBOSS:
    ti = np.where(top)[0]
    for v in ti:
        if in_letters(pos[v,0], pos[v,2]): mask[v]=True
    print("embossed vertices:", int(mask.sum()))
    pos[mask,1] += DEPTH
else:
    print("emboss disabled, top face untouched")

# ---------- recompute normals ----------
nrm_new = np.zeros_like(pos, dtype=np.float64)
p0 = pos[idx[:,0]]; p1 = pos[idx[:,1]]; p2 = pos[idx[:,2]]
fn = np.cross(p1-p0, p2-p0)
for k in range(3):
    np.add.at(nrm_new, idx[:,k], fn)
ln = np.linalg.norm(nrm_new, axis=1)
ln[ln==0]=1
nrm_new = (nrm_new/ln[:,None]).astype(np.float32)

# ---------- write positions/normals back ----------
pos32 = pos.astype(np.float32)
pos_bytes = pos32.tobytes(); nrm_bytes = nrm_new.tobytes()
binbuf[posOff:posOff+len(pos_bytes)] = pos_bytes
nrmA = gltf['accessors'][prim['attributes']['NORMAL']]
nrmBV = gltf['bufferViews'][nrmA['bufferView']]
nrmOff = nrmBV.get('byteOffset',0) + nrmA.get('byteOffset',0)
binbuf[nrmOff:nrmOff+len(nrm_bytes)] = nrm_bytes
posA['min'] = [float(x) for x in pos32.min(axis=0)]
posA['max'] = [float(x) for x in pos32.max(axis=0)]
print("bounds min", posA['min'], "max", posA['max'])

# ---------- procedural concrete textures ----------
rng = np.random.default_rng(20261104)
S = 1024
yy,xx = np.mgrid[0:S,0:S]

def fbm(size, octaves, seed):
    r = np.random.default_rng(seed)
    acc = np.zeros((size,size)); amp=1.0; tot=0.0
    for o in range(octaves):
        g = 4*(2**o)
        coarse = r.random((g,g))
        img = np.array(Image.fromarray((coarse*255).astype(np.uint8)).resize((size,size), Image.BICUBIC), dtype=np.float64)/255.0
        acc += amp*img; tot += amp; amp*=0.55
    return acc/tot

low = fbm(S, 5, 11)          # low-frequency tone variation
fine = rng.random((S,S))     # grain
fine_blur = np.array(Image.fromarray((fine*255).astype(np.uint8)).resize((S//2,S//2)).resize((S,S)), dtype=np.float64)/255.0

# height field for normal map + slight albedo modulation
height = 0.62*low + 0.38*fine_blur
# pores: sparse dark pits
pore_mask = (rng.random((S,S)) > 0.999).astype(np.float64)
pores = np.array(Image.fromarray((pore_mask*255).astype(np.uint8)).resize((S,S), Image.BILINEAR), dtype=np.float64)/255.0
pores = np.clip(pores*1.6, 0, 1)
height -= pores*0.35

# albedo: mid grey cement, target mean ~ (150,152,147)
lum = 122 + (low-0.5)*20 + (fine_blur-0.5)*14 - pores*42
lum = np.clip(lum, 78, 175)
r = lum*1.000; g = lum*1.008; b = lum*0.975   # very slight warm-neutral cement tint
albedo = np.stack([r,g,b],axis=-1).astype(np.uint8)
img_albedo = Image.fromarray(albedo, 'RGB')

# ---------- flat factory marking "МОНОЛИТ" on the top face ----------
# Надпись рисуется настоящим жирным геометрическим шрифтом с кириллицей
# (по референсу заказчика) в растровую маску в мировых координатах верхней
# грани. UV-развёртка грани фрагментированная, поэтому маска переносится в
# текстуру потреугольно. Геометрия модели не изменяется.
FONT_CANDIDATES = [
    "C:/Windows/Fonts/ariblk.ttf",      # Arial Black
    "C:/Windows/Fonts/arialbd.ttf",     # Arial Bold
    "C:/Windows/Fonts/impact.ttf",
]
TEXT = "МОНОЛИТ"
TEXT_H = 0.150          # высота букв в мировых координатах (~30 мм)
TEXT_W_MAX = 0.86       # максимальная ширина надписи (~172 мм)
DARKEN = 0.52           # затемнение бетона внутри букв (краска, впитавшаяся в поверхность)

img_albedo_top = img_albedo
if MARKING:
    from PIL import ImageFont
    import os
    font_path = next(p for p in FONT_CANDIDATES if os.path.exists(p))
    font = ImageFont.truetype(font_path, 800)
    l, t_, r, b = font.getbbox(TEXT)
    tw, th = r - l, b - t_
    pad = 40
    txt_img = Image.new('L', (tw + 2*pad, th + 2*pad), 0)
    ImageDraw.Draw(txt_img).text((pad - l, pad - t_), TEXT, font=font, fill=255)
    textmask = np.asarray(txt_img)
    W_img, H_img = txt_img.size
    aspect = W_img / H_img
    h_w = TEXT_H
    w_w = h_w * aspect
    if w_w > TEXT_W_MAX:
        w_w = TEXT_W_MAX
        h_w = w_w / aspect
    x_min, x_max = -w_w/2, w_w/2
    z_min, z_max = -h_w/2, h_w/2

    uv2 = uv.reshape(-1, 2)
    top_tris_m = np.all(top[idx], axis=1)
    tris_m = idx[top_tris_m]
    cx = pos[tris_m, 0].mean(axis=1)
    cz = pos[tris_m, 2].mean(axis=1)
    fx = (cx - x_min) / (x_max - x_min) * (W_img - 1)
    fy = (cz - z_min) / (z_max - z_min) * (H_img - 1)
    inb = (fx >= 0) & (fx <= W_img - 1) & (fy >= 0) & (fy <= H_img - 1)
    xi = np.clip(np.round(fx).astype(np.int64), 0, W_img - 1)
    yi = np.clip(np.round(fy).astype(np.int64), 0, H_img - 1)
    sel = np.where(inb & (textmask[yi, xi] >= 128))[0]
    S2 = S * 2   # суперсэмплинг маски для гладких краёв букв
    letter_mask = Image.new('L', (S2, S2), 0)
    md = ImageDraw.Draw(letter_mask)
    uv_t = uv2[tris_m[sel]]
    for t in range(len(sel)):
        md.polygon([(float(uv_t[t, k, 0]) * S2, float(uv_t[t, k, 1]) * S2) for k in range(3)], fill=255)
    letter_mask = letter_mask.resize((S, S), Image.LANCZOS)
    dark_arr = (np.asarray(img_albedo).astype(np.float32) * DARKEN).astype(np.uint8)
    dark = Image.fromarray(dark_arr, 'RGB')   # тот же бетон, затемнённый — как впитавшаяся краска
    img_albedo_top = Image.composite(dark, img_albedo, letter_mask)
    print("marking triangles:", len(sel), "of", int(top_tris_m.sum()),
          "| text world: %.3f x %.3f" % (w_w, h_w), "| font:", font_path)

# roughness/metallic (glTF: G=roughness, B=metallic)
rough = np.clip(245 + (fine_blur-0.5)*14 + pores*10, 225, 255).astype(np.uint8)
mr = np.zeros((S,S,3), dtype=np.uint8); mr[...,1]=rough; mr[...,2]=0
img_mr = Image.fromarray(mr, 'RGB')

# normal map from height
hs = height*20.0
gy, gx = np.gradient(hs)
nz = np.ones_like(hs)
n = np.stack([-gx, gy, nz], axis=-1)   # glTF: Y up (OpenGL)
n /= np.linalg.norm(n, axis=-1, keepdims=True)
nmap = ((n*0.5+0.5)*255).astype(np.uint8)
img_n = Image.fromarray(nmap, 'RGB')

# ---------- rebuild GLB ----------
def embed(img, fmt, quality=None):
    buf = io.BytesIO()
    if fmt=='JPEG': img.save(buf, 'JPEG', quality=quality or 88)
    else: img.save(buf, 'PNG', optimize=True)
    return buf.getvalue()

b_alb = embed(img_albedo,'JPEG',90)
b_mr  = embed(img_mr.resize((256,256)),'JPEG',90)
b_n   = embed(img_n,'PNG')
print("texture bytes:", len(b_alb), len(b_mr), len(b_n))

# original image bufferViews are the last 3 (indices 4,5,6 per earlier listing order)
order = [img['bufferView'] for img in gltf['images']]  # image0=basecolor, image1=metallicRoughness, image2=normal
data_by_bv = {order[0]: b_alb, order[1]: b_mr, order[2]: b_n}

# ---------- split top-face triangles into their own primitive ----------
NEW_BV = {}
if MARKING:
    b_alb_top = embed(img_albedo_top,'JPEG',90)
    top_tris = np.all(top[idx], axis=1)
    acc_idx = gltf['accessors'][prim['indices']]
    comp = acc_idx['componentType']
    dt = np.dtype('<'+CT[comp])
    d_rest = np.ascontiguousarray(idx[~top_tris].ravel()).astype(dt).tobytes()
    d_top  = np.ascontiguousarray(idx[top_tris].ravel()).astype(dt).tobytes()
    gltf['bufferViews'].append({'buffer':0,'byteLength':len(d_rest),'target':34963})
    bv_rest = len(gltf['bufferViews'])-1
    gltf['bufferViews'].append({'buffer':0,'byteLength':len(d_top),'target':34963})
    bv_top = len(gltf['bufferViews'])-1
    gltf['bufferViews'].append({'buffer':0,'byteLength':len(b_alb_top)})
    bv_img_top = len(gltf['bufferViews'])-1
    gltf['accessors'].append({'bufferView':bv_rest,'componentType':comp,'count':int((~top_tris).sum())*3,'type':'SCALAR'})
    acc_rest = len(gltf['accessors'])-1
    gltf['accessors'].append({'bufferView':bv_top,'componentType':comp,'count':int(top_tris.sum())*3,'type':'SCALAR'})
    acc_top = len(gltf['accessors'])-1
    gltf['images'].append({'bufferView':bv_img_top,'mimeType':'image/jpeg'})
    data_by_bv[bv_rest] = d_rest
    data_by_bv[bv_top] = d_top
    data_by_bv[bv_img_top] = b_alb_top
    print("split primitives: top tris", int(top_tris.sum()), "| rest", int((~top_tris).sum()))

newbin = bytearray()
orig = [dict(bv) for bv in gltf['bufferViews']]
for i, bv in enumerate(gltf['bufferViews']):
    while len(newbin) % 4: newbin += b'\0'
    if i in data_by_bv:
        data = data_by_bv[i]
        bv['byteOffset'] = len(newbin); bv['byteLength'] = len(data)
        newbin += data
    else:
        s = orig[i].get('byteOffset', 0); e = s + orig[i]['byteLength']
        bv['byteOffset'] = len(newbin)
        newbin += binbuf[s:e]
gltf['buffers'][0]['byteLength'] = len(newbin)

mat = gltf['materials'][0]
mat['name'] = 'natural_concrete'
pbr = mat['pbrMetallicRoughness']
pbr['baseColorFactor'] = [1.0,1.0,1.0,1.0]
pbr['metallicFactor'] = 0.0
pbr['roughnessFactor'] = 1.0
mat['normalTexture'] = {'index':2,'scale':0.5}

if MARKING:
    gltf['textures'].append({'source':len(gltf['images'])-1,'sampler':0})
    mat_top = copy.deepcopy(mat)
    mat_top['name'] = 'natural_concrete_marking'
    mat_top['pbrMetallicRoughness']['baseColorTexture'] = {'index':len(gltf['textures'])-1}
    gltf['materials'].append(mat_top)
    prim['indices'] = acc_rest
    prim['material'] = 0
    prim_top = {k:v for k,v in prim.items() if k not in ('indices','material')}
    prim_top['indices'] = acc_top
    prim_top['material'] = len(gltf['materials'])-1
    gltf['meshes'][0]['primitives'].append(prim_top)

js_out = json.dumps(gltf, separators=(',',':')).encode()
while len(js_out)%4: js_out += b' '
while len(newbin)%4: newbin += b'\0'
total = 12 + 8+len(js_out) + 8+len(newbin)
out = struct.pack('<III', 0x46546C67, 2, total)
out += struct.pack('<II', len(js_out), 0x4E4F534A) + js_out
out += struct.pack('<II', len(newbin), 0x004E4942) + bytes(newbin)
open(DST,'wb').write(out)
print("written", DST, total, "bytes")
