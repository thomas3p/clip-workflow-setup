# Desktop Draft: โปรเจกต์ CapCut PC ที่แก้ต่อได้

แยกจาก CapCut MCP/cloud `stdraft`: การ authorize plugin ไม่ได้ติดตั้งไลบรารีเขียนไฟล์ PC และ cloud Draft ไม่ใช่หลักฐานว่าโปรเจกต์ปรากฏใน CapCut Desktop

รูปแบบ native Draft ไม่ใช่ API ที่รับประกันความเข้ากันได้ อาจเปลี่ยนหรืออ่านเป็น JSON ไม่ได้ ใช้เฉพาะเวอร์ชัน/โครงที่ตรวจจากเครื่องนี้และทดสอบในสำเนาแล้ว หาก JSON อ่านไม่ได้ ให้รายงานสิ่งที่พบและใช้ช่องทางอื่น ไม่เดาฟิลด์หรือพยายามถอดรหัส

## 1. สำรวจแบบอ่านอย่างเดียว

รันจาก workspace ที่สร้างแล้ว:

```text
python tools/capcut_inspect.py
python tools/capcut_inspect.py "<project>" --root "<draft-root>"
```

`--root` ใช้โฟลเดอร์ที่เก็บโปรเจกต์ ไม่ใช่โปรเจกต์หนึ่งรายการ; argument project อาจเป็นพาธเต็มได้เช่นกัน ค่าเริ่มต้นที่พบบ่อย:

- Windows: `%LOCALAPPDATA%/CapCut/User Data/Projects/com.lveditor.draft`
- macOS: `~/Movies/CapCut/User Data/Projects/com.lveditor.draft`

ผู้ใช้อาจเปลี่ยนตำแหน่งได้ ยึดพาธที่ตรวจพบ/ผู้ใช้ให้ อย่าค้นข้อมูลบัญชีหรือ token เพื่อหาพาธ

ตรวจไฟล์ root `draft_content.json`, `draft_meta_info.json` และเมื่อมี `Timelines/project.json`, `Timelines/<id>/draft_content.json` ว่า active/main timeline เลือกอย่างไร มี `draft_virtual_store.json` หรือ registry อย่างไร เรียนรู้จากตัวอย่างของเวอร์ชันจริงก่อนแก้ การอ่าน JSON ได้อย่างเดียวไม่รับรองว่าเปิดใน CapCut ได้

## 2. ใช้โปรเจกต์ตัวอย่างที่มีอยู่ก่อน

ตรวจว่ามีตัวอย่าง video/photo/text/font/animation/audio/effect ที่ต้องการแล้วหรือยัง ใช้ของที่มีเมื่อเหมาะสม ถ้าฟีเจอร์จำเป็นยังไม่มีตัวอย่าง ให้ผู้ใช้เพิ่มเฉพาะชิ้นนั้นในโปรเจกต์ทดลอง ไม่ขอสร้างตัวอย่างใหม่ครบทุกอย่างทุกครั้ง

จด schema ที่จำเป็นใน `tools/capcut_notes.md`: materials, tracks/segments, material_id/extra_material_refs, source/target_timerange, scale/transform, หน่วยเวลา, project/timeline IDs และรูปแบบ registry เขียน helper เฉพาะเวอร์ชันโดยโคลนตัวอย่างแล้วเปลี่ยนเฉพาะค่าที่เข้าใจ ห้ามสร้างโครงจากความจำหรือสมมติว่า Desktop Draft กับ cloud stdraft เหมือนกัน

## 3. ขั้นเขียนที่ต้องรักษา

