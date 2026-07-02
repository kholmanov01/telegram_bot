# 📤 GitHub'ga yuklash — 2 ta variant

Repo: https://github.com/kholmanov01/telegram_bot.git
Holat: Repo ochiq (public), default branch `main`
Git commit: TAYYOR (`26d5524 Enterprise Task Management Bot — production ready`)

Git repo to'liq tayyor — 118 fayl, 15,235 qator kod.
**Faqat push qilish qoldi.**

---

## 🥇 1-VARIANT: Token bilan (eng oson — tavsiya)

GitHub Personal Access Token oling va menga yuboring — men o'zim push qilaman.

### Token olish:

1. **GitHub'ga kiring:** https://github.com
2. Yuqori o'ng burchakdagi **avatar** → **Settings**
3. Chap menyu oxirida: **Developer settings**
4. **Personal access tokens** → **Tokens (classic)**
5. **"Generate new token"** → **"Generate new token (classic)"**
6. To'ldiring:
   - **Note:** `taskbot-deploy`
   - **Expiration:** `7 days` (1 hafta yetarli)
   - **Select scopes:** faqat **`repo`** belgilang (boshqalari kerak emas)
7. Pastda yashil tugma: **"Generate token"**
8. **Token'ni nusxalang** (ko'rinadigan — `ghp_xxxxxxxxxxxx...`)

### Menga yuboring:
Token'ni shu yerga yozib yuboring — men darhol push qilaman.

> ⚠ Token 1 hafta amal qiladi, keyin o'chiriladi. Push qilgandan keyin
> token'ni GitHub'dan o'chirib tashlashingiz mumkin (revoke).

---

## 🥈 2-VARIANT: O'zingiz yuklang (token'siz — SSH kalit bilan)

Agar token bermasangiz, o'zingizning kompyuteringizdan yuklang.

### A. Loyihani ZIP qilib oling (mendan):

Loyiha papkasini ZIP qiling — barcha fayllar tayyor:
```bash
cd /home/z/my-project/task_manager_bot
# (men tayyorlayman)
```

### B. O'z kompyuteringizda:

1. ZIP'ni yuklab oling va oching
2. Terminal ochib:
```bash
cd telegram_bot
git init
git add .
git commit -m "Enterprise Task Management Bot — production ready"
git branch -M main
git remote add origin https://github.com/kholmanov01/telegram_bot.git
git push -u origin main
```

Push vaqtida GitHub **username va password** so'raydi:
- **Username:** `kholmanov01`
- **Password:** GitHub token'ingiz (parol emas — token!)

---

## 📊 Nima yuklanadi (118 fayl):

```
✅ Dockerfile, docker-compose.yml, requirements.txt
✅ alembic.ini + migrations/
✅ .env.example (TOKENSIZ — namuna)
✅ .gitignore (.env, taskbot.db, loglar kirmaydi)
✅ app/ — to'liq Python kodi (Aiogram 3.x, SQLAlchemy, ...)
✅ tests/ — 75 ta test
✅ README.md, ORACLE_DEPLOY.md, DEPLOY.md
```

### ❌ Yuklanmaydi (xavfsizlik):
- `.env` (sizning token'laringiz)
- `taskbot.db` (ma'lumotlar bazasi)
- `run.log`, `supervisor.log` (sandbox loglari)

---

## ✅ Push qilingandan keyin:

Repo'ni yangilang: https://github.com/kholmanov01/telegram_bot

Keyin Oracle serverda:
```bash
git clone https://github.com/kholmanov01/telegram_bot.git
cd telegram_bot
cp .env.example .env
nano .env  # token, admin ID, parollarni to'ldiring
docker compose up -d --build
docker compose exec bot alembic upgrade head
```

---

## 🎯 Eng oson yo'l:

**1-Variant** — token oling (1 daqiqa) va menga yuboring.
Men 10 soniyada push qilaman. Tugadi! ✅
