import asyncio, wave, json, subprocess
import numpy as np
import edge_tts
import imageio_ffmpeg
FFX = imageio_ffmpeg.get_ffmpeg_exe()
SR = 44100
RD = '/workspace/render'

MAD = 'hi-IN-MadhurNeural'
PRA = 'en-IN-PrabhatNeural'

# story lines: list of (phrase, rate, pitch) segments
LINES = [
    [('इमजिन करो।', '+9%', '+2Hz'), ('पंद्रह हज़ार रुपए —', '+2%', '+0Hz'),
     ('सिर्फ एक guild join करने के लिए।', '-4%', '-3Hz')],
    [('पैसे गए।', '-3%', '-2Hz'), ('और वापसी में?', '+5%', '+0Hz'),
     ('कुछ नहीं मिला।', '-7%', '-4Hz')],
    [('फिर मिला GW Sarkarr।', '+3%', '+0Hz'), ('same game, same skill —', '-3%', '-1Hz'),
     ('लेकिन entry फ्री।', '+7%', '+2Hz')],
    [('रोज़ नए tournaments,', '+2%', '+0Hz'), ('free entry,', '+4%', '+1Hz'),
     ('और prize का पैसा सीधा leaderboard पर।', '+5%', '+1Hz')],
    [('और जीत के पैसे?', '+7%', '+2Hz'), ('straight UPI पे।', '+1%', '+0Hz'),
     ('न कोई इंतज़ार, न भागदौड़।', '-5%', '-3Hz')],
    [('फर्क game का नहीं है।', '-8%', '-3Hz'), ('फर्क platform का है।', '-3%', '-1Hz')],
    [('GW Sarkarr।', '+3%', '+0Hz'), ('join फ्री है — खेलो, जीतो, और कमाओ।', '+2%', '+1Hz'),
     ('link bio में है।', '-2%', '-1Hz')],
]

AUD = {
 'vt_A_madhur_dev': ([[('इमजिन करो।', '+9%', '+2Hz')], LINES[0], [('GW Sarkarr।', '+3%', '+0Hz'), ('join फ्री है — खेलो, जीतो, और कमाओ।', '+2%', '+1Hz'), ('link bio में है।', '-2%', '-1Hz')]], MAD, 0.26),
 'vt_B_prabhat': ([[('Imagine karo.', '+9%', '+2Hz'), ('Pandrah hazaar rupaye —', '+2%', '+0Hz'), ('sirf ek guild join karne ke liye.', '-4%', '-3Hz')], [('Fark game ka nahi hai.', '-8%', '-3Hz'), ('fark platform ka hai.', '-3%', '-1Hz')], [('GW Sarkarr.', '+3%', '+0Hz'), ('join free hai — khelo, jeeto, aur kamao.', '+2%', '+1Hz')]], PRA, 0.22),
}

async def gen(text, voice, rate, pitch, out):
    c = edge_tts.Communicate(text, voice, rate=rate, pitch=pitch)
    await c.save(out)

async def build():
    for name, (lines, voice, gaps) in AUD.items():
        k = 0
        for li, segs in enumerate(lines):
            for txt, r, p in segs:
                await gen(txt, voice, r, p, f'{RD}/{name}_{k}.mp3'); k += 1
        print(name, 'segs', k)
    k = 0
    for line in LINES:
        for txt, r, p in line:
            await gen(txt, voice=MAD, rate=r, pitch=p, out=f'{RD}/ns_{k}.mp3'); k += 1
    print('main segs', k)

asyncio.run(build())

def load(path):
    raw = subprocess.run([FFX, '-i', path, '-f', 's16le', '-acodec', 'pcm_s16le',
                          '-ac', '1', '-ar', str(SR), '-'], capture_output=True).stdout
    seg = np.frombuffer(raw, dtype=np.int16).astype(np.float32) / 32768
    return seg

def trim(sig, th=0.01):
    idx = np.where(np.abs(sig) > th)[0]
    if len(idx) == 0: return sig
    a, b = idx[0], idx[-1]
    pad = int(0.04 * SR)
    return sig[max(0, a - pad):min(len(sig), b + pad)]

def assemble(spec, out_wav):
    buf = np.zeros(int(spec['total'] * SR), dtype=np.float32)
    for name, t0 in spec['items']:
        s = load(f'{RD}/{name}.mp3')
        i0 = int(t0 * SR); n2 = min(len(s), len(buf) - i0)
        if n2 > 0: buf[i0:i0 + n2] += s[:n2]
    sgn = np.sign(buf); ab = np.abs(buf); A = 0.6
    buf = np.where(ab <= A, buf, sgn * (A + (ab - A) * 0.2))
    pk = np.max(np.abs(buf))
    if pk > 0: buf *= 0.93 / pk
    with wave.open(out_wav, 'w') as wf:
        wf.setnchannels(1); wf.setsampwidth(2); wf.setframerate(SR)
        wf.writeframes((buf * 32767).astype(np.int16).tobytes())

# audition files: join segments with 0.28s phrase gap
info = {}
for name, (lines, voice, gaps) in AUD.items():
    segs = []
    k = 0
    for li, line in enumerate(lines):
        for txt, r, p in line:
            segs.append(trim(load(f'{RD}/{name}_{k}.mp3'))); k += 1
    out = np.zeros(1)
    for si, s in enumerate(segs):
        if si: out = np.concatenate([out, np.zeros(int(0.28 * SR))])
        out = np.concatenate([out, s])
    outf = f'{RD}/{name}.wav'
    with wave.open(outf, 'w') as wf:
        wf.setnchannels(1); wf.setsampwidth(2); wf.setframerate(SR)
        wf.writeframes((np.clip(out, -1, 1) * 32767).astype(np.int16).tobytes())
    info[name] = round(len(out) / SR, 2)

# main story track: phrases, 0.22s word-gap, 0.45s line-gap, start at 0.7 then voice-paced
t = 0.7
items = []
durs = []
kg = 0
for li, line in enumerate(LINES):
    t_line = t
    for pi, (txt, r, p) in enumerate(line):
        s = trim(load(f'{RD}/ns_{kg}.mp3')); kg += 1
        if pi > 0: t_line += 0.22
        items.append((f'ns_{kg-1}', t_line))
        t_line += len(s) / SR
    # to mp3 for repo audition
    durs.append(round(t_line - t, 2))
    if li < len(LINES) - 1:
        t = t_line + 0.95
    else:
        total = t_line + 2.4
spec = {'total': round(total, 2), 'items': [(n, round(x, 3)) for n, x in items]}
starts = [round(x, 2) for n, x in items if n.startswith('ns_') and x not in [y for yy in starts for y in [yy]]] if False else None
vstarts = []
prev = None
for n, x in items:
    if x != prev:
        vstarts.append(round(x, 2)); prev = x
print('voice starts:', vstarts)
json.dump(spec, open(f'{RD}/story_spec.json', 'w'), indent=1)
assemble(spec, f'{RD}/story_audio.wav')
print('voice line durations:', durs)
print('total', spec['total'])
print(info)
