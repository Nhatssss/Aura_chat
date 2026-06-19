# ⬡ AURA CHAT — Hệ thống chat đa người dùng

Giao diện futuristic giống dashboard AI, chạy hoàn toàn cục bộ trên máy tính.

## Cấu trúc thư mục

```
aura_chat/
├── app.py                  ← Server Flask + SocketIO
├── requirements.txt        ← Thư viện cần cài
├── run.bat                 ← Khởi động nhanh (Windows)
├── templates/
│   ├── login.html          ← Trang đăng nhập / đăng ký
│   └── chat.html           ← Dashboard chat chính
├── static/
│   └── uploads/            ← Ảnh người dùng gửi (tự tạo)
└── data/
    ├── accounts.json       ← Tài khoản người dùng
    └── messages.json       ← Lịch sử tin nhắn
```

## Cài đặt & Chạy

### Cách 1 — Chạy nhanh (Windows)
```
Double-click vào run.bat
```

### Cách 2 — Thủ công
```bash
# Cài thư viện (chỉ cần làm 1 lần)
pip install flask flask-socketio

# Khởi động server
python app.py
```

### Mở trình duyệt
```
http://localhost:5000
```

## Tính năng

| Tính năng | Chi tiết |
|-----------|----------|
| Đăng ký / Đăng nhập | Mật khẩu hash SHA-256, lưu `data/accounts.json` |
| Chat thời gian thực | WebSocket (Socket.IO), cập nhật ngay lập tức |
| Gửi ảnh | PNG/JPG/GIF/WEBP, tối đa 10 MB, lưu `static/uploads/` |
| Danh sách online | Hiển thị ai đang online, dedup nhiều tab |
| Typing indicator | Hiển thị "... đang nhập" khi người khác gõ |
| Activity Log | Ghi lại join/leave/ảnh theo thời gian thực |
| Xem ảnh fullscreen | Click ảnh để phóng to lightbox |
| Lịch sử tin nhắn | Tải 100 tin nhắn gần nhất khi vào chat |

## Dữ liệu JSON

### `data/accounts.json`
```json
{
  "users": [
    {
      "id": "uuid",
      "username": "nhat",
      "password": "sha256_hash",
      "avatar_color": "#00e5ff",
      "created_at": "2024-01-01T00:00:00"
    }
  ]
}
```

### `data/messages.json`
```json
{
  "messages": [
    {
      "id": "uuid",
      "sender_id": "uuid",
      "sender_name": "nhat",
      "avatar_color": "#00e5ff",
      "content": "Xin chào!",
      "type": "text",
      "image_url": null,
      "timestamp": "2024-01-01T10:00:00"
    }
  ]
}
```

## Test với nhiều người dùng

Mở nhiều tab hoặc nhiều trình duyệt, đăng ký các tài khoản khác nhau → chat với nhau ngay lập tức.

## Ghi chú

- Server chạy cổng `5000`, nếu muốn đổi → sửa `port=5000` trong `app.py`
- Lưu tối đa **300 tin nhắn** trong JSON (tự động xoá cũ nhất)
- Chỉ phục vụ mạng LAN nếu muốn dùng từ máy khác: truy cập `http://<IP_máy_bạn>:5000`
