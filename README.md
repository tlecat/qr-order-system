# 🍽️ QR Order System — คู่มือ Deploy

## ไฟล์ในชุดนี้
- `qr-order-system.py` — Backend API (Flask)
- `requirements.txt` — Python packages ที่ต้องติดตั้ง

---

## สิ่งที่เพิ่มมาจากเวอร์ชันเดิม

| ฟีเจอร์ | รายละเอียด |
|--------|-----------|
| ✅ Database จริง | SQLite (dev) / PostgreSQL (production) |
| ✅ QR Code | สร้าง QR ต่อโต๊ะ คืนเป็นรูป base64 |
| ✅ Authentication | Staff login ด้วย JWT Token |
| ✅ Role-based | Admin vs Staff แยกสิทธิ์ |
| ✅ Filter orders | `GET /api/orders?status=pending` |
| ✅ Summary | ยอดขายและสถิติรายวัน |

---

## API ทั้งหมด

### Public (ไม่ต้อง login)
| Method | Endpoint | คำอธิบาย |
|--------|----------|----------|
| POST | `/api/orders` | ลูกค้าสั่งอาหาร |
| GET | `/api/orders/<id>` | ดูออเดอร์ตาม ID |
| GET | `/api/qr/<table>` | สร้าง QR Code สำหรับโต๊ะ |

### Staff (ต้อง login)
| Method | Endpoint | คำอธิบาย |
|--------|----------|----------|
| POST | `/api/auth/login` | เข้าสู่ระบบ |
| GET | `/api/orders` | ดูออเดอร์ทั้งหมด |
| PUT | `/api/orders/<id>/status` | อัปเดตสถานะ |
| GET | `/api/summary` | สรุปยอดขายวันนี้ |

### Admin เท่านั้น
| Method | Endpoint | คำอธิบาย |
|--------|----------|----------|
| DELETE | `/api/orders/<id>` | ลบออเดอร์ |
| POST | `/api/setup` | ติดตั้ง DB ครั้งแรก |

---

## วิธี Deploy (แนะนำ 3 ตัวเลือก)

### 🥇 ตัวเลือกที่ 1: Railway (แนะนำที่สุด)
**ฟรี $5/เดือน — ง่ายที่สุด เหมาะมือใหม่**

1. สมัคร https://railway.app
2. กด "New Project" → "Deploy from GitHub"
3. อัป repo ขึ้น GitHub ก่อน
4. Railway จะ detect Flask อัตโนมัติ
5. เพิ่ม PostgreSQL plugin ใน Railway
6. ตั้ง Environment Variables:
   ```
   DATABASE_URL=<Railway จะให้อัตโนมัติ>
   JWT_SECRET=<สุ่มตัวอักษรยาวๆ>
   FRONTEND_URL=https://your-frontend.com
   ```
7. เปิด `/api/setup` ครั้งเดียวเพื่อสร้าง DB

---

### 🥈 ตัวเลือกที่ 2: Render (ฟรี)
**ฟรีแต่ sleep หลัง 15 นาที ไม่มีคนใช้**

1. สมัคร https://render.com
2. New → Web Service → เชื่อม GitHub
3. Build Command: `pip install -r requirements.txt`
4. Start Command: `gunicorn qr-order-system:app`
5. เพิ่ม PostgreSQL database แยก
6. ตั้ง Environment Variables เหมือน Railway

---

### 🥉 ตัวเลือกที่ 3: VPS (DigitalOcean/Vultr ~$6/เดือน)
**ควบคุมได้เต็มที่ แต่ต้องตั้งค่าเอง**

```bash
# บน server Ubuntu
sudo apt update && sudo apt install python3-pip postgresql -y
pip install -r requirements.txt
pip install gunicorn

# สร้าง DB
sudo -u postgres createdb qrorders

# รัน
gunicorn -w 4 -b 0.0.0.0:5000 qr-order-system:app
```

---

## เริ่มต้นใช้งานหลัง Deploy

```bash
# 1. ติดตั้ง DB (ทำครั้งเดียว)
POST /api/setup

# 2. Login รับ token
POST /api/auth/login
{"username": "admin", "password": "admin1234"}

# 3. สร้าง QR โต๊ะ T1
GET /api/qr/T1

# 4. ลูกค้าสแกน QR แล้วสั่งอาหาร
POST /api/orders
{"table_number":"T1","items":[{"item_id":"001","name":"ข้าวผัด","quantity":1,"price":80}]}
```

---

## ⚠️ สิ่งที่ต้องทำก่อน Production
- [ ] เปลี่ยน password admin จาก `admin1234`
- [ ] ใช้ `bcrypt` แทนการเก็บ password ตรงๆ
- [ ] ตั้ง `JWT_SECRET` เป็นค่าสุ่มที่ซับซ้อน
- [ ] เปิด HTTPS เสมอ
