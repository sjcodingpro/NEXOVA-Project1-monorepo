# website

Nexova's public corporate site: landing page and talent registration form.

## Objective

Present Nexova's services and capture structured leads from professionals
interested in job opportunities, replacing the previous unstructured
email-based intake described in CONTEXT.md.

## Technology

Static HTML + Tailwind CSS (built via the Tailwind CLI) + vanilla JS for
form validation. No frontend framework — served as static files.

## Pages

- `index.html` / `index.es.html` — landing page (English / Spanish)
- `application.html` / `application.es.html` — talent registration form

## Running locally

    npm install
    npm run dev

Serves on http://localhost:3000. `npm run dev` runs the Tailwind watcher
and a static file server concurrently.

## Building for deployment

    npm run build:vercel

Compiles Tailwind output and copies the static files into `public/` for
deployment (Vercel config in `vercel.json`).
