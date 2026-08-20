# Product

<!-- impeccable:product-schema 1 -->

## Platform

web

## Stack

FastAPI + SQLite backend, vanilla HTML/CSS/JS dashboard, served via Cloudflare Tunnel at `https://restusec.my.id`.

## Users

Single primary user: the owner (RestuSec). No school or foundation audience — no students, teachers, or parents use this dashboard. The owner fills in attendance status per entry themselves.

## Product Purpose

Personal attendance tracker. The owner records whether an entry is Hadir (present), Izin (permitted leave), or Sakit (sick), keeps a daily log, and reviews it later via a recap. Success means a fast, pleasant way to log attendance and trust the records.

## Positioning

A personal, self-hosted attendance log behind a private dashboard — no institutional overhead, no multi-tenant complexity, just "did they come today?" recorded and recallable.

## Operating Context

- Used from the owner's own laptop and phone browser.
- Primary workflow: open dashboard, see today's log, mark entries Hadir/Izin/Sakit, occasionally export or check recap.
- A public `/absen` page lets someone with the QR token mark attendance for a person without logging in.

## Capabilities and Constraints

- Authentication: admin login per unit (MI/MTs/RA) with bcrypt; JWT bearer tokens in sessionStorage.
- Features: attendance log with date filter, stats cards (total/hadir/izin/sakit), batch delete via long-press, murid list with per-murid QR codes, recap by date range, materi (notes), nilai (grades) with averages, Excel export of log and recap.
- Backend runs on port 8001; `start_all.bat` launches backend + Cloudflare Tunnel (`restusec.my.id`).
- Single-user; data is local SQLite behind the tunnel.

## Brand Commitments

- Name: RestuSec. Keep the existing logo (`static/img/logo.png`).
- Identity may be restyled visually but the name and logo stay.

## Evidence on Hand

- Live app at `https://restusec.my.id` (login page, dashboard, absen page).
- Source: `backend/dashboard/*.html`, `backend/dashboard/static/css/style.css`, `backend/dashboard/static/js/*.js`, `backend/main.py`.
- No fabricated testimonials, customers, or benchmarks — must not invent any.

## Product Principles

- Fast and light: no heavy frameworks, no slow UI, minimal friction for a daily action.
- Honest and simple: one job per screen, clear states (Hadir/Izin/Sakit).
- Private and secure: personal data stays behind auth and the tunnel.
- Self-contained: everything runs from the local folder with `.env`.

## Accessibility & Inclusion

- Works on both laptop and phone browsers (responsive layout already present).
- No product-specific accessibility requirement was established beyond standard web usability.