from datetime import date, datetime, timedelta
from functools import wraps
from pathlib import Path
from uuid import uuid4

from flask import (
    Blueprint,
    current_app,
    flash,
    jsonify,
    redirect,
    render_template,
    request,
    session,
    url_for,
)
from sqlalchemy import inspect, text
from werkzeug.utils import secure_filename

from models import Admin, Booking, CabinImage, GalleryImage, HeroImage, Home, db


main_bp = Blueprint("main", __name__)


DEFAULT_HERO = "https://images.unsplash.com/photo-1500530855697-b586d89ba3ee?auto=format&fit=crop&w=1800&q=85"
DEFAULT_CABIN_IMAGES = [
    "https://images.unsplash.com/photo-1518733057094-95b53143d2a7?auto=format&fit=crop&w=900&q=80",
    "https://images.unsplash.com/photo-1600585154340-be6161a56a0c?auto=format&fit=crop&w=900&q=80",
]
DEFAULT_GALLERY_IMAGES = [
    "https://images.unsplash.com/photo-1519681393784-d120267933ba?auto=format&fit=crop&w=900&q=80",
    "https://images.unsplash.com/photo-1506905925346-21bda4d32df4?auto=format&fit=crop&w=900&q=80",
    "https://images.unsplash.com/photo-1482192505345-5655af888cc4?auto=format&fit=crop&w=900&q=80",
    "https://images.unsplash.com/photo-1448375240586-882707db888b?auto=format&fit=crop&w=900&q=80",
    "https://images.unsplash.com/photo-1464822759023-fed622ff2c3b?auto=format&fit=crop&w=900&q=80",
    "https://images.unsplash.com/photo-1470770841072-f978cf4d019e?auto=format&fit=crop&w=900&q=80",
]

BOOKING_HOLD_HOURS = 24
ACTIVE_BOOKING_STATUSES = {"pending", "confirmed", "blocked"}
BOOKING_STATUSES = ACTIVE_BOOKING_STATUSES | {"rejected", "expired"}


def login_required(view):
    @wraps(view)
    def wrapped_view(*args, **kwargs):
        if "admin_id" not in session:
            flash("Спочатку увійдіть в адмін-панель.", "warning")
            return redirect(url_for("main.admin_login"))
        return view(*args, **kwargs)

    return wrapped_view


def parse_date(value):
    try:
        return date.fromisoformat(value)
    except (TypeError, ValueError):
        return None


def date_range(start_date, end_date):
    current = start_date
    while current < end_date:
        yield current
        current += timedelta(days=1)


def to_int(value, default=None):
    try:
        if value in (None, ""):
            return default
        return int(value)
    except (TypeError, ValueError):
        return default


def get_home_or_none(home_id):
    parsed_home_id = to_int(home_id)
    if not parsed_home_id:
        return None
    return Home.query.get(parsed_home_id)


def expire_pending_bookings():
    now = datetime.utcnow()
    expired = Booking.query.filter(
        Booking.status == "pending",
        Booking.expires_at.isnot(None),
        Booking.expires_at <= now,
    ).all()
    if not expired:
        return 0

    for booking in expired:
        booking.status = "expired"
    db.session.commit()
    return len(expired)


def normalize_booking_statuses():
    updated = False
    for booking in Booking.query.filter_by(status="cancelled").all():
        booking.status = "rejected"
        updated = True
    for booking in Booking.query.filter_by(status="pending").filter(Booking.expires_at.is_(None)).all():
        booking.expires_at = (booking.created_at or datetime.utcnow()) + timedelta(hours=BOOKING_HOLD_HOURS)
        updated = True
    if updated:
        db.session.commit()


