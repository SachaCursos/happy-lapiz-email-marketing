# Plataforma de email marketing — Happy Lápiz

Plataforma interna de email marketing construida con FastAPI + Next.js + Resend. Permite gestionar contactos, segmentos, campañas, automatizaciones y plantillas de email.

---

## Stack

- **Backend:** Python / FastAPI + PostgreSQL (Railway)
- **Frontend:** Next.js 14 + Tailwind CSS
- **Envío:** Resend API
- **Infra:** Docker Compose (local) / Railway (producción)

---

## Módulos principales

- **Contactos:** importación CSV, perfiles enriquecidos, opt-in/opt-out
- **Segmentos:** constructor visual de condiciones (AND/OR) por atributos y comportamiento
- **Campañas:** broadcast con programación, vista previa y analítica
- **Automatizaciones:** flujos disparados por eventos (bienvenida, reactivación, etc.)
- **Plantillas:** editor de bloques con variables dinámicas `{{nombre}}`, etc.
- **Analítica:** enviados, abiertos, clics, rebotes por campaña

---

## Inicio rápido (local)

```bash
cp backend/.env.example backend/.env
cp frontend/.env.example frontend/.env
# Edita backend/.env con tus credenciales
docker compose up --build
```

Frontend: http://localhost:3000  
API docs: http://localhost:8000/docs

---

## Variables de entorno (backend)

| Variable | Descripción |
|---|---|
| `DATABASE_URL` | PostgreSQL donde viven las tablas de email marketing |
| `SECRET_KEY` | Clave JWT (genera con `openssl rand -hex 32`) |
| `RESEND_API_KEY` | API key de Resend |
| `RESEND_FROM_EMAIL` | Dirección remitente verificada en Resend |
| `FRONTEND_URL` | URL del frontend (para links en emails) |
