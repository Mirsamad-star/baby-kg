# Baby KG — Modern V2

Modern Flask + SQLite online shop.

## Ishga tushirish
```bash
pip install -r requirements.txt
python app.py
```
Open `http://127.0.0.1:5000`

## Admin
`http://127.0.0.1:5000/admin/login`
- Username: `Gulnoz`
- Password: `234`

## Yangi funksiyalar
- Modern responsive design
- Search, category filter, price sorting
- Product detail page
- Admin image upload (local files) or image URL
- Admin product edit / hide / show / delete
- Cart and checkout with login protection
- Customer name, phone and address on order
- Admin order management and status
- 1–5 star reviews + comments
- Wishlist ❤️ for logged-in customers
- Customer order history
- Dashboard statistics


## Yangilangan versiya
- Demo mahsulotlar avtomatik yaratilmaydi.
- Mahsulotlar faqat admin paneldan qo‘shiladi.
- Admin qo‘shgan/tahrirlagan/o‘chirgan ma’lumotlar SQLite bazaga yoziladi.
- Mahsulot sahifasida 1–5 yulduz va kommentariya mavjud.
- Mahsulot cardlarida o‘rtacha reyting va fikrlar soni ko‘rsatiladi.
- Render Start Command: `gunicorn app:app`
- Render uchun ma'lumotlar deploylar orasida ham saqlanishi kerak bo‘lsa, Render Persistent Disk (`/var/data`) ulang.