1. **วัด VO จริงก่อน**: ใช้ไฟล์เสียงสุดท้ายหลัง conversion/ตัด/normalize วางเวลาและซับจาก alignment ที่ตรวจแล้ว ไม่มี VO_PENDING ในงานที่รายงานว่าใส่เสียงเสร็จ
2. **ตรวจ CapCut ปิดอยู่ก่อน commit**: ใช้ `capcut_backup.py --running` หรือ process API ที่มี หากตรวจไม่ได้อย่าสรุปว่าปิด ห้ามปิดแอป/kill process จนงานมือสูญหาย ถ้าเปิดอยู่ให้เตรียม staging ต่อและรอผู้ใช้บันทึก/ปิด
3. **สำรองก่อนแก้**: `python tools/capcut_backup.py "<project>" --to "<backup-folder>"` สำรองทั้งโฟลเดอร์ สำหรับการเพิ่ม/แก้รายการโปรเจกต์ต้องสำรอง registry แยกด้วย helper นี้ไม่สำรอง registry ให้ การ backup ขณะแอปเปิดอาจไม่สอดคล้อง ต้องทำใหม่หลังปิดก่อนเขียน
4. **ทำ staging แยก**: คำขอแก้เฉพาะจุดให้ patch เฉพาะส่วนที่สั่ง เก็บ timeline/งานมือเดิม คำขอเวอร์ชันใหม่สร้างสำเนาหรือ timeline ใหม่ตาม schema ที่ยืนยันแล้ว อย่าแทนที่โปรเจกต์ที่ผู้ใช้แก้ต่อด้วยผล build เก่า
5. **ตรวจ baseline ก่อนเขียนจริง**: เก็บ hash/mtime ของไฟล์เป้าหมายและ registry ตอนอ่าน ถ้าเปลี่ยนระหว่างทำงาน ให้ re-read และรวมงานผู้ใช้ก่อน commit ไม่ overwrite จาก baseline เก่า
6. **รักษา identity และความสัมพันธ์**: โปรเจกต์เดิมคง project/draft/timeline IDs ที่ผูกกัน; โปรเจกต์ใหม่ใช้ ID ใหม่ตามชนิด ตรวจ segment/material IDs และ refs ไม่ชน/ไม่ขาด ถ้าเวอร์ชันต้องเก็บ root content เป็นสำเนา active timeline ให้เนื้อหาตรงกันพร้อม selector/metadata อย่าเปลี่ยน selector หรือ root ฝ่ายเดียว
7. **ลงทะเบียนโปรเจกต์ตามโครงจริง**: ก๊อปโฟลเดอร์อย่างเดียวอาจไม่ขึ้นหน้า Home ถ้า registry ของรุ่นนั้นต้องมีรายการ ให้เพิ่มเฉพาะรายการใหม่หรือแก้เฉพาะรายการเป้าหมาย คงชนิดข้อมูล (ตัวเลข/list/object) และรายการอื่นทั้งหมด ห้ามจัดรูป/สร้าง registry ใหม่ทั้งก้อนจากการเดา
8. **commit และ rollback**: เขียนแต่ละ JSON ผ่านไฟล์ชั่วคราวแล้ว replace การแทนหลายไฟล์ไม่ใช่ transaction เดียว จึงต้องมี backup/baseline และ rollback ถ้าเกิดข้อผิดพลาด ตรวจแอปยังปิดและ baseline ยังเดิมก่อนเริ่ม commit ทันที

## 4. ตรวจผลและขอบเขตคำว่าเสร็จ

- อ่าน staging และไฟล์ที่ commit แล้วซ้ำ ตรวจไฟล์สื่อที่อ้างถึงมีอยู่จริง, refs ครบ, duration/size/FPS ตรงโจทย์, source ไม่เกินไฟล์, ไม่มีช่องว่างที่ไม่ได้ตั้งใจ และ root/active สอดคล้องตาม schema รุ่นนั้น
- `capcut_inspect.py` ช่วยอ่านโครง/สื่อ/ช่วงเวลาและพบปัญหาทั่วไป แต่ไม่รับรอง effect cache, font, speed mapping หรือ schema ทุกเวอร์ชัน ต้องตรวจสิ่งที่ helper ไม่รองรับแยก
- ใช้ path เต็มใน Draft บนเครื่อง สื่อห้ามถูกย้าย/ลบหลังอ้างถึง ถ้าส่งเครื่องอื่นต้องย้ายพร้อม asset และ relink ไม่เอาพาธส่วนตัวไป hardcode ใน skill สาธารณะ
- ตรวจทรัพยากร effect/text-template/cache ที่ใช้จริง ถ้าไม่เคยโหลดบนเครื่องเป้าหมายอาจหาย ไม่อ้างว่าเปิดได้จากแค่ JSON ที่ parse ผ่าน
- พรีวิว FFmpeg ใช้ทบทวนภาพ/เสียงได้แต่ต่างจาก native renderer โดยเฉพาะฟอนต์ text animation blend/effect ระบุว่าเป็น approximation; หากต้องการ native final ต้องเปิดและ Export ด้วย CapCut จริง (ทำผ่าน UI ที่มีสิทธิ์หรือให้ผู้ใช้ทำขั้นนี้)
- ส่งพาธโปรเจกต์/พรีวิว/backup และบอกว่าตรวจเปิด/Export จริงหรือยัง หากไม่ได้ทำ ห้ามเขียนว่า CapCut export สำเร็จ

## ฟีเจอร์ที่ต้องตรวจจากเครื่องมือปัจจุบัน

Auto-caption, remove background และฟีเจอร์ Pro อาจมีช่องทาง MCP/cloud หรือ UI บางรุ่น ตรวจ tools/skill ของ plugin ที่ติดตั้งก่อนใช้ ไม่เหมารวมว่าเอเจนต์ทำไม่ได้หรือทำได้ทั้งหมด การเรียก cloud feature อาจต้องอัปโหลด/สมาชิก/เครดิตตามการอนุญาตที่เกี่ยวข้อง
