# Phat hien te nga + gui canh bao Gmail

Du an nay nhan dien nguoi bi nga tu webcam/video, sau do:
- Luu anh tai thoi diem nghi nga.
- Tao clip ngan quanh su co.
- Gui email Gmail kem anh + video.

## 1) Cai dat

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

## 2) Cau hinh Gmail

1. Bat xac minh 2 buoc cho tai khoan Google.
2. Tao **App Password** (16 ky tu) trong phan Bao mat.
3. Tao file `.env` (co the copy tu `.env.example`) va dien:

```env
SMTP_USER=your_gmail@gmail.com
SMTP_APP_PASSWORD=abcdefghijklmnop
ALERT_TO_EMAIL=nguoi_nhan@gmail.com
```

## 3) Chay phat hien te nga

### Chay voi webcam

```bash
python fall_live.py --camera 0 --detect-every-n-frames 3 --after-sec 3
```

### Chay voi video file

```bash
python fall_live.py --video "video_2.mp4" --playback-speed 1.0 --after-sec 3
```

Khi phat hien te nga, chuong trinh se:
- Luu file trong `outputs/falls`
- Gui 1 email kem **anh + video ngan**

## 4) Test gui email truoc khi chay that

```bash
python fall_live.py --test-email
```

Neu thanh cong, man hinh in ra: `Da gui email test toi ...`

## 5) Tham so quan trong

- `--fall-aspect-threshold`: nguong ti le ngang/doc de xac dinh tu the nga.
- `--horizontal-only-threshold`: nguong tu the nam ro rang.
- `--cooldown-sec`: khoang nghi giua hai canh bao de tranh spam.
- `--after-sec`: do dai clip sau su co.
- `--send-immediate-image`: gui them 1 email anh ngay khi vua xac nhan nga.

Nhan `q` de thoat.
