"""Create a brand's clip-production workspace from answers.json (see references/setup-interview.md).

usage: python setup_workspace.py --answers answers.json --root "<workspace folder>" [--force]

Creates the folder tree, renders the templates in ../assets/templates, copies the helper scripts to <root>/tools/,
drafts the brand skill in <root>/brand-skill/<slug>-clips/SKILL.md and writes <root>/clip-workspace.json.
Existing files are never overwritten unless --force is given (then the old file is kept in a timestamped .bak).
"""
import argparse, datetime, json, re, shutil, sys
from pathlib import Path

if hasattr(sys.stdout, 'reconfigure'): sys.stdout.reconfigure(encoding='utf-8')
SKILL = Path(__file__).resolve().parent.parent
TPL = SKILL / 'assets' / 'templates'
MODES = {'plan': 'วางแผน: เอเจนต์ทำแพ็กงานตัดต่อ ผู้ใช้ตัดเองใน CapCut',
         'mcp': 'CapCut MCP: ใช้เครื่องมือที่ติดตั้งและ authorize แล้วตามความสามารถจริง (ไม่ใช่การควบคุม PC โดยอัตโนมัติ)',
         'capcut': 'Desktop Draft: เอเจนต์แก้ draft ที่ตรวจ schema แล้ว (ปิดแอป + backup ก่อน commit)',
         'plan-then-capcut': 'เริ่มแบบวางแผน แล้วค่อยเปิดโหมด CapCut เมื่อเครื่องมือพร้อม'}
DIRS = ['brand', 'footage/sheets', 'assets/sfx', 'assets/bgm', 'assets/memes', 'assets/images', 'logs',
        'projects/_template', 'tools', 'backups']


def posix(p):
    s = Path(p).as_posix()
    return s[4:] if s.startswith('//?/') else s          # Windows long-path prefix


def bullet(items, empty='-'):
    items = [str(i) for i in items if str(i).strip()]
    return '\n'.join(f'- {i}' for i in items) if items else empty


def render(text, values):
    for k, v in values.items(): text = text.replace('{{' + k + '}}', v)
    left = sorted(set(re.findall(r'\{\{([A-Z_]+)\}\}', text)))
    if left: raise SystemExit(f'template placeholders without a value: {left}')
    return text


