import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageFilter
import math, subprocess, os

W, H, FPS = 1088, 1920, 24
OUT = '/tmp/guild_v2_silent.mp4'
FD = '/home/appuser/.local/lib/python3.12/site-packages/font_fredoka_one/files/FredokaOne-Regular.ttf'
FB = '/home/appuser/.local/lib/python3.12/site-packages/font_roboto/files/Roboto-Bold.ttf'
FK = '/home/appuser/.local/lib/python3.12/site-packages/font_roboto/files/Roboto-Black.ttf'
FR = '/home/appuser/.local/lib/python3.12/site-packages/font_roboto/files/Roboto-Regular.ttf'

_font_cache = {}
def F(path, size):
    key = (path, size)
    if key not in _font_cache:
        _font_cache[key] = ImageFont.truetype(path, size)
    return _font_cache[key]

def fit(path, size, txt, maxw=980):
    while size > 20:
        f = F(path, size)
        im = Image.new('RGB', (10, 10)); d = ImageDraw.Draw(im)
        if d.textlength(txt, font=f) <= maxw:
            return f
        size -= 4
    return F(path, size)

BG = {}
def load_bgs():
    for k, p in {'arena': '/workspace/render/bg_arena.jpg',
                 'soldier': '/workspace/render/bg_soldier.jpg',
                 'smoke': '/workspace/render/bg_smoke.jpg'}.items():
        BG[k] = cv2.imread(p)

RED = (255, 42, 56, 255)
YELLOW = (255, 205, 40, 255)
WHITE = (255, 255, 255, 255)
GRAY = (215, 215, 220, 255)

def cover(img, zoom=1.0, cx=0.5, cy=0.5):
    h, w = img.shape[:2]
    scale = max(W / w, H / h) * zoom
    interp = cv2.INTER_AREA if scale < 1 else cv2.INTER_LINEAR
    im = cv2.resize(img, (int(w * scale + 1), int(h * scale + 1)), interpolation=interp)
    h, w = im.shape[:2]
    x = int((w - W) * cx); y = int((h - H) * cy)
    x = max(0, min(x, w - W)); y = max(0, min(y, h - H))
    return im[y:y+H, x:x+W]

def eob(t, s=2.4):
    t = min(1.0, max(0.0, t))
    return 1 + (s + 1) * (t - 1) ** 3 + s * (t - 1) ** 2

def eo(t):
    t = min(1.0, max(0.0, t))
    return 1 - (1 - t) ** 3

def slam(t, t0, dur=0.4):
    if t < t0: return 0.0
    lt = (t - t0) / dur
    if lt >= 1.0: return 1.0
    return eob(lt)

def line_in(t, t0, dur=0.35):
    if t < t0: return 0.0
    return min(1.0, (t - t0) / dur)

