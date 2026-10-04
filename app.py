
from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify
import sqlite3
import os
import uuid
from functools import wraps
from datetime import datetime
from werkzeug.utils import secure_filename


app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "baby-kg-modern-secret")

BASE = os.path.dirname(os.path.abspath(__file__))

# Render'da persistent disk ishlatilsa:
# /var/data/baby_kg.db ga saqlanadi.
# Lokal kompyuterda esa loyiha papkasida baby_kg.db yaratiladi.
if os.path.exists("/var/data"):
    DATA_DIR = "/var/data"
else:
    DATA_DIR = BASE

os.makedirs(DATA_DIR, exist_ok=True)

DB = os.path.join(DATA_DIR, "baby_kg.db")

UP = os.path.join(BASE, "static", "uploads")
os.makedirs(UP, exist_ok=True)


CATEGORIES = [
    "Barchasi",
    "Kurtka",
    "Shim",
    "Oyoq kiyim",
    "Ko‘ylak",
    "Aksessuar",
]


PRODUCTS = []


def db():
    connection = sqlite3.connect(DB)
    connection.row_factory = sqlite3.Row

    connection.executescript("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            phone TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            created_at TEXT
        );

        CREATE TABLE IF NOT EXISTS products (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            category TEXT NOT NULL,
            price INTEGER NOT NULL,
            description TEXT,
            image TEXT,
            active INTEGER DEFAULT 1,
            created_at TEXT,
            views INTEGER DEFAULT 0
        );

        CREATE TABLE IF NOT EXISTS product_images (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            product_id INTEGER NOT NULL,
            image TEXT,
            sort_order INTEGER DEFAULT 0
        );

        CREATE TABLE IF NOT EXISTS orders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            customer_name TEXT,
            phone TEXT,
            address TEXT,
            total INTEGER,
            status TEXT DEFAULT 'Yangi',
            created_at TEXT
        );

        CREATE TABLE IF NOT EXISTS order_items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            order_id INTEGER,
            product_id INTEGER,
            qty INTEGER,
            price INTEGER
        );

        CREATE TABLE IF NOT EXISTS reviews (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            product_id INTEGER,
            user_id INTEGER,
            rating INTEGER,
            comment TEXT,
            created_at TEXT
        );

        CREATE TABLE IF NOT EXISTS wishlist (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            product_id INTEGER,
            UNIQUE(user_id, product_id)
        );
    """)

    connection.commit()
    return connection


def init_db():
    """
    Database va barcha jadvallarni yaratadi.
    Render'da yangi instance ishga tushganda ham
    products jadvali avtomatik yaratiladi.
    """

    c = db()

    c.executescript(
        """
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            phone TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            created_at TEXT
        );

        CREATE TABLE IF NOT EXISTS products (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            category TEXT NOT NULL,
            price INTEGER NOT NULL,
            description TEXT,
            image TEXT,
            active INTEGER DEFAULT 1,
            created_at TEXT,
            views INTEGER DEFAULT 0
        );

        CREATE TABLE IF NOT EXISTS product_images (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            product_id INTEGER NOT NULL,
            image TEXT,
            sort_order INTEGER DEFAULT 0
        );

        CREATE TABLE IF NOT EXISTS orders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            customer_name TEXT,
            phone TEXT,
            address TEXT,
            total INTEGER,
            status TEXT DEFAULT 'Yangi',
            created_at TEXT
        );

        CREATE TABLE IF NOT EXISTS order_items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            order_id INTEGER,
            product_id INTEGER,
            qty INTEGER,
            price INTEGER
        );

        CREATE TABLE IF NOT EXISTS reviews (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            product_id INTEGER,
            user_id INTEGER,
            rating INTEGER,
            comment TEXT,
            created_at TEXT
        );

        CREATE TABLE IF NOT EXISTS wishlist (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            product_id INTEGER,
            UNIQUE(user_id, product_id)
        );
        """
    )

    # products jadvali mavjudligini tekshiramiz
    product_columns = {
        row["name"]
        for row in c.execute("PRAGMA table_info(products)").fetchall()
    }

    if "views" not in product_columns:
        c.execute(
            "ALTER TABLE products ADD COLUMN views INTEGER DEFAULT 0"
        )

    # Demo mahsulotlar avtomatik qo'shilmaydi.
    # Mahsulotlarni faqat admin panel orqali qo'shish mumkin.

    # Product gallery
    existing_products = c.execute(
        "SELECT id, image FROM products"
    ).fetchall()

    for product in existing_products:
        has_image = c.execute(
            """
            SELECT 1
            FROM product_images
            WHERE product_id = ?
            LIMIT 1
            """,
            (product["id"],),
        ).fetchone()

        if product["image"] and not has_image:
            c.execute(
                """
                INSERT INTO product_images
                (
                    product_id,
                    image,
                    sort_order
                )
                VALUES (?, ?, 0)
                """,
                (product["id"], product["image"]),
            )

    c.commit()
    c.close()


# MUHIM:
# Flask/Gunicorn ishga tushganda database yaratiladi.
init_db()


def login_required(function):
    @wraps(function)
    def wrapper(*args, **kwargs):
        if not session.get("user"):
            flash(
                "Buyurtma berish uchun avval login qiling.",
                "error",
            )
            return redirect(
                url_for(
                    "login",
                    next=request.path,
                )
            )

        return function(*args, **kwargs)

    return wrapper


def admin_required(function):
    @wraps(function)
    def wrapper(*args, **kwargs):
        if not session.get("admin"):
            return redirect(url_for("admin_login"))

        return function(*args, **kwargs)

    return wrapper


@app.context_processor
def ctx():
    cart = session.get("cart", {})

    wishlist_ids = []

    if session.get("user"):
        c = db()

        wishlist_ids = [
            row["product_id"]
            for row in c.execute(
                """
                SELECT product_id
                FROM wishlist
                WHERE user_id = ?
                """,
                (session["user"]["id"],),
            ).fetchall()
        ]

        c.close()

    return {
        "cart_count": sum(cart.values()),
        "cats": CATEGORIES,
        "user": session.get("user"),
        "wishlist_ids": wishlist_ids,
    }


@app.route("/")
def home():
    c = db()

    products = c.execute(
        """
        SELECT
            p.*,
            COALESCE(ROUND(AVG(r.rating), 1), 0) AS avg_rating,
            COUNT(r.id) AS review_count
        FROM products p
        LEFT JOIN reviews r ON r.product_id = p.id
        WHERE p.active = 1
        GROUP BY p.id
        ORDER BY p.id DESC
        """
    ).fetchall()

    featured = products[:4]

    reviews = c.execute(
        """
        SELECT
            r.*,
            p.name AS product_name,
            u.name AS user_name
        FROM reviews r
        JOIN products p ON p.id = r.product_id
        JOIN users u ON u.id = r.user_id
        ORDER BY r.id DESC
        LIMIT 6
        """
    ).fetchall()

    c.close()

    return render_template(
        "home.html",
        products=products,
        featured=featured,
        reviews=reviews,
    )


@app.route("/shop")
def shop():
    q = request.args.get("q", "").strip()
    category = request.args.get(
        "category",
        "Barchasi",
    )
    sort = request.args.get(
        "sort",
        "new",
    )

    c = db()

    sql = """
        SELECT
            p.*,
            COALESCE(ROUND(AVG(r.rating), 1), 0) AS avg_rating,
            COUNT(r.id) AS review_count
        FROM products p
        LEFT JOIN reviews r ON r.product_id = p.id
        WHERE p.active = 1
    """

    args = []

    if q:
        sql += """
            AND (
                name LIKE ?
                OR description LIKE ?
            )
        """

        args.extend(
            [
                f"%{q}%",
                f"%{q}%",
            ]
        )

    if category != "Barchasi":
        sql += " AND category = ?"
        args.append(category)

    sql += """
        GROUP BY p.id
    """

    sql += {
        "price_low": " ORDER BY p.price ASC",
        "price_high": " ORDER BY p.price DESC",
    }.get(
        sort,
        " ORDER BY p.id DESC",
    )

    products = c.execute(
        sql,
        args,
    ).fetchall()

    c.close()

    return render_template(
        "shop.html",
        products=products,
        q=q,
        category=category,
        sort=sort,
        wishlist_page=request.args.get("wishlist") == "1",
    )


@app.route("/product/<int:pid>")
def product(pid):
    c = db()

    p = c.execute(
        """
        SELECT *
        FROM products
        WHERE id = ?
        AND active = 1
        """,
        (pid,),
    ).fetchone()

    if not p:
        c.close()
        return "Mahsulot topilmadi", 404

    c.execute(
        """
        UPDATE products
        SET views = COALESCE(views, 0) + 1
        WHERE id = ?
        """,
        (pid,),
    )

    images = c.execute(
        """
        SELECT image
        FROM product_images
        WHERE product_id = ?
        ORDER BY sort_order, id
        """,
        (pid,),
    ).fetchall()

    reviews = c.execute(
        """
        SELECT
            r.*,
            u.name AS user_name
        FROM reviews r
        JOIN users u ON u.id = r.user_id
        WHERE r.product_id = ?
        ORDER BY r.id DESC
        """,
        (pid,),
    ).fetchall()

    avg = c.execute(
        """
        SELECT
            ROUND(AVG(rating), 1) AS a,
            COUNT(*) AS n
        FROM reviews
        WHERE product_id = ?
        """,
        (pid,),
    ).fetchone()

    related = c.execute(
        """
        SELECT *
        FROM products
        WHERE category = (
            SELECT category
            FROM products
            WHERE id = ?
        )
        AND id != ?
        AND active = 1
        LIMIT 4
        """,
        (pid, pid),
    ).fetchall()

    c.commit()
    c.close()

    return render_template(
        "product.html",
        p=p,
        images=images,
        reviews=reviews,
        avg=avg,
        related=related,
    )


@app.route("/register", methods=["GET", "POST"])
def register():
    # Akkaunt yaratish o'chirilgan
    flash("Akkaunt yaratish hozircha yopiq.", "error")
    return redirect(url_for("login"))



@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        c = db()

        row = c.execute(
            """
            SELECT id, name, phone
            FROM users
            WHERE phone = ?
            AND password = ?
            """,
            (
                request.form.get("phone", "").strip(),
                request.form.get("password", ""),
            ),
        ).fetchone()

        c.close()

        if row:
            session["user"] = dict(row)

            flash(
                "Xush kelibsiz!",
                "success",
            )

            return redirect(
                request.args.get("next")
                or url_for("home")
            )

        flash(
            "Telefon yoki parol noto‘g‘ri.",
            "error",
        )

    return render_template(
        "auth.html",
        mode="login",
    )


@app.route("/logout")
def logout():
    session.pop("user", None)
    return redirect(url_for("home"))


@app.post("/review/<int:pid>")
@login_required
def review(pid):
    try:
        rating = int(
            request.form.get(
                "rating",
                5,
            )
        )
    except ValueError:
        rating = 5

    rating = max(
        1,
        min(5, rating),
    )

    comment = request.form.get(
        "comment",
        "",
    ).strip()

    if not comment:
        flash(
            "Izoh yozing.",
            "error",
        )

        return redirect(
            url_for(
                "product",
                pid=pid,
            )
        )

    c = db()

    product_exists = c.execute(
        """
        SELECT id FROM products
        WHERE id = ? AND active = 1
        """,
        (pid,),
    ).fetchone()

    if not product_exists:
        c.close()
        flash("Mahsulot topilmadi.", "error")
        return redirect(url_for("shop"))

    c.execute(
        """
        INSERT INTO reviews
        (
            product_id,
            user_id,
            rating,
            comment,
            created_at
        )
        VALUES (?, ?, ?, ?, ?)
        """,
        (
            pid,
            session["user"]["id"],
            rating,
            comment,
            datetime.now().isoformat(),
        ),
    )

    c.commit()
    c.close()

    flash(
        "Rahmat! Fikringiz qo‘shildi.",
        "success",
    )

    return redirect(
        url_for(
            "product",
            pid=pid,
        )
    )


@app.post("/wishlist/<int:pid>")
@login_required
def wishlist_toggle(pid):
    c = db()

    row = c.execute(
        """
        SELECT id
        FROM wishlist
        WHERE user_id = ?
        AND product_id = ?
        """,
        (
            session["user"]["id"],
            pid,
        ),
    ).fetchone()

    if row:
        c.execute(
            "DELETE FROM wishlist WHERE id = ?",
            (row["id"],),
        )
        added = False
    else:
        c.execute(
            """
            INSERT OR IGNORE INTO wishlist
            (
                user_id,
                product_id
            )
            VALUES (?, ?)
            """,
            (
                session["user"]["id"],
                pid,
            ),
        )
        added = True

    c.commit()
    c.close()

    return jsonify(
        ok=True,
        added=added,
    )


@app.route("/wishlist")
@login_required
def wishlist():
    c = db()

    products = c.execute(
        """
        SELECT p.*
        FROM products p
        JOIN wishlist w
            ON w.product_id = p.id
        WHERE w.user_id = ?
        AND p.active = 1
        ORDER BY w.id DESC
        """,
        (session["user"]["id"],),
    ).fetchall()

    c.close()

    return render_template(
        "shop.html",
        products=products,
        q="",
        category="Barchasi",
        sort="new",
        wishlist_page=True,
    )


@app.route("/cart")
def cart():
    c = db()

    items = []
    total = 0

    for sid, qty in session.get(
        "cart",
        {},
    ).items():

        product = c.execute(
            """
            SELECT *
            FROM products
            WHERE id = ?
            AND active = 1
            """,
            (int(sid),),
        ).fetchone()

        if product:
            subtotal = product["price"] * qty

            items.append(
                {
                    "p": product,
                    "qty": qty,
                    "subtotal": subtotal,
                }
            )

            total += subtotal

    c.close()

    return render_template(
        "cart.html",
        items=items,
        total=total,
    )


@app.post("/cart/add/<int:pid>")
def add_cart(pid):
    c = db()

    exists = c.execute(
        """
        SELECT id
        FROM products
        WHERE id = ?
        AND active = 1
        """,
        (pid,),
    ).fetchone()

    c.close()

    if not exists:
        return jsonify(ok=False)

    cart = session.setdefault(
        "cart",
        {},
    )

    key = str(pid)

    cart[key] = cart.get(key, 0) + 1

    session.modified = True

    return jsonify(
        ok=True,
        count=sum(cart.values()),
    )


@app.post("/cart/remove/<int:pid>")
def remove_cart(pid):
    cart = session.get(
        "cart",
        {},
    )

    cart.pop(
        str(pid),
        None,
    )

    session.modified = True

    return redirect(
        url_for("cart")
    )


@app.post("/cart/update")
def update_cart():
    cart = session.get(
        "cart",
        {},
    )

    for key, value in request.form.items():
        try:
            cart[key] = max(
                1,
                min(20, int(value)),
            )
        except (ValueError, TypeError):
            pass

    session.modified = True

    return redirect(
        url_for("cart")
    )


@app.route("/checkout")
@login_required
def checkout():
    c = db()

    rows = []
    total = 0

    for sid, qty in session.get(
        "cart",
        {},
    ).items():

        product = c.execute(
            """
            SELECT *
            FROM products
            WHERE id = ?
            AND active = 1
            """,
            (int(sid),),
        ).fetchone()

        if product:
            rows.append(
                (
                    product,
                    qty,
                )
            )

            total += product["price"] * qty

    c.close()

    return render_template(
        "checkout.html",
        rows=rows,
        total=total,
    )


@app.post("/order")
@login_required
def order():
    form = request.form

    name = form.get(
        "name",
        "",
    ).strip()

    phone = form.get(
        "phone",
        "",
    ).strip()

    address = form.get(
        "address",
        "",
    ).strip()

    if not name or not phone:
        flash(
            "Ism va telefon kerak.",
            "error",
        )

        return redirect(
            url_for("checkout")
        )

    c = db()

    items = []
    total = 0

    for sid, qty in session.get(
        "cart",
        {},
    ).items():

        product = c.execute(
            """
            SELECT *
            FROM products
            WHERE id = ?
            AND active = 1
            """,
            (int(sid),),
        ).fetchone()

        if product:
            items.append(
                (
                    product,
                    qty,
                )
            )

            total += product["price"] * qty

    if not items:
        c.close()

        return redirect(
            url_for("shop")
        )

    cursor = c.execute(
        """
        INSERT INTO orders
        (
            user_id,
            customer_name,
            phone,
            address,
            total,
            status,
            created_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (
            session["user"]["id"],
            name,
            phone,
            address,
            total,
            "Yangi",
            datetime.now().isoformat(),
        ),
    )

    order_id = cursor.lastrowid

    for product, qty in items:
        c.execute(
            """
            INSERT INTO order_items
            (
                order_id,
                product_id,
                qty,
                price
            )
            VALUES (?, ?, ?, ?)
            """,
            (
                order_id,
                product["id"],
                qty,
                product["price"],
            ),
        )

    c.commit()
    c.close()

    session["cart"] = {}

    flash(
        f"Buyurtma #{order_id} qabul qilindi!",
        "success",
    )

    return redirect(
        url_for("orders")
    )


