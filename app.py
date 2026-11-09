import functools
import hmac
import json
import logging
import re
import secrets
import smtplib
import sqlite3
import urllib.request
import uuid
from email.message import EmailMessage
from pathlib import Path

import click
from flask import (
    Flask, abort, flash, g, jsonify, redirect, render_template, request,
    send_from_directory, session, url_for,
)
from PIL import Image
from werkzeug.middleware.proxy_fix import ProxyFix
from werkzeug.security import check_password_hash, generate_password_hash

from config import Config

app = Flask(__name__)
app.config.from_object(Config)
if app.config["TRUST_PROXY"]:
    app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1)
Path(app.config["UPLOAD_FOLDER"]).mkdir(parents=True, exist_ok=True)
Path(app.config["DATABASE"]).parent.mkdir(parents=True, exist_ok=True)

DEFAULT_SETTINGS = {
    "paver_rate": "50",
    "border_rate": "1",
    "delivery_text": "Доставка осуществляется по Томску и Томской области. Стоимость и условия доставки согласовываются с менеджером при оформлении заявки.",
    "contact_phone": "",
    "contact_email": "",
    "contact_address": "",
    "work_hours": "",
    "messengers": "",
    "company_details": "",
}
ORDER_STATUSES = {
    "new": "Новая",
    "processing": "В работе",
    "completed": "Завершена",
    "cancelled": "Отменена",
}
SETTING_LABELS = {
    "contact_phone": "Телефон",
    "contact_email": "Электронная почта",
    "contact_address": "Адрес",
    "work_hours": "График работы",
    "messengers": "Мессенджеры",
    "company_details": "Реквизиты компании",
}


def get_db():
    if "db" not in g:
        g.db = sqlite3.connect(app.config["DATABASE"])
        g.db.row_factory = sqlite3.Row
        g.db.execute("PRAGMA foreign_keys = ON")
        g.db.execute("PRAGMA journal_mode = WAL")
    return g.db


def close_db(_error=None):
    db = g.pop("db", None)
    if db is not None:
        db.close()


def init_db():
    db = get_db()
    db.executescript((Path(app.root_path) / "database" / "schema.sql").read_text(encoding="utf-8"))
    db.executemany(
        "INSERT OR IGNORE INTO settings (key, value) VALUES (?, ?)",
        DEFAULT_SETTINGS.items(),
    )
    db.execute(
        """INSERT OR IGNORE INTO products
        (slug, name, dimensions, consumption, description) VALUES (?, ?, ?, ?, ?)""",
        (
            "paver", "Брусчатка", "100 × 200 × 60 мм",
            "50 шт./м²",
            "Прямоугольная бетонная брусчатка для мощения дорожек, дворовых территорий и площадок.",
        ),
    )
    db.execute(
        """INSERT OR IGNORE INTO products
        (slug, name, dimensions, consumption, description) VALUES (?, ?, ?, ?, ?)""",
        (
            "border", "Бордюр", "200 × 50 × 400 мм",
            "1 шт./пог. м",
            "Бетонный элемент для оформления границ дорожек и зон мощения. Длина изделия — 400 мм.",
        ),
    )
    db.commit()


app.teardown_appcontext(close_db)


@app.cli.command("init-db")
def init_db_command():
    init_db()
    click.echo("База данных инициализирована.")


@app.cli.command("password-hash")
def password_hash_command():
    password = click.prompt("Новый пароль администратора", hide_input=True, confirmation_prompt=True)
    if len(password) < 12:
        raise click.ClickException("Используйте пароль длиной не менее 12 символов.")
    click.echo("Добавьте в переменные окружения:")
    click.echo(f"ADMIN_PASSWORD_HASH={generate_password_hash(password)}")


def csrf_token():
    if "_csrf" not in session:
        session["_csrf"] = secrets.token_urlsafe(32)
    return session["_csrf"]


