
Fajlovi:
- index.html
- style.css
- script.js

Kako pokrenuti:
1. Uđi u folder frontend-basic
2. Otvori index.html direktno u browseru
ili pokreni neki mali lokalni server, npr:
   python -m http.server 5500
3. Otvori http://localhost:5500

NAPOMENA:
Frontend je napravljen kao najklasičniji HTML/CSS/JS i pretpostavlja sledeće rute:
- user-service:   GET/POST /users
- user-service:   POST /follow
- post-service:   GET/POST /posts
- feed-service:   GET /feed/<user_id>

Ako su kod tebe rute drugačije, samo promeni u script.js u objektu API.routes.

Ako dobiješ CORS grešku, dodaj CORS u Flask servise.
