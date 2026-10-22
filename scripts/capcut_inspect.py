"""READ-ONLY look into CapCut desktop drafts. Never writes anything.

usage:
  python capcut_inspect.py                       list projects in the CapCut drafts folder
  python capcut_inspect.py "<project>"           timelines, tracks, durations and problems of one project
  python capcut_inspect.py "<project>" --timeline "<part of a timeline name>"
  add --root "<drafts folder>" if CapCut keeps drafts somewhere else

Problems reported per timeline: media files that no longer exist, gaps on the main video track, and segments that use
more of a file than the file has (overrun). If JSON is unreadable, use another editing route rather than guessing
the format. A successful check does not prove native CapCut compatibility or effect-cache availability.
"""
import argparse, json, os, platform, sys, time
from pathlib import Path

if hasattr(sys.stdout, 'reconfigure'): sys.stdout.reconfigure(encoding='utf-8')


def drafts_root(arg):
    if arg: return Path(arg).expanduser()
    if platform.system() == 'Windows':
        if not os.environ.get('LOCALAPPDATA'): raise SystemExit('LOCALAPPDATA is unavailable; specify --root')
        return Path(os.environ['LOCALAPPDATA']) / 'CapCut/User Data/Projects/com.lveditor.draft'
    if platform.system() == 'Darwin': return Path.home() / 'Movies/CapCut/User Data/Projects/com.lveditor.draft'
    raise SystemExit('Specify --root on this operating system; no CapCut desktop location is assumed')


def timelines(proj):
    pj = proj / 'Timelines' / 'project.json'
    if pj.exists():
        meta = json.loads(pj.read_text('utf-8-sig'))
        for t in meta.get('timelines', []):
            if not t.get('is_marked_delete'): yield t.get('name', t['id']), proj / 'Timelines' / t['id'] / 'draft_content.json'
    elif (proj / 'draft_content.json').exists():
        yield proj.name, proj / 'draft_content.json'


def check(name, f):
    try: d = json.loads(f.read_text('utf-8-sig'))
    except (UnicodeDecodeError, json.JSONDecodeError):
        print(f'  [{name}] อ่าน JSON ไม่ได้ — CapCut เวอร์ชันนี้อาจเข้ารหัส draft: ใช้โหมดวางแผนแทน'); return 1
    except FileNotFoundError:
        print(f'  [{name}] ไม่พบไฟล์ {f}'); return 1
    mats = d.get('materials', {})
    media = {m['id']: m for kind in ('videos', 'audios') for m in mats.get(kind, []) if m.get('id')}
    all_materials = [m for items in mats.values() if isinstance(items, list) for m in items if isinstance(m, dict) and m.get('id')]
    material_ids = {m['id'] for m in all_materials}
    paths = {m.get('path', '') for m in media.values() if m.get('path')}
    missing = sorted(p for p in paths if not p.startswith(('https://', 'http://')) and not Path(p).expanduser().exists())
    tracks = d.get('tracks', [])
    desc = ', '.join(f"{t.get('type')}{'(' + t['name'] + ')' if t.get('name') else ''}:{len(t.get('segments', []))}" for t in tracks)
    print(f"  [{name}] ยาว {d.get('duration', 0) / 1e6:.1f} วิ | tracks {desc}")
    problems = 0
    if len(material_ids) != len(all_materials):
        problems += 1; print('    material IDs ซ้ำ: ต้องตรวจ schema/refs ก่อนเขียน')
    if missing:
        problems += len(missing); print('    ไฟล์สื่อหาย:'); [print('     ', p) for p in missing[:10]]
    main = next((t for t in tracks if t.get('type') == 'video'), None)
    if main:
        segs = sorted(main.get('segments', []), key=lambda s: (s.get('target_timerange') or {}).get('start', 0)); end = 0
        for s in segs:
            target = s.get('target_timerange') or {}; st = target.get('start', 0)
            if st - end > 50_000: problems += 1; print(f'    ช่องว่างบนแทร็กหลัก {end / 1e6:.2f}–{st / 1e6:.2f} วิ')
            end = max(end, st + target.get('duration', 0))
        if d.get('duration', 0) - end > 50_000:
            problems += 1; print(f'    แทร็กหลักจบก่อน timeline: {end / 1e6:.2f}–{d["duration"] / 1e6:.2f} วิ (อาจตั้งใจให้มีแค่เสียง/กราฟิก)')
    for t in tracks:
        for s in t.get('segments', []):
            target = s.get('target_timerange') or {}
            if not target or target.get('start', -1) < 0 or target.get('duration', 0) <= 0:
                problems += 1; print(f'    ช่วงเวลา target ไม่ถูกต้อง: segment {s.get("id", "?")}')
            elif target['start'] + target['duration'] > d.get('duration', 0) + 50_000:
                problems += 1; print(f'    segment เลย duration ของ timeline: {s.get("id", "?")}')
            refs = ([s['material_id']] if s.get('material_id') else []) + (s.get('extra_material_refs') or [])
            dangling = [ref for ref in refs if ref not in material_ids]
            if dangling:
                problems += len(dangling); print(f'    material refs ไม่มีใน draft: {dangling}')
            m = media.get(s.get('material_id')); src = s.get('source_timerange') or {}
            if m and m.get('type') != 'photo' and m.get('duration') and src:
                over = src.get('start', 0) + src.get('duration', 0) - m['duration']
                if over > 50_000:
                    problems += 1; print(f"    ใช้เกินความยาวไฟล์ {over / 1e6:.2f} วิ: {Path(m.get('path', '?')).name} @ {s['target_timerange']['start'] / 1e6:.2f} วิ")
    return problems


