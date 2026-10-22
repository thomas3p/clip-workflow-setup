# Clip Workflow Setup

ให้ **Codex หรือ Claude Code ช่วยทำคลิป** จากฟุตเทจของคุณ ตั้งแต่อ่านภาพ เขียนบท ลงเสียง จัด SFX/BGM และโมชั่นกราฟิก ไปจนถึงแพ็กตัดต่อหรือ Draft ที่แก้ต่อได้

## คัดลอกข้อความนี้ไปติดตั้งได้เลย

วางข้อความเดียวกันนี้ใน **Codex Desktop** หรือ **Claude Code**:

```text
ติดตั้ง Clip Workflow Setup จาก https://github.com/thomas3p/clip-workflow-setup
อ่านและทำตาม https://raw.githubusercontent.com/thomas3p/clip-workflow-setup/main/INSTALL.md
ตรวจว่าคุณกำลังทำงานใน Codex หรือ Claude Code แล้วเลือกขั้นตอนของแอปนั้น
ติดตั้ง workflow และเชื่อม CapCut ให้พร้อมใช้งาน ถ้าเป็น Claude Code ให้ใช้ adapter
ที่แปลงชุด CapCut ของ Codex เป็น Claude skills และ HTTP MCP ตามคู่มือ
รักษาการตั้งค่าและงานเดิม ไม่ขอข้อมูลที่มีแล้ว และให้ฉันล็อกอินผ่าน Browser เอง
ทดสอบเครื่องมือจริงก่อนรายงานว่าเชื่อมบัญชีสำเร็จ แล้วเริ่มใช้ workflow นี้ต่อ
```

เอเจนต์จะดาวน์โหลด repository ติดตั้ง skill และจัดการขั้นตอน CapCut ให้ เหลือการลงชื่อเข้าใช้/กดอนุญาตที่คุณทำใน Browser และการอนุมัติของแอปเมื่อจำเป็น

## แต่ละแอปติดตั้งอะไร

| ใช้ใน | Workflow | CapCut |
| --- | --- | --- |
| Codex Desktop | `~/.agents/skills/clip-workflow-setup` | ปลั๊กอินทางการล่าสุดและ OAuth ของ Codex |
| Claude Code | `~/.claude/skills/clip-workflow-setup` | Adapter จาก bundle ของ Codex: Claude skills + HTTP MCP ในโปรเจกต์ของคุณ และ OAuth ของ Claude |

Claude adapter แปลงการตั้งค่าและคำสั่งที่ขึ้นกับโฮสต์ ไม่คัดลอก token จาก Codex และไม่ต้องติดตั้ง Codex CLI การ์ด/Browser บางอย่างของ Codex มีข้อจำกัดต่างจาก Claude; adapter ใช้เครื่องมือที่โฮสต์มีจริงและไม่อ้างว่าเชื่อมสำเร็จจากแค่การสร้าง config

## เริ่มทำคลิป

ใน Codex ใช้ `$clip-workflow-setup` ใน Claude Code ใช้ `/clip-workflow-setup` แล้วบอกโฟลเดอร์ฟุตเทจและผลลัพธ์ เช่น:

```text
ทำคลิปสอนติดตั้งโปรแกรมจาก Screen Record ในโฟลเดอร์ที่ให้
เวอร์ชันหลักแนวนอน 16:9 และเวอร์ชันสั้นแนวตั้ง 9:16
ใช้เสียง WAV และมาสคอต MOV ที่มี ใส่ SFX เบา ๆ
ส่ง Draft ที่แก้ต่อได้กับพรีวิว ใช้ข้อมูลที่ให้แล้วและเริ่มงานต่อได้เลย
```

รองรับทั้งคลิปสินค้าและคลิปสอน/Screen Record มีข้อมูลต้นทาง style guide แผนฟุตเทจ บท เสียง และบันทึกบทเรียนแยกตาม workspace

## ติดตั้งด้วย Terminal

ถ้าต้องการติดตั้ง workflow เอง:

```sh
git clone https://github.com/thomas3p/clip-workflow-setup.git
cd clip-workflow-setup
python install.py --agent both
```

Windows ใช้ `py -3` แทน `python` ได้ หรือดับเบิลคลิก `INSTALL-WINDOWS.cmd` บน macOS/Linux อาจใช้ชื่อ `python3` ต้องมี Python 3.10 ขึ้นไป ตัวติดตั้ง workflow ไม่ต้องลงแพ็กเกจ Python เพิ่ม

```sh
python install.py --agent codex
python install.py --agent claude
python install.py --agent both --project "<โฟลเดอร์โปรเจกต์>"
python install.py --agent both --dry-run
```

คำสั่งเหล่านี้ติดตั้ง workflow ส่วนการติดตั้งและเชื่อม CapCut ให้ทำต่อด้วย [INSTALL.md](INSTALL.md) สำหรับ Claude ใช้ [คู่มือ adapter](references/claude-capcut-adapter.md)

## เครื่องมือเพิ่มเติมตามงาน

| งาน | เครื่องมือ |
| --- | --- |
| สแกนวิดีโอ แยกเฟรม ตรวจเสียง | `ffmpeg` และ `ffprobe` ใน PATH |
| Contact sheet | Pillow: `python -m pip install Pillow` |
| ลงเสียง | ไฟล์ VO ที่มี หรือ TTS ที่คุณเลือก |
| แปลงเป็นเสียงตัวเอง | Voice conversion เช่น Seed-VC 44K |
| มาสคอต / Motion graphic | MOV โปร่งใส, HyperFrames หรือเครื่องมือที่เหมาะกับงาน |

เอเจนต์ใช้เครื่องมือที่มีและจำเป็นกับคลิป ไม่ดาวน์โหลดโมเดลเสียงหรือสร้างสื่อแบบเสียเครดิตทุกครั้งโดยอัตโนมัติ

## Draft และพรีวิว

CapCut cloud MCP กับโปรเจกต์ Desktop เป็นคนละรูปแบบ workflow เลือกช่องทางตามโจทย์และเครื่องมือที่รองรับ การเขียน Desktop Draft ต้องตรวจรูปแบบของรุ่นนั้น สำรองงานและรักษา timeline/registry เดิม พรีวิว FFmpeg อาจแสดงฟอนต์/เอฟเฟกต์ต่างจาก CapCut การเปิดและ Export ผ่าน CapCut ต้องตรวจแยก

## อัปเดต

```sh
git pull --ff-only
python install.py --agent both --replace
```

skill เดิมถูกเก็บใน `.agents/skill-backups/` หรือ `.claude/skill-backups/` การอัปเดต CapCut ใช้ขั้นตอนเฉพาะโฮสต์ใน INSTALL.md

## ลิขสิทธิ์และข้อมูลส่วนตัว

workflow ใช้ [MIT License](LICENSE) ส่วนชุด CapCut ต้นฉบับดาวน์โหลดจากผู้เผยแพร่ตอนติดตั้ง ไม่รวม bundle ใน repository สาธารณะ เพราะต้นฉบับระบุ `UNLICENSED` ดู [Third-party notices](THIRD_PARTY_NOTICES.md) แต่ละเครื่องเชื่อมบัญชีเอง ไม่เก็บบัญชี OAuth เสียงอ้างอิงหรือฟุตเทจส่วนตัวใน repository

เอกสารอ้างอิง: [Codex skills](https://developers.openai.com/codex/skills), [Claude skills](https://code.claude.com/docs/en/skills), [Claude MCP](https://code.claude.com/docs/en/mcp)
