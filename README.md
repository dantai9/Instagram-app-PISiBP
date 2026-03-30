# Gramo — Instagram replika

Projektni zadatak iz Projektovanja informacionih sistema i baza podataka.

## Tim

| Ime i prezime | Uloga |
|---|---|
| Dušan Veljković | Frontend inženjer |
| Kosta Petrović | Backend inženjer A |
| Danilo Milivojević | Backend inženjer B |
| Filip Bogdanović | Backend inženjer C |

---

## Arhitektura aplikacije

Aplikacija je implementirana kao skup od 4 mikroservisa koji međusobno komuniciraju putem HTTP zahteva:

- **user-service** (port 5000) — registracija, prijava, praćenje, blokiranje, pretraga korisnika
- **post-service** (port 5001) — kreiranje objava, upload fajlova, lajkovi, komentari
- **feed-service** (port 5002) — agregira objave praćenih profila i vraća sortiranu vremensku liniju
- **frontend** (port 8080) — statički HTML/CSS/JS fajlovi koje servira nginx

Svaki servis ima svoju SQLite bazu podataka. Autentifikacija je implementirana pomoću JWT tokena koji se deli između servisa putem zajedničkog tajnog ključa.

```
Browser
  ├── frontend:8080          (nginx — statički fajlovi)
  ├── user-service:5000
  ├── post-service:5001
  └── feed-service:5002
        ├── user-service:5000  (lista praćenih)
        └── post-service:5001  (objave po korisniku)
```

---

## Tok izvršavanja funkcionalnosti

**Registracija i prijava**
Korisnik se registruje unosom imena, korisničkog imena, email adrese i lozinke. Prijava je moguća korisničkim imenom ili email adresom. Nakon uspešne prijave, user-service vraća JWT token koji se čuva u localStorage pretraživača i šalje uz svaki naredni zahtev.

**Praćenje korisnika**
Za javne profile, zahtev za praćenje se automatski odobrava. Za privatne profile, kreira se FollowRequest zapis sa statusom "pending" koji vlasnik profila može prihvatiti ili odbiti na stranici za zahteve za praćenje.

**Objavljivanje**
Korisnik može objaviti do 20 fotografija ili video klipova u jednoj objavi (maksimalno 50MB po fajlu). Uz svaku objavu može dodati opis koji je naknadno moguće izmeniti.

**Vremenska linija**
Feed servis dohvata listu praćenih profila od user-servisa, paralelno dohvata objave svakog profila od post-servisa, sortira ih hronološki i vraća paginiranu listu.

**Blokiranje**
Kada korisnik blokira nekog, automatski se ukidaju međusobna praćenja. Lajkovi i komentari blokiranih korisnika se ne prikazuju, a blokirani korisnici ne mogu pronaći profil u pretrazi.

---

## Pokretanje aplikacije

### Preduslov

- Docker i Docker Compose

### Koraci

1. Klonirajte repozitorijum:
```bash
git clone https://github.com/dantai9/Instagram-app-PISiBP.git
cd Instagram-app-PISiBP
```

2. Kreirajte `.env` fajl (opcionalno — aplikacija koristi podrazumevani ključ ako `.env` ne postoji):
```bash
echo "SECRET_KEY=vas_tajni_kljuc" > .env
```

3. Pokrenite aplikaciju:
```bash
docker compose up --build
```

4. Otvorite pretraživač na `http://localhost:8080`

### Zaustavljanje

```bash
docker compose down
```

---

## Pokretanje testova

**Unit testovi:**
```bash
cd user-service && pytest tests/ -v --cov=app
cd post-service && pytest tests/ -v --cov=app
cd feed-service && pytest tests/ -v --cov=app
cd frontend && npm install && npm test
```

**API integracioni testovi** (aplikacija mora biti pokrenuta):
```bash
cd tests && pip install -r requirements.txt
pytest api/test_integration.py -v
```

**UI testovi** (potreban Chromium):
```bash
cd tests
pytest ui/test_ui.py -v
```

---

## CI/CD

- Svaki **Pull Request** automatski pokreće unit testove za sve servise
- Svaki **commit na main granu** pokreće testove i gradi Docker slike koje se objavljuju na Docker Hub sa oznakom u formatu `yyyymmdd-hhmmss`

---


