# 🚀 Serverga yuklash qo'llanmasi (Bepul variantlar)

Bot tayyor — endi uni real serverga yuklash uchun 3 ta eng yaxshi **bepul** variant. Har biri uchun bosqichma-bosqich ko'rsatma.

> ⚠ **Muhim:** Men (AI) tashqi serverlarga sizning akkauntingizsiz kira olmayman.
> Quyidagi qadamlarni **o'zingiz** bajarishingiz kerak. Barcha kod va
> konfiguratsiya tayyor — faqat nusxalash-qo'yish kerak.

---

## 🥇 1-VARIANT: Oracle Cloud Free Tier (ENG YAXSHI — 24/7 doimiy)

**Bepul:** 2 ta AMD VM (1 GB RAM, 1/8 CPU) **abadiy** — bot 24/7 ishlaydi.
**Kerak:** kiritma kartasi (verifikatsiya uchun, pul yechilmaydi).

### Bosqichlar:

1. **Oracle Cloud'ga ro'yxatdan o'ting:** https://www.oracle.com/cloud/free/
   - Email, telefon, kiritma kartasi kerak
   - "Always Free" bosing

2. **VM yarating:**
   - "Create Compute Instance"
   - Image: **Canonical Ubuntu 22.04**
   - Shape: **VM.Standard.E2.1.Micro** (Always Free)
   - "Save SSH keys" — private key ni yuklab oling (`ssh-key.pem`)
   - "Create"

3. **Serverga ulaning (SSH):**
   ```bash
   chmod 400 ssh-key.pem
   ssh -i ssh-key.pem ubuntu@<server-public-IP>
   ```

4. **Serverda Docker o'rnatish:**
   ```bash
   sudo apt update && sudo apt install -y docker.io docker-compose git
   sudo usermod -aG docker $USER
   exit
   # qayta ulaning
   ```

5. **Loyihani ko'chirish:**
   ```bash
   git init taskbot && cd taskbot
   # (loyiha fayllarini shu yerga ko'chiring — scp yoki git orqali)
   ```

6. **`.env` faylini yarating:**
   ```bash
   cp .env.example .env
   nano .env
   ```
   ```
   BOT_TOKEN=<sizning-tokeningiz>
   SUPER_ADMIN_IDS=<sizning-telegram-id>
   DATABASE_URL=postgresql+asyncpg://taskbot:taskbot_secret@postgres:5432/taskbot
   USE_WEBHOOK=false
   APP_ENV=production
   ```

7. **Docker' bilan ishga tushiring:**
   ```bash
   docker compose up -d --build
   docker compose exec bot alembic upgrade head
   docker compose logs -f bot
   ```

**Tayyor!** Bot 24/7 ishlaydi. IP: https://<server-ip>

---

## 🥈 2-VARIANT: PythonAnywhere (ENG OSON — kiritma kartasisiz)

**Bepul:** Python web app, lekin free tier'da always-on yo'q.
**Yechim:** Webhook + cron-job.org bilan 24/7 ishlatish.

### Bosqichlar:

1. **PythonAnywhere'ga ro'yxatdan o'ting:** https://www.pythonanywhere.com/ (FREE)

2. **Bash konsol oching:** "Consoles" → "Bash"

3. **Loyihani yuklang:**
   ```bash
   git clone https://github.com/siz/loyiha.git taskbot
   cd taskbot
   ```

4. **Virtualenv va paketlar:**
   ```bash
   mkvirtualenv --python=/usr/bin/python3.12 taskbot
   pip install -r requirements.txt
   ```

5. **SQLite ishlatish (free tier'da Postgres yo'q):**
   ```bash
   cp .env.example .env
   nano .env
   ```
   ```
   BOT_TOKEN=<sizning-tokeningiz>
   SUPER_ADMIN_IDS=<sizning-telegram-id>
   DATABASE_URL=sqlite+aiosqlite:////home/sizning-username/taskbot/taskbot.db
   USE_WEBHOOK=true
   WEBHOOK_URL=https://sizning-username.pythonanywhere.com/webhook
   ```

6. **Migration:**
   ```bash
   alembic upgrade head
   ```

