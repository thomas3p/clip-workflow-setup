# Clip Workflow Setup

ระบบให้ **Codex หรือ Claude Code ช่วยทำคลิป** ตั้งแต่จัดข้อมูลแบรนด์ อ่านฟุตเทจ เขียนบท เตรียมเสียงพากย์ จัดภาพและเสียงประกอบ ไปจนถึงแพ็กตัดต่อหรือ Draft ที่แก้ต่อได้

ใช้ workflow เดียวกันได้ทั้งสองแอป เลือกทำงานด้วยเครื่องมือที่ติดตั้งและเชื่อมต่ออยู่จริง ไม่จำเป็นต้องใช้บริการ AI ทุกตัว

## เริ่มใช้ใน 3 ขั้นตอน

1. ดาวน์โหลด repository นี้จาก GitHub ด้วย **Code → Download ZIP** แล้วแตกไฟล์ หรือใช้ `git clone` กับ URL ของ repository นี้
2. เปิด Terminal ในโฟลเดอร์ที่แตกไฟล์ แล้วรัน:

   ```sh
   python install.py --agent both
   ```

   Windows ดับเบิลคลิก `INSTALL-WINDOWS.cmd` ได้เช่นกัน บน macOS/Linux ใช้ `python3` แทน `python` หากเครื่องใช้ชื่อนั้น ต้องมี Python 3.10 ขึ้นไป ตัวติดตั้งใช้เฉพาะ standard library ไม่ต้อง `pip install`

3. เปิดแชตใหม่ในแอปที่ต้องการ แล้วส่ง:

   **Codex**

   ```text
   ใช้ $clip-workflow-setup ช่วยวางระบบทำคลิปให้แบรนด์ของฉัน
   โฟลเดอร์งานคือ <โฟลเดอร์ที่ฉันเลือก> ฟุตเทจอยู่ที่ <โฟลเดอร์ฟุตเทจ>
   ใช้ข้อมูลที่ให้ไปแล้ว ถามเฉพาะสิ่งที่ยังขาด แล้วเริ่มทำคลิปทดลอง 1 คลิป
   ```

   **Claude Code**

   ```text
   /clip-workflow-setup
   ช่วยวางระบบทำคลิปให้แบรนด์ของฉัน โฟลเดอร์งานคือ <โฟลเดอร์ที่ฉันเลือก>
   ฟุตเทจอยู่ที่ <โฟลเดอร์ฟุตเทจ> ใช้ข้อมูลที่มีแล้วและเริ่มทำคลิปทดลอง 1 คลิป
   ```

## เลือกแอปและตำแหน่งติดตั้ง

```sh
python install.py --agent codex
python install.py --agent claude
python install.py --agent both --project "<โฟลเดอร์โปรเจกต์>"
python install.py --agent both --dry-run
```

| แอป | ติดตั้งสำหรับผู้ใช้ | ติดตั้งเฉพาะโปรเจกต์ |
| --- | --- | --- |
| Codex | `~/.agents/skills/clip-workflow-setup/` | `<project>/.agents/skills/clip-workflow-setup/` |
| Claude Code | `~/.claude/skills/clip-workflow-setup/` | `<project>/.claude/skills/clip-workflow-setup/` |

ตัวติดตั้งคัดลอกเฉพาะ skill, references, templates และสคริปต์ workflow ไม่ติดตั้ง CapCut, ไม่เชื่อมบัญชี และไม่แก้การตั้งค่า MCP ถ้ามีไฟล์เดิมที่เหมือนกันจะข้ามให้ ถ้าต่างกันจะหยุดก่อนเขียนทับ

อัปเดตจาก repository รุ่นใหม่ด้วย `python install.py --agent both --replace` ตัวติดตั้งจะเก็บสำเนา skill เดิมไว้ใน `.agents/skill-backups/` หรือ `.claude/skill-backups/` และแจ้งพาธจริง แยกจากโฟลเดอร์ที่แอปค้นหา skill เพื่อไม่ให้โหลดสำเนาซ้ำ ไม่ต้องลบ skill เดิมก่อน

