import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageFilter
import subprocess, wave

import imageio_ffmpeg
FFX = imageio_ffmpeg.get_ffmpeg_exe()

W, H, FPS = 1088, 1920, 24
RD = '/workspace/render'
FB = '/home/appuser/.local/lib/python3.12/site-packages/font_roboto/files/Roboto-Bold.ttf'
FK = '/home/appuser/.local/lib/python3.12/site-packages/font_roboto/files/Roboto-Black.ttf'
FR = '/home/appuser/.local/lib/python3.12/site-packages/font_roboto/files/Roboto-Regular.ttf'
FM = '/home/appuser/.local/lib/python3.12/site-packages/font_roboto/files/Roboto-Medium.ttf'

_fc = {}
def F(path, size):
    k = (path, size)
    if k not in _fc: _fc[k] = ImageFont.truetype(path, size)
    return _fc[k]

def fit(path, size, txt, maxw):
    while size > 20:
        f = F(path, size)
        d = ImageDraw.Draw(Image.new('RGB', (10, 10)))
        if d.textlength(txt, font=f) <= maxw: return f
        size -= 4
    return F(path, 20)

BG = (255, 237, 224)
INK = (32, 30, 34)
SOFT = (128, 118, 112)
ACC = (240, 78, 56)
GREEN = (34, 168, 92)
NAVY = (34, 34, 40)
FAINT = (239, 229, 222)

MX = 74
CW = W - MX * 2

def eo(t):
    t = min(1.0, max(0.0, t))
    return 1 - (1 - t) ** 3

def lin(t, t0, dur=0.55):
    return 0.0 if t < t0 else min(1.0, (t - t0) / dur)

def rise(p):
    return int(54 * (1 - eo(p)))

def canvas():
    im = Image.new('RGBA', (W, H), BG + (255,))
    return im, ImageDraw.Draw(im)

def head_line(d, y, parts, t, size=102, fk=False):
    x = MX
    base = FK if fk else FB
    for wi, (txt, col) in enumerate(parts):
        p = lin(t, 0.1 + wi * 0.16, 0.55)
        f = fit(base, size, txt, CW - (x - MX) - 20)
        if p <= 0:
            x += d.textlength(txt + ' ', font=f); continue
        d.text((x, y + rise(p)), txt, font=f, fill=col + (int(255 * p),), anchor='la')
        x += d.textlength(txt + ' ', font=f)

def body_line(d, y, txt, t, t0=0.8, size=42, color=SOFT):
    p = lin(t, t0)
    if p <= 0: return
    f = fit(FR, size, txt, CW)
    d.text((MX, y + rise(p)), txt, font=f, fill=color + (int(255 * p),), anchor='la')

def card_shadow(w, h, blur=32, alpha=95, oy=18):
    im = Image.new('RGBA', (w + blur * 6, h + blur * 6 + oy), (0, 0, 0, 0))
    ImageDraw.Draw(im).rounded_rectangle([blur*3, blur*3 + oy, blur*3 + w, blur*3 + h + oy],
                                         radius=36, fill=(160, 96, 70, alpha))
    return im.filter(ImageFilter.GaussianBlur(blur)), blur * 3, blur * 3

def card(im, y, h, t, t0=0.35, draw_fn=None):
    p = lin(t, t0, 0.65)
    if p <= 0: return
    sh, bx, by = card_shadow(CW, h)
    c = Image.new('RGBA', sh.size, (0, 0, 0, 0))
    dc = ImageDraw.Draw(c)
    dc.rounded_rectangle([bx, by, bx + CW, by + h], radius=36, fill=(255, 255, 255, 255),
                         outline=(238, 228, 222, 255), width=2)
    if draw_fn: draw_fn(dc, bx, by, t)
    dy = rise(1.0) - rise(eo(p))
    s = 0.95 + 0.05 * eo(p)
    if s < 0.999:
        sh = sh.resize((int(sh.width * s), int(sh.height * s)), Image.LANCZOS)
        c = c.resize((int(c.width * s), int(c.height * s)), Image.LANCZOS)
    a = min(1.0, p * 1.25)
    if a < 1:
        c = c.copy(); c.putalpha(c.split()[3].point(lambda v: int(v * a)))
    im.alpha_composite(sh, (int(W/2 - sh.width/2), int(y - sh.height/2 + dy)))
    im.alpha_composite(c, (int(W/2 - sh.width/2), int(y - sh.height/2 + dy)))

def chip(d, x, y, txt, fg, bg, font=None, padx=20, pady=9, anchor_l=True):
    f = font or F(FB, 28)
    tw = d.textlength(txt, font=f)
    th = f.size
    ox = x if anchor_l else x - tw/2 - padx
    d.rounded_rectangle([ox, y - th/2 - pady, ox + tw + padx*2, y + th/2 + pady],
                        radius=9999, fill=bg)
    d.text((ox + padx, y), txt, font=f, fill=fg, anchor='lm')
    return tw + padx * 2

