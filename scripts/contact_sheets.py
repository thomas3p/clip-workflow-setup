"""Contact sheets of indexed footage: 4 frames per file (10/35/60/85 %), 2 files per row, 10 files per sheet.

usage: python contact_sheets.py footage/index.json --out footage/sheets [--ids C0001 C0002 ...] [--per-sheet 10]

Each file gets a label (id + length) and every frame shows its time in seconds, so a shot can be picked as id@seconds.
Frames are shown upright (ffmpeg applies the rotation). Needs ffmpeg and Pillow (pip install pillow).
"""
import argparse, json, subprocess, sys, tempfile
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

if hasattr(sys.stdout, 'reconfigure'): sys.stdout.reconfigure(encoding='utf-8')
try:
    from PIL import Image, ImageDraw, ImageFont
except ImportError:
    raise SystemExit('ต้องติดตั้ง Pillow ก่อน: pip install pillow')

FW, FH, PCTS = 240, 320, (.10, .35, .60, .85)


def font(size):
    for f in ('C:/Windows/Fonts/tahoma.ttf', '/System/Library/Fonts/Supplemental/Arial.ttf', '/Library/Fonts/Arial.ttf',
              '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf'):
        try: return ImageFont.truetype(f, size)
        except OSError: pass
    return ImageFont.load_default()


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('index'); ap.add_argument('--out', default='footage/sheets'); ap.add_argument('--ids', nargs='*')
    ap.add_argument('--per-sheet', type=int, default=10); ap.add_argument('--min-dur', type=float, default=1.0)
    a = ap.parse_args()
    idx = [o for o in json.loads(Path(a.index).read_text('utf-8')) if o['dur'] >= a.min_dur and (not a.ids or o['id'] in a.ids)]
    if not idx: raise SystemExit('nothing to draw')
    tmp = Path(tempfile.mkdtemp()); out = Path(a.out); out.mkdir(parents=True, exist_ok=True)

    def grab(job):
        k, o, j = job; t = o['dur'] * PCTS[j]; f = tmp / f'{k}_{j}.jpg'
        subprocess.run(['ffmpeg', '-nostdin', '-v', 'error', '-y', '-ss', f'{t:.2f}', '-i', o['path'], '-frames:v', '1', '-vf',
                        f'scale={FW - 2}:{FH - 2}:force_original_aspect_ratio=decrease,pad={FW}:{FH}:-1:-1', str(f)])
        return f
    with ThreadPoolExecutor(8) as ex: list(ex.map(grab, [(k, o, j) for k, o in enumerate(idx) for j in range(4)]))

    F, Fs = font(20), font(17); per = a.per_sheet; n = 0
    for s in range(0, len(idx), per):
        grp = idx[s:s + per]; S = Image.new('RGB', (FW * 8, FH * ((len(grp) + 1) // 2)), 'white'); d = ImageDraw.Draw(S)
        for j, o in enumerate(grp):
            k = s + j; x0, y0 = (j % 2) * FW * 4, (j // 2) * FH
            for q, p in enumerate(PCTS):
                f = tmp / f'{k}_{q}.jpg'
                if f.exists(): S.paste(Image.open(f), (x0 + q * FW, y0))
                d.text((x0 + q * FW + 5, y0 + FH - 26), f'{o["dur"] * p:.1f}s', font=Fs, fill='yellow', stroke_width=2, stroke_fill='black')
            lab = f'{o["id"]}  {o["dur"]:.0f}s'; d.rectangle((x0, y0, x0 + 12 * len(lab) + 10, y0 + 26), fill='black')
            d.text((x0 + 5, y0 + 2), lab, font=F, fill='yellow'); d.line((x0, y0, x0, y0 + FH), fill='red', width=3)
        p = out / f'sheet_{s // per:02d}.jpg'; S.save(p, quality=88); n += 1
    print(f'{len(idx)} ไฟล์ -> {n} แผ่น ใน {out}')


if __name__ == '__main__':
    main()
