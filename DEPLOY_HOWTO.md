# Deploy AURA Chat & Dùng Trên Mobile

## Đã thêm PWA support cho app

Các file mới:
- `static/manifest.json` — cấu hình PWA
- `static/sw.js` — service worker (cache + offline fallback)
- `static/icons/icon-192.png`, `icon-512.png` — icon cho màn hình chính
- `Procfile` — cho Render/Railway
- `runtime.txt` — Python version

---

## Cách 1: Host miễn phí trên Render (nhanh nhất)

### 1. Push code lên GitHub
```bash
cd D:\code\web\aura_chat_v2\aura_chat
git init
git add .
git commit -m "aura chat + pwa"
# Tạo repo trên GitHub, chạy:
# git remote add origin https://github.com/<user>/aura-chat.git
# git push -u origin main
```

### 2. Deploy lên Render
1. Vào https://render.com — đăng ký free
2. New → Web Service → kết nối GitHub repo
3. Cấu hình:
   - **Name**: `aura-chat`
   - **Region**: Singapore (gần VN nhất)
   - **Branch**: `main`
   - **Runtime**: `Python 3`
   - **Build Command**: `pip install -r requirements.txt`
   - **Start Command**: `gunicorn app:app --worker-class eventlet --bind 0.0.0.0:$PORT`
   - **Plan**: Free ($0/tháng)
4. Thêm Environment Variable:
   - `SECRET_KEY`: `(tự đặt 1 chuỗi ngẫu nhiên)`
   - `ASYNC_MODE`: `eventlet`
5. Deploy → đợi 2-3 phút

### 3. Xài trên mobile
Render trả URL dạng `https://aura-chat.onrender.com`
- Mở URL trên Chrome/Safari → **Add to Home Screen** → icon AURA xuất hiện, bấm vào chạy như app

---

## Cách 2: Ngrok (test nhanh, không cần deploy)

Chạy local, expose ra internet:
```bash
cd D:\code\web\aura_chat_v2\aura_chat
python app.py
# Trong terminal khác:
ngrok http 5000
```
→ Mở URL ngrok trên mobile. Không có PWA install được nhưng dùng tạm được.

---

## Cách 3: Android APK thật (WebView wrapper)

Dùng **Capacitor** (Ionic) bọc app thành APK:
```bash
npm install -g @capacitor/cli
npx cap init AuraChat
npx cap add android
# Sửa capacitor.config.json -> url thành URL Render
npx cap open android
```
→ Build ra APK bằng Android Studio. iOS cần Mac + Xcode.

---

## Tóm lại

| Phương án | Độ khó | Chi phí | UX |
|-----------|--------|---------|----|
| PWA + Render | Dễ | $0 | Khá ngon |
| Ngrok | Cực dễ | $0 (free tier) | Tạm được |
| WebView APK | Trung bình | $0 | Ngon nhất |

Mình recommend **PWA + Render** — mất 5 phút deploy, xài như app thật, không cần build store.