@app.route("/orders")
@login_required
def orders():
    c = db()

    user_orders = c.execute(
        """
        SELECT *
        FROM orders
        WHERE user_id = ?
        ORDER BY id DESC
        """,
        (session["user"]["id"],),
    ).fetchall()

    c.close()

    return render_template(
        "orders.html",
        orders=user_orders,
    )


@app.route("/admin/login", methods=["GET", "POST"])
def admin_login():
    if request.method == "POST":

        username = request.form.get(
            "username",
            "",
        )

        password = request.form.get(
            "password",
            "",
        )

        if username == "Gulnoz" and password == "234":
            session["admin"] = True

            return redirect(
                url_for("admin")
            )

        flash(
            "Admin login yoki parol noto‘g‘ri.",
            "error",
        )

    return render_template(
        "admin_login.html"
    )


@app.route("/admin/logout")
def admin_logout():
    session.pop(
        "admin",
        None,
    )

    return redirect(
        url_for("home")
    )


@app.route("/admin")
@admin_required
def admin():
    c = db()

    products = c.execute(
        """
        SELECT *
        FROM products
        ORDER BY id DESC
        """
    ).fetchall()

    orders = c.execute(
        """
        SELECT *
        FROM orders
        ORDER BY id DESC
        """
    ).fetchall()

    stats = {
        "active_products": c.execute(
            """
            SELECT COUNT(*) AS c
            FROM products
            WHERE active = 1
            """
        ).fetchone()["c"],

        "orders": c.execute(
            """
            SELECT COUNT(*) AS c
            FROM orders
            """
        ).fetchone()["c"],

        "revenue": c.execute(
            """
            SELECT COALESCE(SUM(total), 0) AS s
            FROM orders
            """
        ).fetchone()["s"],

        "users": c.execute(
            """
            SELECT COUNT(*) AS c
            FROM users
            """
        ).fetchone()["c"],

        "views": c.execute(
            """
            SELECT COALESCE(SUM(views), 0) AS v
            FROM products
            """
        ).fetchone()["v"],

        "reviews": c.execute(
            """
            SELECT COUNT(*) AS c
            FROM reviews
            """
        ).fetchone()["c"],

        "wishlists": c.execute(
            """
            SELECT COUNT(*) AS c
            FROM wishlist
            """
        ).fetchone()["c"],

        "new_orders": c.execute(
            """
            SELECT COUNT(*) AS c
            FROM orders
            WHERE status = 'Yangi'
            """
        ).fetchone()["c"],
    }

    top = c.execute(
        """
        SELECT name, views
        FROM products
        ORDER BY views DESC, id DESC
        LIMIT 5
        """
    ).fetchall()

    # Batafsil ro'yxatlar (statistika kartochkalari uchun)
    active_products_list = c.execute(
        """
        SELECT id, name, category, price, views, created_at
        FROM products
        WHERE active = 1
        ORDER BY id DESC
        """
    ).fetchall()

    users_list = c.execute(
        """
        SELECT id, name, phone, created_at
        FROM users
        ORDER BY id DESC
        """
    ).fetchall()

    views_list = c.execute(
        """
        SELECT id, name, category, price, views
        FROM products
        WHERE views > 0
        ORDER BY views DESC, id DESC
        """
    ).fetchall()

    reviews_list = c.execute(
        """
        SELECT
            r.id,
            r.rating,
            r.comment,
            r.created_at,
            u.name AS user_name,
            u.phone AS user_phone,
            p.name AS product_name,
            p.id AS product_id
        FROM reviews r
        LEFT JOIN users u ON u.id = r.user_id
        LEFT JOIN products p ON p.id = r.product_id
        ORDER BY r.id DESC
        """
    ).fetchall()

    wishlists_list = c.execute(
        """
        SELECT
            w.id,
            u.name AS user_name,
            u.phone AS user_phone,
            p.name AS product_name,
            p.id AS product_id,
            p.price AS product_price
        FROM wishlist w
        LEFT JOIN users u ON u.id = w.user_id
        LEFT JOIN products p ON p.id = w.product_id
        ORDER BY w.id DESC
        """
    ).fetchall()

    new_orders_list = c.execute(
        """
        SELECT *
        FROM orders
        WHERE status = 'Yangi'
        ORDER BY id DESC
        """
    ).fetchall()

    c.close()

    return render_template(
        "admin.html",
        products=products,
        orders=orders,
        stats=stats,
        top=top,
        active_products_list=active_products_list,
        users_list=users_list,
        views_list=views_list,
        reviews_list=reviews_list,
        wishlists_list=wishlists_list,
        new_orders_list=new_orders_list,
    )


