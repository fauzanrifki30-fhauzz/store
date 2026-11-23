from flask import Flask, render_template, request, redirect, url_for, session, flash
from functools import wraps
import sqlite3
from datetime import datetime

app = Flask(__name__)
app.secret_key = "ganti-dengan-secret-key-acak-anda"
DB_NAME = "inventaris.db"


import os
import sqlite3

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

DATABASE = os.path.join(BASE_DIR, "inventaris.db")

def get_db():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    return conn


def setup_database():
    conn = get_db()
    cur = conn.cursor()

    cur.execute("""
        CREATE TABLE IF NOT EXISTS users (
            username TEXT PRIMARY KEY,
            password TEXT NOT NULL,
            role TEXT NOT NULL
        )
    """)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS barang (
            kode_barang TEXT PRIMARY KEY,
            nama_barang TEXT NOT NULL,
            stok INTEGER NOT NULL DEFAULT 0
        )
    """)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS kartu_stok (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            tanggal TEXT NOT NULL,
            kode_barang TEXT NOT NULL,
            jenis TEXT NOT NULL,
            jumlah INTEGER NOT NULL,
            stok_awal INTEGER NOT NULL,
            stok_akhir INTEGER NOT NULL,
            keterangan TEXT,
            oleh TEXT NOT NULL,
            FOREIGN KEY (kode_barang) REFERENCES barang (kode_barang)
        )
    """)

    # Migrasi aman untuk database lama.
    kolom_barang = [r["name"] for r in conn.execute("PRAGMA table_info(barang)").fetchall()]
    if "aktif" not in kolom_barang:
        cur.execute("ALTER TABLE barang ADD COLUMN aktif INTEGER NOT NULL DEFAULT 1")

    cur.execute("UPDATE users SET role = 'staf' WHERE role = 'user'")
    cur.execute(
        "INSERT OR IGNORE INTO users (username, password, role) VALUES (?, ?, ?)",
        ("admin", "admin123", "admin")
    )
    cur.execute(
        "INSERT OR IGNORE INTO users (username, password, role) VALUES (?, ?, ?)",
        ("staf1", "staf123", "staf")
    )
    cur.execute(
        "INSERT OR IGNORE INTO users (username, password, role) VALUES (?, ?, ?)",
        ("staf2", "staf456", "staf")
    )

    conn.commit()
    conn.close()


def login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if "username" not in session:
            flash("Silakan login terlebih dahulu.", "warning")
            return redirect(url_for("login"))
        return view(*args, **kwargs)
    return wrapped


def roles_required(*roles):
    def decorator(view):
        @wraps(view)
        @login_required
        def wrapped(*args, **kwargs):
            if session.get("role") not in roles:
                flash("Kamu tidak memiliki akses ke halaman tersebut.", "danger")
                return redirect(url_for("dashboard"))
            return view(*args, **kwargs)
        return wrapped
    return decorator



def buat_kode_barang(conn, kategori):
    prefix_map = {"makanan": "MAK", "minuman": "MNM",
                  "alat_tulis": "ATK", "elektronik": "ELK", "umum": "BRG"}
    prefix = prefix_map.get(kategori, "BRG")
    rows = conn.execute("SELECT kode_barang FROM barang WHERE kode_barang LIKE ?",
                        (prefix + "%",)).fetchall()
    terbesar = 0
    for row in rows:
        akhir = row["kode_barang"][len(prefix):]
        if akhir.isdigit():
            terbesar = max(terbesar, int(akhir))
    return f"{prefix}{terbesar + 1:03d}"