def topbar(d, bx, by, w, title, t):
    a = int(255 * lin(t, 0.45))
    d.rounded_rectangle([bx + 40, by + 40, bx + w - 40, by + 150], radius=24, fill=NAVY + (a,))
    d.text((bx + 78, by + 95), title, font=F(FB, 32), fill=(255, 255, 255, a), anchor='lm')
    d.ellipse([bx + w - 108, by + 80, bx + w - 76, by + 112], fill=GREEN + (a,))

def url_bar(d, bx, by, w, t):
    a = int(255 * lin(t, 0.4))
    d.rounded_rectangle([bx + 40, by + 36, bx + w - 40, by + 108], radius=9999,
                        fill=(247, 244, 242, a))
    d.ellipse([bx + 62, by + 64, bx + 82, by + 84], fill=GREEN + (a,))
    d.text((bx + 96, by + 72), 'gwesports.vercel.app', font=F(FR, 26), fill=SOFT + (a,), anchor='lm')

def m_receipt(d, bx, by, t):
    a0 = int(255 * lin(t, 0.45))
    d.text((bx + 70, by + 120), 'GUILD ENTRY FEES', font=F(FB, 26), fill=SOFT + (a0,), anchor='lm')
    d.text((bx + 70, by + 188), 'Rs 15,000', font=F(FB, 58), fill=INK + (a0,), anchor='lm')
    w15 = d.textlength('Rs 15,000', font=F(FB, 58))
    k = lin(t, 1.2, 0.4)
    if k > 0.01:
        yl = by + 172
        d.line([bx + 70, yl, bx + 70 + w15 * eo(k), by + 172], fill=ACC + (255,), width=8)
    p = lin(t, 1.8)
    if p > 0:
        d.rounded_rectangle([bx + 70, by + 250, bx + CW - 70, by + 344], radius=20,
                            fill=(255, 241, 238, int(255 * p)))
        d.text((bx + 96, by + 297), 'Wapas mila?  Kuch nahi.', font=F(FB, 30),
               fill=ACC + (int(255 * p),), anchor='lm')

def m_tournament(d, bx, by, t):
    w = CW
    url_bar(d, bx, by, w, t)
    topbar(d, bx, by + 84, w, 'GW SARKARR', t)
    tx = bx + 70
    for i, tb in enumerate(['Live', 'Upcoming', 'Free']):
        p = lin(t, 0.6 + i * 0.14)
        if p <= 0: continue
        a = int(255 * p)
        tf = F(FB, 26)
        tw = d.textlength(tb, font=tf)
        if i == 0:
            d.rounded_rectangle([tx, by + 320, tx + tw + 40, by + 372], radius=9999, fill=ACC + (a,))
            d.text((tx + 20, by + 346), tb, font=tf, fill=(255, 255, 255, a), anchor='lm')
        else:
            d.text((tx + 20, by + 346), tb, font=tf, fill=(196, 186, 180, a), anchor='lm')
        tx += tw + 64
    rows = [('FF Customs #24', 'Free entry', '9:00 PM', ACC),
            ('Solo Clash', 'Rs 0', '10:30 PM', GREEN),
            ('Pro Scrim', 'Invite', 'Aaj raat', (190, 182, 176)),
            ('Rush Squad #7', 'Free entry', '11:00 PM', GREEN)]
    for i, (nm, tag, tme, col) in enumerate(rows):
        r0 = lin(t, 0.85 + i * 0.18)
        if r0 <= 0: continue
        a = int(255 * r0)
        ry = by + 420 + i * 136
        d.rounded_rectangle([bx + 60, ry, bx + CW - 60, ry + 112], radius=22,
                            fill=(252, 250, 249, a), outline=(240, 232, 228, a), width=2)
        d.rounded_rectangle([bx + 84, ry + 22, bx + 142, ry + 90], radius=18, fill=(255, 238, 233, a))
        d.text((bx + 113, ry + 56), ('FF', 'SC', 'PS', 'RS')[i], font=F(FB, 25), fill=ACC + (a,), anchor='mm')
        d.text((bx + 170, ry + 36), nm, font=F(FB, 30), fill=INK + (a,), anchor='lm')
        d.text((bx + 170, ry + 80), tme, font=F(FR, 24), fill=SOFT + (a,), anchor='lm')
        chip(d, bx + CW - 310, ry + 56, 'JOIN', (255, 255, 255, a), ACC + (a,), font=F(FB, 24), pady=9)
        chip(d, bx + CW - 496, ry + 56, tag.upper(), col + (a,), (246, 242, 240, a), font=F(FB, 20), pady=8)

