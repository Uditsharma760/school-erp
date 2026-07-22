# School ERP Pro — Online-ready Django ERP

यह package school के लिए role-based, responsive ERP web application है। इसे Windows computer पर local test किया जा सकता है और PostgreSQL + HTTPS hosting पर deploy करके mobile/desktop से online ERP की तरह use किया जा सकता है।

## क्या-क्या integrated है

### अलग portals और permissions

- Principal/Director portal: `/management/login/`
- Teacher portal: `/teacher/login/`
- Parent portal: `/parent/login/`
- Student portal: `/student/login/`
- General login: `/login/`
- Roles: Director, Principal, Teacher, Accountant, Transport Manager, Parent और Student
- Teacher को केवल assigned class/section/subject का academic access
- Principal/Director को पूरे ERP का access
- Parent को केवल linked children का data
- Student को केवल अपना record
- Audit logs: login, attendance, marks, fees, setup और account actions

### Admission और student records

- Public online registration with CAPTCHA
- Personal, guardian, address और academic details
- Parent/guardian consent checkbox, consent timestamp और IP record
- Pending registration approval workflow
- Class और subsection-wise student count/list
- Student/parent User ID और temporary password generation
- Virtual ID card PDF with QR verification

### Attendance, marks और results

- Class-section-wise bulk daily attendance
- Teacher assignment-based permissions
- Exam और subject-wise bulk marks entry
- Automatic total, percentage, grade और pass/fail
- Parent/student online result viewing
- Result PDF download

### Fees और online payment

- Fee structures, manual receipts, paid/due balance
- Razorpay Orders API based UPI/card/netbanking checkout integration
- Server-side payment-signature verification
- Razorpay webhook endpoint: `/webhooks/razorpay/`
- Payment gateway keys न होने पर online payment button disabled रहता है; fake receipt नहीं बनती

### Timetable, transport और payroll

- Class/section timetable
- Teacher timetable और parent/student timetable view
- Vehicle, driver, attendant, route, stops और pickup/drop time
- Student transport assignment और monthly transport fee
- Staff salary structure
- Monthly payroll generation, paid status और payslip PDF

> Transport module administrative route management देता है। Live GPS tracking के लिए अलग GPS device/provider API चाहिए। Payroll में salary/payslip workflow है; statutory PF, ESI, TDS और bank bulk-transfer rules school/accountant को configure या आगे develop करने होंगे।

### SMS, WhatsApp और mobile use

- MSG91 transactional SMS integration hook
- Meta WhatsApp Cloud API template-message integration hook
- Keys/templates न होने पर messages `DEMO` mode में log होते हैं और वास्तव में send नहीं होते
- Installable Progressive Web App (PWA): Android/desktop पर browser से install किया जा सकता है
- Private student pages service worker cache में save नहीं किए जाते

> यह native Play Store/App Store application नहीं है। यह mobile-friendly installable web app है और internet connection पर काम करती है।

---

## Windows पर सबसे आसान installation

1. ZIP को **Extract All** करें।
2. Main folder खोलें, जिसमें `manage.py` दिखाई दे।
3. `FIX_AND_START_ERP.bat` पर double-click करें।
4. पहली installation में internet connected रखें।
5. Browser में `http://127.0.0.1:8000` खुलेगा।

बाद में ERP चलाने के लिए केवल `start_windows.bat` चलाएँ।

### Demo login

| Role | User ID | Password |
|---|---|---|
| Director | `director` | `Director@123` |
| Principal | `principal` | `Principal@123` |
| Teacher | `teacher` | `Teacher@123` |
| Accountant | `accountant` | `Accountant@123` |
| Transport | `transport` | `Transport@123` |
| Parent | `parentdemo` | `Parent@123` |
| Student | `studentdemo` | `Student@123` |

Live use से पहले demo accounts/passwords बदलें या हटाएँ।

### उसी Wi-Fi के phone में local test

