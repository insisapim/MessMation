# Dataset notes — MessMation

## ขอบเขตและการแบ่งข้อมูล

- `dev.jsonl`: 10 ข้อความ; `dev-images.jsonl`: 4 ภาพ สำหรับพัฒนา prompt/validation
- `test-text.jsonl`: 15 ข้อความสังเคราะห์ ใช้ ChatGPT ช่วยสร้างและผู้จัดทำยืนยันเฉลย
- `test-images.jsonl`: 15 ภาพตัวอย่าง/แม่แบบออนไลน์ (ID 001–017 ยกเว้น 006 และ 015) พร้อมเฉลยที่ผู้จัดทำยืนยัน
- เป็น curated gold set ของโปรเจกต์ ไม่ใช่ benchmark มาตรฐาน ไม่ใช่ข้อมูลธุรกรรมจริงทั้งหมด และไม่มีการวัดความสอดคล้องระหว่างผู้ให้เฉลยหลายคน
- ผล test หลักมาจาก baseline/agent อย่างละหนึ่งรอบบนชุดเดียวกัน; ใช้ข้อมูล dev สำหรับปรับระบบ ไม่มีการแก้ gold ในงานเตรียม UI/deployment นี้

## แนวทางเฉลย

1. ชื่อร้านใช้ผู้ขาย ไม่ใช่ลูกค้าหรือ watermark/software brand; เก็บชื่อสาขาเมื่อเฉลยกำหนดไว้
2. วันที่แปลงเป็น ค.ศ. `YYYY-MM-DD` เมื่ออ่านได้แน่นอน; แปลงปี พ.ศ. โดยลบ 543 เฉพาะปี และคงวัน/เดือน; ถ้าแยก DD/MM กับ MM/DD ไม่ได้ให้ `null`
3. ยอดรวมใช้ยอดสุทธิที่ปรากฏ ไม่ใช้เงินรับ เงินทอน หรือ subtotal และไม่คำนวณยอดที่หาย
4. สกุลเงินใช้หลักฐานชัดเจน เช่น บาท/฿/THB หรือ INR; `$` เดี่ยวไม่เพียงพอ; ไม่อนุมานจากภาษา ประเทศ หรือชื่อร้าน
5. เลขที่เอกสารใช้ receipt/document/invoice/bill identifier ที่เฉลยระบุ ไม่แทนด้วย transaction/authentication/tax/customer/RX identifier
6. missing/unreadable/ambiguous ใช้ `null`; required keys ยังต้องมีครบทั้ง 5
7. `evaluate.py` เปรียบเทียบค่าหลัง schema parse แบบตรงตัว ไม่มี fuzzy matching หรือ normalize punctuation เพิ่ม เช่น `#0000001` ต่างจาก `0000001`

มีตัวอย่างรูปแบบ invoice ปะปนอยู่ในชุดภาพ จึงควรขยายเกณฑ์ receipt/invoice ให้ชัดเจนก่อนนำไปใช้เป็น benchmark ภายนอก ภาพ 006 ตัดออกเพราะอ่านไม่ชัด ภาพ 015 เป็น Cash App payment confirmation ใช้ negative example แยกต่างหาก ไม่รวม extraction score

## ที่มาภาพ test

ตารางนี้บันทึก URL ที่ผู้จัดทำให้ไว้ในขั้นตอนสร้างชุดข้อมูล ไม่ได้ยืนยันสิทธิ์การแจกจ่ายภาพหรือความพร้อมของ URL ในอนาคต ภาพที่ใช้ประเมินจริงคือ local file ตาม JSONL; บางไฟล์เปลี่ยนนามสกุลตามรูปแบบที่ดาวน์โหลด จึงให้ใช้ byte content/local file เป็นหลัก

