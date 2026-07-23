from datetime import date, timedelta
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
from werkzeug.utils import secure_filename

from models import Admin, Booking, CabinImage, GalleryImage, HeroImage, db


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


def dates_are_available(check_in, check_out, ignore_booking_id=None):
    blocked = Booking.query.filter(Booking.status.in_(["confirmed", "blocked"]))
    if ignore_booking_id:
        blocked = blocked.filter(Booking.id != ignore_booking_id)

    for booking in blocked.all():
        overlaps = check_in < booking.check_out and check_out > booking.check_in
        if overlaps:
            return False
    return True


def get_blocked_dates():
    bookings = Booking.query.filter(Booking.status.in_(["confirmed", "blocked"])).all()
    unavailable_dates = set()

    for booking in bookings:
        for day in date_range(booking.check_in, booking.check_out):
            unavailable_dates.add(day.isoformat())

    return sorted(unavailable_dates)


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


def get_home_images():
    hero = HeroImage.query.filter_by(is_active=True).order_by(HeroImage.created_at.desc()).first()
    cabin_images = CabinImage.query.order_by(CabinImage.created_at.desc()).all()
    gallery_images = GalleryImage.query.order_by(GalleryImage.created_at.desc()).all()

    return {
        "hero_image": hero.image_path if hero else DEFAULT_HERO,
        "cabin_images": cabin_images or DEFAULT_CABIN_IMAGES,
        "gallery_images": gallery_images or DEFAULT_GALLERY_IMAGES,
    }


@main_bp.route("/")
def index():
    images = get_home_images()
    return render_template(
        "index.html",
        blocked_dates=get_blocked_dates(),
        **images,
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

        required_fields = ["first_name", "last_name", "phone", "email"]
        missing_fields = [field for field in required_fields if not form.get(field, "").strip()]

        if missing_fields or not check_in or not check_out:
            flash("Заповніть усі обов'язкові поля.", "error")
            return render_template("booking.html", form=form, blocked_dates=get_blocked_dates())

        if check_in < date.today() or check_out <= check_in:
            flash("Перевірте дати заїзду та виїзду.", "error")
            return render_template("booking.html", form=form, blocked_dates=get_blocked_dates())

        if not dates_are_available(check_in, check_out):
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

    return render_template("admin_login.html")


@main_bp.route("/admin/logout")
def admin_logout():
    session.clear()
    flash("Ви вийшли з адмін-панелі.", "success")
    return redirect(url_for("main.admin_login"))


@main_bp.route("/admin")
@login_required
def admin_dashboard():
    bookings = Booking.query.order_by(Booking.created_at.desc()).all()
    return render_template(
        "admin_dashboard.html",
        bookings=bookings,
        hero_images=HeroImage.query.order_by(HeroImage.created_at.desc()).all(),
        cabin_images=CabinImage.query.order_by(CabinImage.created_at.desc()).all(),
        gallery_images=GalleryImage.query.order_by(GalleryImage.created_at.desc()).all(),
        blocked_dates=get_blocked_dates(),
    )


@main_bp.post("/admin/bookings/<int:booking_id>/<status>")
@login_required
def update_booking_status(booking_id, status):
    if status not in {"confirmed", "cancelled", "pending"}:
        flash("Невідомий статус бронювання.", "error")
        return redirect(url_for("main.admin_dashboard"))

    booking = Booking.query.get_or_404(booking_id)

    if status == "confirmed" and not dates_are_available(booking.check_in, booking.check_out, booking.id):
        flash("Ці дати перетинаються з іншим підтвердженим бронюванням.", "error")
        return redirect(url_for("main.admin_dashboard"))

    booking.status = status
    db.session.commit()
    flash("Статус бронювання оновлено.", "success")
    return redirect(url_for("main.admin_dashboard"))


@main_bp.post("/admin/manual-booking")
@login_required
def add_manual_booking():
    check_in = parse_date(request.form.get("check_in"))
    check_out = parse_date(request.form.get("check_out"))

    if not check_in or not check_out or check_out <= check_in:
        flash("Вкажіть коректний період для блокування дат.", "error")
        return redirect(url_for("main.admin_dashboard"))

    if not dates_are_available(check_in, check_out):
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
    )
    db.session.add(booking)
    db.session.commit()
    flash("Дати додано як недоступні.", "success")
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
    try:
        image_path = save_uploaded_image(request.files.get("image"), folder)
    except ValueError as error:
        flash(str(error), "error")
        return redirect(url_for("main.admin_dashboard"))

    if not image_path:
        flash("Оберіть файл для завантаження.", "error")
        return redirect(url_for("main.admin_dashboard"))

    if image_type == "hero":
        HeroImage.query.update({"is_active": False})
        image = image_model(image_path=image_path, alt_text=request.form.get("alt_text") or "Гори біля хатинки")
    else:
        image = image_model(image_path=image_path, alt_text=request.form.get("alt_text") or "Фото хатинки")

    db.session.add(image)
    db.session.commit()
    flash("Зображення завантажено.", "success")
    return redirect(url_for("main.admin_dashboard"))
