"""Stills of a finished (or preview) video every N seconds, tiled with timestamps, for checking a clip by eye.

usage: python stills.py clip.mp4 [--every 1.25] [--out clip_stills.jpg] [--cols 10]

Look at every tile: does the picture match what is said, is any other product/brand in frame, do captions fit,
do memes cover a face or the product, is the end card complete. Needs ffmpeg and Pillow.
"""
import argparse, os, subprocess, sys, tempfile
from pathlib import Path

if hasattr(sys.stdout, 'reconfigure'): sys.stdout.reconfigure(encoding='utf-8')
try:
    from PIL import Image, ImageDraw, ImageFont
except ImportError:
    raise SystemExit('ต้องติดตั้ง Pillow ก่อน: pip install pillow')


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('video'); ap.add_argument('--every', type=float, default=1.25); ap.add_argument('--out')
    ap.add_argument('--cols', type=int, default=10); ap.add_argument('--width', type=int, default=162)
    a = ap.parse_args()
    v = Path(a.video); out = Path(a.out) if a.out else v.with_name(v.stem + '_stills.jpg')
    tmp = tempfile.mkdtemp()
    subprocess.run(['ffmpeg', '-nostdin', '-v', 'error', '-i', str(v), '-vf', f'fps=1/{a.every},scale={a.width}:-2',
                    os.path.join(tmp, '%04d.jpg')], check=True)
    fs = sorted(Path(tmp).glob('*.jpg'))
    if not fs: raise SystemExit('ไม่ได้ภาพเลย (ไฟล์สั้นเกินหรือเปิดไม่ได้)')
    w, h = Image.open(fs[0]).size; cols = min(a.cols, len(fs)); rows = (len(fs) + cols - 1) // cols
    S = Image.new('RGB', (w * cols, h * rows), 'black'); d = ImageDraw.Draw(S)
    try: F = ImageFont.truetype('C:/Windows/Fonts/tahoma.ttf', 13)
    except OSError: F = ImageFont.load_default()
    for k, f in enumerate(fs):
        x, y = (k % cols) * w, (k // cols) * h; S.paste(Image.open(f), (x, y))
        d.rectangle((x, y + h - 16, x + 40, y + h), fill='black'); d.text((x + 3, y + h - 15), f'{k * a.every:.1f}', font=F, fill='yellow')
    S.save(out, quality=88); print(f'{len(fs)} ภาพ -> {out}')


if __name__ == '__main__':
    main()