def ensure_runtime_schema():
    inspector = inspect(db.engine)
    existing_tables = set(inspector.get_table_names())

    if "home" in existing_tables:
        home_columns = {column["name"] for column in inspector.get_columns("home")}
        home_column_sql = {
            "number": "ALTER TABLE home ADD COLUMN number VARCHAR(30)",
            "discount": "ALTER TABLE home ADD COLUMN discount INTEGER",
            "capacity": "ALTER TABLE home ADD COLUMN capacity INTEGER",
            "area": "ALTER TABLE home ADD COLUMN area INTEGER",
            "rooms": "ALTER TABLE home ADD COLUMN rooms INTEGER",
            "beds": "ALTER TABLE home ADD COLUMN beds INTEGER",
            "rules": "ALTER TABLE home ADD COLUMN rules TEXT",
        }
        for column_name, statement in home_column_sql.items():
            if column_name not in home_columns:
                db.session.execute(text(statement))

    if "bookings" in existing_tables:
        booking_columns = {column["name"] for column in inspector.get_columns("bookings")}
        if "home_id" not in booking_columns:
            db.session.execute(text("ALTER TABLE bookings ADD COLUMN home_id INTEGER NOT NULL DEFAULT 1"))
        if "expires_at" not in booking_columns:
            db.session.execute(text("ALTER TABLE bookings ADD COLUMN expires_at DATETIME"))

    if "cabin_images" in existing_tables:
        image_columns = {column["name"] for column in inspector.get_columns("cabin_images")}
        if "home_id" not in image_columns:
            db.session.execute(text("ALTER TABLE cabin_images ADD COLUMN home_id INTEGER NOT NULL DEFAULT 1"))
        if "is_main" not in image_columns:
            db.session.execute(text("ALTER TABLE cabin_images ADD COLUMN is_main BOOLEAN NOT NULL DEFAULT 0"))

    db.session.commit()


@main_bp.before_app_request
def refresh_booking_holds():
    if request.endpoint == "static":
        return
    ensure_runtime_schema()
    normalize_booking_statuses()
    expire_pending_bookings()


def dates_are_available(home_id, check_in, check_out, ignore_booking_id=None):
    blocked = Booking.query.filter(
        Booking.home_id == home_id,
        Booking.status.in_(ACTIVE_BOOKING_STATUSES),
    )
    if ignore_booking_id:
        blocked = blocked.filter(Booking.id != ignore_booking_id)

    for booking in blocked.all():
        overlaps = check_in < booking.check_out and check_out > booking.check_in
        if overlaps:
            return False
    return True


def get_blocked_dates():
    bookings = Booking.query.filter(Booking.status.in_(ACTIVE_BOOKING_STATUSES)).all()
    unavailable_dates = {}

    for booking in bookings:
        if booking.home_id not in unavailable_dates:
            unavailable_dates[booking.home_id] = set()

        for day in date_range(booking.check_in, booking.check_out):
            unavailable_dates[booking.home_id].add(day.isoformat())

    return {
        home_id: sorted(dates)
        for home_id, dates in unavailable_dates.items()
    }


def allowed_file(filename):
    extension = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    return extension in current_app.config["ALLOWED_IMAGE_EXTENSIONS"]


def save_uploaded_image(file_storage, folder_name):
    if not file_storage or not file_storage.filename:
        return None
    if not allowed_file(file_storage.filename):
        raise ValueError("Підтримуються лише JPG, PNG або WEBP зображення.")

    upload_dir = Path(current_app.config["UPLOAD_FOLDER"]) / folder_name
    upload_dir.mkdir(parents=True, exist_ok=True)

    safe_name = secure_filename(file_storage.filename)
    filename = f"{uuid4().hex}_{safe_name}"
    file_storage.save(upload_dir / filename)
    return f"uploads/{folder_name}/{filename}"


def remove_uploaded_file(image_path):
    if not image_path or image_path.startswith(("http://", "https://")):
        return
    upload_root = Path(current_app.config["UPLOAD_FOLDER"]).resolve()
    file_path = (current_app.static_folder and Path(current_app.static_folder) / image_path) or None
    if not file_path:
        return
    resolved_path = file_path.resolve()
    if upload_root in resolved_path.parents and resolved_path.exists():
        resolved_path.unlink()


def fill_home_from_form(home, form):
    home.number = form.get("number", "").strip() or None
    home.name = form.get("name", "").strip()
    home.description = form.get("description", "").strip()
    home.daily_price = to_int(form.get("daily_price"), 0)
    home.holiday_price = to_int(form.get("holiday_price"), home.daily_price)
    home.discount = to_int(form.get("discount"))
    home.capacity = to_int(form.get("capacity"))
    home.area = to_int(form.get("area"))
    home.rooms = to_int(form.get("rooms"))
    home.beds = to_int(form.get("beds"))
    home.amenities = ", ".join(form.getlist("amenities")) or form.get("amenities_text", "").strip()
    home.rules = form.get("rules", "").strip() or None
    return home


