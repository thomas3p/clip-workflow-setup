"""Check frames (and crops) of chosen shots: 6 per row, labelled.

usage: python frame_check.py out.jpg C0123:4.5 C0123:4.5:1.4:0:0.4 "D:/clips/a.mp4:2" [--index footage/index.json]

Each item is  <id or file>:<seconds>[:<zoom>:<x>:<y>]
  zoom 1 = the whole frame, 1.4 = 140 % (shows 1/1.4 of the width and height)
  x, y move the view in half-frame units: x > 0 shows more of the right side, y > 0 shows more of the bottom
To reproduce a crop in the editing app: set the same zoom, then drag the picture until it matches the check image.
Needs ffmpeg and Pillow.
"""
import argparse, json, os, subprocess, sys, tempfile
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

if hasattr(sys.stdout, 'reconfigure'): sys.stdout.reconfigure(encoding='utf-8')
try:
    from PIL import Image, ImageDraw, ImageFont
except ImportError:
    raise SystemExit('ต้องติดตั้ง Pillow ก่อน: pip install pillow')
W, H = 300, 420


def num(s):
    try: float(s); return True
    except ValueError: return False


def parse(item):
    parts = item.rsplit(':', 4)
    if len(parts) == 5 and all(num(p) for p in parts[1:]): return parts[0], *map(float, parts[1:])
    src, t = item.rsplit(':', 1)
    return src, float(t), 1.0, 0.0, 0.0


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('out'); ap.add_argument('items', nargs='+'); ap.add_argument('--index', default='footage/index.json')
    a = ap.parse_args()
    idx = {o['id']: o['path'] for o in json.loads(Path(a.index).read_text('utf-8'))} if Path(a.index).exists() else {}
    jobs = []
    for it in a.items:
        src, t, z, x, y = parse(it); path = idx.get(src, src)
        if not Path(path).exists(): raise SystemExit(f'ไม่พบ {src} (ไม่มีใน index และไม่ใช่ไฟล์)')
        jobs.append((it, path, t, max(z, 1.0), x, y))
    tmp = tempfile.mkdtemp()

    def grab(k):
        it, path, t, z, x, y = jobs[k]; f = os.path.join(tmp, f'{k}.jpg'); vf = ''
        if z > 1.0 or x or y:
            cx, cy = .5 + x / 2, .5 + y / 2; half = .5 / z
            x0, y0 = min(max(cx - half, 0), 1 - 2 * half), min(max(cy - half, 0), 1 - 2 * half)
            vf = f'crop=iw/{z}:ih/{z}:iw*{x0:.4f}:ih*{y0:.4f},'
        subprocess.run(['ffmpeg', '-nostdin', '-v', 'error', '-y', '-ss', f'{t:.2f}', '-i', path, '-frames:v', '1', '-vf',
                        vf + f'scale={W - 2}:{H - 2}:force_original_aspect_ratio=decrease,pad={W}:{H}:-1:-1', f])
        return f
    with ThreadPoolExecutor(6) as ex: fs = list(ex.map(grab, range(len(jobs))))
    try: F = ImageFont.truetype('C:/Windows/Fonts/tahoma.ttf', 15)
    except OSError: F = ImageFont.load_default()
    n = 6; S = Image.new('RGB', (W * min(n, len(fs)), H * ((len(fs) + n - 1) // n)), 'white'); d = ImageDraw.Draw(S)
    for k, (f, job) in enumerate(zip(fs, jobs)):
        x0, y0 = (k % n) * W, (k // n) * H
        if os.path.exists(f): S.paste(Image.open(f), (x0, y0))
        lab = Path(job[0]).name if len(job[0]) > 40 else job[0]
        d.rectangle((x0, y0, x0 + 8 * len(lab) + 8, y0 + 20), fill='black'); d.text((x0 + 4, y0 + 2), lab, font=F, fill='yellow')
    Path(a.out).parent.mkdir(parents=True, exist_ok=True); S.save(a.out, quality=90); print(a.out, S.size)


if __name__ == '__main__':
    main()
