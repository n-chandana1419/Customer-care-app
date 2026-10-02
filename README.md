# 🎧 CustomerCareHub

A modern, full-stack style **Customer Care Management System** built with **Python**, **Streamlit** and **SQLite**. Customers can register, log in, submit complaints, track their status, and read responses from the support team.

---

## 1. Introduction

CustomerCareHub is a web-based complaint management platform designed as a final-year college project. It demonstrates a complete CRUD workflow with authentication, database persistence, session management and a clean professional UI.

---

## 2. Features

- 🔐 **User Registration** with validation (email format, 10-digit phone, password strength, duplicate email check).
- 🔒 **Secure Login** with salted SHA-256 password hashing (no plain-text passwords).
- 📊 **Customer Dashboard** with live complaint statistics (Total / Submitted / In Progress / Resolved).
- ➕ **New Complaint** form with category, priority and description.
- 🔎 **My Complaints** page with status filter (All / Submitted / In Progress / Resolved / Rejected).
- 📋 **Complaint Details** view (protected — customer can only see their own complaints).
- 🚪 **Logout** that fully clears the session.
- 🎨 **Professional UI** with custom CSS, metric cards, status badges and clean typography.

---

## 3. Technologies Used

| Layer | Technology |
|-------|------------|
| Frontend | Streamlit + HTML/CSS |
| Backend | Python 3.9+ |
| Database | SQLite (built-in) |
| Security | `hashlib` + `os.urandom` for salted password hashing |

---

## 4. Folder Structure
