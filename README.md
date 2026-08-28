# 🍽️ DineSmart — Restaurant Management & Online Ordering System

DineSmart is a full-stack web application for a Bangladeshi restaurant, built as a
Software Engineering course project. It combines online food ordering, conflict-free
table reservations, a staff management dashboard, customer reviews, and an AI-powered
chatbot assistant.

---

## 📋 Table of Contents
1. [Features](#-features)
2. [Tech Stack](#-tech-stack)
3. [System Architecture](#-system-architecture)
4. [Project Structure](#-project-structure)
5. [Setup Instructions](#-setup-instructions)
6. [Default Accounts & Demo Data](#-default-accounts--demo-data)
7. [Key Design Decisions](#-key-design-decisions)

---

## ✨ Features

### Customer-facing
- Browse menu with category filter & search
- Add to cart, checkout with simulated payment (bKash / Nagad / Rocket / Card / Cash on Delivery)
- Real-time order status tracking (Pending → Preparing → Ready → Delivered)
- Table reservation with **conflict-free booking** (two customers can never double-book
  the same table & time slot)
- Leave star ratings + comments on delivered dishes
- AI chatbot (bilingual Bangla/English) that answers questions using **live** menu,
  order, and reservation data — not made-up answers
- Register / Login / Forgot Password (email-based reset)

### Staff-facing
- Separate staff login (`/staff/login/`), independent from the customer-facing site
- Accept or reject incoming orders
- Advance orders through Preparing → Ready → Delivered
- Confirm or reject table reservation requests
- Customers automatically receive an email notification on every status change

### Admin (Django Admin Panel)
- Full CRUD on menu items, categories, tables, orders, reservations, reviews
- Upload real dish photos directly from the admin panel

---

## 🛠️ Tech Stack

| Layer | Technology |
|---|---|
| Frontend | HTML5, CSS3 (custom design system), Bootstrap 5, vanilla JavaScript, Django Templates |
| Backend | Python 3, Django 4.2 (LTS) |
| Database | MySQL (via XAMPP), connected using PyMySQL |
| AI Chatbot | Groq API (Llama 3.3 70B) with a lightweight Retrieval-Augmented Generation (RAG) approach |
| Auth | Django's built-in authentication system |
| Email | Django console/SMTP email backend (password reset, status notifications) |
| Image handling | Pillow (for uploaded menu item photos) |

---

## 🏗️ System Architecture

```
┌─────────────────┐        renders/AJAX        ┌──────────────────┐
│   Frontend       │ ◄────────────────────────► │   Backend         │
│  (Django          │   Django Views + Forms      │  (Django Views,   │
│   Templates,      │   fetch() for chatbot &     │   URLs, Models)   │
│   Bootstrap, JS)   │   staff actions             │                    │
└─────────────────┘                              └─────────┬─────────┘
                                                              │ Django ORM
                                                              ▼
                                                   ┌──────────────────┐
                                                   │   MySQL Database  │
                                                   │  (via XAMPP)       │
                                                   │  Users, MenuItem,  │
                                                   │  Order, Reservation│
                                                   │  Review, etc.      │
                                                   └──────────────────┘

                          ┌──────────────────────┐
                          │   Groq AI (external)  │
                          │  Called from a Django  │
                          │  view; the view first   │
                          │  pulls live data from    │
                          │  MySQL to ground the      │
                          │  answer (RAG).            │
                          └──────────────────────┘
```

**How the three tiers connect:**
- **Frontend ↔ Backend:** Django templates are rendered server-side with data passed
  from views (`render(request, 'menu.html', {'items': items})`). Dynamic interactions
  (add to cart, chatbot, staff actions) use `fetch()` / form POSTs to Django view endpoints
  that return JSON or redirect.
- **Backend ↔ Database:** Django's ORM (`core/models.py`) maps Python classes directly
  to MySQL tables — no raw SQL needed. Table booking uses `select_for_update()` inside
  `transaction.atomic()` blocks, combined with a `unique_together` database constraint,
  to make double-booking impossible even under concurrent requests.
- **Backend ↔ AI:** The chatbot endpoint (`/chatbot/ask/`) queries the database for
  live menu/order/reservation data, builds a context string, and sends it alongside the
  user's question to the Groq API — this is the "Retrieval-Augmented Generation" pattern.

---

## 📁 Project Structure

```
dinesmart/
├── manage.py
├── requirements.txt
├── .env.example              # copy to .env and add your GROQ_API_KEY
├── dinesmart_project/         # Django project settings
│   ├── settings.py
│   ├── urls.py
│   └── __init__.py            # PyMySQL + Python 3.14 compatibility patches
├── core/                      # main Django app
│   ├── models.py              # Category, MenuItem, Order, Reservation, Review, etc.
│   ├── views.py                # all page logic
│   ├── urls.py
│   ├── admin.py
│   ├── chatbot.py              # RAG logic for the AI assistant
│   └── management/commands/
│       └── seed_demo_data.py   # populates sample menu items & tables
└── frontend/
    ├── templates/               # all HTML pages
    └── static/
        ├── css/style.css        # design system (CSS variables/tokens)
        └── js/main.js
```

---

## 🚀 Setup Instructions

### Prerequisites
- Python 3.x installed
- [XAMPP](https://www.apachefriends.org/) installed (for MySQL)
- A free [Groq API key](https://console.groq.com/keys) (for the chatbot)

### 1. Start MySQL
Open XAMPP Control Panel → Start **Apache** and **MySQL**.

### 2. Create the database
Go to `http://localhost/phpmyadmin` → click **New** → create a database named
exactly `dinesmart_db`.

### 3. Set up the Python environment
```bash
cd dinesmart
python -m venv venv
source venv/Scripts/activate      # Windows Git Bash
# venv\Scripts\activate           # Windows CMD
pip install -r requirements.txt
```

### 4. Configure your Groq API key
```bash
cp .env.example .env
```
Open `.env` in a text editor and replace the placeholder with your real key:
```
GROQ_API_KEY=gsk_your_real_key_here
```

### 5. Run migrations & seed sample data
```bash
python manage.py migrate
python manage.py seed_demo_data
python manage.py createsuperuser
```

### 6. Run the server
```bash
python manage.py runserver
```
Visit **http://127.0.0.1:8000/**

---

## 👤 Default Accounts & Demo Data

- **Superuser** — whatever you set with `createsuperuser`. Use it to log into:
  - `/admin/` — full Django admin panel
  - `/staff/login/` — the custom staff dashboard (same credentials)
- **Demo data** — `seed_demo_data` creates 9 menu items across 5 categories and 4
  restaurant tables, ready to browse/order/book immediately.
- **Customer accounts** — anyone can self-register via `/register/`.

---

## 🔑 Key Design Decisions

- **Django 4.2 (not the newest version)** was chosen specifically because XAMPP's
  bundled MariaDB (10.4) doesn't meet the minimum version required by Django 5.1+.
- **PyMySQL instead of mysqlclient** — avoids requiring a C compiler / Visual Studio
  Build Tools on Windows, since PyMySQL is pure Python.
- **Direct Groq SDK instead of full LangChain** — fewer dependencies, same RAG
  approach (retrieve live DB data → augment the prompt → generate an answer).
- **Console email backend by default** — so password reset & notification emails can
  be tested locally (they print to the terminal) without needing real SMTP credentials.