7. **Web app yarating:**
   - "Web" → "Add a new web app" → "Manual configuration" → Python 3.12
   - Source: `/home/sizning-username/taskbot`
   - Working directory: `/home/sizning-username/taskbot`
   - Virtualenv: `/home/sizning-username/.virtualenvs/taskbot`
   - WSGI faylga quyidagini yozing:
     ```python
     import os, sys
     path = "/home/sizning-username/taskbot"
     if path not in sys.path: sys.path.append(path)
     os.chdir(path)
     from app.main import app  # agar aiohttp app export qilinsa
     application = app
     ```

8. **Botni ishga tushiring (webhook + scheduler):**
   - "Tasks" → "Add a scheduled task"
   - Har 10 daqiqada: `python /home/siz/username/taskbot/run_scheduler.py`

9. **Web app'ni reload qiling** → bot webhook rejimida ishlaydi.

---

## 🥉 3-VARIANT: Render.com (OSON, lekin uyquga ketadi)

**Bepul:** Web service, lekin 15 daqiqadan keyin "uyquga ketadi".
**Yechim:** cron-job.org bilan har 10 daqiqada ping.

### Bosqichlar:

1. **GitHub'ga loyihani yuklang:**
   ```bash
   cd task_manager_bot
   git init
   git add .
   git commit -m "Enterprise Task Bot"
   git remote add origin https://github.com/siz/taskbot.git
   git push -u origin main
   ```

2. **Render.com'ga ro'yxatdan o'ting:** https://render.com (GitHub bilan)

3. **"New +" → "Web Service":**
   - Repository: `taskbot`
   - Runtime: Python 3
   - Build Command: `pip install -r requirements.txt && alembic upgrade head`
   - Start Command: `python -m app.main`
   - Plan: **Free**

4. **Environment Variables qo'shing:**
   ```
   BOT_TOKEN=<sizning-tokeningiz>
   SUPER_ADMIN_IDS=<sizning-telegram-id>
   DATABASE_URL=sqlite+aiosqlite:///./taskbot.db
   USE_WEBHOOK=true
   WEBHOOK_URL=https://taskbot.onrender.com/webhook
   APP_ENV=production
   ```

5. **"Create Web Service"** → Render avtomatik build + deploy qiladi.

6. **Uyquga ketmaslik uchun** cron-job.org'da har 10 daqiqada
   `https://taskbot.onrender.com/health` URL'ga GET so'rov yuboring.

---

## 📊 Variantlarni solishtirish

| Xususiyat | Oracle Cloud | PythonAnywhere | Render |
|-----------|--------------|----------------|--------|
| **Bepul muddat** | Abadiy ✅ | Abadiy ✅ | Abadiy ✅ |
| **24/7 ishlaydi** | Ha ✅ | Cron bilan | Ping bilan |
| **Kiritma kartasi** | Kerak ⚠ | Kerak emas ✅ | Kerak emas ✅ |
| **PostgreSQL** | Ha ✅ | Yo'q (SQLite) | Yo'q (SQLite) |
| **Redis** | Ha ✅ | Yo'q | Yo'q |
| **Murakkablik** | O'rta | Oson | Eng oson |
| **Tezlik** | Tez ✅ | O'rta | Sekin (uyqu) |

---

## 🎯 Tavsiya

- **Kiritma kartangiz bo'lsa** → **Oracle Cloud** (eng yaxshi, 24/7, to'liq PostgreSQL+Redis)
- **Kartangiz bo'lmasa** → **PythonAnywhere** (eng ishonchli bepul, webhook bilan)
- **Tez sinab ko'rmoqchi bo'lsangiz** → **Render** (eng oson, lekin uyquga ketadi)

---

## 🔧 Deploy uchun tayyor fayllar (allaqachon mavjud)

- `Dockerfile` — Docker image uchun
- `docker-compose.yml` — PostgreSQL + Redis + Bot
- `requirements.txt` — barcha Python paketlar
- `alembic.ini` + migrations — DB schema
- `.env.example` — konfiguratsiya namunasi
- `app/main.py` — **webhook rejimi qo'shildi** (`USE_WEBHOOK=true`)
- `start_bot.sh` — lokal ishga tushirish skripti

---

## ❓ Yordam

Qaysi variantni tanlasangiz, ayting — men:
- Shu variant uchun **aniq qadam-qadam ko'rsatma** beraman
- Kerakli **konfiguratsiya fayllarini** tayyorlayman
- **Git'ga yuklash** uchun yordam beraman
- Xatolik bo'lsa **tuzatishga** yordam beraman

**Eng oson boshlash uchun:** PythonAnywhere tanlang — kiritma kartasisiz, 10 daqiqada tayyor.