| ID | ไฟล์ใน `images/test/` | แหล่งที่มา |
|---|---|---|
| 001 | dev-images-001.webp | https://receiptmaker.us.com/templates/previews/rona-receipt.webp |
| 002 | dev-images-002.webp | https://images.squarespace-cdn.com/content/v1/577c006b725e25e0affed0c1/d8cba5f9-003f-437f-9cf7-f21b56270c9a/Regular+receipt+example.png |
| 003 | dev-images-003.png | https://www.makemyreceipt.com/receipts/Pharmacy-Receipt.png |
| 004 | dev-images-004.png | https://craftmypdf.s3.ap-southeast-1.amazonaws.com/apps/receipt/receipt-type-1.png |
| 005 | dev-images-005.jpg | https://encrypted-tbn0.gstatic.com/images?q=tbn:ANd9GcRkkzQFmj3an41q7VZVipUGJqhmeEJ3KojXKXeNhTNQnk4p23NL5Umg6xo&s=10 |
| 006 (excluded) | dev-images-006.jpg | https://images.ctfassets.net/txhaodyqr481/3uHrou4XfYB2qu1xFtvbHq/4ccf1d2cf2b8b507438509a349eec04b/receiptarticle.jpg |
| 007 | dev-images-007.jpg | https://encrypted-tbn0.gstatic.com/images?q=tbn:ANd9GcRwyfjN2LHUsFiHCASPyY6g4h3siFn_4r7GCQSaDX23af0RWyfJs2crNKU&s=10 |
| 008 | dev-images-008.webp | https://assets.billquest.in/public-assets/template-previews/restaurant.compact-thermal-receipt/restaurant-compact-thermal-receipt-in-80.webp |
| 009 | dev-images-009.png | https://encrypted-tbn0.gstatic.com/images?q=tbn:ANd9GcQ6NaFhLukEC3ajeK5okHs_TJxTUtzo8slfN8-ZSI8ev6xyjYdouN41KCe6&s=10 |
| 010 | dev-images-010.webp | https://receiptmaker.us.com/templates/previews/wendys-receipt.webp |
| 011 | dev-images-011.webp | https://receiptmaker.us.com/templates/previews/family-dollar-receipt.webp |
| 012 | dev-images-012.webp | https://receiptmaker.us.com/templates/previews/kfc-receipt.webp |
| 013 | dev-images-013.jpg | https://makereceipt.com/images/club-pump-receipt-sm.jpg |
| 014 | dev-images-014.jpg | https://encrypted-tbn0.gstatic.com/images?q=tbn:ANd9GcQF-A8eLbkHm0OJmfzLSWg9ME_aMatesM545NapJRrBhwWTH2sVUvpIrPQA&s=10 |
| 015 (negative only) | dev-images-015.png | https://www.makemyreceipt.com/receipts/Cash-App-Receipt.png |
| 016 | dev-images-016.png | https://encrypted-tbn0.gstatic.com/images?q=tbn:ANd9GcS2OhH_YcC6XCLXhynPhdFaPRlCQ5fZfosQ1qIi2NuosShhiwxR5GTFdKs&s=10 |
| 017 | dev-images-017.jpg | https://encrypted-tbn0.gstatic.com/images?q=tbn:ANd9GcQPruSlIxucEJjMS-9xPxxYq6cGOofB7Vr6GgVxzS30FqUuFMC_0j6yWCY&s=10 |

Google thumbnail URLs ไม่ใช่เว็บไซต์ผู้สร้างต้นฉบับ จึงยังมีข้อจำกัดเรื่อง provenance ภาพ dev รับจากไฟล์ที่ผู้จัดทำแนบ; source URLs ต้นทางบางรายการยังไม่ได้บันทึก ไม่ควรแต่งแหล่งที่มาเพิ่ม

## ประวัติและการอ่านผล

ผล dev เก่าบางชุดใช้ภาพก่อน crop หรือ gold ที่ยังอ่านผิด (เช่นปีในภาพ dev 001 เคยแก้จาก 2015 เป็น 2025) เก็บเป็นประวัติ ไม่รวมกับผล test สุดท้าย

ไฟล์ผลเดิมไม่เก็บชื่อโหมด/model revision/prompt hash/จำนวน tool rounds อัตโนมัติ ตาราง README จึงอาศัยการระบุโหมดจากผู้จัดทำ ไม่สามารถพิสูจน์จากไฟล์นั้นเพียงอย่างเดียวว่ามี repair จริงกี่ครั้ง

การรัน unit tests ที่ใช้ mock ยืนยัน control flow เท่านั้น; Cash App ยืนยันการปฏิเสธถูกต้องหนึ่งกรณีเท่านั้น การทดลองใหม่ควรเก็บ metadata และเพิ่มกรณี negative/unclear แยกจาก extraction metrics
