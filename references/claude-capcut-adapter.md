# ปรับ CapCut สำหรับ Claude Code

ตัว adapter สร้าง wrapper skills และ HTTP MCP config จาก official bundle ที่ดาวน์โหลดไว้บนเครื่อง ไม่รัน Codex ไม่ทำ OAuth และไม่ใช้ credentials ของ Codex ร่วมกับ Claude

ใช้ Python 3.10+ จากโฟลเดอร์ repo ที่ clone มา โดยระบุ project ที่จะทำคลิปจริง:

```powershell
python scripts/adapt_capcut_claude.py --source "$HOME/.codex/plugin-marketplaces/CapCut" --project "C:/work/my-clips" --dry-run
python scripts/adapt_capcut_claude.py --source "$HOME/.codex/plugin-marketplaces/CapCut" --project "C:/work/my-clips"
```

หากใช้ Claude อย่างเดียว ให้ดาวน์โหลด official CapCut bundle ตาม INSTALL.md เก็บไว้นอก project เป้าหมาย แล้วส่งพาธ marketplace root หรือโฟลเดอร์ `codex` ผ่าน `--source` ไม่จำเป็นต้องติดตั้งหรือ login Codex

สิ่งที่สร้าง:

- `.claude/skills/capcut-stdraft-builder`: Python atomic functions แก้และตรวจ STDraft ในเครื่อง
- `.claude/skills/capcut-upload`: ขั้นตอน upload ที่เปลี่ยนวิธีเรียก host และหยุดเมื่อไม่มีช่อง stdin ที่ปลอดภัย
- `.claude/skills/capcut-video-editing`: route rough cut / captions / post-editing พร้อมตรวจเครื่องมือที่มี
- `.claude/skills/capcut-web-collaborative-editing`: session, version check, cloud save และรับมือ conflict
- `.mcp.json`: เฉพาะสอง canonical CapCut HTTPS endpoints แบบ Claude `type: http` และ `headers`; คง unrelated servers/config เดิม

ไฟล์ upstream เดิมอยู่ใน `references/original/` ของแต่ละ wrapper โดย paths ของ scripts/imports ภายในคงเดิม ให้เริ่มจาก wrapper ก่อนอ่านต้นฉบับ เพราะคำสั่ง Codex/auth/browser ในต้นฉบับต้องใช้คำอธิบาย host adaptation แทน Sibling links ที่ย้ายตำแหน่งแล้วให้เปิด wrapper คู่กันตามชื่อใน host guide ไม่ตามลิงก์ `mcp-auth` เดิม

ไฟล์ต่างจากเดิมจะไม่ถูกเขียนทับ ใช้ `--replace` เมื่อตั้งใจเปลี่ยน โดยสำรองต้นฉบับไว้นอก discovery ที่ `.claude/skill-backups/` ก่อน และรักษา config ของ server อื่นไว้ ห้ามนำสำเนา upstream หรือ backup ซึ่งอาจมี config ส่วนตัวไป commit แจกต่อ

## เปิดใช้และตรวจจริง

1. เปิด Claude Code ใน project เป้าหมาย ยอมรับ workspace trust และตรวจ/อนุมัติ project `.mcp.json` ตาม UI ของ Claude
2. พิมพ์ `/mcp` แล้ว authenticate เฉพาะ `capcut_creation` ผ่าน OAuth ของ Claude ไม่รัน `capcut-login.mjs`, `codex app-server` หรือ login `capcut_creation_resource`
3. ตรวจสถานะด้วย `/mcp` หรือ `claude mcp get capcut_creation` จากนั้นให้ agent discover และเรียก `search_capcut_material` ด้วย `type: font`, `prompt: font`, `top_n: 1` เพื่อทดสอบ protected read จริง
4. หาก OAuth discovery/redirect/region/server ไม่รองรับ ให้รายงานข้อความผิดพลาดที่ปลอดภัยและหยุด ห้ามยืม cookies/tokens จาก Codex หรือให้ผู้ใช้ส่ง credentials

การสร้าง config สำเร็จยังไม่พิสูจน์ว่า OAuth สำเร็จ ผล font search สำเร็จพิสูจน์แค่ protected read ไม่พิสูจน์ upload, cards, save, preview หรือ export

## ขอบเขตที่ต้องตรวจตาม host

- Python local builder ใช้ stdlib และทำงานได้โดยไม่ login แต่ STDraft เป็น cloud interchange format ไม่ใช่ `draft_content.json` ของ CapCut PC
- Upload ใช้ Node.js 14+ และ ticket อายุสั้นผ่าน TTY/stdin ที่ไม่แสดงค่า หาก Claude host ไม่มี secure process bridge ให้หยุดก่อนขอ ticket ห้ามใส่ ticket ใน Bash command, heredoc, env, ไฟล์ชั่วคราวหรือแชต ใช้ media ที่อัปโหลดแล้วหรือให้ผู้ใช้อัปโหลดใน CapCut แทน
- MCP Apps/cards และ browser bridge ของ Codex ไม่ได้ติดมากับ HTTP config หากขั้นตอนต้องใช้ renderer แต่ host ไม่มี ให้หยุดขั้นตอนนั้นพร้อมบอก capability ที่ขาด ไม่สร้าง card responses หรือการอนุมัติค่าใช้จ่ายขึ้นเอง
- Cloud save ใช้ session/version checks เดิมและส่ง exact editor link หลังสำเร็จ ถ้าไม่มี browser tool ให้บอกว่ายังไม่ได้ตรวจภาพจริง ไม่อ้างว่า export หรือควบคุม CapCut PC ได้
- ไม่ติดตั้ง Codex-only `mcp-auth`, template-search หรือ media-generation workflow ไม่สัญญาว่า plugin ทางการรองรับ Claude ครบทุกความสามารถ

เอกสารทางการ: [Claude skills](https://code.claude.com/docs/en/skills), [HTTP MCP และ OAuth](https://code.claude.com/docs/en/mcp)