@app.post("/admin/product/add")
@admin_required
def product_add():
    form = request.form

    uploaded = []

    for file in request.files.getlist(
        "image_files"
    ):
        if file and file.filename:

            safe_name = secure_filename(
                file.filename
            )

            ext = (
                os.path.splitext(
                    safe_name
                )[1].lower()
                or ".jpg"
            )

            filename = (
                uuid.uuid4().hex
                + ext
            )

            file.save(
                os.path.join(
                    UP,
                    filename,
                )
            )

            uploaded.append(
                url_for(
                    "static",
                    filename="uploads/" + filename,
                )
            )

    image = (
        uploaded[0]
        if uploaded
        else form.get(
            "image_url",
            "",
        ).strip()
    )

    c = db()

    cursor = c.execute(
        """
        INSERT INTO products
        (
            name,
            category,
            price,
            description,
            image,
            active,
            created_at,
            views
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, 0)
        """,
        (
            form["name"],
            form["category"],
            int(form["price"]),
            form["description"],
            image,
            1,
            datetime.now().isoformat(),
        ),
    )

    product_id = cursor.lastrowid

    urls = (
        uploaded
        or ([image] if image else [])
    )

    for index, image_url in enumerate(
        urls[:5]
    ):
        c.execute(
            """
            INSERT INTO product_images
            (
                product_id,
                image,
                sort_order
            )
            VALUES (?, ?, ?)
            """,
            (
                product_id,
                image_url,
                index,
            ),
        )

    c.commit()
    c.close()

    flash(
        "Mahsulot qo‘shildi!",
        "success",
    )

    return redirect(
        url_for("admin")
    )