def get_home_images():
    hero = HeroImage.query.filter_by(is_active=True).order_by(HeroImage.created_at.desc()).first()
    cabin_images = CabinImage.query.order_by(CabinImage.is_main.desc(), CabinImage.created_at.desc()).all()
    gallery_images = GalleryImage.query.order_by(GalleryImage.created_at.desc()).all()

    return {
        "hero_image": hero.image_path if hero else DEFAULT_HERO,
        "cabin_images": cabin_images or DEFAULT_CABIN_IMAGES,
        "gallery_images": gallery_images or DEFAULT_GALLERY_IMAGES,
    }


@main_bp.route("/")
def index():
    images = get_home_images()

    ICON_MAP = {
        "Камін": "icon-fire",
        "Wi-Fi": "icon-wifi",
        "Парковка": "icon-car",
        "Мангал": "icon-fire",
        "Джакузі": "icon-bath",
        "Тераса": "icon-tree",
        "Кухня": "icon-kitchen",
        "Кондиціонер": "icon-snow",
    }

    home = Home.query.order_by(Home.id.asc()).all()

    return render_template(
        "index.html",
        blocked_dates=get_blocked_dates(),
        **images,
        icon_map=ICON_MAP,
        home=home,
    )


@main_bp.route("/availability")
def availability():
    return jsonify({"blocked_dates": get_blocked_dates()})


@main_bp.route("/booking", methods=["GET", "POST"])
def booking():
    if request.method == "POST":
        form = request.form
        check_in = parse_date(form.get("check_in"))
        check_out = parse_date(form.get("check_out"))
        home = get_home_or_none(form.get("home_id"))

        required_fields = ["first_name", "last_name", "phone", "email"]
        missing_fields = [field for field in required_fields if not form.get(field, "").strip()]

        if missing_fields or not check_in or not check_out or not home:
            flash("Заповніть усі обов'язкові поля.", "error")
            return render_template("booking.html", form=form, blocked_dates=get_blocked_dates())

        if check_in < date.today() or check_out <= check_in:
            flash("Перевірте дати заїзду та виїзду.", "error")
            return render_template("booking.html", form=form, blocked_dates=get_blocked_dates())

        if not dates_are_available(home.id, check_in, check_out):
            flash("На жаль, обрані дати вже недоступні.", "error")
            return render_template("booking.html", form=form, blocked_dates=get_blocked_dates())

        new_booking = Booking(
            first_name=form["first_name"].strip(),
            last_name=form["last_name"].strip(),
            phone=form["phone"].strip(),
            email=form["email"].strip(),
            check_in=check_in,
            check_out=check_out,
            comment=form.get("comment", "").strip() or None,
            home_id=home.id,
            status="pending",
            expires_at=datetime.utcnow() + timedelta(hours=BOOKING_HOLD_HOURS),
        )
        db.session.add(new_booking)
        db.session.commit()

        flash("Заявку на бронювання надіслано. Ми зв'яжемося з вами для підтвердження.", "success")
        return redirect(url_for("main.booking"))

    return render_template(
        "booking.html",
        form=request.args,
        blocked_dates=get_blocked_dates(),
    )


@main_bp.route("/admin/login", methods=["GET", "POST"])
def admin_login():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        admin = Admin.query.filter_by(username=username).first()

        config_user = current_app.config["ADMIN_USERNAME"]
        config_password = current_app.config["ADMIN_PASSWORD"]
        fallback_login = username == config_user and password == config_password

        if admin and admin.check_password(password):
            session["admin_id"] = admin.id
            return redirect(url_for("main.admin_dashboard"))
        if fallback_login:
            session["admin_id"] = 0
            return redirect(url_for("main.admin_dashboard"))

        flash("Невірний логін або пароль.", "error")

    return render_template("admin_login.html", blocked_dates=[])


@main_bp.route("/admin/logout")
def admin_logout():
    session.clear()
    flash("Ви вийшли з адмін-панелі.", "success")
    return redirect(url_for("main.admin_login"))