def catat_stok(conn, kode, jenis, jumlah, awal, akhir, keterangan, oleh):
    waktu = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    conn.execute("""
        INSERT INTO kartu_stok
        (tanggal, kode_barang, jenis, jumlah, stok_awal, stok_akhir, keterangan, oleh)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, (waktu, kode, jenis, jumlah, awal, akhir, keterangan, oleh))


@app.route("/")
def index():
    if "username" in session:
        return redirect(url_for("dashboard"))
    return redirect(url_for("login"))


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "").strip()

        conn = get_db()
        user = conn.execute(
            "SELECT username, role FROM users WHERE username = ? AND password = ?",
            (username, password)
        ).fetchone()
        conn.close()

        if user:
            session.clear()
            session["username"] = user["username"]
            session["role"] = user["role"]
            flash(f"Selamat datang, {user['username']}!", "success")
            return redirect(url_for("dashboard"))

        flash("Username atau password salah.", "danger")

    return render_template("login.html")


@app.route("/logout")
def logout():
    session.clear()
    flash("Kamu berhasil logout.", "success")
    return redirect(url_for("login"))


@app.route("/dashboard")
@login_required
def dashboard():
    conn = get_db()
    total_barang = conn.execute("SELECT COUNT(*) AS n FROM barang WHERE aktif = 1").fetchone()["n"]
    total_stok = conn.execute("SELECT COALESCE(SUM(stok), 0) AS n FROM barang WHERE aktif = 1").fetchone()["n"]
    stok_menipis = conn.execute("SELECT COUNT(*) AS n FROM barang WHERE aktif = 1 AND stok <= 5").fetchone()["n"]
    transaksi_keluar = conn.execute(
        "SELECT COUNT(*) AS n FROM kartu_stok WHERE jenis = 'KELUAR'"
    ).fetchone()["n"]
    barang_terbaru = conn.execute(
        "SELECT * FROM barang WHERE aktif = 1 ORDER BY nama_barang LIMIT 8"
    ).fetchall()
    conn.close()
    return render_template(
        "dashboard.html",
        total_barang=total_barang,
        total_stok=total_stok,
        stok_menipis=stok_menipis,
        transaksi_keluar=transaksi_keluar,
        barang=barang_terbaru
    )


@app.route("/barang", methods=["GET", "POST"])
@roles_required("admin")
def barang():
    conn = get_db()
    if request.method == "POST":
        kategori = request.form.get("kategori", "umum")
        nama = request.form.get("nama_barang", "").strip()
        try:
            stok = int(request.form.get("stok", "0"))
        except ValueError:
            stok = -1
        if not nama or stok < 0:
            flash("Nama barang wajib diisi dan stok tidak boleh negatif.", "danger")
        else:
            kode = buat_kode_barang(conn, kategori)
            conn.execute("INSERT INTO barang (kode_barang, nama_barang, stok, aktif) VALUES (?, ?, ?, 1)",
                         (kode, nama, stok))
            if stok > 0:
                catat_stok(conn, kode, "MASUK", stok, 0, stok, "Stok awal", session["username"])
            conn.commit()
            flash(f"Barang berhasil ditambahkan dengan kode {kode}.", "success")
        conn.close()
        return redirect(url_for("barang"))
    rows = conn.execute("SELECT * FROM barang WHERE aktif = 1 ORDER BY kode_barang").fetchall()
    conn.close()
    return render_template("barang.html", barang=rows)


@app.route("/barang/hapus/<kode>", methods=["POST"])
@roles_required("admin")
def hapus_barang(kode):
    conn = get_db()
    item = conn.execute("SELECT * FROM barang WHERE kode_barang = ?", (kode,)).fetchone()
    if not item:
        flash("Barang tidak ditemukan.", "warning")
    else:
        conn.execute("UPDATE barang SET aktif = 0 WHERE kode_barang = ?", (kode,))
        conn.commit()
        flash("Barang dipindahkan ke arsip. Riwayat transaksi tetap tersimpan.", "success")
    conn.close()
    return redirect(url_for("barang"))


@app.route("/arsip-barang")
@roles_required("admin")
def arsip_barang():
    conn = get_db()
    rows = conn.execute("SELECT * FROM barang WHERE aktif = 0 ORDER BY kode_barang").fetchall()
    conn.close()
    return render_template("arsip_barang.html", barang=rows)


@app.route("/barang/pulihkan/<kode>", methods=["POST"])
@roles_required("admin")
def pulihkan_barang(kode):
    conn = get_db()
    conn.execute("UPDATE barang SET aktif = 1 WHERE kode_barang = ?", (kode,))
    conn.commit()
    conn.close()
    flash("Barang berhasil dipulihkan.", "success")
    return redirect(url_for("arsip_barang"))


@app.route("/barang/masuk", methods=["GET", "POST"])
@roles_required("admin")
def barang_masuk():
    conn = get_db()
    if request.method == "POST":
        kode = request.form.get("kode_barang", "").strip().upper()
        keterangan = request.form.get("keterangan", "").strip() or "Restock barang"
        try:
            jumlah = int(request.form.get("jumlah", "0"))
        except ValueError:
            jumlah = 0

        item = conn.execute("SELECT * FROM barang WHERE kode_barang = ?", (kode,)).fetchone()
        if not item:
            flash("Kode barang tidak ditemukan. Tambahkan barang terlebih dahulu.", "danger")
        elif jumlah <= 0:
            flash("Jumlah masuk harus lebih dari 0.", "danger")
        else:
            awal = item["stok"]
            akhir = awal + jumlah
            conn.execute("UPDATE barang SET stok = ? WHERE kode_barang = ?", (akhir, kode))
            catat_stok(conn, kode, "MASUK", jumlah, awal, akhir, keterangan, session["username"])
            conn.commit()
            flash(f"Barang masuk berhasil. Stok sekarang {akhir}.", "success")
            conn.close()
            return redirect(url_for("barang_masuk"))

    rows = conn.execute("SELECT * FROM barang WHERE aktif = 1 ORDER BY nama_barang").fetchall()
    conn.close()
    return render_template("barang_masuk.html", barang=rows)


@app.route("/barang/keluar", methods=["GET", "POST"])
@roles_required("admin", "staf")
def barang_keluar():
    conn = get_db()
    if request.method == "POST":
        kode = request.form.get("kode_barang", "").strip().upper()
        keterangan = request.form.get("keterangan", "").strip() or "Pengambilan barang"
        try:
            jumlah = int(request.form.get("jumlah", "0"))
        except ValueError:
            jumlah = 0

        item = conn.execute("SELECT * FROM barang WHERE kode_barang = ?", (kode,)).fetchone()
        if not item:
            flash("Kode barang tidak ditemukan.", "danger")
        elif jumlah <= 0:
            flash("Jumlah keluar harus lebih dari 0.", "danger")
        elif jumlah > item["stok"]:
            flash(f"Stok tidak cukup. Stok tersedia: {item['stok']}.", "danger")
        else:
            awal = item["stok"]
            akhir = awal - jumlah
            conn.execute("UPDATE barang SET stok = ? WHERE kode_barang = ?", (akhir, kode))
            catat_stok(conn, kode, "KELUAR", jumlah, awal, akhir, keterangan, session["username"])
            conn.commit()
            flash(f"Barang keluar berhasil. Sisa stok {akhir}.", "success")
            conn.close()
            return redirect(url_for("barang_keluar"))

    rows = conn.execute("SELECT * FROM barang WHERE aktif = 1 ORDER BY nama_barang").fetchall()
    conn.close()
    return render_template("barang_keluar.html", barang=rows)


@app.route("/stok")
@login_required
def stok():
    conn = get_db()
    rows = conn.execute("SELECT * FROM barang WHERE aktif = 1 ORDER BY kode_barang").fetchall()
    conn.close()
    return render_template("stok.html", barang=rows)


@app.route("/riwayat")
@login_required
def riwayat():
    conn = get_db()
    rows = conn.execute("""
        SELECT k.*, b.nama_barang
        FROM kartu_stok k
        JOIN barang b ON b.kode_barang = k.kode_barang
        WHERE k.jenis = 'KELUAR'
        ORDER BY k.id DESC
    """).fetchall()
    conn.close()
    return render_template("riwayat.html", transaksi=rows)


@app.route("/riwayat-masuk")
@login_required
def riwayat_masuk():
    conn = get_db()
    rows = conn.execute("""
        SELECT k.*, b.nama_barang FROM kartu_stok k
        JOIN barang b ON b.kode_barang = k.kode_barang
        WHERE k.jenis = 'MASUK' ORDER BY k.id DESC
    """).fetchall()
    conn.close()
    return render_template("riwayat_masuk.html", transaksi=rows)


@app.route("/kartu-stok")
@roles_required("admin")
def kartu_stok():
    kode = request.args.get("kode", "").strip().upper()
    conn = get_db()
    if kode:
        rows = conn.execute("""
            SELECT k.*, b.nama_barang FROM kartu_stok k
            JOIN barang b ON b.kode_barang = k.kode_barang
            WHERE k.kode_barang = ? ORDER BY k.id DESC
        """, (kode,)).fetchall()
    else:
        rows = conn.execute("""
            SELECT k.*, b.nama_barang FROM kartu_stok k
            JOIN barang b ON b.kode_barang = k.kode_barang
            ORDER BY k.id DESC
        """).fetchall()
    daftar_barang = conn.execute("SELECT kode_barang, nama_barang FROM barang WHERE aktif = 1 ORDER BY nama_barang").fetchall()
    conn.close()
    return render_template("kartu_stok.html", transaksi=rows, barang=daftar_barang, kode=kode)


@app.route("/barang/edit/<kode>", methods=["GET", "POST"])
@roles_required("admin")
def edit_barang(kode):
    conn = get_db()

    item = conn.execute(
        "SELECT * FROM barang WHERE kode_barang = ?",
        (kode,)
    ).fetchone()

    if not item:
        conn.close()
        flash("Barang tidak ditemukan.", "danger")
        return redirect(url_for("barang"))

    if request.method == "POST":
        nama = request.form.get("nama_barang", "").strip()

        try:
            stok = int(request.form.get("stok", ""))

            if not nama or stok < 0:
                raise ValueError

            stok_awal = item["stok"]
            conn.execute("""
                UPDATE barang SET nama_barang = ?, stok = ?
                WHERE kode_barang = ?
            """, (nama, stok, kode))
            if stok != stok_awal:
                catat_stok(conn, kode, "PENYESUAIAN", abs(stok-stok_awal),
                           stok_awal, stok, "Penyesuaian stok melalui edit barang",
                           session["username"])
            conn.commit()
            flash("Barang berhasil diperbarui.", "success")

        except ValueError:
            flash("Nama atau stok tidak valid.", "danger")

        finally:
            conn.close()

        return redirect(url_for("barang"))

    conn.close()
    return render_template("edit_barang.html", item=item)

# Membuat tabel dan menjalankan migrasi database
setup_database()

# Menjalankan aplikasi Flask
if __name__ == "__main__":
    app.run(
        host="0.0.0.0",
        port=50,
        debug=True
    )

ASE_DIR = os.path.dirname(os.path.abspath(__file__))

DATABASE = os.path.join(BASE_DIR, "inventaris.db")
