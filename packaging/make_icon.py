"""Gera o ícone do OwLock (PNG e .ico) a partir de docs/logo-original.png.

Rode na raiz do projeto: python packaging/make_icon.py (requer pillow e numpy).
"""
import numpy as np
from PIL import Image, ImageFilter, ImageDraw

SRC = "docs/logo-original.png"  # imagem base: cadeado branco em fundo grafite
src = np.asarray(Image.open(SRC).convert("RGB")).astype(np.float32)
lum = src @ np.array([0.299, 0.587, 0.114])

# 1) máscara do cadeado: luminância alta (branco/cinza) vs fundo grafite (~20-35)
alpha = np.clip((lum - 45) / 40, 0, 1)
ys, xs = np.where(alpha > 0.5)
# só a região central (evita bordas do ladrilho original)
keep = (xs > 200) & (xs < 1054) & (ys > 150) & (ys < 1100)
y0, y1, x0, x1 = ys[keep].min(), ys[keep].max(), xs[keep].min(), xs[keep].max()

# 2) buraco da fechadura: região escura conectada ao centro do furo
dark = (lum < 60).astype(np.uint8) * 255
dimg = Image.fromarray(dark).copy()
seed = (627, 700)
ImageDraw.floodfill(dimg, seed, 128)
hole0 = Image.fromarray(((np.asarray(dimg) == 128) * 255).astype(np.uint8))
hole = np.asarray(hole0.filter(ImageFilter.MaxFilter(5))) > 127
hy, hx = np.where(hole)

# recorte com margem
pad = 6
crop = (x0 - pad, y0 - pad, x1 + pad, y1 + pad)
rgb = src[crop[1]:crop[3], crop[0]:crop[2]]
a = alpha[crop[1]:crop[3], crop[0]:crop[2]].copy()
h = hole[crop[1]:crop[3], crop[0]:crop[2]]

# 3) furo em verde-menta "aceso": gradiente vertical, mais claro no topo
mint_top = np.array([214, 255, 244]); mint_bot = np.array([62, 214, 176])
hh = np.where(h)
t = (hh[0] - hh[0].min()) / max(1, (hh[0].max() - hh[0].min()))
rgb = rgb.copy()
col = mint_top * (1 - t[:, None]) + mint_bot * t[:, None]
cy = hh[0].min() + (hh[0].max() - hh[0].min()) * 0.28; cx = hh[1].mean()
r = np.sqrt((hh[0] - cy) ** 2 + (hh[1] - cx) ** 2) / (hh[1].max() - hh[1].min())
core = np.clip(1 - r * 1.6, 0, 1)[:, None]
rgb[hh] = col * (1 - core * 0.6) + np.array([240, 255, 250]) * core * 0.6
a[h] = 1.0
lock = Image.fromarray(np.dstack([rgb, a * 255]).astype(np.uint8), "RGBA")
# suaviza a borda do furo
hmask = Image.fromarray((h * 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(1.2))

def squircle_mask(size, n=5.0, ss=4):
    S = size * ss
    yy, xx = np.mgrid[0:S, 0:S]
    u = (xx + 0.5) / S * 2 - 1; v = (yy + 0.5) / S * 2 - 1
    m = (np.abs(u) ** n + np.abs(v) ** n) <= 1
    return Image.fromarray((m * 255).astype(np.uint8)).resize((size, size), Image.LANCZOS)

def make(size=1024):
    # ladrilho: degradê grafite diagonal
    yy, xx = np.mgrid[0:size, 0:size] / size
    t = np.clip((xx + yy) / 2, 0, 1)[..., None]
    c0 = np.array([30, 31, 38]); c1 = np.array([7, 7, 9])
    tile = (c0 * (1 - t) + c1 * t)
    # brilho sutil no topo
    top = np.clip(1 - yy / 0.18, 0, 1)[..., None] * 10
    tile = np.clip(tile + top, 0, 255).astype(np.uint8)
    base = Image.fromarray(tile, "RGB").convert("RGBA")
    mask = squircle_mask(size)
    # borda interna fina mais clara
    edge = Image.new("RGBA", (size, size), (255, 255, 255, 0))
    inner = squircle_mask(size - max(2, size // 256))
    ring = Image.new("L", (size, size), 0); ring.paste(mask)
    off = (size - inner.size[0]) // 2
    tmp = Image.new("L", (size, size), 0); tmp.paste(inner, (off, off))
    ring = Image.fromarray(np.clip(np.asarray(ring, np.int16) - np.asarray(tmp, np.int16), 0, 255).astype(np.uint8))
    edge.putalpha(ring.point(lambda v: v * 0.10))
    base = Image.alpha_composite(base, edge)

    # cadeado centralizado ocupando ~60% da largura
    target_w = int(size * 0.60)
    scale = target_w / lock.size[0]
    L = lock.resize((target_w, int(lock.size[1] * scale)), Image.LANCZOS)
    pos = ((size - L.size[0]) // 2, (size - L.size[1]) // 2 + int(size * 0.01))
    # sombra suave sob o cadeado
    sh = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    sa = L.split()[3].point(lambda v: v * 0.55)
    shadow = Image.new("RGBA", L.size, (0, 0, 0, 255)); shadow.putalpha(sa)
    sh.paste(shadow, (pos[0], pos[1] + int(size * 0.02)), shadow)
    sh = sh.filter(ImageFilter.GaussianBlur(size * 0.025))
    base = Image.alpha_composite(base, sh)
    layer = Image.new("RGBA", (size, size), (0, 0, 0, 0)); layer.paste(L, pos, L)
    base = Image.alpha_composite(base, layer)
    base.putalpha(Image.fromarray(np.minimum(np.asarray(base.split()[3]), np.asarray(mask))))
    return base

big = make(1024)
for s in (512,):
    make(s).save("docs/logo.png")
# .ico multi-tamanho (cada tamanho renderizado do 1024 com boa reamostragem)
big.save("packaging/owlock.ico", sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)])
# marca sem ladrilho (só o cadeado) para usar dentro da interface
make(256).save("owlock/web/img/owlock-icon.png")
print("ok")
