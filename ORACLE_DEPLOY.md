# 🥇 Oracle Cloud Free Tier — To'liq Deploy Qo'llanmasi

Botni Oracle Cloud'ga yuklab, 24/7 bepul ishlatish uchun bosqichma-bosqich qo'llanma.
**Bepul:** 2 ta VM abadiy (1 GB RAM, 1/8 CPU) — bot 24/7 ishlaydi.

---

## 📋 Kerakli narsalar

1. ✅ Kiritma kartasi (Visa/Mastercard) — **verifikatsiya uchun, pul yechilmaydi**
2. ✅ Telegram Bot Token (sizda bor: `8802727198:...`)
3. ✅ Sizning Telegram ID (sizda bor: `8722446867`)
4. ✅ 30 daqiqa vaqt

---

## 1-BOSQICH: Oracle Cloud akkaunt yarating

1. **Ro'yxatdan o'ting:** https://www.oracle.com/cloud/free/
   - "Start for free" bosing
   - Email, telefon raqami, mamlakat
   - Kiritma kartasi ma'lumotlari (1$ vaqtinchalik bloklanadi, keyin qaytariladi)

2. **Email tasdiqlang** va Oracle Cloud Console'ga kiring:
   https://cloud.oracle.com

3. **Region tanlang:** "Germany Central (Frankfurt)" yoki "Netherlands Northwest"
   (Yaqin, tez)

---

## 2-BOSQICH: Virtual Server (VM) yarating

1. Console'da **"Compute" → "Instances" → "Create Instance"**

2. Quyidagilarni sozlang:
   - **Name:** `taskbot-server`
   - **Image:** `Canonical Ubuntu 22.04` (default)
   - **Shape:** `VM.Standard.E2.1.Micro` (Always Free eligible) ✅
   - **Networking:** "Create new VCN" (default) — avtomatik
   - **Public IP:** "Assign a public IPv4 address" ✅

3. **SSH kalit yarating:**
   - "Add SSH keys" → "Generate SSH key pair"
   - **Private Key** va **Public Key** ikkalasini ham yuklab oling (.key fayl)
   - **BU FAYLLARNI SAFDAGI JOYGA SAQLANG!** Serverga kirish uchun kerak

4. **"Create"** bosing — 1-2 daqiqada server tayyor

5. **Server public IP'sini yozib oling** (masalan: `129.154.45.123`)

---

## 3-BOSQICH: Serverga ulaning (SSH)