def public_settings():
    rows = get_db().execute("SELECT key, value FROM settings").fetchall()
    settings = {**DEFAULT_SETTINGS, **{row["key"]: row["value"] for row in rows}}
    try:
        settings["paver_rate"] = float(settings["paver_rate"])
        settings["border_rate"] = float(settings["border_rate"])
    except (TypeError, ValueError):
        settings["paver_rate"] = 50.0
        settings["border_rate"] = 1.0
    return settings


@app.before_request
def protect_request():
    g.csp_nonce = secrets.token_urlsafe(18)
    if request.method == "POST":
        token = request.form.get("_csrf", "") or request.headers.get("X-CSRF-Token", "")
        if not token or not hmac.compare_digest(token, session.get("_csrf", "")):
            abort(400, "Сессия формы устарела. Обновите страницу и повторите действие.")
    if request.path.startswith("/admin") and request.endpoint != "admin_login":
        if not session.get("admin_authenticated"):
            return redirect(url_for("admin_login"))


@app.after_request
def security_headers(response):
    nonce = getattr(g, "csp_nonce", "")
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
    response.headers["Content-Security-Policy"] = (
        "default-src 'self'; "
        f"script-src 'self' 'nonce-{nonce}'; "
        "style-src 'self'; img-src 'self' data: blob:; font-src 'self'; "
        "connect-src 'self' blob:; object-src 'none'; base-uri 'self'; "
        "frame-ancestors 'none'; form-action 'self'"
    )
    return response


@app.context_processor
def template_helpers():
    return {"csrf_token": csrf_token, "order_statuses": ORDER_STATUSES}


@app.get("/")
def index():
    db = get_db()
    products = db.execute("SELECT * FROM products ORDER BY id").fetchall()
    gallery = db.execute("SELECT * FROM gallery ORDER BY sort_order, id DESC").fetchall()
    return render_template(
        "index.html", products=products, settings=public_settings(), gallery=gallery,
    )


@app.get("/policy")
def policy():
    return render_template("policy.html", settings=public_settings())


@app.get("/favicon.ico")
def favicon():
    return app.send_static_file("images/favicon.ico")


@app.get("/robots.txt")
def robots():
    content = (Path(app.static_folder) / "robots.txt").read_text(encoding="utf-8")
    content = content.replace("Sitemap: /sitemap.xml", f"Sitemap: {request.url_root}sitemap.xml")
    return app.response_class(content, mimetype="text/plain")


@app.get("/sitemap.xml")
def sitemap():
    base = request.url_root.rstrip("/")
    content = render_template("sitemap.xml", base_url=base)
    return app.response_class(content, mimetype="application/xml")


@app.get("/media/<path:filename>")
def uploaded_file(filename):
    if not re.fullmatch(r"[a-f0-9]{32}\.webp", filename):
        abort(404)
    return send_from_directory(app.config["UPLOAD_FOLDER"], filename, max_age=86400)


def clean_text(value, maximum):
    return " ".join(str(value or "").strip().split())[:maximum]


def validate_order(data):
    is_callback = data.get("request_type") == "callback"
    name = clean_text(data.get("name"), 100)
    phone = clean_text(data.get("phone"), 30)
    city = clean_text(data.get("city"), 120)
    address = clean_text(data.get("address"), 250)
    comment = clean_text(data.get("comment"), 1500)
    errors = {}
    if len(name) < 2:
        errors["name"] = "Укажите имя (не менее 2 символов)."
    digits = re.sub(r"\D", "", phone)
    if not 10 <= len(digits) <= 15 or not re.fullmatch(r"[+\d\s()\-]+", phone):
        errors["phone"] = "Укажите корректный номер телефона."
    quantities = {}
    for field in ("paver_qty", "border_qty"):
        raw = str(data.get(field, "0") or "0").strip()
        try:
            value = int(raw)
        except ValueError:
            value = -1
        if not 0 <= value <= 1_000_000:
            errors[field] = "Укажите целое количество от 0 до 1 000 000."
        quantities[field] = value
    if not is_callback and not errors and quantities["paver_qty"] == 0 and quantities["border_qty"] == 0:
        errors["paver_qty"] = "Укажите количество хотя бы одного изделия."
    if data.get("consent") not in (True, "true", "1", "on"):
        errors["consent"] = "Необходимо согласие на обработку персональных данных."
    if clean_text(data.get("website"), 100):
        abort(400)
    return errors, {
        "name": name, "phone": phone, "city": city, "address": address,
        "comment": comment, **quantities,
    }


