"""Measure loudness (integrated LUFS) of audio/video files and suggest a background-music volume.

usage: python loudness.py file1.mp3 file2.wav ... [--bgm-target -29] [--vo-target -16]

- A finished clip should land around -14 to -17 LUFS.
- A voice-over should be normalised to about -16 LUFS:
    ffmpeg -i vo.wav -af loudnorm=I=-16:TP=-1.5:LRA=11 -ar 48000 vo_norm.wav
- Background music sits about 13 dB under the voice. "volume" is the linear factor to type into the editing app
  (CapCut shows volume in dB: use the dB column there).
"""
import argparse, math, re, subprocess, sys

if hasattr(sys.stdout, 'reconfigure'): sys.stdout.reconfigure(encoding='utf-8')


def lufs(path):
    r = subprocess.run(['ffmpeg', '-hide_banner', '-nostdin', '-i', path, '-af', 'ebur128', '-f', 'null', '-'],
                       capture_output=True, text=True, encoding='utf-8', errors='replace')
    m = re.findall(r'I:\s+(-?[\d.]+) LUFS', r.stderr)
    return float(m[-1]) if m else None


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('files', nargs='+'); ap.add_argument('--bgm-target', type=float, default=-29.0)
    ap.add_argument('--vo-target', type=float, default=-16.0)
    a = ap.parse_args()
    print(f'{"ไฟล์":40} {"LUFS":>7} {"BGM volume":>11} {"BGM dB":>7}')
    for f in a.files:
        l = lufs(f)
        if l is None or l < -70: print(f'{f[-40:]:40} {"เงียบ/อ่านไม่ได้":>7}'); continue
        db = a.bgm_target - l; vol = 10 ** (db / 20)
        print(f'{f[-40:]:40} {l:7.1f} {vol:11.3f} {db:+7.1f}')
    print(f'\nเป้าหมาย: เสียงพากย์ {a.vo_target} LUFS, เพลงพื้นหลัง {a.bgm_target} LUFS, คลิปรวม -14 ถึง -17 LUFS')


if __name__ == '__main__':
    main()