@app.post("/admin/product/<int:pid>/edit")
@admin_required
def product_edit(pid):
    form = request.form

    c = db()

    product = c.execute(
        """
        SELECT image
        FROM products
        WHERE id = ?
        """,
        (pid,),
    ).fetchone()

    image = (
        product["image"]
        if product
        else ""
    )

    uploaded = []

    for file in request.files.getlist(
        "image_files"
    ):
        if file and file.filename:

            safe_name = secure_filename(
                file.filename
            )

            ext = (
                os.path.splitext(
                    safe_name
                )[1].lower()
                or ".jpg"
            )

            filename = (
                uuid.uuid4().hex
                + ext
            )

            file.save(
                os.path.join(
                    UP,
                    filename,
                )
            )

            uploaded.append(
                url_for(
                    "static",
                    filename="uploads/" + filename,
                )
            )

    if uploaded:
        image = uploaded[0]

    elif form.get(
        "image_url",
        "",
    ).strip():
        image = form["image_url"].strip()

    c.execute(
        """
        UPDATE products
        SET
            name = ?,
            category = ?,
            price = ?,
            description = ?,
            image = ?
        WHERE id = ?
        """,
        (
            form["name"],
            form["category"],
            int(form["price"]),
            form["description"],
            image,
            pid,
        ),
    )

    if uploaded:
        c.execute(
            """
            DELETE FROM product_images
            WHERE product_id = ?
            """,
            (pid,),
        )

        for index, image_url in enumerate(
            uploaded[:5]
        ):
            c.execute(
                """
                INSERT INTO product_images
                (
                    product_id,
                    image,
                    sort_order
                )
                VALUES (?, ?, ?)
                """,
                (
                    pid,
                    image_url,
                    index,
                ),
            )

    elif (
        image
        and not c.execute(
            """
            SELECT 1
            FROM product_images
            WHERE product_id = ?
            LIMIT 1
            """,
            (pid,),
        ).fetchone()
    ):
        c.execute(
            """
            INSERT INTO product_images
            (
                product_id,
                image,
                sort_order
            )
            VALUES (?, ?, 0)
            """,
            (
                pid,
                image,
            ),
        )

    c.commit()
    c.close()

    return redirect(
        url_for("admin")
    )