def notification_text(order):
    return "\n".join([
        f"Новая заявка №{order['id']} — Томск Монолит",
        f"Имя: {order['name']}",
        f"Телефон: {order['phone']}",
        f"Брусчатка: {order['paver_qty']} шт.",
        f"Бордюры: {order['border_qty']} шт.",
        f"Населённый пункт: {order['city'] or 'не указан'}",
        f"Адрес доставки: {order['address'] or 'не указан'}",
        f"Комментарий: {order['comment'] or 'нет'}",
    ])


def send_telegram(order):
    token = app.config["TELEGRAM_BOT_TOKEN"]
    chat_id = app.config["TELEGRAM_CHAT_ID"]
    if not token or not chat_id:
        return False
    payload = json.dumps({"chat_id": chat_id, "text": notification_text(order)}).encode()
    req = urllib.request.Request(
        f"https://api.telegram.org/bot{token}/sendMessage",
        data=payload, headers={"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=5) as response:
            return 200 <= response.status < 300
    except Exception as error:
        app.logger.error(
            "Не удалось отправить Telegram-уведомление для заявки %s (%s)",
            order["id"], type(error).__name__,
        )
        return False


def send_email(order):
    host = app.config["SMTP_HOST"]
    recipient = app.config["NOTIFY_EMAIL_TO"]
    if not host or not recipient:
        return False
    message = EmailMessage()
    message["Subject"] = f"Заявка №{order['id']} — Томск Монолит"
    message["From"] = app.config["SMTP_FROM"] or app.config["SMTP_USERNAME"]
    message["To"] = recipient
    message.set_content(notification_text(order))
    try:
        smtp_class = smtplib.SMTP_SSL if app.config["SMTP_USE_SSL"] else smtplib.SMTP
        with smtp_class(host, app.config["SMTP_PORT"], timeout=5) as smtp:
            if not app.config["SMTP_USE_SSL"] and app.config["SMTP_USE_TLS"]:
                smtp.starttls()
            if app.config["SMTP_USERNAME"]:
                smtp.login(app.config["SMTP_USERNAME"], app.config["SMTP_PASSWORD"])
            smtp.send_message(message)
        return True
    except Exception:
        app.logger.exception("Не удалось отправить email-уведомление для заявки %s", order["id"])
        return False


@app.post("/api/orders")
def create_order():
    data = request.get_json(silent=True) if request.is_json else request.form
    if data is None:
        return jsonify({"ok": False, "message": "Некорректный формат данных."}), 400
    errors, order = validate_order(data)
    if errors:
        return jsonify({"ok": False, "errors": errors, "message": "Проверьте выделенные поля."}), 422
    db = get_db()
    cursor = db.execute(
        """INSERT INTO orders
        (name, phone, paver_qty, border_qty, city, address, comment)
        VALUES (:name, :phone, :paver_qty, :border_qty, :city, :address, :comment)""",
        order,
    )
    db.commit()
    order["id"] = cursor.lastrowid
    telegram_sent = send_telegram(order)
    email_sent = send_email(order)
    db.execute(
        "UPDATE orders SET telegram_sent = ?, email_sent = ? WHERE id = ?",
        (int(telegram_sent), int(email_sent), order["id"]),
    )
    db.commit()
    return jsonify({
        "ok": True, "order_id": order["id"],
        "message": f"Заявка №{order['id']} сохранена. Мы свяжемся с вами для уточнения деталей.",
    }), 201


def admin_required(view):
    @functools.wraps(view)
    def wrapped(*args, **kwargs):
        if not session.get("admin_authenticated"):
            return redirect(url_for("admin_login"))
        return view(*args, **kwargs)
    return wrapped


@app.route("/admin/login", methods=("GET", "POST"))
def admin_login():
    if session.get("admin_authenticated"):
        return redirect(url_for("admin_dashboard"))
    if request.method == "POST":
        configured = bool(app.config["ADMIN_PASSWORD_HASH"])
        valid_user = hmac.compare_digest(
            request.form.get("username", ""), app.config["ADMIN_USERNAME"],
        )
        valid_password = configured and check_password_hash(
            app.config["ADMIN_PASSWORD_HASH"], request.form.get("password", ""),
        )
        if configured and valid_user and valid_password:
            session.clear()
            session["admin_authenticated"] = True
            session.permanent = True
            return redirect(url_for("admin_dashboard"))
        flash("Неверный логин или пароль, либо доступ администратора ещё не настроен.", "error")
    return render_template("admin/login.html")


@app.post("/admin/logout")
@admin_required
def admin_logout():
    session.clear()
    return redirect(url_for("admin_login"))


@app.get("/admin")
@admin_required
def admin_dashboard():
    status = request.args.get("status", "")
    if status in ORDER_STATUSES:
        orders = get_db().execute(
            "SELECT * FROM orders WHERE status = ? ORDER BY id DESC", (status,),
        ).fetchall()
    else:
        status = ""
        orders = get_db().execute("SELECT * FROM orders ORDER BY id DESC").fetchall()
    counts = {
        row["status"]: row["count"] for row in get_db().execute(
            "SELECT status, COUNT(*) AS count FROM orders GROUP BY status",
        ).fetchall()
    }
    return render_template(
        "admin/dashboard.html", orders=orders, counts=counts, current_status=status,
    )


@app.get("/admin/orders/<int:order_id>")
@admin_required
def admin_order(order_id):
    order = get_db().execute("SELECT * FROM orders WHERE id = ?", (order_id,)).fetchone()
    if order is None:
        abort(404)
    return render_template("admin/order.html", order=order)


@app.post("/admin/orders/<int:order_id>/status")
@admin_required
def admin_order_status(order_id):
    status = request.form.get("status", "")
    if status not in ORDER_STATUSES:
        abort(400)
    db = get_db()
    db.execute("UPDATE orders SET status = ? WHERE id = ?", (status, order_id))
    db.commit()
    flash("Статус заявки обновлён.", "success")
    return redirect(url_for("admin_order", order_id=order_id))


@app.route("/admin/content", methods=("GET", "POST"))
@admin_required
def admin_content():
    db = get_db()
    if request.method == "POST":
        errors = []
        prices = {}
        for slug in ("paver", "border"):
            raw = request.form.get(f"{slug}_price", "").strip().replace(",", ".")
            if not raw:
                prices[slug] = None
                continue
            try:
                price = float(raw)
                if not 0 <= price <= 100_000_000:
                    raise ValueError
                prices[slug] = price
            except ValueError:
                errors.append("Цена должна быть неотрицательным числом или пустым полем.")
        rates = {}
        for key in ("paver_rate", "border_rate"):
            try:
                rate = float(request.form.get(key, "").replace(",", "."))
                if not 0 < rate <= 10000:
                    raise ValueError
                rates[key] = rate
            except ValueError:
                errors.append("Нормы расхода должны быть числами больше нуля.")
        descriptions = {
            slug: clean_text(request.form.get(f"{slug}_description"), 1500)
            for slug in ("paver", "border")
        }
        if any(len(value) < 10 for value in descriptions.values()):
            errors.append("Описание каждого товара должно содержать не менее 10 символов.")
        if errors:
            for error in errors:
                flash(error, "error")
        else:
            for slug in ("paver", "border"):
                rate = f"{rates['paver_rate' if slug == 'paver' else 'border_rate']:g}".replace(".", ",")
                unit = "м²" if slug == "paver" else "пог. м"
                consumption = f"{rate} шт./{unit}"
                db.execute(
                    "UPDATE products SET description = ?, price = ?, consumption = ? WHERE slug = ?",
                    (descriptions[slug], prices[slug], consumption, slug),
                )
            values = {key: clean_text(request.form.get(key), 2000) for key in DEFAULT_SETTINGS}
            values.update({key: str(value) for key, value in rates.items()})
            db.executemany(
                "INSERT INTO settings (key, value) VALUES (?, ?) "
                "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
                values.items(),
            )
            db.commit()
            flash("Содержимое и настройки сохранены.", "success")
            return redirect(url_for("admin_content"))
    products = db.execute("SELECT * FROM products ORDER BY id").fetchall()
    return render_template(
        "admin/content.html", products=products, settings=public_settings(),
        setting_labels=SETTING_LABELS,
    )


@app.route("/admin/gallery", methods=("GET", "POST"))
@admin_required
def admin_gallery():
    db = get_db()
    if request.method == "POST":
        file = request.files.get("image")
        caption = clean_text(request.form.get("caption"), 250)
        if file is None or not file.filename:
            flash("Выберите изображение в формате JPEG, PNG или WebP.", "error")
        else:
            try:
                image = Image.open(file.stream)
                if image.format not in ("JPEG", "PNG", "WEBP"):
                    raise ValueError("Неподдерживаемый формат")
                if image.width > 12000 or image.height > 12000:
                    raise ValueError("Слишком большое изображение")
                image.load()
                image = image.convert("RGB")
                image.thumbnail((2400, 2400), Image.Resampling.LANCZOS)
                filename = f"{uuid.uuid4().hex}.webp"
                destination = Path(app.config["UPLOAD_FOLDER"]) / filename
                image.save(destination, "WEBP", quality=86, method=6)
                db.execute(
                    "INSERT INTO gallery (filename, caption) VALUES (?, ?)",
                    (filename, caption),
                )
                db.commit()
                flash("Фотография добавлена в галерею.", "success")
                return redirect(url_for("admin_gallery"))
            except (OSError, ValueError, Image.DecompressionBombError):
                flash("Не удалось обработать файл. Загрузите корректный JPEG, PNG или WebP.", "error")
    images = db.execute("SELECT * FROM gallery ORDER BY sort_order, id DESC").fetchall()
    return render_template("admin/gallery.html", images=images)


@app.post("/admin/gallery/<int:image_id>/delete")
@admin_required
def admin_gallery_delete(image_id):
    db = get_db()
    image = db.execute("SELECT * FROM gallery WHERE id = ?", (image_id,)).fetchone()
    if image is None:
        abort(404)
    db.execute("DELETE FROM gallery WHERE id = ?", (image_id,))
    db.commit()
    (Path(app.config["UPLOAD_FOLDER"]) / image["filename"]).unlink(missing_ok=True)
    flash("Фотография удалена.", "success")
    return redirect(url_for("admin_gallery"))


@app.errorhandler(400)
def bad_request(error):
    if request.path.startswith("/api/"):
        return jsonify({"ok": False, "message": str(error.description)}), 400
    return render_template("error.html", code=400, message=str(error.description)), 400


@app.errorhandler(404)
def not_found(_error):
    return render_template("error.html", code=404, message="Страница не найдена."), 404


@app.errorhandler(413)
def file_too_large(_error):
    flash("Размер файла не должен превышать 6 МБ.", "error")
    return redirect(url_for("admin_gallery"))


with app.app_context():
    init_db()

if __name__ == "__main__":
    app.run(debug=True, host="127.0.0.1", port=5000)
