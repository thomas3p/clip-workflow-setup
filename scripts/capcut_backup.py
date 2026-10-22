"""Back up one CapCut project folder before any change, and tell whether CapCut is running.

usage: python capcut_backup.py "<project>" [--to backups] [--root "<drafts folder>"]
       python capcut_backup.py --running          only report whether CapCut is open

Copies the whole project folder to <to>/<project>_<YYYYmmdd_HHMMSS>/ (the original is only read).
Writing into drafts while CapCut is open can lose work, so tools that write must call capcut_running() first.
"""
import argparse, platform, shutil, subprocess, sys, time, uuid
from pathlib import Path

if hasattr(sys.stdout, 'reconfigure'): sys.stdout.reconfigure(encoding='utf-8')
sys.path.insert(0, str(Path(__file__).parent))
from capcut_inspect import drafts_root  # noqa: E402


def capcut_running():
    if platform.system() == 'Windows':
        result = subprocess.run(['tasklist', '/FI', 'IMAGENAME eq CapCut.exe', '/FO', 'CSV', '/NH'],
                                capture_output=True, text=True, errors='replace', check=True)
        out = result.stdout
        return 'capcut.exe' in out.lower()
    result = subprocess.run(['pgrep', '-xi', 'capcut'], capture_output=True)
    if result.returncode not in (0, 1): raise RuntimeError('Could not determine whether CapCut is running')
    return result.returncode == 0


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('project', nargs='?'); ap.add_argument('--to', default='backups'); ap.add_argument('--root')
    ap.add_argument('--running', action='store_true')
    a = ap.parse_args()
    try: on = capcut_running()
    except (OSError, subprocess.CalledProcessError, RuntimeError) as exc:
        raise SystemExit(f'ตรวจ process ไม่ได้ ({type(exc).__name__}); ไม่ได้สำรองหรือเขียน Draft')
    if a.running or not a.project:
        print('CapCut เปิดอยู่' if on else 'CapCut ปิดอยู่'); return
    src = (drafts_root(a.root) / Path(a.project).expanduser()).resolve()
    if not src.exists(): raise SystemExit(f'ไม่พบโปรเจกต์ {src}')
    if not src.is_dir(): raise SystemExit('project must be a directory')
    dst = Path(a.to).expanduser().resolve() / f"{src.name}_{time.strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:8]}"
    if dst == src or src in dst.parents: raise SystemExit('Backup destination must be outside the source project')
    shutil.copytree(src, dst)
    size = sum(f.stat().st_size for f in dst.rglob('*') if f.is_file()) / 1e6
    print(f'backup แล้ว: {dst} ({size:.1f} MB)')
    if on: print('คำเตือน: CapCut ยังเปิดอยู่ — สำเนาอาจไม่สอดคล้อง ต้องสำรองใหม่หลังบันทึกและปิดก่อนเขียน draft')


if __name__ == '__main__':
    main()