def glass_card(w, h, radius=34, fill=(8, 8, 12, 185), border=RED, bw=5, glow=20, alpha_mul=1.0, tape=False, sheen=False):
    gpad = glow * 3
    im = Image.new('RGBA', (w + 2 * gpad, h + 2 * gpad), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    d.rounded_rectangle([gpad, gpad, gpad + w, gpad + h], radius=radius,
                        fill=(fill[0], fill[1], fill[2], int(fill[3] * alpha_mul)),
                        outline=(255, 255, 255, 30), width=2)
    if sheen:
        top = Image.new('RGBA', im.size, (0, 0, 0, 0))
        td = ImageDraw.Draw(top)
        td.rounded_rectangle([gpad, gpad, gpad + w, gpad + h / 2], radius=radius, fill=(255, 255, 255, 16))
        im = Image.alpha_composite(im, top)
    if tape:
        for yy in (gpad + 56, gpad + h - 56):
            strip = Image.new('RGBA', (w + 2 * gpad, 26), (0, 0, 0, 0))
            sd = ImageDraw.Draw(strip)
            step = 46
            for sx in range(-step, strip.width + step, step):
                sd.polygon([(sx, 26), (sx + 23, 0), (sx + 46, 26)], fill=(240, 180, 20, 220),
                           outline=(20, 20, 20, 255))
            strip = strip.rotate(0)
            im.alpha_composite(strip, (0, yy - 13))
    d.rounded_rectangle([gpad, gpad, gpad + w, gpad + h], radius=radius,
                        outline=(border[0], border[1], border[2], int(border[3] * alpha_mul)), width=bw)
    if bw == 0:
        d.rounded_rectangle([gpad + 3, gpad + 3, gpad + w - 3, gpad + h - 3], radius=max(4, radius - 6),
                            outline=(200, 200, 205, 120), width=2)
    for cx, cy, sx, sy in [(gpad+16, gpad+16, 1, 1), (gpad+w-16, gpad+16, -1, 1),
                           (gpad+16, gpad+h-16, 1, -1), (gpad+w-16, gpad+h-16, -1, -1)]:
        d.line([cx, cy, cx + 34 * sx, cy], fill=(255, 205, 40, 220), width=4)
        d.line([cx, cy, cx, cy + 34 * sy], fill=(255, 205, 40, 220), width=4)
    g = im.filter(ImageFilter.GaussianBlur(glow))
    a = g.split()[3].point(lambda v: int(v * 0.85))
    gg = g.copy(); gg.putalpha(a)
    out = Image.new('RGBA', im.size, (0, 0, 0, 0))
    out = Image.alpha_composite(out, gg)
    out = Image.alpha_composite(out, gg)
    out = Image.alpha_composite(out, im)
    return out, gpad

def paste_center(base, layer, cx, cy, scale=1.0, alpha=1.0):
    if scale != 1.0:
        nw = max(1, int(layer.width * scale)); nh = max(1, int(layer.height * scale))
        layer = layer.resize((nw, nh), Image.LANCZOS)
    if alpha < 1.0:
        a = layer.split()[3].point(lambda v: int(v * alpha))
        layer = layer.copy(); layer.putalpha(a)
    x = int(cx - layer.width / 2); y = int(cy - layer.height / 2)
    base.alpha_composite(layer, (x, y))

def soft_dark(cx, cy, w, h, strength=110):
    im = Image.new('RGBA', (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    d.ellipse([cx - w / 2, cy - h / 2, cx + w / 2, cy + h / 2], fill=(0, 0, 0, strength))
    return im.filter(ImageFilter.GaussianBlur(60))

def stamp_layer(txt, font, fill, stroke_fill, rot):
    pad = 90
    im = Image.new('RGBA', (W + 2 * pad, H + 2 * pad), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    d.text((im.width / 2, im.height / 2), txt, font=font, fill=fill, anchor='mm',
           stroke_width=12, stroke_fill=stroke_fill)
    return im.rotate(rot, resample=Image.BICUBIC, expand=False)

EMBERS = []
_rng = np.random.RandomState(7)
for i in range(60):
    EMBERS.append(dict(x0=_rng.uniform(0, W), y0=_rng.uniform(0, H),
                       speed=_rng.uniform(60, 190), size=_rng.uniform(2.2, 7.5),
                       alpha=_rng.uniform(35, 120), wig=_rng.uniform(6, 26), ph=_rng.uniform(0, 6.28)))

def add_particles(base_bgr, t, heat=1.0):
    addl = np.zeros_like(base_bgr)
    for e in EMBERS:
        yy = (e['y0'] - e['speed'] * t) % (H + 120) - 60
        xx = (e['x0'] + e['wig'] * math.sin(t * 0.9 + e['ph'])) % W
        a = e['alpha'] * heat
        if yy > H - 200: a *= max(0.0, 1 - (yy - (H - 200)) / 200)
        if yy < 300: a *= max(0.35, yy / 300)
        col = (int(30 * a / 255), int(a), int(a * 1.15))
        r = int(e['size'])
        cv2.circle(addl, (int(xx), int(yy)), r, col, -1, cv2.LINE_AA)
        rr = int(r * 2.6)
        cv2.circle(addl, (int(xx), int(yy)), rr, (col[0] // 4, col[1] // 4, col[2] // 4), -1, cv2.LINE_AA)
    return cv2.add(base_bgr, addl)

_noise = None
def grain(img, idx):
    global _noise
    if _noise is None:
        rngs = np.random.RandomState(3)
        _noise = rngs.randint(-9, 10, (H, W, 1)).astype(np.int16)
    return np.clip(img.astype(np.int16) + np.roll(_noise, idx * 7, axis=1), 0, 255).astype(np.uint8)

_yy, _xx = np.mgrid[0:H, 0:W]
_d = np.sqrt(((_xx - W / 2) / (W / 2)) ** 2 + ((_yy - H / 2) / (H / 2)) ** 2)
VIG = (1 - 0.42 * np.clip(_d - 0.55, 0, 1) ** 1.6)[:, :, None].astype(np.float32)

GLITCH_TS = None

def glitch(base, t, gts):
    for gt in gts:
        dt = t - gt
        if 0 <= dt < 0.26:
            k = 1.0 - dt / 0.26
            out = base.copy()
            shift = int(14 * k)
            b, g, r = cv2.split(base)
            r = np.roll(r, shift, axis=1)
            b = np.roll(b, -shift, axis=1)
            out = cv2.merge([b, g, r])
            rng = np.random.RandomState(int(t * 1000) + 3)
            for _ in range(int(3 + 10 * k)):
                y0 = rng.randint(0, H - 70)
                hgt = rng.randint(10, 70)
                dx = rng.randint(-int(60 * k) - 4, int(60 * k) + 5)
                out[y0:y0+hgt] = np.roll(out[y0:y0+hgt], dx, axis=1)
            if dt < 0.05:
                out = cv2.addWeighted(out, 0.3, np.full_like(out, 255), 0.7, 0)
            return out
    return base

def grade_dark(img, amount=0.45, tint=1.06):
    img = img.astype(np.float32) * (1 - amount)
    img[:, :, 2] *= tint
    return np.clip(img, 0, 255).astype(np.uint8)

def chevron(d, cx, cy, size, color, alpha):
    c = (color[0], color[1], color[2], alpha)
    d.polygon([(cx - size, cy - size * 0.6), (cx + size, cy - size * 0.6), (cx, cy + size * 0.7)], fill=c)

MARKER_S1 = [0]
def scene1(t, d, im):
    d2 = ImageDraw.Draw(soft_dark(W/2, 900, 1000, 900))
    if t < 1.9: im.alpha_composite(d2._image)
    s = slam(t, 0.1, 0.45)
    if s > 0.01:
        f = fit(FD, 118, 'WARNING')
        f = f if s >= 1 else F(FD, max(20, int(f.size * s)))
        a = int(255 * min(1, s * 1.6))
        d.text((W/2, 470), 'WARNING', font=f, fill=(255, 255, 255, a), anchor='mm',
               stroke_width=9, stroke_fill=(170, 0, 12, a))
    s2 = line_in(t, 0.55)
    if s2 > 0:
        a = int(255 * s2)
        y0 = 700 + int(30 * (1 - eo(s2)))
        d.text((W/2, y0), 'FF GUILD', font=F(FD, 130), fill=(255, 255, 255, a), anchor='mm',
               stroke_width=10, stroke_fill=(0, 0, 0, a))
    s3 = slam(t, 0.9, 0.45)
    if s3 > 0.01:
        f = fit(FD, 92, 'JOIN KAR RAHE HO?')
        f = f if s3 >= 1 else F(FD, max(20, int(f.size * s3)))
        a = int(255 * min(1, s3 * 1.5))
        d.text((W/2, 880), 'JOIN KAR RAHE HO?', font=f, fill=(255, 220, 60, a), anchor='mm',
               stroke_width=8, stroke_fill=(0, 0, 0, a))
    cs = slam(t, 2.0, 0.55)
    if cs > 0.01:
        card, gp = glass_card(930, 360, tape=True, sheen=True, alpha_mul=min(1.0, cs * 1.3))
        cdl = ImageDraw.Draw(card)
        cdl.text((card.width/2, gp + 128), '99% GUILDS FAKE HAI', font=fit(FD, 76, '99% GUILDS FAKE HAI'),
                 fill=(255, 255, 255, 255), anchor='mm', stroke_width=6, stroke_fill=(150, 0, 10, 255))
        cdl.text((card.width/2, gp + 250), '(PAISA DO - KUCH NAHI MILTA)', font=F(FR, 46),
                 fill=(230, 230, 235, 255), anchor='mm')
        paste_center(im, card, W/2, 1330, scale=cs, alpha=min(1.0, cs * 1.3))

def scene2(t, d, im):
    if t < 3.2: im.alpha_composite(ImageDraw.Draw(soft_dark(W/2, 750, 1000, 620))._image)
    s1 = slam(t, 0.15, 0.4)
    if s1 > 0.01:
        f = fit(FD, 104, 'TUMHARA PAISA?')
        f = f if s1 >= 1 else F(FD, max(20, int(f.size * s1)))
        a = int(255 * min(1, s1 * 1.5))
        d.text((W/2, 620), 'TUMHARA PAISA?', font=f, fill=WHITE, anchor='mm', stroke_width=9, stroke_fill=(0,0,0,a))
    s2 = slam(t, 1.15, 0.35)
    if s2 > 0.01:
        f = fit(FD, 170, 'GAYA.', maxw=900)
        f = f if s2 >= 1 else F(FD, max(20, int(f.size * s2)))
        a = int(255 * min(1, s2 * 1.4))
        d.text((W/2, 850), 'GAYA.', font=f, fill=(255, 42, 56, a), anchor='mm', stroke_width=13, stroke_fill=(0,0,0,a))
    s3 = slam(t, 3.6, 0.4)
    if s3 > 0.01:
        f = fit(FD, 96, 'TUMHARA RANK?')
        f = f if s3 >= 1 else F(FD, max(20, int(f.size * s3)))
        a = int(255 * min(1, s3 * 1.5))
        d.text((W/2, 1130), 'TUMHARA RANK?', font=f, fill=WHITE, anchor='mm', stroke_width=9, stroke_fill=(0,0,0,a))
    s4 = slam(t, 4.4, 0.35)
    if s4 > 0.01:
        st = stamp_layer('DOOB GAYA', F(FD, 150), (255, 42, 56, 255), (0, 0, 0, 255), -7)
        paste_center(im, st, W/2, 1400, scale=s4, alpha=min(1.0, s4 * 1.4))

def scene3(t, d, im):
    pulse = 0.97 + 0.03 * math.sin(t * 6.3)
    s1 = slam(t, 0.2, 0.5)
    if s1 > 0.01:
        f = fit(FD, 138, 'GW SARKARR')
        f = f if s1 >= 1 else F(FD, max(20, int(f.size * s1)))
        a = int(255 * min(1, s1 * 1.4))
        d.text((W/2, 400), 'GW SARKARR', font=f, fill=(255, 205, 40, a), anchor='mm',
               stroke_width=12, stroke_fill=(90, 0, 0, a))
    cs = slam(t, 1.1, 0.5)
    if cs > 0.01:
        card, gp = glass_card(880, 980, sheen=True, alpha_mul=min(1.0, cs * 1.5))
        cdl = ImageDraw.Draw(card)
        hd = gp + 74
        cdl.rounded_rectangle([gp + 40, hd - 54, gp + 840 - 40, hd + 54], radius=20, fill=(180, 0, 12, 235))
        cv0 = [40, 43, 40]
        cdl.ellipse([gp + 66, hd - 14, gp + 94, hd + 14], fill=(80, 240, 90, 255))
        cdl.text((gp + 130, hd), 'OFFICIAL  TOURNAMENTS', font=F(FB, 42),
                 fill=(255, 255, 255, 255), anchor='lm')
        rows = [('DAILY CUSTOMS', 'FREE ENTRY', 2.1), ('PAID TOURNAMENTS', 'DAILY', 2.7), ('REAL PRIZE MONEY', 'UPI', 3.3)]
        for i, (txt, tag, tt) in enumerate(rows):
            rs = slam(t, tt, 0.4)
            if rs <= 0.01: continue
            ry = hd + 200 + i * 245
            pul = 255 if t > 1.5 else int(255 * rs)
            cdl.rectangle([gp + 55, ry - 27, gp + 109, ry + 27], fill=(255, 42, 56, pul))
            col = (255, 205, 40) if i == 2 else (255, 255, 255)
            cdl.text((gp + 150, ry), txt, font=F(FK, 56), fill=col + (int(255 * min(1, rs * 1.6)),),
                     anchor='lm', stroke_width=5, stroke_fill=(0, 0, 0, 255))
            tg = f'{tag}'
            tf = F(FB, 30)
            tw = cdl.textlength(tg, font=tf)
            cdl.rounded_rectangle([gp + 825 - 36 - tw, ry - 26, gp + 825 - 12, ry + 26],
                                  radius=14, fill=(255, 205, 40, 60), outline=(255, 205, 40, 200), width=2)
            cdl.text((gp + 825 - 24 - tw / 2, ry), tg, font=tf, fill=(255, 205, 40, 230), anchor='mm')
            if i < 2:
                cdl.line([gp + 55, ry + 122, gp + 825, ry + 122], fill=(255, 255, 255, 40), width=3)
        paste_center(im, card, W/2, 1240, scale=cs * pulse, alpha=min(1.0, cs * 1.4))

def scene4(t, d, im):
    if t < 2.0: im.alpha_composite(ImageDraw.Draw(soft_dark(W/2, 840, 1000, 760))._image)
    s1 = slam(t, 0.15, 0.4)
    if s1 > 0.01:
        f = fit(FD, 78, 'LEKIN SUN...')
        f = f if s1 >= 1 else F(FD, max(20, int(f.size * s1)))
        a = int(255 * min(1, s1 * 1.5))
        d.text((W/2, 610), 'LEKIN SUN...', font=f, fill=GRAY, anchor='mm', stroke_width=7, stroke_fill=(0,0,0,a))
        uw = line_in(t, 0.5)
        if uw > 0:
            d.rectangle([W/2 - 230 * uw, 696, W/2 + 230 * uw, 712], fill=(255, 42, 56, 255))
    s2 = slam(t, 1.1, 0.45)
    if s2 > 0.01:
        f = fit(FD, 122, 'SIRF PRO', maxw=940)
        f = f if s2 >= 1 else F(FD, max(20, int(f.size * s2)))
        a = int(255 * min(1, s2 * 1.4))
        d.text((W/2, 880), 'SIRF PRO', font=f, fill=WHITE, anchor='mm', stroke_width=10, stroke_fill=(0,0,0,a))
    s3 = slam(t, 1.45, 0.45)
    if s3 > 0.01:
        f = fit(FD, 122, 'BANDE')
        f = f if s3 >= 1 else F(FD, max(20, int(f.size * s3)))
        a = int(255 * min(1, s3 * 1.4))
        d.text((W/2, 1050), 'BANDE', font=f, fill=(255, 42, 56, a), anchor='mm', stroke_width=10, stroke_fill=(0,0,0,a))

def scene5(t, d, im):
    if t < 2.0: im.alpha_composite(ImageDraw.Draw(soft_dark(W/2, 780, 1000, 640))._image)
    s1 = slam(t, 0.2, 0.45)
    if s1 > 0.01:
        f = fit(FD, 92, 'TU SACH ME')
        f = f if s1 >= 1 else F(FD, max(20, int(f.size * s1)))
        a = int(255 * min(1, s1 * 1.5))
        d.text((W/2, 660), 'TU SACH ME', font=f, fill=WHITE, anchor='mm', stroke_width=9, stroke_fill=(0,0,0,a))
    s2 = slam(t, 0.6, 0.45)
    if s2 > 0.01:
        f = fit(FD, 92, 'PRO HAI?')
        f = f if s2 >= 1 else F(FD, max(20, int(f.size * s2)))
        a = int(255 * min(1, s2 * 1.5))
        d.text((W/2, 810), 'PRO HAI?', font=f, fill=(255, 205, 40, a), anchor='mm', stroke_width=9, stroke_fill=(0,0,0,a))
    cs = slam(t, 1.6, 0.5)
    if cs > 0.01:
        flash = 0.94 + 0.06 * abs(math.sin(t * 4.2))
        card, gp = glass_card(780, 240, border=(255, 255, 255, 235), fill=(255, 255, 255, 235), bw=0, glow=16,
                              alpha_mul=min(1.0, cs * 1.4), sheen=True)
        cdl = ImageDraw.Draw(card)
        cdl.text((card.width/2, card.height/2), "COMMENT: 'PRO'", font=F(FK, 72),
                 fill=(20, 20, 24, 255), anchor='mm')
        paste_center(im, card, W/2, 1230, scale=cs * flash, alpha=min(1.0, cs * 1.4))
        if t > 2.6:
            bnc = abs(math.sin((t - 2.6) * 5.0))
            chevron(d, W/2, 1470 - int(bnc * 55), 50, (255, 42, 56), 255)
    s4 = line_in(t, 4.6)
    if s4 > 0:
        a = int(200 * s4)
        d.text((W/2, 1690), 'FOLLOW  @GW_SARKARR', font=F(FB, 46), fill=(255, 255, 255, a), anchor='mm')

def render_loop(duration, scenes, out_path, gts=None):
    if not BG: load_bgs()
    if gts is None: gts = [s[0] for s in scenes]
    NF_ = int(duration * FPS)
    ff = __import__('imageio_ffmpeg').get_ffmpeg_exe()
    cmd = [ff, '-y', '-f', 'rawvideo', '-pix_fmt', 'bgr24', '-s', f'{W}x{H}',
           '-r', str(FPS), '-i', '-', '-c:v', 'libx264', '-preset', 'medium',
           '-crf', '19', '-pix_fmt', 'yuv420p', out_path]
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    for fi in range(NF_):
        t = min(duration, fi / FPS)
        start, bgname, fn = scenes[0]
        for sc in scenes:
            if t >= sc[0]: start, bgname, fn = sc
        tl = t - start
        punch = 1 + 0.10 * (1 - eo(min(1.0, tl / 0.45))) if tl < 0.45 else 1.0
        kb_z = (1.06 + 0.05 * min(1.0, tl / 6.0)) * punch
        kb_cx = 0.5 + 0.03 * math.sin(t * 0.35 + start)
        kb_cy = 0.42 + 0.02 * math.cos(t * 0.3)
        base = cover(BG[bgname], zoom=kb_z, cx=kb_cx, cy=kb_cy)
        base = grade_dark(base, amount=0.55 if bgname != 'smoke' else 0.42)
        base = add_particles(base, t + start * 3.0)
        if tl < 0.35:
            base = cv2.addWeighted(base, 1 - 0.35 * (1 - tl / 0.35), np.full_like(base, 60), 0.35 * (1 - tl / 0.35), 0)
        dx, dy = 0, 0
        for g, mv in [(0.0, 0), (1.15, 16), (4.6, 10), (8.0, 14), (20.3, 12), (23.8, 10)]:
            dt = t - g
            if 0 <= dt < 0.5:
                m = mv * (1 - dt / 0.5)
                if m > (abs(dx) if dx else 0):
                    rng = np.random.RandomState(int(t * 240) + 1)
                    dx, dy = int(rng.uniform(-m, m)), int(rng.uniform(-m, m))
        if dx or dy:
            M = np.float32([[1, 0, dx], [0, 1, dy]])
            base = cv2.warpAffine(base, M, (W, H), borderMode=cv2.BORDER_REFLECT)
        frame = Image.fromarray(cv2.cvtColor(base, cv2.COLOR_BGR2RGB)).convert('RGBA')
        d = ImageDraw.Draw(frame)
        fn(tl, d, frame)
        frame = Image.alpha_composite(Image.new('RGBA', (W, H), (0, 0, 0, 255)), frame)
        wg, gp2 = glass_card(300, 92, radius=20, fill=(8, 8, 12, 160), border=(255, 45, 60, 200), bw=3, glow=8)
        wdl = ImageDraw.Draw(wg)
        wdl.text((wg.width/2, wg.height/2), 'GW SARKARR', font=F(FK, 40), fill=(255, 255, 255, 230), anchor='mm')
        walpha = 0.55 + 0.2 * abs(math.sin(t * 2.1))
        paste_center(frame, wg, W - 240, 130, alpha=walpha)
        frame = frame.convert('RGB')
        out = cv2.cvtColor(np.array(frame), cv2.COLOR_RGB2BGR)
        out = glitch(out, t, gts)
        out = grain(out, fi % 8)
        out = (out.astype(np.float32) * VIG).astype(np.uint8)
        bar = int(W * min(1.0, t / duration))
        out[H - 14:H, 0:bar] = (255, 42, 56)
        out[H - 14:H, bar:] = (30, 30, 34)
        proc.stdin.write(out.tobytes())
        if fi % 120 == 0: print('frame', fi, flush=True)
    proc.stdin.close()
    proc.wait()
    print('done', out_path)

def pscene1(t, d, im):
    fade = 1.0 if t < 1.8 else max(0.0, 1 - (t - 1.8) / 0.9)
    a = int(255 * fade)
    ring = slam(t, 0.05, 0.5)
    d.ellipse([W/2 - 300 * ring, 560 - 300 * ring, W/2 + 300 * ring, 560 + 300 * ring],
              outline=(255, 42, 56, int(160 * fade)), width=12)
    s = slam(t, 0.15, 0.45)
    if s > 0.01:
        f = F(FD, max(20, int(300 * s)))
        d.text((W/2, 560), 'GW', font=f, fill=(230, 20, 34, a), anchor='mm',
               stroke_width=16, stroke_fill=(0, 0, 0, a))
    s2 = line_in(t, 0.9)
    if s2 > 0:
        d.text((W/2, 800), 'SARKARR', font=F(FK, 64), fill=(255, 205, 40, int(255 * s2)), anchor='mm',
               stroke_width=6, stroke_fill=(0, 0, 0, int(255 * s2)))
    s3 = line_in(t, 1.3)
    if s3 > 0:
        d.text((W/2, 890), 'INDIA KA ESPORTS PLATFORM', font=F(FB, 40),
               fill=(220, 220, 225, int(230 * s3)), anchor='mm')

def bullet_rows(d, t, rows, cy, w=860, delay0=0.0, gap=104):
    for i, txt in enumerate(rows):
        rs = line_in(t, delay0 + i * 0.42)
        if rs <= 0: continue
        ry = cy + i * gap
        xoff = int(60 * (1 - eo(rs)))
        a = int(255 * min(1, rs * 1.5))
        d.rectangle([W/2 - w/2 + xoff, ry - 34, W/2 - w/2 + xoff + 14, ry + 34], fill=(255, 42, 56, a))
        d.text((W/2 - w/2 + 50 + xoff, ry), txt, font=F(FB, 50), fill=(245, 245, 248, a), anchor='lm',
               stroke_width=5, stroke_fill=(0, 0, 0, a))

def pscene2(t, d, im):
    if t < 2.0: im.alpha_composite(ImageDraw.Draw(soft_dark(W/2, 820, 1020, 700))._image)
    s1 = slam(t, 0.15, 0.4)
    if s1 > 0.01:
        f = fit(FD, 124, 'FREE FIRE')
        f = f if s1 >= 1 else F(FD, max(20, int(f.size * s1)))
        a = int(255 * min(1, s1 * 1.5))
        d.text((W/2, 560), 'FREE FIRE', font=f, fill=WHITE, anchor='mm', stroke_width=10, stroke_fill=(0,0,0,a))
    s2 = slam(t, 0.5, 0.4)
    if s2 > 0.01:
        f = fit(FD, 116, 'TOURNAMENTS')
        f = f if s2 >= 1 else F(FD, max(20, int(f.size * s2)))
        a = int(255 * min(1, s2 * 1.5))
        d.text((W/2, 720), 'TOURNAMENTS', font=f, fill=(255, 42, 56, a), anchor='mm', stroke_width=10, stroke_fill=(0,0,0,a))
    if t > 1.6:
        card, gp = glass_card(900, 420, sheen=True)
        cdl = ImageDraw.Draw(card)
        bullet_rows(cdl, t - 1.6, ['ENTRY FEE SIRF EK BAAR', 'PRIZE HAZARON ME', 'COMPETITION LIVE'], gp + 110, w=760, delay0=0.2)
        paste_center(im, card, W/2, 1360, scale=1.0, alpha=min(1.0, slam(t, 1.6, 0.4) * 1.2))

def pscene3(t, d, im):
    if t < 1.8: im.alpha_composite(ImageDraw.Draw(soft_dark(W/2, 720, 1000, 640))._image)
    s1 = slam(t, 0.15, 0.4)
    if s1 > 0.01:
        f = fit(FD, 110, 'WIN REAL')
        f = f if s1 >= 1 else F(FD, max(20, int(f.size * s1)))
        a = int(255 * min(1, s1 * 1.5))
        d.text((W/2, 580), 'WIN REAL', font=f, fill=WHITE, anchor='mm', stroke_width=10, stroke_fill=(0,0,0,a))
    s2 = slam(t, 0.55, 0.45)
    if s2 > 0.01:
        f = fit(FD, 165, 'PRIZES', maxw=940)
        f = f if s2 >= 1 else F(FD, max(20, int(f.size * s2)))
        a = int(255 * min(1, s2 * 1.4))
        d.text((W/2, 790), 'PRIZES', font=f, fill=(255, 205, 40, a), anchor='mm', stroke_width=12, stroke_fill=(0,0,0,a))
    cs = slam(t, 1.4, 0.5)
    if cs > 0.01:
        card, gp = glass_card(760, 300, sheen=True, alpha_mul=min(1.0, cs * 1.3))
        cdl = ImageDraw.Draw(card)
        cdl.text((card.width/2, gp + 150), 'DIAMONDS', font=F(FK, 62), fill=(255, 255, 255, 255), anchor='mm')
        cdl.text((card.width/2, gp + 150), '   |   ', font=F(FK, 62), fill=(255, 42, 56, 255), anchor='mm')
        cdl.ellipse([gp + 362, gp + 118, gp + 398, gp + 154], fill=(255, 42, 56, 255))
        cdl.text((card.width - 190, gp + 150), 'GIFT VOUCHERS', font=F(FK, 56), fill=(255, 255, 255, 255), anchor='mm')
        paste_center(im, card, W/2, 1260, scale=cs, alpha=min(1.0, cs * 1.3))

def pscene4(t, d, im):
    if t < 1.6: im.alpha_composite(ImageDraw.Draw(soft_dark(W/2, 800, 1020, 700))._image)
    s1 = slam(t, 0.15, 0.4)
    if s1 > 0.01:
        f1 = fit(FD, 108, 'INSTANT')
        f1 = f1 if s1 >= 1 else F(FD, max(20, int(f1.size * s1)))
        d.text((W/2, 540), 'INSTANT', font=f1, fill=(255, 205, 40, int(255 * min(1, s1 * 1.5))), anchor='mm', stroke_width=10, stroke_fill=(0,0,0,255))
    s2 = slam(t, 0.45, 0.4)
    if s2 > 0.01:
        f2 = fit(FD, 108, 'WITHDRAW')
        f2 = f2 if s2 >= 1 else F(FD, max(20, int(f2.size * s2)))
        d.text((W/2, 690), 'WITHDRAW', font=f2, fill=WHITE, anchor='mm', stroke_width=10, stroke_fill=(0,0,0,255))
    cs = slam(t, 1.0, 0.5)
    if cs > 0.01:
        card, gp = glass_card(880, 460, sheen=True, alpha_mul=min(1.0, cs * 1.4))
        cdl = ImageDraw.Draw(card)
        for i, txt in enumerate(['UPI  -  PAYTM  -  BANK', '24/7  -  NO WAIT']):
            rs = slam(t, 1.0 + 0.4 + i * 0.45, 0.4)
            if rs <= 0.01: continue
            ry = gp + 130 + i * 190
            a = int(255 * min(1, rs * 1.5))
            cdl.rounded_rectangle([gp + 70, ry - 46, gp + 130, ry + 14], radius=12, fill=(50, 220, 90, a))
            cdl.line([gp + 82, ry - 20, gp + 95, ry - 6], fill=(10, 30, 16, a), width=7)
            cdl.line([gp + 95, ry - 6, gp + 118, ry - 34], fill=(10, 30, 16, a), width=7)
            cdl.text((gp + 170, ry - 16), txt, font=F(FK, 60), fill=(255, 255, 255, a), anchor='lm')
        paste_center(im, card, W/2, 1250, scale=cs, alpha=min(1.0, cs * 1.4))

def pscene5(t, d, im):
    s1 = slam(t, 0.15, 0.45)
    if s1 > 0.01:
        f = fit(FD, 112, 'DOWNLOAD')
        f = f if s1 >= 1 else F(FD, max(20, int(f.size * s1)))
        a = int(255 * min(1, s1 * 1.5))
        d.text((W/2, 520), 'DOWNLOAD', font=f, fill=WHITE, anchor='mm', stroke_width=11, stroke_fill=(0,0,0,a))
    s2 = slam(t, 0.5, 0.45)
    if s2 > 0.01:
        f = fit(FD, 112, 'APP NOW')
        f = f if s2 >= 1 else F(FD, max(20, int(f.size * s2)))
        a = int(255 * min(1, s2 * 1.5))
        d.text((W/2, 670), 'APP NOW', font=f, fill=(255, 205, 40, a), anchor='mm', stroke_width=11, stroke_fill=(0,0,0,a))
    cs = slam(t, 1.2, 0.5)
    if cs > 0.01:
        flash = 0.94 + 0.06 * abs(math.sin(t * 4.2))
        card, gp = glass_card(820, 560, border=(255, 205, 40, 240), sheen=True, alpha_mul=min(1.0, cs * 1.4))
        cdl = ImageDraw.Draw(card)
        cdl.rounded_rectangle([gp + 260, gp + 60, gp + 560, gp + 150], radius=24, fill=(255, 42, 56, 255))
        cdl.text((card.width/2, gp + 105), 'JOIN FREE', font=F(FK, 54), fill=(255, 255, 255, 255), anchor='mm')
        cdl.text((card.width/2, gp + 260), 'gwesports.vercel.app', font=F(FB, 56), fill=(255, 255, 255, 255), anchor='mm')
        cdl.text((card.width/2, gp + 400), 'LIVE  TOURNAMENTS  ROZ', font=F(FB, 36), fill=(255, 205, 40, 255), anchor='mm')
        paste_center(im, card, W/2, 1250, scale=cs * flash, alpha=min(1.0, cs * 1.4))
        if t > 2.4:
            bnc = abs(math.sin((t - 2.4) * 5.0))
            chevron(d, W/2, 1630 - int(bnc * 45), 44, (255, 205, 40), 255)

GUILD_SCENES = [(0.0, 'arena', scene1), (4.6, 'soldier', scene2), (11.2, 'smoke', scene3), (20.0, 'soldier', scene4), (23.8, 'arena', scene5)]
PROMO_SCENES = [(0.0, 'smoke', pscene1), (2.7, 'arena', pscene2), (6.2, 'soldier', pscene3), (9.8, 'smoke', pscene4), (12.5, 'arena', pscene5)]
PROMO_GTS = [0.0, 2.7, 6.2, 9.8, 12.5]

if __name__ == '__main__':
    render_loop(29.83, GUILD_SCENES, OUT)