def root_active_check(proj):
    """Check explicit known selectors, without inferring unknown version-specific schemas."""
    pj = proj / 'Timelines' / 'project.json'; root_content = proj / 'draft_content.json'
    if not pj.exists() or not root_content.exists(): return 0
    meta = json.loads(pj.read_text('utf-8-sig'))
    active = meta.get('main_timeline_id') or meta.get('active_timeline_id')
    if not active:
        print('  ไม่พบ selector ที่ helper รู้จัก: ยังไม่ได้ตรวจ root/active consistency'); return 0
    active_file = proj / 'Timelines' / active / 'draft_content.json'
    if not active_file.exists(): print('  ไม่พบไฟล์ active timeline ที่ selector อ้างถึง'); return 1
    if json.loads(root_content.read_text('utf-8-sig')) != json.loads(active_file.read_text('utf-8-sig')):
        print('  root และ active content ต่างกัน: ตรวจตาม schema ของเวอร์ชันก่อน commit'); return 1
    print('  root/active content ตรงกัน'); return 0


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('project', nargs='?'); ap.add_argument('--timeline'); ap.add_argument('--root')
    a = ap.parse_args()
    root = drafts_root(a.root)
    if not root.exists(): raise SystemExit(f'ไม่พบโฟลเดอร์ draft: {root}  (ระบุเองด้วย --root)')
    if not a.project:
        print(f'โฟลเดอร์ draft: {root}')
        for p in sorted((p for p in root.iterdir() if p.is_dir()), key=lambda p: p.stat().st_mtime, reverse=True):
            n = sum(1 for _ in timelines(p))
            print(f"  {time.strftime('%Y-%m-%d %H:%M', time.localtime(p.stat().st_mtime))}  {p.name}  ({n} timeline)")
        return
    proj = (root / Path(a.project).expanduser()).resolve()
    if not proj.exists(): raise SystemExit(f'ไม่พบโปรเจกต์ {proj}')
    try: total = root_active_check(proj)
    except (OSError, ValueError, TypeError, KeyError) as exc:
        raise SystemExit(f'อ่านโครงโปรเจกต์ไม่ได้ ({type(exc).__name__}); ไม่ได้แก้ไฟล์')
    count = 0
    for name, f in timelines(proj):
        if a.timeline and a.timeline not in name: continue
        total += check(name, f); count += 1
    print(f'\n{count} timeline, ปัญหา {total} จุด (สคริปต์นี้อ่านอย่างเดียว ไม่ได้แก้อะไร)')
    if not count: raise SystemExit(2)
    if total: raise SystemExit(1)


if __name__ == '__main__':
    main()