@app.post("/admin/product/<int:pid>/toggle")
@admin_required
def toggle(pid):
    c = db()

    c.execute(
        """
        UPDATE products
        SET active = 1 - active
        WHERE id = ?
        """,
        (pid,),
    )

    c.commit()
    c.close()

    return redirect(
        url_for("admin")
    )


@app.post("/admin/product/<int:pid>/delete")
@admin_required
def delete_product(pid):
    c = db()

    # Gallery
    c.execute(
        """
        DELETE FROM product_images
        WHERE product_id = ?
        """,
        (pid,),
    )

    # Wishlist
    c.execute(
        """
        DELETE FROM wishlist
        WHERE product_id = ?
        """,
        (pid,),
    )

    # Reviews
    c.execute(
        """
        DELETE FROM reviews
        WHERE product_id = ?
        """,
        (pid,),
    )

    # Product
    c.execute(
        """
        DELETE FROM products
        WHERE id = ?
        """,
        (pid,),
    )

    c.commit()
    c.close()

    return redirect(
        url_for("admin")
    )


@app.post("/admin/order/<int:oid>/status")
@admin_required
def order_status(oid):
    status = request.form.get(
        "status",
        "Yangi",
    )

    allowed_statuses = {
        "Yangi",
        "Qabul qilindi",
        "Tayyorlanmoqda",
        "Yo‘lda",
        "Yetkazildi",
        "Bekor qilindi",
    }

    if status not in allowed_statuses:
        status = "Yangi"

    c = db()

    c.execute(
        """
        UPDATE orders
        SET status = ?
        WHERE id = ?
        """,
        (
            status,
            oid,
        ),
    )

    c.commit()
    c.close()

    return redirect(
        url_for("admin")
    )


# Render/Gunicorn uchun:
# gunicorn app:app
if __name__ == "__main__":
    port = int(
        os.environ.get(
            "PORT",
            5000,
        )
    )

    app.run(
        debug=True,
        host="0.0.0.0",
        port=port,
    )