def m_leaderboard(d, bx, by, t):
    url_bar(d, bx, by, CW, t)
    topbar(d, bx, by + 84, CW, 'Solo Clash - Results', t)
    rows = [('1', 'Tu Bhai', 'Rs 2,500', 'TUM', True),
            ('2', 'SK Ridesh', 'Rs 1,200', 'Player', False),
            ('3', 'OP Ravi', 'Rs 800', 'Player', False)]
    for i, (rk, nm, pr, tag, me) in enumerate(rows):
        r0 = lin(t, 0.7 + i * 0.26)
        if r0 <= 0: continue
        a = int(255 * r0)
        ry = by + 370 + i * 152
        d.rounded_rectangle([bx + 60, ry, bx + CW - 60, ry + 126], radius=22,
                            fill=(255, 242, 239, a) if me else (252, 250, 249, a),
                            outline=ACC + (a,) if me else (240, 232, 228, a), width=3 if me else 2)
        d.ellipse([bx + 92, ry + 36, bx + 152, ry + 96], fill=(255, 238, 233, a) if me else (238, 232, 228, a),
                  outline=ACC + (a,), width=2)
        d.text((bx + 122, ry + 66), ('1', '2', '3')[i], font=F(FB, 30), fill=ACC + (a,) if me else SOFT + (a,), anchor='mm')
        d.text((bx + 178, ry + 44), nm, font=F(FB, 29), fill=INK + (a,), anchor='lm')
        d.text((bx + 178, ry + 92), tag, font=F(FR, 23), fill=ACC + (a,) if me else SOFT + (a,), anchor='lm')
        d.text((bx + CW - 94, ry + 66), pr, font=F(FB, 30), fill=(GREEN if me else INK) + (a,), anchor='rm')

def m_withdraw(d, bx, by, t):
    url_bar(d, bx, by, CW, t)
    topbar(d, bx, by + 84, CW, 'My Winnings', t)
    r1 = lin(t, 0.7)
    if r1 > 0:
        a = int(255 * r1)
        d.rounded_rectangle([bx + 60, by + 360, bx + CW - 60, by + 560], radius=22,
                            fill=(242, 250, 245, a), outline=GREEN + (a,), width=2)
        cx = bx + CW / 2
        k = lin(t, 1.1, 0.4)
        if k >= 1:
            d.line([cx - 52, by + 430, cx - 14, by + 464], fill=GREEN + (255,), width=18)
            d.line([cx - 14, by + 464, cx + 52, by + 396], fill=GREEN + (255,), width=18)
        d.text((cx, by + 520), 'Withdraw successful', font=F(FB, 26), fill=GREEN + (a,), anchor='mm')
        p4 = lin(t, 1.15)
        if p4 > 0:
            chip(d, cx - 250, by + 408, 'TO: UPI', ACC + (int(255*p4),), (255, 238, 233, int(255*p4)), font=F(FB, 22))
            chip(d, cx + 250, by + 408, '24/7 OPEN', GREEN + (int(255*p4),), (240, 250, 244, int(255*p4)), font=F(FB, 22), anchor_l=False)
    r2 = lin(t, 1.6)
    if r2 > 0:
        d.text((bx + CW / 2, by + 660), 'Rs 2,500', font=F(FB, 92), fill=INK + (int(255 * r2),), anchor='mm')
        chip(d, bx + CW / 2, by + 770, 'UPI - INSTANT', (255, 255, 255, int(255 * r2)), ACC + (int(255 * r2),),
             font=F(FB, 26), anchor_l=False)
    r3 = lin(t, 2.1)
    if r3 > 0:
        d.text((bx + CW / 2, by + 860), 'Bina wait ke, seedha account mein.', font=F(FR, 30),
               fill=SOFT + (int(230 * r3),), anchor='mm')

def handle(d):
    f = F(FB, 30)
    d.text((MX, 88), 'GW SARKARR', font=f, fill=INK + (255,), anchor='lm')
    d.ellipse([MX + d.textlength('GW SARKARR', font=f) + 18, 76, MX + d.textlength('GW SARKARR', font=f) + 36, 94],
              fill=ACC + (255,))

def slide1(d, im, t):
    head_line(d, 330, [('Pandrah hazaar rupee ', INK), ('diye.', ACC)], t, size=120, fk=True)
    body_line(d, 680, 'Sirf isliye, kyunki ek bade gamer ki guild thi.', t, t0=1.1, size=46)

def slide2(d, im, t):
    head_line(d, 300, [('Wapas ', INK), ('kuch nahi mila.', ACC)], t, size=104, fk=True)
    card(im, 880, 400, t, t0=0.4, draw_fn=m_receipt)

