"""Index video footage with ffprobe.

usage: python footage_index.py "<folder>" ["<folder2>" ...] --out footage/index.json

Writes index.json (and index.csv next to it): one entry per video with a short unique id (file name without extension),
absolute path, folder, duration (s), width/height as displayed (rotation applied), fps and rotation.
Prints a summary: file count, total minutes, very short files, and duplicate names that got a new id.
Read-only: footage files are never changed.
"""
import argparse, csv, json, subprocess, sys
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

if hasattr(sys.stdout, 'reconfigure'): sys.stdout.reconfigure(encoding='utf-8')
EXTS = {'.mp4', '.mov', '.m4v', '.mkv', '.avi', '.mts'}


def probe(path):
    r = subprocess.run(['ffprobe', '-v', 'error', '-show_entries',
                        'format=duration:stream=codec_type,width,height,r_frame_rate:stream_tags=rotate:stream_side_data=rotation',
                        '-of', 'json', str(path)], capture_output=True, text=True, encoding='utf-8', errors='replace')
    try: j = json.loads(r.stdout or '{}')
    except json.JSONDecodeError: j = {}
    v = next((s for s in j.get('streams', []) if s.get('codec_type') == 'video'), None)
    if not v: return None
    rot = 0
    for sd in v.get('side_data_list') or []:
        if 'rotation' in sd: rot = int(float(sd['rotation']))
    if not rot and v.get('tags', {}).get('rotate'): rot = int(v['tags']['rotate'])
    w, h = v.get('width', 0), v.get('height', 0)
    if abs(rot) % 180 == 90: w, h = h, w
    num, _, den = (v.get('r_frame_rate') or '0/1').partition('/')
    fps = round(float(num) / float(den or 1), 2) if float(den or 1) else 0
    return {'dur': round(float(j.get('format', {}).get('duration') or 0), 2), 'w': w, 'h': h, 'fps': fps, 'rot': rot}


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('folders', nargs='+'); ap.add_argument('--out', default='footage/index.json')
    a = ap.parse_args()
    files = sorted(p for f in a.folders for p in Path(f).expanduser().rglob('*') if p.suffix.lower() in EXTS and p.is_file())
    if not files: raise SystemExit('no video files found')
    with ThreadPoolExecutor(8) as ex: infos = list(ex.map(probe, files))
    out, seen, renamed = [], Counter(), []
    for p, info in zip(files, infos):
        if info is None: print(f'อ่านไม่ได้ (ข้าม): {p}'); continue
        base = p.stem; seen[base] += 1
        fid = base if seen[base] == 1 else f'{p.parent.name}-{base}' if seen[base] == 2 else f'{p.parent.name}-{base}-{seen[base]}'
        if fid != base: renamed.append(f'{p} -> {fid}')
        out.append({'id': fid, 'path': p.resolve().as_posix().removeprefix('//?/'), 'folder': p.parent.name, **info})
    dst = Path(a.out); dst.parent.mkdir(parents=True, exist_ok=True)
    dst.write_text(json.dumps(out, ensure_ascii=False, indent=1), 'utf-8')
    with open(dst.with_suffix('.csv'), 'w', newline='', encoding='utf-8-sig') as fh:
        w = csv.DictWriter(fh, fieldnames=['id', 'dur', 'w', 'h', 'fps', 'rot', 'folder', 'path']); w.writeheader(); w.writerows(out)
    print(f'{len(out)} ไฟล์, รวม {sum(o["dur"] for o in out) / 60:.1f} นาที -> {dst}')
    print('ขนาดภาพ (กว้างxสูง @fps):', dict(Counter(f'{o["w"]}x{o["h"]}@{o["fps"]}' for o in out)))
    short = [o['id'] for o in out if o['dur'] < 2]
    if short: print('สั้นกว่า 2 วิ:', ' '.join(short))
    if renamed: print('ชื่อซ้ำ ตั้งรหัสใหม่:\n  ' + '\n  '.join(renamed))


if __name__ == '__main__':
    main()