1. पहले normal setup पूरा करें।
2. `START_LAN_MODE.bat` चलाएँ।
3. दूसरे CMD में `ipconfig` चलाकर PC का IPv4 address देखें।
4. Phone और PC एक ही Wi-Fi पर रखें।
5. Phone में `http://PC-IP:8000` खोलें, उदाहरण `http://192.168.1.8:8000`।

यह केवल LAN testing है। PC और black CMD window चालू रहने चाहिए। Public internet के लिए hosting आवश्यक है।

---

## पुराने ERP data को इस version में लाना

1. पुराने ERP और सभी CMD windows बंद करें।
2. पुराने folder की `db.sqlite3` और `media` folder का backup लें।
3. नए package में मौजूद `db.sqlite3` का भी backup लें।
4. पुराने `db.sqlite3` को नए main folder में copy करके replace करें।
5. पुराना `media` folder भी नए folder में copy करें।
6. `FIX_AND_START_ERP.bat` चलाएँ।

Script migrations चलाएगा। Existing users मिलने पर demo data add नहीं किया जाएगा। Backup verify किए बिना पुराना folder delete न करें।

---

# Online ERP बनाने की requirements

## अनिवार्य infrastructure

1. **Domain/subdomain** — जैसे `erp.schoolname.in`
2. **HTTPS web hosting** — Django/Gunicorn चलाने वाली service
3. **Managed PostgreSQL database** — SQLite को real multi-user production में use न करें
4. **Persistent media/object storage** — student photos, school logo आदि के लिए S3-compatible storage
5. **Automated backups** — database और media दोनों
6. **Transactional providers** — Razorpay, SMS provider और WhatsApp Business Platform
7. **Monitoring and support** — errors, uptime, disk/database usage और security updates

## Recommended production environment variables

```env
SECRET_KEY=very-long-random-secret
DEBUG=False
ALLOWED_HOSTS=erp.schoolname.in
CSRF_TRUSTED_ORIGINS=https://erp.schoolname.in
DATABASE_URL=postgresql://...
SECURE_SSL_REDIRECT=True
SECURE_HSTS_SECONDS=31536000

INITIAL_ADMIN_USERNAME=your-director-user-id
INITIAL_ADMIN_PASSWORD=use-a-strong-one-time-password
INITIAL_ADMIN_EMAIL=director@schoolname.in
```

पहले successful login के बाद initial password बदलें और hosting dashboard से `INITIAL_ADMIN_PASSWORD` variable हटा दें।

## Student photos के लिए S3-compatible storage

```env
AWS_STORAGE_BUCKET_NAME=...
AWS_ACCESS_KEY_ID=...
AWS_SECRET_ACCESS_KEY=...
AWS_S3_REGION_NAME=...
AWS_S3_ENDPOINT_URL=...
AWS_S3_CUSTOM_DOMAIN=...
AWS_QUERYSTRING_AUTH=True
```

Free hosting की local filesystem पर uploaded photos रखना सुरक्षित नहीं है क्योंकि redeploy/restart पर files हट सकती हैं।

---

# External integrations activate करना

## 1. Razorpay UPI/card payment

Required:

```env
RAZORPAY_KEY_ID=...
RAZORPAY_KEY_SECRET=...
RAZORPAY_WEBHOOK_SECRET=...
```

Setup:

1. Razorpay merchant account बनाकर business/KYC activation पूरा करें।
2. पहले Test Mode keys use करें।
3. Hosting पर तीन variables add करें।
4. Razorpay dashboard में webhook URL set करें:  
   `https://erp.schoolname.in/webhooks/razorpay/`
5. कम-से-कम `payment.captured` और `payment.failed` events enable करें।
6. Test payment और reconciliation verify करने के बाद Live keys लगाएँ।

Key Secret कभी source code, GitHub या screenshot में share न करें।

## 2. MSG91 SMS

Required:

```env
MSG91_AUTH_KEY=...
MSG91_TEMPLATE_ID=...
MSG91_MESSAGE_VARIABLE=MESSAGE
```

