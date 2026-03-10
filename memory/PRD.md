# Second Chance Market - PRD

## Panoramica
Second Chance Market è una piattaforma mobile per la compravendita di oggetti usati nella comunità locale. Ricrea l'esperienza del mercatino di quartiere nel mondo digitale.

## Valori Fondanti
- **Comunità** - Mercato "rionale" digitale
- **Fiducia** - Transazioni sicure con Stripe e commissione 5%
- **Seconda vita** - Riuso e sostenibilità

## Stack Tecnologico
- **Frontend**: React Native (Expo SDK 54), Expo Router, lucide-react-native
- **Backend**: FastAPI, Python
- **Database**: MongoDB (Motor async driver)
- **Auth**: JWT (email + password)
- **Pagamenti**: Stripe Checkout (chiave test integrata)

## Funzionalità Implementate

### Autenticazione
- Registrazione con nome, email, password
- **Selezione macro area obbligatoria** (20 regioni italiane con tutte le province e coordinate GPS)
- **Checkbox obbligatori** per accettazione Privacy Policy e Regole Community (timestamp salvato in DB)
- Login con JWT token
- Sessione persistente con AsyncStorage

### Pagamenti Stripe
- Stripe Checkout integrato nel flusso acquisto
- Commissione 5% calcolata e mostrata all'utente
- Sessione di pagamento con redirect a Stripe hosted page
- Polling automatico per verifica stato pagamento
- Pagine callback: /payment-success e /payment-cancel
- Webhook Stripe per conferma server-side

### Pannello Admin
- **In-app**: Visibile solo per account admin nel tab Profilo → "Pannello Admin"
- **Web esterno**: Accessibile a `/api/admin-panel` da browser
  - Login: `admin@scm.it` / `admin2024!`
  - Dashboard con statistiche (utenti, annunci, transazioni, revenue commissioni)
  - Tabella utenti con nome, email, zona, ruolo, annunci, acquisti, privacy, data registrazione
  - Eliminazione utenti con rimozione annunci correlati

### Documenti Legali
- **Privacy Policy** GDPR-compliant (12 sezioni) — navigabile da registrazione e profilo
- **Regole Community** (11 sezioni) — navigabile da registrazione e profilo
- Timestamp accettazione salvato per ogni utente
- Riferimento a MongoDB (non Supabase) per archiviazione dati

### Macro Aree (20 Regioni)
- Tutte le 20 regioni italiane con province e coordinate GPS
- Selezione Regione → Provincia in fase di registrazione
- Coordinate GPS assegnate automaticamente in base alla provincia
- Cambio posizione con selettore regione/provincia (limite 24h)

### Home & Navigazione
- 5 tab: Home, Cerca, Vendi, Chat, Profilo
- 6 categorie
- Feed annunci con filtro per categoria
- Watermark Sprout su ogni schermata

### Annunci, Ricerca, Chat
- CRUD annunci completo
- Ricerca con filtri (categoria, prezzo, condizione, keyword)
- Chat post-acquisto per organizzare ritiro/spedizione

## Come integrare le tue chiavi Stripe
Per passare da test a produzione:
1. Vai su https://dashboard.stripe.com/apikeys
2. Copia la tua **Secret Key** (inizia con `sk_live_`)
3. Sostituisci il valore di `STRIPE_API_KEY` in `/app/backend/.env`
4. Riavvia il backend

## API Endpoints
| Metodo | Endpoint | Descrizione |
|--------|----------|-------------|
| GET | /api/macro-areas | 20 regioni con province e coordinate |
| POST | /api/auth/register | Registrazione con regione/provincia |
| POST | /api/auth/login | Login |
| GET | /api/auth/me | Utente corrente |
| PUT | /api/users/location | Aggiorna posizione (24h) |
| GET | /api/listings | Lista annunci (filtri) |
| POST | /api/listings | Crea annuncio |
| GET | /api/listings/{id} | Dettaglio annuncio |
| POST | /api/checkout/create | Crea sessione Stripe |
| GET | /api/checkout/status/{id} | Verifica pagamento |
| POST | /api/webhook/stripe | Webhook Stripe |
| GET | /api/chats | Le mie chat |
| POST | /api/chats/{id}/messages | Invia messaggio |
| GET | /api/categories | Categorie con conteggio |
