import os
os.startfile("chrome.exe")

from flask import Flask
app = Flask(__name__)

import sqlite3
from datetime import datetime


class SistemInventaris:
    def __init__(self, db_name="inventaris.db"):
        self.conn = sqlite3.connect(db_name)
        self.cursor = self.conn.cursor()
        self.setup_database()

    def setup_database(self):
        # Tabel pengguna
        self.cursor.execute("""
            CREATE TABLE IF NOT EXISTS users (
                username TEXT PRIMARY KEY,
                password TEXT NOT NULL,
                role TEXT NOT NULL
            )
        """)

        # Tabel master barang
        self.cursor.execute("""
            CREATE TABLE IF NOT EXISTS barang (
                kode_barang TEXT PRIMARY KEY,
                nama_barang TEXT NOT NULL,
                stok INTEGER NOT NULL DEFAULT 0
            )
        """)

        # Tabel kartu stok
        self.cursor.execute("""
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

        # Menyesuaikan akun lama yang sebelumnya memakai role 'user'
        self.cursor.execute(
            "UPDATE users SET role = 'staf' WHERE role = 'user'"
        )

        # Akun bawaan: Admin dan Staf
        self.cursor.execute("""
            INSERT OR IGNORE INTO users (username, password, role)
            VALUES ('admin', 'admin123', 'admin')
        """)
        self.cursor.execute("""
            INSERT OR IGNORE INTO users (username, password, role)
            VALUES ('staf1', 'staf123', 'staf')
        """)
        self.cursor.execute("""
            INSERT OR IGNORE INTO users (username, password, role)
            VALUES ('staf2', 'staf456', 'staf')
        """)

        self.conn.commit()

    def login(self):
        print("\n=== LOGIN SISTEM INVENTARIS ===")
        username = input("Username : ").strip()
        password = input("Password : ").strip()

        self.cursor.execute("""
            SELECT username, role
            FROM users
            WHERE username = ? AND password = ?
        """, (username, password))

        result = self.cursor.fetchone()

        if result:
            username, role = result
            print(
                f"\nLogin berhasil! Selamat datang, "
                f"{username} ({role.upper()})."
            )
            return username, role

        print("\n[!] Username atau password salah.")
        return None, None

    def tambah_barang_baru(self):
        print("\n--- TAMBAH BARANG BARU ---")
        kode = input("Kode Barang : ").strip().upper()
        nama = input("Nama Barang : ").strip()

        if not kode or not nama:
            print("[!] Kode dan nama barang wajib diisi.")
            return

        try:
            stok_awal = int(input("Stok Awal   : "))
            if stok_awal < 0:
                print("[!] Stok awal tidak boleh negatif.")
                return
        except ValueError:
            print("[!] Input stok harus berupa angka.")
            return

        try:
            self.cursor.execute("""
                INSERT INTO barang (kode_barang, nama_barang, stok)
                VALUES (?, ?, ?)
            """, (kode, nama, stok_awal))

            if stok_awal > 0:
                self._catat_kartu_stok(
                    kode, "MASUK", stok_awal, 0, stok_awal,
                    "Stok Awal", "admin"
                )

            self.conn.commit()
            print(f"[✓] Barang '{nama}' berhasil ditambahkan.")

        except sqlite3.IntegrityError:
            print("[!] Kode barang sudah terdaftar.")

    def transaksi_masuk(self, pelaku):
        print("\n--- INPUT BARANG MASUK ---")
        kode = input("Kode Barang : ").strip().upper()

        self.cursor.execute("""
            SELECT nama_barang, stok
            FROM barang
            WHERE kode_barang = ?
        """, (kode,))
        item = self.cursor.fetchone()

        if not item:
            print("[!] Kode barang tidak ditemukan. Tambahkan barang baru terlebih dahulu.")
            return

        nama_barang, stok_awal = item
        print(f"Barang: {nama_barang} | Stok Saat Ini: {stok_awal}")

        try:
            jumlah = int(input("Jumlah Masuk: "))
            if jumlah <= 0:
                print("[!] Jumlah harus lebih dari 0.")
                return
        except ValueError:
            print("[!] Jumlah harus berupa angka.")
            return

        keterangan = input("Keterangan  : ").strip() or "Restock barang"
        stok_akhir = stok_awal + jumlah

        self.cursor.execute("""
            UPDATE barang SET stok = ?
            WHERE kode_barang = ?
        """, (stok_akhir, kode))
        self._catat_kartu_stok(
            kode, "MASUK", jumlah, stok_awal, stok_akhir,
            keterangan, pelaku
        )
        self.conn.commit()
        print(f"[✓] Stok '{nama_barang}' bertambah menjadi {stok_akhir}.")

    def transaksi_keluar(self, pelaku):
        print("\n--- AMBIL BARANG / BARANG KELUAR ---")
        kode = input("Kode Barang  : ").strip().upper()

        self.cursor.execute("""
            SELECT nama_barang, stok
            FROM barang
            WHERE kode_barang = ?
        """, (kode,))
        item = self.cursor.fetchone()

        if not item:
            print("[!] Kode barang tidak ditemukan.")
            return

        nama_barang, stok_awal = item
        print(f"Barang: {nama_barang} | Stok Tersedia: {stok_awal}")

        try:
            jumlah = int(input("Jumlah Diambil: "))
            if jumlah <= 0:
                print("[!] Jumlah harus lebih dari 0.")
                return
            if jumlah > stok_awal:
                print(f"[!] Stok tidak mencukupi! Stok tersedia hanya {stok_awal}.")
                return
        except ValueError:
            print("[!] Jumlah harus berupa angka.")
            return

        keterangan = input("Keterangan   : ").strip() or "Pengambilan barang"
        stok_akhir = stok_awal - jumlah

        self.cursor.execute("""
            UPDATE barang SET stok = ?
            WHERE kode_barang = ?
        """, (stok_akhir, kode))
        self._catat_kartu_stok(
            kode, "KELUAR", jumlah, stok_awal, stok_akhir,
            keterangan, pelaku
        )
        self.conn.commit()

        print(
            f"[✓] Pengambilan barang berhasil dicatat. "
            f"Sisa stok '{nama_barang}': {stok_akhir}."
        )

    def _catat_kartu_stok(
        self, kode, jenis, jumlah, stok_awal, stok_akhir,
        keterangan, oleh
    ):
        waktu = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self.cursor.execute("""
            INSERT INTO kartu_stok
            (tanggal, kode_barang, jenis, jumlah, stok_awal,
             stok_akhir, keterangan, oleh)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            waktu, kode, jenis, jumlah, stok_awal,
            stok_akhir, keterangan, oleh
        ))

    def lihat_daftar_barang(self):
        print("\n=== DAFTAR STOK BARANG ===")
        self.cursor.execute("""
            SELECT kode_barang, nama_barang, stok
            FROM barang
            ORDER BY kode_barang
        """)
        rows = self.cursor.fetchall()

        if not rows:
            print("Belum ada data barang.")
            return

        print(f"{'KODE':<12} | {'NAMA BARANG':<25} | {'STOK':>6}")
        print("-" * 50)
        for kode, nama, stok in rows:
            print(f"{kode:<12} | {nama:<25} | {stok:>6}")

    def lihat_barang_keluar(self):
        print("\n=== RIWAYAT BARANG KELUAR ===")
        self.cursor.execute("""
            SELECT k.tanggal, k.kode_barang, b.nama_barang,
                   k.jumlah, k.stok_awal, k.stok_akhir,
                   k.oleh, k.keterangan
            FROM kartu_stok k
            JOIN barang b ON k.kode_barang = b.kode_barang
            WHERE k.jenis = 'KELUAR'
            ORDER BY k.id DESC
        """)
        rows = self.cursor.fetchall()

        if not rows:
            print("Belum ada riwayat barang keluar.")
            return

        print(
            f"{'TANGGAL':<19} | {'KODE':<10} | {'NAMA BARANG':<20} | "
            f"{'JUMLAH':>6} | {'SISA':>5} | {'OLEH':<10} | KETERANGAN"
        )
        print("-" * 110)

        for tgl, kode, nama, jumlah, awal, akhir, oleh, ket in rows:
            print(
                f"{tgl:<19} | {kode:<10} | {nama:<20} | "
                f"{jumlah:>6} | {akhir:>5} | {oleh:<10} | {ket}"
            )

    def lihat_kartu_stok(self):
        print("\n=== KARTU STOK (SEMUA TRANSAKSI) ===")
        kode = input(
            "Masukkan Kode Barang (kosongkan untuk semua): "
        ).strip().upper()

        if kode:
            self.cursor.execute("""
                SELECT k.tanggal, k.kode_barang, b.nama_barang,
                       k.jenis, k.stok_awal, k.jumlah, k.stok_akhir,
                       k.oleh, k.keterangan
                FROM kartu_stok k
                JOIN barang b ON k.kode_barang = b.kode_barang
                WHERE k.kode_barang = ?
                ORDER BY k.id ASC
            """, (kode,))
        else:
            self.cursor.execute("""
                SELECT k.tanggal, k.kode_barang, b.nama_barang,
                       k.jenis, k.stok_awal, k.jumlah, k.stok_akhir,
                       k.oleh, k.keterangan
                FROM kartu_stok k
                JOIN barang b ON k.kode_barang = b.kode_barang
                ORDER BY k.id ASC
            """)

        rows = self.cursor.fetchall()

        if not rows:
            print("Belum ada riwayat transaksi.")
            return

        print(
            f"{'TANGGAL':<19} | {'KODE':<8} | {'JENIS':<6} | "
            f"{'AWAL':>5} | {'JUMLAH':>6} | {'AKHIR':>5} | "
            f"{'OLEH':<10} | KETERANGAN"
        )
        print("-" * 110)

        for r in rows:
            tgl, kd, nama, jenis, awal, jml, akhir, oleh, ket = r
            tanda = "+" if jenis == "MASUK" else "-"
            print(
                f"{tgl:<19} | {kd:<8} | {jenis:<6} | "
                f"{awal:>5} | {tanda}{jml:<5} | {akhir:>5} | "
                f"{oleh:<10} | {ket}"
            )

    def menu_admin(self, username):
        while True:
            print("\n========== MENU ADMIN ==========")
            print("1. Tambah Barang Baru")
            print("2. Input Barang Masuk")
            print("3. Ambil Barang / Barang Keluar")
            print("4. Lihat Stok Barang")
            print("5. Lihat Riwayat Barang Keluar")
            print("6. Lihat Semua Kartu Stok")
            print("7. Logout")

            pilihan = input("Pilih menu (1-7): ").strip()

            if pilihan == "1":
                self.tambah_barang_baru()
            elif pilihan == "2":
                self.transaksi_masuk(username)
            elif pilihan == "3":
                self.transaksi_keluar(username)
            elif pilihan == "4":
                self.lihat_daftar_barang()
            elif pilihan == "5":
                self.lihat_barang_keluar()
            elif pilihan == "6":
                self.lihat_kartu_stok()
            elif pilihan == "7":
                print("Logout berhasil.")
                break
            else:
                print("[!] Pilihan tidak valid.")

    def menu_staf(self, username):
        while True:
            print("\n========== MENU STAF ==========")
            print("1. Ambil Barang / Barang Keluar")
            print("2. Lihat Riwayat Barang Keluar")
            print("3. Lihat Stok Barang")
            print("4. Logout")

            pilihan = input("Pilih menu (1-4): ").strip()

            if pilihan == "1":
                self.transaksi_keluar(username)
            elif pilihan == "2":
                self.lihat_barang_keluar()
            elif pilihan == "3":
                self.lihat_daftar_barang()
            elif pilihan == "4":
                print("Logout berhasil.")
                break
            else:
                print("[!] Pilihan tidak valid.")

    def jalankan(self):
        try:
            while True:
                username, role = self.login()

                if not role:
                    coba = input("Coba login lagi? (y/n): ").strip().lower()
                    if coba != "y":
                        break
                    continue

                if role == "admin":
                    self.menu_admin(username)
                elif role == "staf":
                    self.menu_staf(username)
                else:
                    print("[!] Role pengguna tidak dikenal.")

                keluar = input(
                    "\nTutup aplikasi sepenuhnya? (y/n): "
                ).strip().lower()
                if keluar == "y":
                    break
        finally:
            self.conn.close()
            print("Program selesai.")


@app.route("/")
def home():
    return"<h1>Hello Word</h1>"

if __name__ == "__main__":
    app = SistemInventaris()
    app.jalankan()