def slide3(d, im, t):
    head_line(d, 290, [('Ab, ', INK), ('doosri taraf', ACC), ('.', INK)], t, size=112, fk=True)
    body_line(d, 560, 'Same game. Same skill. Zero entry fee.', t, t0=0.9, size=46)
    card(im, 1220, 990, t, t0=1.4, draw_fn=m_tournament)

def slide4(d, im, t):
    head_line(d, 290, [('Apni skill dikha, ', INK), ('prize jeeto.', ACC)], t, size=108, fk=True)
    card(im, 1080, 880, t, t0=0.4, draw_fn=m_leaderboard)

def slide5(d, im, t):
    head_line(d, 290, [('Seedha ', INK), ('UPI pe.', ACC)], t, size=112, fk=True)
    card(im, 1060, 1000, t, t0=0.4, draw_fn=m_withdraw)

def slide6(d, im, t):
    head_line(d, 600, [('Fark game ka', INK)], t, size=118, fk=True)
    head_line(d, 730, [('nahi hai.', INK)], t, size=118, fk=True)
    p = lin(t, 0.9, 0.55)
    if p > 0:
        f = fit(FB, 104, 'Fark platform ka hai.', CW)
        d.text((MX, 900 + rise(p)), 'Fark platform ka hai.', font=f, fill=ACC + (int(255 * p),), anchor='la')

def slide7(d, im, t):
    head_line(d, 540, [('GW Sarkarr.', INK)], t, size=128, fk=True)
    p = lin(t, 0.9)
    if p > 0:
        f = F(FB, 54)
        d.rounded_rectangle([MX, 760, MX + CW, 880], radius=9999, fill=ACC + (int(255 * p),))
        d.text((W / 2, 820 + rise(p)), 'JOIN FREE  -  LINK BIO MEIN', font=F(FB, 42),
               fill=(255, 255, 255, int(255 * p)), anchor='mm')
    p2 = lin(t, 1.6)
    if p2 > 0:
        f2 = F(FR, 40)
        d.text((W / 2, 1000 + rise(p2)), 'gwesports.vercel.app', font=f2, fill=SOFT + (int(220 * p2),), anchor='mm')

SLIDES = [(0.3, slide1), (6.0, slide2), (9.9, slide3), (16.1, slide4),
          (22.3, slide5), (28.6, slide6), (32.9, slide7)]
TOTAL = 41.8

def main():
    SR = 44100

    slides_fn = dict(SLIDES)
    order = [s[0] for s in SLIDES]
    nxt_of = {order[i]: (order[i+1] if i+1 < len(order) else TOTAL + 2) for i in range(len(order))}
    NF_ = int(TOTAL * FPS)
    proc = subprocess.Popen([FFX, '-y', '-f', 'rawvideo', '-pix_fmt', 'bgr24', '-s', f'{W}x{H}',
                             '-r', str(FPS), '-i', '-', '-c:v', 'libx264', '-preset', 'medium',
                             '-crf', '19', '-pix_fmt', 'yuv420p', '/tmp/story_v5_silent.mp4'],
                            stdin=subprocess.PIPE, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    for fi in range(NF_):
        t = fi / FPS
        cur = order[0]
        for st in order:
            if t >= st: cur = st
        tl = t - cur
        idx = order.index(cur)
        nxt = nxt_of[cur]
        if nxt - t < 0.45:
            k = 1 - (nxt - t) / 0.45
            im1, _ = canvas()
            slides_fn[cur](ImageDraw.Draw(im1), im1, tl + 95)
            b1 = np.array(im1.convert('RGB'), dtype=np.float32)
            nst = order[idx + 1] if idx + 1 < len(order) else None
            if nst is not None:
                im2, _ = canvas()
                slides_fn[nst](ImageDraw.Draw(im2), im2, 0.0)
                b2 = np.array(im2.convert('RGB'), dtype=np.float32)
                b1 = b1 * (1 - eo(k)) + b2 * eo(k)
            frame = Image.fromarray(b1.astype(np.uint8)).convert('RGBA')
            d = ImageDraw.Draw(frame)
        else:
            frame, d = canvas()
            slides_fn[cur](d, frame, tl)
        handle(d)
        arr = cv2.cvtColor(np.array(frame.convert('RGB')), cv2.COLOR_RGB2BGR)
        proc.stdin.write(arr.tobytes())
        if fi % 240 == 0: print(' f', fi, flush=True)
    proc.stdin.close(); proc.wait()
    REPO = '/workspace/github__Nitin-Linux__Social__Box/reels-pack'
    subprocess.run([FFX, '-y', '-i', '/tmp/story_v5_silent.mp4', '-i', f'{RD}/story_audio.wav',
                    '-c:v', 'copy', '-c:a', 'aac', '-b:a', '160k', '-shortest',
                    f'{REPO}/gw-story-reel-minimal.mp4'],
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    print('ok')

if __name__ == '__main__':
    main()