@main_bp.route("/admin")
@login_required
def admin_dashboard():
    bookings = Booking.query.order_by(Booking.created_at.desc()).all()
    homes = Home.query.order_by(Home.id.asc()).all()
    return render_template(
        "admin_dashboard.html",
        bookings=bookings,
        homes=homes,
        hero_images=HeroImage.query.order_by(HeroImage.created_at.desc()).all(),
        cabin_images=CabinImage.query.order_by(CabinImage.is_main.desc(), CabinImage.created_at.desc()).all(),
        gallery_images=GalleryImage.query.order_by(GalleryImage.created_at.desc()).all(),
        blocked_dates=get_blocked_dates(),
    )


@main_bp.post("/admin/bookings/<int:booking_id>/<status>/<int:home>")
@login_required
def update_booking_status(booking_id, status, home):
    if status == "cancelled":
        status = "rejected"

    if status not in BOOKING_STATUSES:
        flash("Невідомий статус бронювання.", "error")
        return redirect(url_for("main.admin_dashboard"))

    booking = Booking.query.get_or_404(booking_id)

    if status == "confirmed" and not dates_are_available(booking.home_id, booking.check_in, booking.check_out, booking.id):
        flash("Ці дати перетинаються з іншим підтвердженим бронюванням.", "error")
        return redirect(url_for("main.admin_dashboard"))

    booking.status = status
    if status in {"confirmed", "rejected", "expired"}:
        booking.expires_at = None
    elif status == "pending" and not booking.expires_at:
        booking.expires_at = datetime.utcnow() + timedelta(hours=BOOKING_HOLD_HOURS)
    db.session.commit()
    flash("Статус бронювання оновлено.", "success")
    return redirect(url_for("main.admin_dashboard"))


@main_bp.post("/admin/manual-booking")
@login_required
def add_manual_booking():
    check_in = parse_date(request.form.get("check_in"))
    check_out = parse_date(request.form.get("check_out"))
    home = get_home_or_none(request.form.get("home_id"))

    if not home or not check_in or not check_out or check_out <= check_in:
        flash("Вкажіть коректний період для блокування дат.", "error")
        return redirect(url_for("main.admin_dashboard"))

    if not dates_are_available(home.id, check_in, check_out):
        flash("Ці дати вже зайняті.", "error")
        return redirect(url_for("main.admin_dashboard"))

    booking = Booking(
        first_name="Адмін",
        last_name="Блокування",
        phone="-",
        email="admin@example.com",
        check_in=check_in,
        check_out=check_out,
        status="blocked",
        source="admin",
        comment=request.form.get("comment", "").strip() or "Додано вручну",
        home_id=home.id,
        expires_at=None,
    )
    db.session.add(booking)
    db.session.commit()
    flash("Дати додано як недоступні.", "success")
    return redirect(url_for("main.admin_dashboard"))


@main_bp.post("/admin/manual-home")
@login_required
def add_manual_home():
    name = request.form.get("name", "").strip()
    description = request.form.get("description", "").strip()
    daily_price = to_int(request.form.get("daily_price"))

    if not name or not description or not daily_price:
        flash("Заповніть всі поля name.", "error")
        return redirect(url_for("main.admin_dashboard"))
    
    home = fill_home_from_form(Home(), request.form)
    db.session.add(home)
    db.session.commit()
    flash("Хатинку додано успішно.", "success")
    return redirect(url_for("main.admin_dashboard"))


@main_bp.post("/admin/homes/<int:home_id>/edit")
@login_required
def edit_home(home_id):
    home = Home.query.get_or_404(home_id)
    name = request.form.get("name", "").strip()
    description = request.form.get("description", "").strip()
    daily_price = to_int(request.form.get("daily_price"))

    if not name or not description or not daily_price:
        flash("Заповніть обов'язкові поля будиночка", "error")
        return redirect(url_for("main.admin_dashboard"))

    fill_home_from_form(home, request.form)
    db.session.commit()
    flash("Дані будиночка оновлено", "success")
    return redirect(url_for("main.admin_dashboard"))