### Windows foydalanuvchilari:
1. **PuTTY** yuklab o'ring: https://www.putty.org/
2. Yoki **Windows Terminal** (Windows 11'da bor) ishlating
3. `.key` faylni PuTTY'ga moslash uchun PuTTYgen bilan konvertatsiya qiling

### Linux/Mac foydalanuvchilari:
Terminal oching va quyidagini bajaring:

```bash
# .key fayl huquqlarini sozlash (yuklab olingan papkerga o'ting)
chmod 400 ssh-key-*.key

# Serverga ulanish (IP ni o'zingiznikiga almashtiring)
ssh -i ssh-key-*.key ubuntu@129.154.45.123
```

Birinchi marta "Are you sure you want to continue?" → `yes`

---

## 4-BOSQICH: Serverda Docker o'rnatish

Serverga ulangach, quyidagi buyruqlarni ketma-ket bajaring:

```bash
# Tizimni yangilash
sudo apt update && sudo apt upgrade -y

# Docker va Docker Compose o'rnatish
sudo apt install -y docker.io docker-compose git

# Docker'ni ubuntu foydalanuvchisiga ruxsat berish
sudo usermod -aG docker $USER

# Tizimdan chiqib qayta kiring (docker huquqlari uchun)
exit
```

**Qayta ulaning:**
```bash
ssh -i ssh-key-*.key ubuntu@129.154.45.123
```

**Tekshirish:**
```bash
docker --version
docker-compose --version
```
Ikkalasi ham versiya raqamini ko'rsatsa — tayyor ✅

---

## 5-BOSQICH: Loyihani serverga yuklash

### Variant A: GitHub orqali (tavsiya)

Avval GitHub'ga loyihani yuklang (sizning kompyuteringizda):

```bash
cd task_manager_bot

# Git init
git init
git add .
git commit -m "Enterprise Task Management Bot"

# GitHub'da yangi repo yarating: https://github.com/new
# "taskbot" nomli public repo oching

git remote add origin https://github.com/SIZNING-USERNAME/taskbot.git
git branch -M main
git push -u origin main
```

Serverda (SSH orqali):
```bash
git clone https://github.com/SIZNING-USERNAME/taskbot.git
cd taskbot
```

### Variant B: To'g'ridan-to'g'ri yuklash (scp)

```bash
# Sizning kompyuteringizdan
scp -i ssh-key-*.key -r task_manager_bot ubuntu@129.154.45.123:~/

# Serverda
cd task_manager_bot
```

---

## 6-BOSQICH: Konfiguratsiya (.env)

Serverda:
```bash
cd ~/taskbot
cp .env.example .env
nano .env
```

Quyidagilarni o'zgartiring:
```ini
# --- Telegram ---
BOT_TOKEN=8802727198:AAEg5VJ2fvvob_T0TWeAy-MRbI4xv8obELo
SUPER_ADMIN_IDS=8722446867

# --- PostgreSQL ---
POSTGRES_USER=taskbot
POSTGRES_PASSWORD=BURAY_BOSHQA_MAXFIY_PAROL_123
POSTGRES_DB=taskbot
DATABASE_URL=postgresql+asyncpg://taskbot:BURAY_BOSHQA_MAXFIY_PAROL_123@postgres:5432/taskbot

# --- Redis ---
REDIS_PASSWORD=BURAY_REDIS_PAROL_456

# --- Application ---
APP_ENV=production
APP_TIMEZONE=Asia/Tashkent
USE_WEBHOOK=false
```

**Saqlash:** `Ctrl+X`, `Y`, `Enter`

> ⚠ PAROLLARNI O'ZGARTIRING! Xavfsizlik uchun murakkab parol o'ylab toping.
> Eslab qoling — keyin kerak bo'ladi.

---

## 7-BOSQICH: Botni ishga tushirish

```bash
# Docker image'larni build qilish va ishga tushirish (background)
docker compose up -d --build
```

Bu jarayon 3-5 daqiqa davom etadi (image yuklab olinadi, build qilinadi).

**Statusni tekshirish:**
```bash
docker compose ps
```

Uchta service ham "running" ko'rinishi kerak:
```
taskbot_postgres   running (healthy)
taskbot_redis      running (healthy)
taskbot_app        running
```

**Migration qo'llash (DB jadvallari):**
```bash
docker compose exec bot alembic upgrade head
```

---

## 8-BOSQICH: Log'larni tekshirish

```bash
# Bot log'lari (jonli)
docker compose logs -f bot

# Faqat oxirgi 50 qator
docker compose logs --tail=50 bot
```

**Muvaffaqiyatli bo'lsa, quyidagini ko'rasiz:**
```
INFO | Starting Enterprise Task Manager Bot | env=production
INFO | Database connection verified.
INFO | Scheduler started with 3 jobs.
INFO | Bot connected: @n1vazifa_bot (id=8802727198)
INFO | Run polling for bot @n1vazifa_bot
```

**Telegram'da botni sinab ko'ring:** `@n1vazifa_bot` → `/start` ✅

---

## 9-BOSQICH: Firewall portlarini ochish (FAQAT webhook uchun)

> Polling rejimida bu KERAK EMAS — bot Telegram'ga o'zi ulanadi.
> Webhook uchun esa port 8443 ochiq bo'lishi kerak.

Oracle Cloud'da portlarni ochish:

1. Console → "Networking" → "Virtual Cloud Networks"
2. Sizning VCN → "Security Lists" → "Default Security List"
3. "Add Ingress Rules":
   - Source CIDR: `0.0.0.0/0`
   - IP Protocol: `TCP`
   - Destination Port Range: `8443`
   - "Add Ingress Rules"

Serverda (iptables):
```bash
sudo iptables -I INPUT 6 -m state --state NEW -p tcp --dport 8443 -j ACCEPT
sudo netfilter-persistent save
```

---

## 🔄 Boshqaruv buyruqlari

```bash
# Botni to'xtatish
docker compose stop

# Botni qayta ishga tushirish
docker compose start

# Botni qayta yuklash (kod o'zgarganda)
git pull origin main
docker compose up -d --build

# Log'larni ko'rish
docker compose logs -f bot

# Barcha service'larni o'chirish
docker compose down

# DB backup
docker compose exec postgres pg_dump -U taskbot taskbot > backup.sql

# DB restore
cat backup.sql | docker compose exec -T postgres psql -U taskbot taskbot
```

---

## 🚨 Mumkin bo'lgan muammolar

### Muammo 1: "Cannot connect to Telegram"
```bash
# Serverdan Telegram'ga ulanishni tekshirish
curl -s https://api.telegram.org/bot8802727198:AAEg5VJ2fvvob_T0TWeAy-MRbI4xv8obELo/getMe
```
Javob bo'lmasa — Oracle region'i Telegram'ni bloklagan. Boshqa regionda server oching.

### Muammo 2: "Database connection failed"
```bash
# Postgres log'larini ko'rish
docker compose logs postgres
```
Parol noto'g'ri bo'lsa — `.env` ni tuzating va `docker compose down && docker compose up -d`.

### Muammo 3: "Alembic upgrade failed"
```bash
# Migration holatini tekshirish
docker compose exec bot alembic current
# Migrationni qayta urinish
docker compose exec bot alembic upgrade head
```

### Muammo 4: Bot javob bermaydi
```bash
# 1. Bot log'larini ko'ring
docker compose logs --tail=100 bot

# 2. Bot process tirikmi
docker compose ps

# 3. Telegram webhook statusini tekshirish
docker compose exec bot python -c "
import asyncio
from app.bot.instance import bot
async def check():
    info = await bot.get_webhook_info()
    print(info)
asyncio.run(check())
"
```

### Muammo 5: Disk to'lib qoldi
```bash
# Docker eski image'larni tozalash
docker system prune -a -f
```

---

## 📊 Server monitoring

### CPU/RAM/Disk:
```bash
htop           # CPU/RAM (install: sudo apt install htop)
df -h          # Disk joyi
docker stats   # Docker konteynerlar
```

### Log fayllari:
```bash
# Bot log fayllari (host'da)
tail -f logs/info.log
tail -f logs/error.log
```

---

## 🆘 Yordam so'rash

Agar muammo chiqsa:
1. **Xato matnni nusxalang** (`docker compose logs --tail=50 bot`)
2. **Buyruqni bajarganda qanday natija chiqqanini yozing**
3. Menga yuboring — tuzatishga yordam beraman

---

## ✅ Muvaffaqiyatli deploy checklist

- [ ] Oracle Cloud akkaunt yaratildi
- [ ] VM (Ubuntu 22.04, Always Free) ochildi
- [ ] SSH bilan ulandim
- [ ] Docker o'rnatildi
- [ ] Loyiha serverga yuklandi
- [ ] `.env` to'ldirildi (token, admin ID, parollar)
- [ ] `docker compose up -d --build` bajarildi
- [ ] `alembic upgrade head` bajarildi
- [ ] Log'larda "Bot connected" ko'rindi
- [ ] Telegram'da `/start` ishladi
- [ ] Bot 24/7 ishlamoqda

**TAYYOR!** Bot endi doimiy ishlaydi, 24/7. 🚀