def write(path, text, force, report):
    if path.exists() and not force:
        report.append(f'ข้าม (มีอยู่แล้ว): {path}'); return
    if path.exists():
        stamp = datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
        shutil.copy2(path, path.with_name(path.name + '.' + stamp + '.bak'))
    path.parent.mkdir(parents=True, exist_ok=True); path.write_text(text, 'utf-8'); report.append(f'สร้าง: {path}')


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--answers', required=True); ap.add_argument('--root', required=True)
    ap.add_argument('--force', action='store_true', help='overwrite existing files (keeps .bak copies)')
    a = ap.parse_args()
    ans = json.loads(Path(a.answers).read_text('utf-8-sig'))
    if not isinstance(ans, dict): raise SystemExit('answers.json must contain an object')
    slug = ans.get('slug', '').strip().lower()
    if not re.fullmatch(r'[a-z0-9](?:[a-z0-9-]{0,39}[a-z0-9])?', slug): raise SystemExit('slug must be 1-41 lowercase letters/digits, optionally interior "-" (e.g. "namprik-maeyai")')
    if not isinstance(ans.get('brand'), str) or not ans['brand'].strip(): raise SystemExit('answers.json needs non-empty "brand"')
    ans['brand'] = ans['brand'].strip()
    products = ans.get('products') or []
    if not isinstance(products, list) or any(not isinstance(p, dict) for p in products): raise SystemExit('products must be a list of objects')
    for key in ('platforms', 'footage_roots', 'never_show', 'assumed'):
        if ans.get(key) is not None and (not isinstance(ans[key], list) or any(not isinstance(v, str) for v in ans[key])):
            raise SystemExit(f'{key} must be a list of strings')
    for key in ('format', 'voice', 'music_policy', 'meme_policy', 'tone', 'cta'):
        if ans.get(key) is not None and not isinstance(ans[key], str): raise SystemExit(f'{key} must be a string')
    ids = set()
    for i, p in enumerate(products):
        p.setdefault('id', f'p{i + 1}')
        if not isinstance(p['id'], str) or not p['id'] or p['id'] in ids: raise SystemExit('product IDs must be non-empty unique strings')
        ids.add(p['id'])
        for key in ('name', 'size', 'notes'):
            if p.get(key) is not None and not isinstance(p[key], str): raise SystemExit(f'product {key} must be a string')
    mode = ans.get('mode', 'plan')
    if mode not in MODES: raise SystemExit(f'mode must be one of {list(MODES)}')
    content_type = ans.get('content_type', 'product')
    if content_type not in ('product', 'general'): raise SystemExit('content_type must be product or general')
    source_of_truth = 'brand/content-facts.md' if content_type == 'general' else 'brand/products.md'

    root = Path(a.root).expanduser().resolve(); report = []
    for d in DIRS: (root / d).mkdir(parents=True, exist_ok=True)
    today = datetime.date.today().isoformat()
    roots = ans.get('footage_roots') or []
    description = f"ระบบทำคลิปของ {ans['brand']} ด้วย Codex หรือ Claude Code และ CapCut: คอนเซปต์ สคริปต์ เสียงจริง แผนฟุตเทจ แพ็กตัดต่อหรือ Draft และตรวจผลงาน ใช้เมื่อต้องทำหรือแก้คลิปของช่องหรือแบรนด์นี้"
    V = {'BRAND': ans['brand'], 'BRAND_DESCRIPTION_YAML': json.dumps(description, ensure_ascii=False), 'SOURCE_OF_TRUTH': source_of_truth, 'SLUG': slug, 'DATE': today, 'ROOT': posix(root),
         'PLATFORMS': ', '.join(ans.get('platforms') or ['TikTok']), 'FORMAT': ans.get('format') or '9:16, 1080x1920, 30–45 วิ (สมมติฐาน)',
         'MODE_TEXT': MODES[mode], 'VOICE': ans.get('voice') or '(ยังไม่ได้เลือก)',
         'MUSIC': ans.get('music_policy') or 'CC0 (freesound) + ไลบรารี CapCut', 'MEMES': ans.get('meme_policy') or 'ไม่ใช้',
         'TONE': ans.get('tone') or '(ยังไม่ได้เลือก)', 'CTA': ans.get('cta') or ('(ตามโจทย์ ไม่มี CTA ขายสินค้า)' if content_type == 'general' else 'กดตะกร้าเลย'),
         'FOOTAGE_ROOTS': ', '.join(f'`{r}`' for r in roots) if roots else '(ยังไม่มีฟุตเทจ)',
         'NEVER_SHOW': ', '.join(ans.get('never_show') or []) or '(ยังไม่ได้ระบุ)',
         'ASSUMED': bullet(ans.get('assumed') or [], '- (ไม่มี)')}

    sec = (TPL / 'product-section.md.tmpl').read_text('utf-8')
    V['PRODUCT_SECTIONS'] = '\n'.join(render(sec, {'P_ID': p['id'], 'P_NAME': p.get('name', ''), 'P_SIZE': p.get('size', '') or '-',
                                                   'P_NOTES': p.get('notes', '') or '-'}) for p in products) or '(ยังไม่มีสินค้า)'
    V['FOOTAGE_SECTIONS'] = '\n'.join(
        f"## {p['id']} — {p.get('name', '')}\n\n### ใช้ได้\n\n| รหัส | เห็นอะไร | ช่วงที่ใช้ได้ (วิ) |\n|---|---|---|\n\n"
        f"### ต้องครอป\n\n| รหัส | ปัญหาที่ขอบภาพ | ซูม / (x, y) ที่ทดสอบแล้ว |\n|---|---|---|\n" for p in products)

    files = {'brand/products.md': 'products.md.tmpl', 'brand/style-guide.md': 'style-guide.md.tmpl',
             'footage/footage-map.md': 'footage-map.md.tmpl', 'logs/concepts-log.md': 'concepts-log.md.tmpl',
             'logs/lessons.md': 'lessons.md.tmpl', 'assets/licences.md': 'licences.md.tmpl',
             f'brand-skill/{slug}-clips/SKILL.md': 'brand-skill.SKILL.md.tmpl'}
    if content_type == 'general':
        del files['brand/products.md']
        write(root / source_of_truth, f'# ข้อมูลและขั้นตอนที่ตรวจได้: {ans["brand"]}\n\n'
              '| ข้อเท็จจริง/ขั้นตอน | แหล่งอ้างอิง/ไฟล์ | รุ่น/วันที่ตรวจ | สถานะ |\n'
              '|---|---|---|---|\n\n## รอยืนยัน\n\n## สิ่งที่ห้ามพูด/ห้ามโชว์\n\n' + V['NEVER_SHOW'] + '\n', a.force, report)
    for out, tpl in files.items(): write(root / out, render((TPL / tpl).read_text('utf-8'), V), a.force, report)
    write(root / 'projects/_template/production-pack.md', (TPL / 'production-pack.md').read_text('utf-8'), a.force, report)

    for s in sorted((SKILL / 'scripts').glob('*.py')):
        if s.name != 'setup_workspace.py': write(root / 'tools' / s.name, s.read_text('utf-8'), a.force, report)

    meta = {'brand': ans['brand'], 'slug': slug, 'created': today, 'mode': mode, 'content_type': content_type,
            'source_of_truth': source_of_truth, 'root': posix(root),
            'brand_skill': f'brand-skill/{slug}-clips', 'answers': ans}
    write(root / 'clip-workspace.json', json.dumps(meta, ensure_ascii=False, indent=2), a.force, report)

    print('\n'.join(report))
    print(f'\nเสร็จ: {root}')
    print(f'ขั้นต่อไป: เติม {source_of_truth} จากแหล่งจริง ใช้ร่าง brand-skill/{slug}-clips ได้ทันที; ถ้าติดตั้ง skill ใช้ .agents/skills (Codex) หรือ .claude/skills (Claude Code) ตามขอบเขตที่เลือก')


if __name__ == '__main__':
    main()