## เชื่อม CapCut ใน Codex

ให้ Codex Desktop ทำตามคู่มือทางการล่าสุด ส่งข้อความนี้ในแชตของ Codex:

```text
Download and read https://sf16-sg.tiktokcdn.com/obj/eden-sg/962370eh7nupenuhbo/capcut_codex_plugin/SKILL.md, then follow it exactly to install and authorize the CapCut plugin.
เมื่อติดตั้งและเชื่อมบัญชีสำเร็จ ให้ทำงานต่อด้วย $clip-workflow-setup
```

ขั้นตอนติดตั้งอ้างอิง [คู่มือทางการของ CapCut](https://sf16-sg.tiktokcdn.com/obj/eden-sg/962370eh7nupenuhbo/capcut_codex_plugin/SKILL.md) ที่ดึงใหม่ในแต่ละรอบ ไม่ใช้ไฟล์คู่มือติดตั้งเก่าจาก repository นี้ รุ่นที่ตรวจระหว่างเตรียมชุดนี้คือ **0.2.5 วันที่ 23 ตุลาคม 2026** ซึ่งไม่ใช่การรับประกันว่าเป็นรุ่นล่าสุดตลอดไป

ลงชื่อเข้าใช้และกดอนุญาตใน Browser ของ Codex ข้อมูลบัญชีอยู่ในระบบของแอป ไม่ต้องส่งรหัสผ่าน คุกกี้ หรือ token ให้เอเจนต์ การติดตั้งสำเร็จ การเชื่อมบัญชีสำเร็จ และการทำงานจริงสำเร็จเป็นคนละสถานะ ต้องมีผลทดสอบเครื่องมือที่ใช้บัญชีจึงจะยืนยันว่าใช้งานได้

หากเคยเชื่อมแล้ว ให้ตรวจการเชื่อมต่อก่อน ไม่ต้องติดตั้งซ้ำทุกครั้ง และไม่ต้องเชื่อม OAuth ให้ `capcut_creation_resource`

## ใช้กับ Claude Code

workflow และสคริปต์ local ของชุดนี้ใช้กับ Claude Code ได้ เมื่อติดตั้งแล้วเรียก `/clip-workflow-setup` ได้ตามปกติ

**CapCut official bundle ที่อ้างอิงในชุดนี้เป็นปลั๊กอินสำหรับ Codex** มี helper สำหรับ Codex App Server และการ์ดที่ขึ้นกับโฮสต์ จึงไม่คัดลอก configuration ของ Codex ไปใส่ Claude โดยอัตโนมัติ และยังไม่ได้ยืนยัน OAuth/การ์ดของ CapCut ผ่าน Claude Code จริง

Claude ทำขั้นตอนอ่านฟุตเทจ เขียนบท จัดเสียง เตรียมแพ็กตัดต่อ และทำงานกับ Desktop Draft เมื่อมีตัวแก้ Draft ที่รองรับรูปแบบนั้นได้ หากมี CapCut MCP integration ที่รองรับ Claude และเชื่อมต่ออยู่ ให้ตรวจเครื่องมือจริงก่อนเลือกโหมด cloud มิฉะนั้นใช้แพ็กตัดต่อหรือโหมด local ที่เหมาะกับงาน

อ่านเอกสารการค้นหา skill ของ [Codex](https://developers.openai.com/codex/skills) และ [Claude Code](https://code.claude.com/docs/en/skills) ส่วนการเชื่อมบริการภายนอกดู [Claude MCP](https://code.claude.com/docs/en/mcp)

## Workflow ที่ได้

1. อ่านบริบทและข้อมูลเดิม ถามข้อมูลที่ขาดเป็นชุดสั้น ๆ
2. สร้าง workspace, ข้อมูลสินค้า, style guide, แผนฟุตเทจ และบันทึกสิทธิ์สื่อ
3. ดูฟุตเทจจริง แยกช่วงที่ใช้ได้ และเลือกคอนเซปต์ตามโจทย์
4. เขียนบทและเตรียม VO ด้วยบริการที่ผู้ใช้เลือก จับเวลาจากไฟล์เสียงจริงก่อนจัด timeline ขั้นสุดท้าย
5. ประกอบฟุตเทจ ซับ SFX/BGM และ motion graphic ตามความจำเป็น
6. ตรวจภาพ จุดตัด ระดับเสียง และไฟล์สื่อ ส่งผลที่ตรวจสอบได้พร้อมสถานะงาน

เลือกได้ 3 รูปแบบ: **แพ็กตัดต่อ**, **CapCut cloud MCP**, หรือ **Desktop Draft** โดย cloud draft กับไฟล์โปรเจกต์ CapCut PC เป็นคนละรูปแบบ การสร้างพรีวิวด้วย FFmpeg ก็ยังไม่ใช่การ Export ผ่าน CapCut จริง

เสียง AI Studio, การแปลงเสียงด้วย Seed-VC 44K, มาสคอต Talking Head และ HyperFrames เป็นตัวเลือก ใช้เมื่อโจทย์ต้องการและเครื่องมีเครื่องมือพร้อม ไม่ติดตั้งโมเดลขนาดใหญ่หรือเจนเสียงใหม่ทุกงานโดยอัตโนมัติ

## ต้องเตรียมอะไรบ้าง

| สิ่งที่ทำ | สิ่งที่ต้องมี |
| --- | --- |
| ติดตั้ง workflow / สร้าง workspace | Python 3.10+ และ Codex หรือ Claude Code |
| อ่านข้อมูลวิดีโอ / แยกเฟรม / วัดเสียง | `ffmpeg` และ `ffprobe` ใน PATH |
| Contact sheet | Pillow: `python -m pip install Pillow` |
| CapCut cloud | ปลั๊กอินทางการใน Codex และบัญชีที่เชื่อมสำเร็จ |
| แก้ Draft บนเครื่อง | CapCut Desktop และตัวแก้ Draft ที่รองรับ schema ของรุ่นนั้น |
| TTS / Voice conversion / Motion graphic | เครื่องมือที่เลือกสำหรับงานนั้น พร้อม runtime/โมเดลของเครื่องมือเอง |

สคริปต์ `capcut_backup.py` และ `capcut_inspect.py` ช่วยสำรองและตรวจข้อมูล ไม่ใช่ตัวตัดต่อหรือรับประกันว่าเขียน Draft ของ CapCut ทุกรุ่นได้ หากยังไม่มีตัวแก้ที่รองรับ ให้ส่งแพ็กงานตัดต่อและแจ้งข้อจำกัดตามจริง

## ตัวอย่างสั่งงาน

```text
ใช้ workflow นี้ทำคลิปสอนติดตั้งโปรแกรมจาก Screen Record ที่ให้
แนวนอน 16:9 มีเวอร์ชันสั้น 9:16 เพิ่มอีกหนึ่งคลิป
ใช้เสียง WAV ที่แนบ ถ้าต้องแปลงเสียงให้ใช้ Seed-VC preset ที่มีอยู่
ใส่มาสคอต MOV โปร่งใสและ SFX เบา ๆ แล้วส่ง Draft ที่แก้ต่อได้กับพรีวิว
```

```text
ทำคลิปขายสินค้านี้ 3 คลิป แนวตั้ง 30–45 วินาที
ข้อมูลสินค้ามีใน brand/products.md ฟุตเทจอยู่ใน footage/
ไม่ต้องถามข้อมูลที่มีแล้ว ให้เลือกคอนเซปต์จาก footage จริง
```

## นำขึ้น GitHub

โฟลเดอร์นี้คือ source ของ workflow ที่พร้อมนำไปสร้าง repository ใหม่ ยังไม่ผูกกับ URL หรือบัญชี GitHub ของใคร และตัวติดตั้งไม่มีขั้นตอน publish อัตโนมัติ

ในเครื่องที่เตรียมชุดนี้ สำเนาปลั๊กอินตามคำขออยู่ที่ `vendor/CapCut/` ซึ่งเก็บเนื้อหาจาก marketplace เดิมไว้ครบ **แต่ถูกแยกออกจาก Git และ public ZIP** เพราะ manifest ทางการระบุ `UNLICENSED` ดู [Third-party notices](THIRD_PARTY_NOTICES.md) ผู้ติดตั้งคนอื่นรับปลั๊กอินจาก CapCut โดยตรงตาม prompt ด้านบน

สร้าง ZIP สำหรับแชร์เฉพาะ workflow ได้ด้วย:

```sh
python package_release.py
```

ไฟล์อยู่ที่ `dist/clip-workflow-setup.zip` ไม่รวม vendor, บัญชี, ฟุตเทจ, เสียงอ้างอิง หรือโปรเจกต์ลูกค้า ตรวจรายชื่อไฟล์ด้วย `python package_release.py --list` ได้ก่อนสร้าง

วิธีง่ายผ่านเว็บ: สร้าง repository เปล่าบน GitHub แตก public ZIP แล้วเลือก **Add file → Upload files** เพื่ออัปโหลดไฟล์และโฟลเดอร์ข้างใน `clip-workflow-setup/` ให้ `README.md` และ `SKILL.md` อยู่ที่ราก repository ไม่ใช่อัปโหลด ZIP อย่างเดียว หากใช้ Git ให้ทำตามคำสั่งของ repository ใหม่และใช้ `.gitignore` ที่ให้มา เก็บงานลูกค้าและข้อมูลบัญชีนอก source ของ skill

## ตรวจชุดก่อนแจก

```sh
python -m unittest discover -s tests -v
python -m unittest discover -s evals -p "test_*.py" -v
python install.py --agent both --dry-run
python package_release.py --list
```

ชุดทดสอบตรวจตัวติดตั้งและสคริปต์ที่เกี่ยวข้อง ไม่ยืนยันการเปิด/Export CapCut หรือการล็อกอิน Claude จากเครื่องของผู้รับ ผู้รับควรลองคลิปสั้นหนึ่งคลิปก่อนนำไปใช้กับงานจริง

## โครงไฟล์

```text
SKILL.md                 ขั้นตอนหลักที่เอเจนต์อ่าน
agents/openai.yaml       ข้อมูลแสดง skill ใน Codex
references/              คู่มือแยกตามงาน
assets/templates/        แบบฟอร์ม workspace และ skill ประจำแบรนด์
scripts/                 สร้าง workspace / วิเคราะห์ฟุตเทจ / ตรวจเสียง / สำรอง Draft
install.py               ติดตั้ง workflow สำหรับ Codex และ Claude Code
INSTALL-WINDOWS.cmd      เปิดตัวติดตั้งบน Windows
package_release.py       สร้าง public ZIP จากรายการไฟล์ที่กำหนด
tests/                   ทดสอบพฤติกรรมตัวติดตั้งและ helper
evals/                   โจทย์ตัวอย่างสำหรับประเมิน skill
vendor/CapCut/           สำเนาปลั๊กอินเฉพาะเครื่อง ไม่รวมใน public release
```

## อัปเดตและถอนการติดตั้ง

อัปเดต source แล้วรัน `install.py --replace` เพื่อเก็บ backup และติดตั้งใหม่ การถอน workflow ให้ลบเฉพาะโฟลเดอร์ `clip-workflow-setup` ที่ตัวติดตั้งรายงานในแต่ละแอป การถอน workflow ไม่ถอน CapCut และไม่ลบ workspace ของผู้ใช้

ไฟล์ workflow ของโครงการนี้ใช้ MIT License ตาม [LICENSE](LICENSE) โดยไม่ครอบคลุมปลั๊กอิน CapCut หรือสื่อจากบุคคลอื่น