@main_bp.post("/admin/images/cabin/<int:image_id>/main")
@login_required
def set_main_cabin_image(image_id):
    image = CabinImage.query.get_or_404(image_id)
    CabinImage.query.filter_by(home_id=image.home_id).update({"is_main": False})
    image.is_main = True
    db.session.commit()
    flash("Головне фото оновлено", "success")
    return redirect(url_for("main.admin_dashboard"))


@main_bp.post("/admin/images/<image_type>/<int:image_id>/delete")
@login_required
def delete_image(image_type, image_id):
    model_map = {
        "hero": HeroImage,
        "cabin": CabinImage,
        "gallery": GalleryImage,
    }
    image_model = model_map.get(image_type)
    if not image_model:
        flash("Невідомий тип зображення", "error")
        return redirect(url_for("main.admin_dashboard"))

    image = image_model.query.get_or_404(image_id)
    home_id = getattr(image, "home_id", None)
    was_main = getattr(image, "is_main", False)
    remove_uploaded_file(image.image_path)
    db.session.delete(image)
    db.session.flush()

    if image_type == "cabin" and was_main and home_id:
        replacement = CabinImage.query.filter_by(home_id=home_id).order_by(CabinImage.created_at.desc()).first()
        if replacement:
            replacement.is_main = True

    db.session.commit()
    flash("Зображення видалено", "success")
    return redirect(url_for("main.admin_dashboard"))





@main_bp.post("/admin/upload/<image_type>")
@login_required
def upload_image(image_type):
    model_map = {
        "hero": (HeroImage, "hero"),
        "cabin": (CabinImage, "cabin"),
        "gallery": (GalleryImage, "gallery"),
    }
    if image_type not in model_map:
        flash("Невідомий тип зображення.", "error")
        return redirect(url_for("main.admin_dashboard"))

    image_model, folder = model_map[image_type]
    files = request.files.getlist("images") or [request.files.get("image")]
    files = [file for file in files if file and file.filename]
    if not files:
        flash("Оберіть файл для завантаження", "error")
        return redirect(url_for("main.admin_dashboard"))

    if image_type == "cabin":
        home = get_home_or_none(request.form.get("home_id") or request.form.get("id"))
        if not home:
            flash("Оберіть будиночок для фото", "error")
            return redirect(url_for("main.admin_dashboard"))
    else:
        home = None



    try:
        image_path = save_uploaded_image(files[0], folder)
    except ValueError as error:
        flash(str(error), "error")
        return redirect(url_for("main.admin_dashboard"))

    if not image_path:
        flash("Оберіть файл для завантаження.", "error")
        return redirect(url_for("main.admin_dashboard"))

    if image_type == "hero":
        HeroImage.query.update({"is_active": False})
        image = image_model(image_path=image_path, alt_text=request.form.get("alt_text") or "Гори біля хатинки")
    elif image_type == "cabin":
        image = image_model(image_path=image_path, alt_text=request.form.get("alt_text") or "Фото хатинки", home_id=request.form.get("id"))
    else:
        image = image_model(image_path=image_path, alt_text=request.form.get("alt_text") or "Фото хатинки")

    if image_type == "cabin":
        should_be_main = request.form.get("is_main") == "1" or not CabinImage.query.filter_by(home_id=home.id).first()
        if should_be_main:
            CabinImage.query.filter_by(home_id=home.id).update({"is_main": False})
        image.home_id = home.id
        image.alt_text = request.form.get("alt_text") or home.name
        image.is_main = should_be_main

    db.session.add(image)



    if image_type in {"cabin", "gallery"} and len(files) > 1:
        for extra_file in files[1:]:
            try:
                extra_path = save_uploaded_image(extra_file, folder)
            except ValueError as error:
                db.session.rollback()
                flash(str(error), "error")
                return redirect(url_for("main.admin_dashboard"))

            if image_type == "cabin":
                extra_image = image_model(
                    image_path=extra_path,
                    alt_text=request.form.get("alt_text") or home.name,
                    home_id=home.id,
                    is_main=False,
                )
            else:
                extra_image = image_model(image_path=extra_path, alt_text=request.form.get("alt_text") or "Gallery image")
            db.session.add(extra_image)
    db.session.commit()
    flash("Зображення завантажено.", "success")
    return redirect(url_for("main.admin_dashboard"))






