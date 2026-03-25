# Fake Medicine Detection System

Full-stack Flask portal for licensed admins and authenticated users to generate and verify QR-coded medicine batches. Admins are separated by account, so every QR belongs to one admin while logged-in users get a live scanner that also accepts uploaded images.

## Highlights
- **Dual access gateway** (`/`) lets visitors choose either user or admin flows immediately with a medically themed hero.
- **User authentication** protects the camera-based scanner at `/scanner`; once logged in, users can also upload JPG/PNG files for QR extraction.
- **Admin features** include secure login/register, medicine entry, UUID-based QR generation, and per-admin filtering.
- The admin batch entry now captures the manufacturing date and shows it alongside the batch/expiry information across the dashboard and scanner modal.
- **QR verification** happens via `POST /api/verify`; the scanner shows a modal with ✅ Real Medicine details or ❌ Fake Medicine warnings and exposes start/stop/scan-again controls.
- **Visual polish** uses a background image at `static/images/health-bg.png`, so drop the provided asset there to match the sample.

## Database schema (auto-created)
- `users` (id, username, email, password, created_at)
- `admins` (id, username, password, license_number, created_at)
- `medicines` (id, admin_id FK, manufacturing_date, medicine_name, manufacturer, batch_number, expiry_date, qr_code_data UUID, qr_image_path, created_at)

## Setup
1. Create a virtual environment and activate it:
   ```powershell
   python -m venv .venv
   .\.venv\Scripts\Activate
   ```
2. Install dependencies:
   ```powershell
   pip install -r requirements.txt
   ```
3. Run the Flask app (SQLite file, `static/qrcodes`, and tables are created automatically):
   ```powershell
   python app.py
   ```
4. Open `http://127.0.0.1:5000/` to choose either user login/register or admin login/register.

## Scanner flow
1. **User** logs in → `/scanner` shows the camera preview, start/stop/scan-again buttons, and an upload control.
2. **Upload a JPG/PNG** and `html5-qrcode` extracts the QR token; the backend responds `{ status: "real" }` or `{ status: "fake" }` via the same endpoint used for camera scans.
3. **Modal result** surfaces the validation outcome, and the Scan Again button lets the user immediately restart scanning.

## Next steps
- Replace `static/images/health-bg.png` with the provided medical background so the onboarding screen matches the requested aesthetic.
- Run the app under HTTPS if you plan to deploy to ensure camera permissions work on modern browsers.
- Extend analytics/audit trails per admin if you need regulatory evidence for fake reports.