India में transactional SMS के लिए school/entity, sender header और message template को DLT platform पर register/approve कराना पड़ता है। ERP message variable का नाम approved MSG91 flow से match होना चाहिए।

## 3. WhatsApp Cloud API

Required:

```env
WHATSAPP_ACCESS_TOKEN=...
WHATSAPP_PHONE_NUMBER_ID=...
WHATSAPP_TEMPLATE_NAME=...
WHATSAPP_TEMPLATE_LANGUAGE=en
WHATSAPP_API_VERSION=v23.0
```

Meta app, WhatsApp Business Account, business phone number और approved template तैयार करें। Current ERP एक body variable वाला template भेजता है; approved template भी उसी structure से match होना चाहिए। Access token को secret रखें।

## 4. Cloudflare Turnstile CAPTCHA

```env
TURNSTILE_SITE_KEY=...
TURNSTILE_SECRET_KEY=...
TURNSTILE_EXPECTED_HOSTNAME=erp.schoolname.in
```

Keys न होने पर local maths CAPTCHA चलता है। Production में Turnstile recommended है और server-side verification code integrated है।

---

# Render पर deployment

Package में `render.yaml` शामिल है।

1. इस folder को private GitHub repository में push करें। `.env`, `db.sqlite3`, `.venv` और `media` GitHub पर push न करें।
2. Render dashboard में **New → Blueprint** चुनकर repository connect करें।
3. Deployment से पहले secret environment variables add करें:
   - `INITIAL_ADMIN_USERNAME`
   - `INITIAL_ADMIN_PASSWORD`
   - `INITIAL_ADMIN_EMAIL`
   - Payment/CAPTCHA/message keys, जब ready हों
4. Deploy करें। Start command migrations चलाकर initial Director account बनाएगा और Gunicorn server शुरू करेगा।
5. Custom domain जोड़ें और environment update करें:

```env
ALLOWED_HOSTS=your-app.onrender.com,erp.schoolname.in
CSRF_TRUSTED_ORIGINS=https://your-app.onrender.com,https://erp.schoolname.in
TURNSTILE_EXPECTED_HOSTNAME=erp.schoolname.in
```

6. Paid PostgreSQL, backups और media object storage configure करने के बाद ही actual student records डालें।

> Included Render Blueprint का free plan केवल demonstration/testing के लिए है। Real school data के लिए free database या temporary filesystem पर निर्भर न रहें।

---

# PWA को phone में install करना

### Android Chrome

ERP HTTPS URL खोलें → browser menu → **Install app** या ERP के top bar में **Install App**।

### iPhone/iPad Safari

ERP URL खोलें → Share button → **Add to Home Screen**।

PWA icon home screen पर आ जाएगा, लेकिन server online और internet available होना चाहिए।

---

# Production security और school responsibilities

- Parent/guardian identity और consent process school policy के अनुसार verify करें
- Aadhaar केवल lawful need पर collect करें; अनावश्यक हो तो field खाली रखें
- HTTPS, strong passwords, least-privilege roles और two-factor protection provider dashboards पर enable करें
- Daily encrypted backups और restore testing रखें
- Payment settlement को Razorpay dashboard/bank statement से reconcile करें
- Audit logs और failed login/provider logs review करें
- Staff exit होते ही account disable करें
- Data retention, correction/deletion requests, grievance contact और breach-response process लिखित रूप में रखें
- Legal/compliance policy के लिए qualified professional से review लें

---

# Testing status

- Django system check passed
- Database migrations passed
- 11 automated access/security/function tests passed
- Principal, teacher, accountant, transport, parent और student portal smoke tests passed
- Result PDF, ID card PDF और payslip PDF generated successfully
- PWA manifest/service worker verified

## Useful URLs

- `/management/login/` — Principal/Director
- `/teacher/login/` — Teacher
- `/parent/login/` — Parent
- `/student/login/` — Student
- `/register/` — Online admission
- `/results/` — Public result lookup
- `/admin/` — Django admin
