# Online School ERP — Requirement Checklist

## Launch से पहले चाहिए

- School का domain/subdomain
- Paid HTTPS-compatible Django hosting
- Managed PostgreSQL database
- Student photos/logo के लिए S3-compatible object storage
- Automated database और media backups
- School privacy notice, guardian consent process और grievance contact
- Director का strong initial administrator account
- Staff roles और section/subject assignments

## External accounts

- Razorpay merchant account + completed activation/KYC + Test/Live API keys + webhook secret
- MSG91 account + DLT entity/header/template approval
- Meta WhatsApp Business Platform + phone number ID + secure token + approved message template
- Cloudflare Turnstile site/secret keys

## Included versus provider-dependent

| Module | Code included | Live activation के लिए |
|---|---|---|
| UPI/card fee payment | Yes | Razorpay activated account and keys |
| SMS | Yes | MSG91 auth key and DLT-approved flow |
| WhatsApp | Yes | Meta WABA, phone number, token and template |
| CAPTCHA | Yes | Turnstile keys; otherwise local maths CAPTCHA |
| Mobile installation | PWA included | HTTPS hosting and supported browser |
| Transport | Vehicle/route/stop/assignment | GPS device/API only for live tracking |
| Payroll | Salary, monthly records, payslip | School-specific PF/ESI/TDS rules need review |

## Suggested rollout

1. Local demo testing
2. School profile, classes, sections and staff setup
3. Private staging deployment with test data
4. Razorpay Test Mode and message-template testing
5. Backup/restore test and permission review
6. Parent/teacher pilot
7. Live keys and real data migration
8. Regular monitoring, backups and updates
