from fastapi import FastAPI, APIRouter, HTTPException, Depends, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.responses import HTMLResponse
from dotenv import load_dotenv
from starlette.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
import os
import logging
from pathlib import Path
from pydantic import BaseModel, Field
from typing import List, Optional, Dict
import uuid
import secrets
from datetime import datetime, timezone, timedelta
from jose import jwt, JWTError
from passlib.context import CryptContext
import math
import resend
import stripe
import json

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env')

mongo_url = os.environ['MONGO_URL']
client = AsyncIOMotorClient(mongo_url)
db = client[os.environ.get('DB_NAME', 'second_chance_market')]

JWT_SECRET = os.environ.get('JWT_SECRET', 'scm-secret-key-2024-very-secure')
JWT_ALGORITHM = "HS256"
JWT_EXPIRE_HOURS = 72

STRIPE_API_KEY = os.environ.get('STRIPE_API_KEY')
STRIPE_WEBHOOK_SECRET = os.environ.get('STRIPE_WEBHOOK_SECRET')
RESEND_API_KEY = os.environ.get('RESEND_API_KEY')

# Setup external services
resend.api_key = RESEND_API_KEY
stripe.api_key = STRIPE_API_KEY

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
security = HTTPBearer()

app = FastAPI()
api_router = APIRouter(prefix="/api")

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# --- Constants ---
CATEGORIES = ["Elettronica", "Abbigliamento", "Casa & Arredamento", "Sport & Tempo Libero", "Libri & Media", "Altro"]
CONDITIONS = ["Nuovo", "Come nuovo", "Buono", "Discreto", "Da riparare"]
COMMISSION_RATE = 0.05

# --- Italian Macro Areas ---
MACRO_AREAS: List[Dict] = [
    {"regione": "Lombardia", "province": [
        {"nome": "Milano", "lat": 45.4642, "lng": 9.1900},
        {"nome": "Brescia", "lat": 45.5416, "lng": 10.2118},
        {"nome": "Bergamo", "lat": 45.6983, "lng": 9.6773},
        {"nome": "Monza e Brianza", "lat": 45.5845, "lng": 9.2744},
        {"nome": "Como", "lat": 45.8080, "lng": 9.0852},
        {"nome": "Varese", "lat": 45.8206, "lng": 8.8257},
        {"nome": "Pavia", "lat": 45.1847, "lng": 9.1582},
        {"nome": "Cremona", "lat": 45.1333, "lng": 10.0167},
        {"nome": "Mantova", "lat": 45.1564, "lng": 10.7914},
        {"nome": "Lecco", "lat": 45.8566, "lng": 9.3976},
        {"nome": "Lodi", "lat": 45.3138, "lng": 9.5035},
        {"nome": "Sondrio", "lat": 46.1699, "lng": 9.8788},
    ]},
    {"regione": "Lazio", "province": [
        {"nome": "Roma", "lat": 41.9028, "lng": 12.4964},
        {"nome": "Latina", "lat": 41.4676, "lng": 12.9037},
        {"nome": "Frosinone", "lat": 41.6400, "lng": 13.3500},
        {"nome": "Viterbo", "lat": 42.4201, "lng": 12.1085},
        {"nome": "Rieti", "lat": 42.4039, "lng": 12.8567},
    ]},
    {"regione": "Campania", "province": [
        {"nome": "Napoli", "lat": 40.8518, "lng": 14.2681},
        {"nome": "Salerno", "lat": 40.6824, "lng": 14.7681},
        {"nome": "Caserta", "lat": 41.0742, "lng": 14.3322},
        {"nome": "Avellino", "lat": 40.9146, "lng": 14.7906},
        {"nome": "Benevento", "lat": 41.1297, "lng": 14.7819},
    ]},
    {"regione": "Piemonte", "province": [
        {"nome": "Torino", "lat": 45.0703, "lng": 7.6869},
        {"nome": "Novara", "lat": 45.4493, "lng": 8.6218},
        {"nome": "Alessandria", "lat": 44.9123, "lng": 8.6151},
        {"nome": "Cuneo", "lat": 44.3842, "lng": 7.5426},
        {"nome": "Asti", "lat": 44.9004, "lng": 8.2069},
        {"nome": "Biella", "lat": 45.5629, "lng": 8.0583},
        {"nome": "Verbano-Cusio-Ossola", "lat": 46.1428, "lng": 8.2728},
        {"nome": "Vercelli", "lat": 45.3220, "lng": 8.4186},
    ]},
    {"regione": "Veneto", "province": [
        {"nome": "Venezia", "lat": 45.4408, "lng": 12.3155},
        {"nome": "Verona", "lat": 45.4384, "lng": 10.9916},
        {"nome": "Padova", "lat": 45.4064, "lng": 11.8768},
        {"nome": "Treviso", "lat": 45.6669, "lng": 12.2430},
        {"nome": "Vicenza", "lat": 45.5455, "lng": 11.5354},
        {"nome": "Belluno", "lat": 46.1403, "lng": 12.2168},
        {"nome": "Rovigo", "lat": 45.0700, "lng": 11.7900},
    ]},
    {"regione": "Emilia-Romagna", "province": [
        {"nome": "Bologna", "lat": 44.4949, "lng": 11.3426},
        {"nome": "Modena", "lat": 44.6471, "lng": 10.9252},
        {"nome": "Parma", "lat": 44.8015, "lng": 10.3279},
        {"nome": "Reggio Emilia", "lat": 44.6989, "lng": 10.6310},
        {"nome": "Ravenna", "lat": 44.4184, "lng": 12.2035},
        {"nome": "Rimini", "lat": 44.0594, "lng": 12.5683},
        {"nome": "Forlì-Cesena", "lat": 44.2227, "lng": 12.0408},
        {"nome": "Ferrara", "lat": 44.8381, "lng": 11.6198},
        {"nome": "Piacenza", "lat": 45.0526, "lng": 9.6930},
    ]},
    {"regione": "Toscana", "province": [
        {"nome": "Firenze", "lat": 43.7696, "lng": 11.2558},
        {"nome": "Pisa", "lat": 43.7228, "lng": 10.4017},
        {"nome": "Livorno", "lat": 43.5485, "lng": 10.3106},
        {"nome": "Siena", "lat": 43.3188, "lng": 11.3308},
        {"nome": "Arezzo", "lat": 43.4633, "lng": 11.8798},
        {"nome": "Lucca", "lat": 43.8429, "lng": 10.5027},
        {"nome": "Prato", "lat": 43.8777, "lng": 11.1026},
        {"nome": "Grosseto", "lat": 42.7602, "lng": 11.1135},
        {"nome": "Pistoia", "lat": 43.9335, "lng": 10.9179},
        {"nome": "Massa-Carrara", "lat": 44.0354, "lng": 10.1395},
    ]},
    {"regione": "Sicilia", "province": [
        {"nome": "Palermo", "lat": 38.1157, "lng": 13.3615},
        {"nome": "Catania", "lat": 37.5079, "lng": 15.0830},
        {"nome": "Messina", "lat": 38.1937, "lng": 15.5542},
        {"nome": "Siracusa", "lat": 37.0755, "lng": 15.2866},
        {"nome": "Trapani", "lat": 38.0174, "lng": 12.5140},
        {"nome": "Agrigento", "lat": 37.3111, "lng": 13.5766},
        {"nome": "Ragusa", "lat": 36.9282, "lng": 14.7322},
        {"nome": "Caltanissetta", "lat": 37.4879, "lng": 14.0604},
        {"nome": "Enna", "lat": 37.5675, "lng": 14.2794},
    ]},
    {"regione": "Puglia", "province": [
        {"nome": "Bari", "lat": 41.1171, "lng": 16.8719},
        {"nome": "Lecce", "lat": 40.3516, "lng": 18.1750},
        {"nome": "Taranto", "lat": 40.4644, "lng": 17.2470},
        {"nome": "Foggia", "lat": 41.4622, "lng": 15.5447},
        {"nome": "Brindisi", "lat": 40.6328, "lng": 17.9418},
        {"nome": "Barletta-Andria-Trani", "lat": 41.3215, "lng": 16.2697},
    ]},
    {"regione": "Sardegna", "province": [
        {"nome": "Cagliari", "lat": 39.2238, "lng": 9.1217},
        {"nome": "Sassari", "lat": 40.7259, "lng": 8.5568},
        {"nome": "Nuoro", "lat": 40.3211, "lng": 9.3300},
        {"nome": "Oristano", "lat": 39.9062, "lng": 8.5885},
        {"nome": "Sud Sardegna", "lat": 39.5088, "lng": 8.8963},
    ]},
    {"regione": "Calabria", "province": [
        {"nome": "Cosenza", "lat": 39.3088, "lng": 16.2503},
        {"nome": "Catanzaro", "lat": 38.9108, "lng": 16.5872},
        {"nome": "Reggio Calabria", "lat": 38.1111, "lng": 15.6472},
        {"nome": "Crotone", "lat": 39.0841, "lng": 17.1228},
        {"nome": "Vibo Valentia", "lat": 38.6730, "lng": 16.1006},
    ]},
    {"regione": "Liguria", "province": [
        {"nome": "Genova", "lat": 44.4056, "lng": 8.9463},
        {"nome": "Savona", "lat": 44.3092, "lng": 8.4772},
        {"nome": "La Spezia", "lat": 44.1025, "lng": 9.8240},
        {"nome": "Imperia", "lat": 43.8896, "lng": 8.0399},
    ]},
    {"regione": "Marche", "province": [
        {"nome": "Ancona", "lat": 43.6158, "lng": 13.5189},
        {"nome": "Pesaro e Urbino", "lat": 43.9098, "lng": 12.9131},
        {"nome": "Macerata", "lat": 43.2991, "lng": 13.4534},
        {"nome": "Ascoli Piceno", "lat": 42.8534, "lng": 13.5749},
        {"nome": "Fermo", "lat": 43.1601, "lng": 13.7154},
    ]},
    {"regione": "Abruzzo", "province": [
        {"nome": "L'Aquila", "lat": 42.3498, "lng": 13.3995},
        {"nome": "Pescara", "lat": 42.4618, "lng": 14.2146},
        {"nome": "Chieti", "lat": 42.3510, "lng": 14.1677},
        {"nome": "Teramo", "lat": 42.6589, "lng": 13.7042},
    ]},
    {"regione": "Friuli Venezia Giulia", "province": [
        {"nome": "Trieste", "lat": 45.6495, "lng": 13.7768},
        {"nome": "Udine", "lat": 46.0711, "lng": 13.2346},
        {"nome": "Pordenone", "lat": 45.9564, "lng": 12.6615},
        {"nome": "Gorizia", "lat": 45.9412, "lng": 13.6218},
    ]},
    {"regione": "Umbria", "province": [
        {"nome": "Perugia", "lat": 43.1107, "lng": 12.3908},
        {"nome": "Terni", "lat": 42.5636, "lng": 12.6427},
    ]},
    {"regione": "Basilicata", "province": [
        {"nome": "Potenza", "lat": 40.6404, "lng": 15.8056},
        {"nome": "Matera", "lat": 40.6664, "lng": 16.6044},
    ]},
    {"regione": "Trentino-Alto Adige", "province": [
        {"nome": "Trento", "lat": 46.0748, "lng": 11.1217},
        {"nome": "Bolzano", "lat": 46.4983, "lng": 11.3548},
    ]},
    {"regione": "Molise", "province": [
        {"nome": "Campobasso", "lat": 41.5608, "lng": 14.6685},
        {"nome": "Isernia", "lat": 41.5961, "lng": 14.2325},
    ]},
    {"regione": "Valle d'Aosta", "province": [
        {"nome": "Aosta", "lat": 45.7370, "lng": 7.3151},
    ]},
]

# --- Models ---
class UserRegister(BaseModel):
    name: str
    email: str
    password: str
    regione: str = ""
    provincia: str = ""
    accepted_privacy: bool = False
    accepted_rules: bool = False

class UserLogin(BaseModel):
    email: str
    password: str

class LocationUpdate(BaseModel):
    latitude: float
    longitude: float
    neighborhood: str = ""
    regione: str = ""
    provincia: str = ""

class ListingCreate(BaseModel):
    title: str
    description: str
    price: float
    category: str
    condition: str
    images: List[str] = []
    latitude: Optional[float] = None
    longitude: Optional[float] = None

class ListingUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    price: Optional[float] = None
    category: Optional[str] = None
    condition: Optional[str] = None
    images: Optional[List[str]] = None

class MessageCreate(BaseModel):
    text: str

class PurchaseRequest(BaseModel):
    listing_id: str
    origin_url: str

class PasswordResetRequest(BaseModel):
    email: str

class PasswordResetConfirm(BaseModel):
    token: str
    new_password: str

class ReportCreate(BaseModel):
    reported_type: str
    reported_id: str
    reason: str
    description: str = ""

class RatingCreate(BaseModel):
    transaction_id: str
    rating: int
    comment: str = ""

class AvatarUpdate(BaseModel):
    avatar: str

class ValuationRequest(BaseModel):
    images: List[str]
    category: str
    dating: str
    condition: str
    description: str
    brand: str = ""
    origin_url: str

class ValuationMessage(BaseModel):
    text: str

# --- Email Service ---
def send_email(to: str, subject: str, html: str):
    try:
        params = {
            "from": "Second Chance Market <noreply@secondchancemarket.store>",
            "to": [to],
            "subject": subject,
            "html": html,
        }
        response = resend.Emails.send(params)
        logger.info(f"Email sent to {to}: {response}")
        return response
    except Exception as e:
        logger.error(f"Failed to send email to {to}: {e}")
        return None

def send_verification_email(to: str, name: str, token: str):
    verification_url = f"https://secondchancemarket.store/verify?token={token}"
    html = f"""
    <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
        <h2 style="color: #2D5A3D;">Benvenuto su Second Chance Market!</h2>
        <p>Ciao <strong>{name}</strong>,</p>
        <p>Grazie per esserti registrato! Per completare la registrazione, conferma il tuo indirizzo email cliccando il pulsante qui sotto:</p>
        <div style="text-align: center; margin: 30px 0;">
            <a href="{verification_url}" style="background-color: #2D5A3D; color: white; padding: 12px 30px; text-decoration: none; border-radius: 25px; font-weight: bold;">
                Verifica Email
            </a>
        </div>
        <p style="color: #666; font-size: 14px;">Se il pulsante non funziona, copia e incolla questo link nel browser:</p>
        <p style="color: #666; font-size: 12px; word-break: break-all;">{verification_url}</p>
        <p style="color: #666; font-size: 14px;">Il link scade tra 24 ore.</p>
        <hr style="border: none; border-top: 1px solid #eee; margin: 20px 0;">
        <p style="color: #999; font-size: 12px;">Se non hai creato un account su Second Chance Market, ignora questa email.</p>
    </div>
    """
    return send_email(to, "Verifica il tuo indirizzo email - Second Chance Market", html)

def send_password_reset_email(to: str, name: str, token: str):
    reset_url = f"https://secondchancemarket.store/reset-password?token={token}"
    html = f"""
    <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
        <h2 style="color: #2D5A3D;">Recupero Password</h2>
        <p>Ciao <strong>{name}</strong>,</p>
        <p>Hai richiesto di reimpostare la tua password. Clicca il pulsante qui sotto per crearne una nuova:</p>
        <div style="text-align: center; margin: 30px 0;">
            <a href="{reset_url}" style="background-color: #2D5A3D; color: white; padding: 12px 30px; text-decoration: none; border-radius: 25px; font-weight: bold;">
                Reimposta Password
            </a>
        </div>
        <p style="color: #666; font-size: 14px;">Se il pulsante non funziona, copia e incolla questo link nel browser:</p>
        <p style="color: #666; font-size: 12px; word-break: break-all;">{reset_url}</p>
        <p style="color: #666; font-size: 14px;">Il link scade tra 1 ora.</p>
        <hr style="border: none; border-top: 1px solid #eee; margin: 20px 0;">
        <p style="color: #999; font-size: 12px;">Se non hai richiesto il recupero password, ignora questa email. La tua password rimarrà invariata.</p>
    </div>
    """
    return send_email(to, "Recupero Password - Second Chance Market", html)

def send_transaction_complete_email(to: str, buyer_name: str, seller_name: str, listing_title: str, is_buyer: bool):
    role = "acquistato" if is_buyer else "venduto"
    other_party = seller_name if is_buyer else buyer_name
    html = f"""
    <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
        <h2 style="color: #2D5A3D;">Transazione Completata!</h2>
        <p>Ciao,</p>
        <p>La transazione per <strong>"{listing_title}"</strong> è stata completata con successo!</p>
        <p>Hai {role} questo articolo {"da" if is_buyer else "a"} <strong>{other_party}</strong>.</p>
        <p>Ora puoi comunicare con {"il venditore" if is_buyer else "l'acquirente"} tramite la chat nell'app per organizzare la consegna.</p>
        <div style="background-color: #f5f5f5; padding: 15px; border-radius: 10px; margin: 20px 0;">
            <p style="margin: 0; color: #666;">Non dimenticare di lasciare una valutazione dopo aver completato lo scambio!</p>
        </div>
        <hr style="border: none; border-top: 1px solid #eee; margin: 20px 0;">
        <p style="color: #999; font-size: 12px;">Grazie per usare Second Chance Market!</p>
    </div>
    """
    return send_email(to, f"Transazione Completata: {listing_title}", html)

# --- Auth Helpers ---
def create_token(user_id: str, email: str) -> str:
    payload = {
        "sub": user_id,
        "email": email,
        "exp": datetime.now(timezone.utc) + timedelta(hours=JWT_EXPIRE_HOURS)
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)

async def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)):
    try:
        payload = jwt.decode(credentials.credentials, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        user_id = payload.get("sub")
        if not user_id:
            raise HTTPException(status_code=401, detail="Token non valido")
        user = await db.users.find_one({"id": user_id}, {"_id": 0})
        if not user:
            raise HTTPException(status_code=401, detail="Utente non trovato")
        return user
    except JWTError:
        raise HTTPException(status_code=401, detail="Token scaduto o non valido")

def haversine_distance(lat1, lon1, lat2, lon2):
    R = 6371
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = math.sin(dlat/2)**2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon/2)**2
    c = 2 * math.asin(math.sqrt(a))
    return R * c

def find_province_coords(regione: str, provincia: str):
    for area in MACRO_AREAS:
        if area["regione"] == regione:
            for prov in area["province"]:
                if prov["nome"] == provincia:
                    return prov["lat"], prov["lng"]
    return 41.9028, 12.4964

# --- Macro Areas Route ---
@api_router.get("/macro-areas")
async def get_macro_areas():
    return MACRO_AREAS

# --- Auth Routes ---
@api_router.post("/auth/register")
async def register(data: UserRegister):
    if not data.accepted_privacy or not data.accepted_rules:
        raise HTTPException(status_code=400, detail="Devi accettare Privacy Policy e Regole per registrarti")
    existing = await db.users.find_one({"email": data.email.lower()})
    if existing:
        raise HTTPException(status_code=400, detail="Email già registrata")

    lat, lng = find_province_coords(data.regione, data.provincia)
    neighborhood = f"{data.provincia}, {data.regione}" if data.provincia and data.regione else "Roma, Lazio"

    verification_token = secrets.token_urlsafe(32)

    user_id = str(uuid.uuid4())
    user = {
        "id": user_id,
        "name": data.name,
        "email": data.email.lower(),
        "password_hash": pwd_context.hash(data.password),
        "latitude": lat,
        "longitude": lng,
        "neighborhood": neighborhood,
        "regione": data.regione or "Lazio",
        "provincia": data.provincia or "Roma",
        "location_updated_at": None,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "avatar": None,
        "role": "user",
        "accepted_privacy_at": datetime.now(timezone.utc).isoformat(),
        "accepted_rules_at": datetime.now(timezone.utc).isoformat(),
        "email_verified": False,
        "email_verification_token": verification_token,
        "email_verification_expires": (datetime.now(timezone.utc) + timedelta(hours=24)).isoformat(),
        "rating_avg": 0,
        "rating_count": 0,
    }
    await db.users.insert_one(user)

    send_verification_email(data.email.lower(), data.name, verification_token)

    token = create_token(user_id, data.email.lower())
    return {
        "token": token,
        "user": {
            "id": user_id,
            "name": data.name,
            "email": data.email.lower(),
            "latitude": lat,
            "longitude": lng,
            "neighborhood": neighborhood,
            "regione": user["regione"],
            "provincia": user["provincia"],
            "email_verified": False,
        }
    }

@api_router.post("/auth/verify-email")
async def verify_email(token: str):
    user = await db.users.find_one({"email_verification_token": token})
    if not user:
        raise HTTPException(status_code=400, detail="Token non valido o scaduto")

    expires = datetime.fromisoformat(user.get("email_verification_expires", ""))
    if datetime.now(timezone.utc) > expires.replace(tzinfo=timezone.utc):
        raise HTTPException(status_code=400, detail="Token scaduto. Richiedi un nuovo link di verifica.")

    await db.users.update_one(
        {"id": user["id"]},
        {"$set": {
            "email_verified": True,
            "email_verification_token": None,
            "email_verification_expires": None,
        }}
    )
    return {"message": "Email verificata con successo!"}

@api_router.post("/auth/resend-verification")
async def resend_verification(user=Depends(get_current_user)):
    if user.get("email_verified"):
        raise HTTPException(status_code=400, detail="Email già verificata")

    new_token = secrets.token_urlsafe(32)
    await db.users.update_one(
        {"id": user["id"]},
        {"$set": {
            "email_verification_token": new_token,
            "email_verification_expires": (datetime.now(timezone.utc) + timedelta(hours=24)).isoformat(),
        }}
    )
    send_verification_email(user["email"], user["name"], new_token)
    return {"message": "Email di verifica inviata"}

@api_router.post("/auth/forgot-password")
async def forgot_password(data: PasswordResetRequest):
    user = await db.users.find_one({"email": data.email.lower()})
    if not user:
        return {"message": "Se l'email esiste, riceverai un link per reimpostare la password"}

    reset_token = secrets.token_urlsafe(32)
    await db.users.update_one(
        {"id": user["id"]},
        {"$set": {
            "password_reset_token": reset_token,
            "password_reset_expires": (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat(),
        }}
    )
    send_password_reset_email(user["email"], user["name"], reset_token)
    return {"message": "Se l'email esiste, riceverai un link per reimpostare la password"}

@api_router.post("/auth/reset-password")
async def reset_password(data: PasswordResetConfirm):
    user = await db.users.find_one({"password_reset_token": data.token})
    if not user:
        raise HTTPException(status_code=400, detail="Token non valido o scaduto")

    expires = datetime.fromisoformat(user.get("password_reset_expires", ""))
    if datetime.now(timezone.utc) > expires.replace(tzinfo=timezone.utc):
        raise HTTPException(status_code=400, detail="Token scaduto. Richiedi un nuovo link.")

    if len(data.new_password) < 6:
        raise HTTPException(status_code=400, detail="La password deve avere almeno 6 caratteri")

    await db.users.update_one(
        {"id": user["id"]},
        {"$set": {
            "password_hash": pwd_context.hash(data.new_password),
            "password_reset_token": None,
            "password_reset_expires": None,
        }}
    )
    return {"message": "Password reimpostata con successo!"}

@api_router.post("/auth/login")
async def login(data: UserLogin):
    user = await db.users.find_one({"email": data.email.lower()}, {"_id": 0})
    if not user or not pwd_context.verify(data.password, user["password_hash"]):
        raise HTTPException(status_code=401, detail="Credenziali non valide")
    token = create_token(user["id"], user["email"])
    return {
        "token": token,
        "user": {
            "id": user["id"],
            "name": user["name"],
            "email": user["email"],
            "latitude": user.get("latitude", 0),
            "longitude": user.get("longitude", 0),
            "neighborhood": user.get("neighborhood", ""),
            "regione": user.get("regione", ""),
            "provincia": user.get("provincia", ""),
            "role": user.get("role", "user"),
        }
    }

@api_router.get("/auth/me")
async def get_me(user=Depends(get_current_user)):
    return {
        "id": user["id"],
        "name": user["name"],
        "email": user["email"],
        "latitude": user.get("latitude", 0),
        "longitude": user.get("longitude", 0),
        "neighborhood": user.get("neighborhood", ""),
        "regione": user.get("regione", ""),
        "provincia": user.get("provincia", ""),
        "role": user.get("role", "user"),
        "avatar": user.get("avatar"),
        "email_verified": user.get("email_verified", False),
        "rating_avg": user.get("rating_avg", 0),
        "rating_count": user.get("rating_count", 0),
        "created_at": user.get("created_at", "")
    }

# --- User Routes ---
@api_router.put("/users/location")
async def update_location(data: LocationUpdate, user=Depends(get_current_user)):
    last_update = user.get("location_updated_at")
    if last_update:
        last_dt = datetime.fromisoformat(last_update) if isinstance(last_update, str) else last_update
        if last_dt.tzinfo is None:
            last_dt = last_dt.replace(tzinfo=timezone.utc)
        diff = datetime.now(timezone.utc) - last_dt
        if diff < timedelta(hours=24):
            remaining = timedelta(hours=24) - diff
            hours = int(remaining.total_seconds() // 3600)
            mins = int((remaining.total_seconds() % 3600) // 60)
            raise HTTPException(status_code=429, detail=f"Puoi cambiare posizione tra {hours}h {mins}m")

    lat = data.latitude
    lng = data.longitude
    if data.regione and data.provincia:
        lat, lng = find_province_coords(data.regione, data.provincia)

    neighborhood = data.neighborhood or (f"{data.provincia}, {data.regione}" if data.provincia else user.get("neighborhood", ""))

    await db.users.update_one(
        {"id": user["id"]},
        {"$set": {
            "latitude": lat,
            "longitude": lng,
            "neighborhood": neighborhood,
            "regione": data.regione or user.get("regione", ""),
            "provincia": data.provincia or user.get("provincia", ""),
            "location_updated_at": datetime.now(timezone.utc).isoformat()
        }}
    )
    return {"message": "Posizione aggiornata", "neighborhood": neighborhood}

@api_router.delete("/users/me")
async def delete_account(user=Depends(get_current_user)):
    user_id = user["id"]

    await db.listings.delete_many({"seller_id": user_id})
    await db.chats.delete_many({"$or": [{"buyer_id": user_id}, {"seller_id": user_id}]})
    await db.reports.delete_many({"reporter_id": user_id})
    await db.ratings.delete_many({"$or": [{"rater_id": user_id}, {"rated_id": user_id}]})
    await db.users.delete_one({"id": user_id})

    logger.info(f"Account deleted: {user['email']}")
    return {"message": "Account eliminato con successo"}

@api_router.put("/users/avatar")
async def update_avatar(data: AvatarUpdate, user=Depends(get_current_user)):
    if not data.avatar:
        raise HTTPException(status_code=400, detail="Avatar richiesto")
    if not data.avatar.startswith('data:image/'):
        raise HTTPException(status_code=400, detail="Formato immagine non valido")

    await db.users.update_one(
        {"id": user["id"]},
        {"$set": {"avatar": data.avatar}}
    )
    return {"message": "Avatar aggiornato", "avatar": data.avatar}

@api_router.get("/users/{user_id}")
async def get_user_profile(user_id: str):
    user = await db.users.find_one({"id": user_id}, {"_id": 0, "password_hash": 0})
    if not user:
        raise HTTPException(status_code=404, detail="Utente non trovato")
    listings_count = await db.listings.count_documents({"seller_id": user_id, "status": "active"})
    sales_count = await db.transactions.count_documents({"seller_id": user_id, "status": "completed"})
    return {
        "id": user["id"],
        "name": user["name"],
        "neighborhood": user.get("neighborhood", ""),
        "regione": user.get("regione", ""),
        "provincia": user.get("provincia", ""),
        "created_at": user.get("created_at", ""),
        "listings_count": listings_count,
        "sales_count": sales_count
    }

# --- Listing Routes ---
@api_router.post("/listings")
async def create_listing(data: ListingCreate, user=Depends(get_current_user)):
    if data.category not in CATEGORIES:
        raise HTTPException(status_code=400, detail="Categoria non valida")
    if data.condition not in CONDITIONS:
        raise HTTPException(status_code=400, detail="Condizione non valida")
    listing_id = str(uuid.uuid4())
    listing = {
        "id": listing_id,
        "title": data.title,
        "description": data.description,
        "price": data.price,
        "category": data.category,
        "condition": data.condition,
        "images": data.images[:5],
        "seller_id": user["id"],
        "seller_name": user["name"],
        "seller_neighborhood": user.get("neighborhood", ""),
        "latitude": data.latitude or user.get("latitude", 0),
        "longitude": data.longitude or user.get("longitude", 0),
        "status": "active",
        "created_at": datetime.now(timezone.utc).isoformat()
    }
    await db.listings.insert_one(listing)
    listing.pop("_id", None)
    return listing

@api_router.get("/listings")
async def get_listings(
    category: Optional[str] = None,
    search: Optional[str] = None,
    min_price: Optional[float] = None,
    max_price: Optional[float] = None,
    condition: Optional[str] = None,
    latitude: Optional[float] = None,
    longitude: Optional[float] = None,
    radius_km: float = 10,
    sort: str = "newest",
    skip: int = 0,
    limit: int = 20,
    seller_id: Optional[str] = None,
):
    query: dict = {"status": "active"}
    if category:
        query["category"] = category
    if search:
        query["$or"] = [
            {"title": {"$regex": search, "$options": "i"}},
            {"description": {"$regex": search, "$options": "i"}}
        ]
    if min_price is not None:
        query.setdefault("price", {})
        query["price"]["$gte"] = min_price
    if max_price is not None:
        query.setdefault("price", {})
        query["price"]["$lte"] = max_price
    if condition:
        query["condition"] = condition
    if seller_id:
        query["seller_id"] = seller_id

    sort_field = [("created_at", -1)]
    if sort == "price_asc":
        sort_field = [("price", 1)]
    elif sort == "price_desc":
        sort_field = [("price", -1)]

    listings = await db.listings.find(query, {"_id": 0}).sort(sort_field).skip(skip).limit(limit).to_list(limit)

    if latitude is not None and longitude is not None:
        listings = [
            l for l in listings
            if haversine_distance(latitude, longitude, l.get("latitude", 0), l.get("longitude", 0)) <= radius_km
        ]

    return listings

@api_router.get("/listings/{listing_id}")
async def get_listing(listing_id: str):
    listing = await db.listings.find_one({"id": listing_id}, {"_id": 0})
    if not listing:
        raise HTTPException(status_code=404, detail="Annuncio non trovato")
    return listing

@api_router.put("/listings/{listing_id}")
async def update_listing(listing_id: str, data: ListingUpdate, user=Depends(get_current_user)):
    listing = await db.listings.find_one({"id": listing_id})
    if not listing:
        raise HTTPException(status_code=404, detail="Annuncio non trovato")
    if listing["seller_id"] != user["id"]:
        raise HTTPException(status_code=403, detail="Non autorizzato")
    update_data = {k: v for k, v in data.dict().items() if v is not None}
    if update_data:
        await db.listings.update_one({"id": listing_id}, {"$set": update_data})
    updated = await db.listings.find_one({"id": listing_id}, {"_id": 0})
    return updated

@api_router.delete("/listings/{listing_id}")
async def delete_listing(listing_id: str, user=Depends(get_current_user)):
    listing = await db.listings.find_one({"id": listing_id})
    if not listing:
        raise HTTPException(status_code=404, detail="Annuncio non trovato")
    if listing["seller_id"] != user["id"]:
        raise HTTPException(status_code=403, detail="Non autorizzato")
    await db.listings.delete_one({"id": listing_id})
    return {"message": "Annuncio eliminato"}

# --- Stripe Payment Routes ---
@api_router.post("/checkout/create")
async def create_checkout(data: PurchaseRequest, request: Request, user=Depends(get_current_user)):
    if not STRIPE_API_KEY:
        raise HTTPException(status_code=500, detail="STRIPE_API_KEY non configurata")

    listing = await db.listings.find_one({"id": data.listing_id, "status": "active"}, {"_id": 0})
    if not listing:
        raise HTTPException(status_code=404, detail="Annuncio non disponibile")
    if listing["seller_id"] == user["id"]:
        raise HTTPException(status_code=400, detail="Non puoi acquistare il tuo annuncio")

    existing = await db.payment_transactions.find_one({
        "listing_id": data.listing_id,
        "buyer_id": user["id"],
        "payment_status": {"$in": ["paid", "initiated"]}
    })
    if existing:
        raise HTTPException(status_code=400, detail="Hai già un pagamento in corso per questo articolo")

    commission = round(listing["price"] * COMMISSION_RATE, 2)
    total = round(listing["price"] + commission, 2)

    origin_url = data.origin_url.rstrip('/')
    success_url = f"{origin_url}/payment-success?session_id={{CHECKOUT_SESSION_ID}}"
    cancel_url = f"{origin_url}/payment-cancel"

    tx_id = str(uuid.uuid4())

    try:
        session = stripe.checkout.Session.create(
            payment_method_types=["card"],
            mode="payment",
            success_url=success_url,
            cancel_url=cancel_url,
            line_items=[{
                "price_data": {
                    "currency": "eur",
                    "product_data": {
                        "name": listing["title"],
                        "description": f'Prezzo articolo €{listing["price"]:.2f} + commissione €{commission:.2f}',
                    },
                    "unit_amount": int(round(total * 100)),
                },
                "quantity": 1,
            }],
            metadata={
                "tx_id": tx_id,
                "listing_id": data.listing_id,
                "buyer_id": user["id"],
                "seller_id": listing["seller_id"],
                "commission": str(commission),
            },
        )
    except Exception as e:
        logger.error(f"Stripe checkout creation failed: {e}")
        raise HTTPException(status_code=500, detail="Errore nella creazione del checkout Stripe")

    payment_tx = {
        "id": tx_id,
        "session_id": session.id,
        "listing_id": data.listing_id,
        "listing_title": listing["title"],
        "listing_image": listing["images"][0] if listing.get("images") else "",
        "buyer_id": user["id"],
        "buyer_name": user["name"],
        "seller_id": listing["seller_id"],
        "seller_name": listing.get("seller_name", ""),
        "price": listing["price"],
        "commission": commission,
        "total": total,
        "currency": "eur",
        "payment_status": "initiated",
        "status": "pending",
        "created_at": datetime.now(timezone.utc).isoformat()
    }
    await db.payment_transactions.insert_one(payment_tx)

    return {"checkout_url": session.url, "session_id": session.id, "tx_id": tx_id}

@api_router.get("/checkout/status/{session_id}")
async def check_payment_status(session_id: str, user=Depends(get_current_user)):
    if not STRIPE_API_KEY:
        raise HTTPException(status_code=500, detail="STRIPE_API_KEY non configurata")

    payment_tx = await db.payment_transactions.find_one({"session_id": session_id}, {"_id": 0})
    if not payment_tx:
        raise HTTPException(status_code=404, detail="Transazione non trovata")

    if payment_tx["payment_status"] == "paid":
        return {"status": "complete", "payment_status": "paid", "tx_id": payment_tx["id"]}

    try:
        session = stripe.checkout.Session.retrieve(session_id)
    except Exception as e:
        logger.error(f"Stripe status check failed: {e}")
        return {
            "status": payment_tx.get("status", "pending"),
            "payment_status": payment_tx["payment_status"],
            "tx_id": payment_tx["id"]
        }

    if session.payment_status == "paid" and payment_tx["payment_status"] != "paid":
        await db.payment_transactions.update_one(
            {"session_id": session_id, "payment_status": {"$ne": "paid"}},
            {"$set": {"payment_status": "paid", "status": "completed"}}
        )
        await _complete_purchase(payment_tx)
        return {"status": "complete", "payment_status": "paid", "tx_id": payment_tx["id"]}

    if getattr(session, "status", None) == "expired":
        await db.payment_transactions.update_one(
            {"session_id": session_id},
            {"$set": {"payment_status": "expired", "status": "expired"}}
        )
        return {"status": "expired", "payment_status": "expired", "tx_id": payment_tx["id"]}

    return {
        "status": "pending",
        "payment_status": getattr(session, "payment_status", "unpaid"),
        "tx_id": payment_tx["id"]
    }

async def _complete_purchase(payment_tx: dict):
    existing_tx = await db.transactions.find_one({"payment_tx_id": payment_tx["id"]})
    if existing_tx:
        return

    await db.listings.update_one({"id": payment_tx["listing_id"]}, {"$set": {"status": "sold"}})

    tx_id = str(uuid.uuid4())
    transaction = {
        "id": tx_id,
        "payment_tx_id": payment_tx["id"],
        "listing_id": payment_tx["listing_id"],
        "listing_title": payment_tx["listing_title"],
        "listing_image": payment_tx.get("listing_image", ""),
        "buyer_id": payment_tx["buyer_id"],
        "buyer_name": payment_tx["buyer_name"],
        "seller_id": payment_tx["seller_id"],
        "seller_name": payment_tx.get("seller_name", ""),
        "price": payment_tx["price"],
        "commission": payment_tx["commission"],
        "total": payment_tx["total"],
        "status": "completed",
        "created_at": datetime.now(timezone.utc).isoformat()
    }
    await db.transactions.insert_one(transaction)

    chat_id = str(uuid.uuid4())
    chat = {
        "id": chat_id,
        "transaction_id": tx_id,
        "listing_id": payment_tx["listing_id"],
        "listing_title": payment_tx["listing_title"],
        "listing_image": payment_tx.get("listing_image", ""),
        "buyer_id": payment_tx["buyer_id"],
        "buyer_name": payment_tx["buyer_name"],
        "seller_id": payment_tx["seller_id"],
        "seller_name": payment_tx.get("seller_name", ""),
        "messages": [{
            "id": str(uuid.uuid4()),
            "sender_id": "system",
            "sender_name": "Second Chance Market",
            "text": f'Acquisto completato! Organizzatevi per il ritiro di "{payment_tx["listing_title"]}".',
            "created_at": datetime.now(timezone.utc).isoformat()
        }],
        "created_at": datetime.now(timezone.utc).isoformat()
    }
    await db.chats.insert_one(chat)

@api_router.post("/webhook/stripe")
async def stripe_webhook(request: Request):
    if not STRIPE_API_KEY:
        raise HTTPException(status_code=500, detail="STRIPE_API_KEY non configurata")

    body = await request.body()
    signature = request.headers.get("Stripe-Signature", "")

    try:
        if STRIPE_WEBHOOK_SECRET:
            event = stripe.Webhook.construct_event(
                payload=body,
                sig_header=signature,
                secret=STRIPE_WEBHOOK_SECRET
            )
        else:
            event = json.loads(body.decode("utf-8"))
            logger.warning("STRIPE_WEBHOOK_SECRET non configurata: webhook non verificato")
    except Exception as e:
        logger.error(f"Webhook verification error: {e}")
        raise HTTPException(status_code=400, detail="Webhook non valido")

    event_type = event.get("type")
    data_object = event.get("data", {}).get("object", {})

    if event_type == "checkout.session.completed":
        session_id = data_object.get("id")
        payment_tx = await db.payment_transactions.find_one({"session_id": session_id}, {"_id": 0})
        if payment_tx and payment_tx["payment_status"] != "paid":
            await db.payment_transactions.update_one(
                {"session_id": session_id, "payment_status": {"$ne": "paid"}},
                {"$set": {"payment_status": "paid", "status": "completed"}}
            )
            await _complete_purchase(payment_tx)

    return {"status": "ok"}

# --- Transaction Routes ---
@api_router.get("/transactions")
async def get_transactions(user=Depends(get_current_user)):
    txs = await db.transactions.find(
        {"$or": [{"buyer_id": user["id"]}, {"seller_id": user["id"]}]},
        {"_id": 0}
    ).sort("created_at", -1).to_list(100)
    return txs

# --- Admin Routes ---
ADMIN_EMAIL = os.environ.get('ADMIN_EMAIL', 'admin@scm.it')

async def get_admin_user(credentials: HTTPAuthorizationCredentials = Depends(security)):
    user = await get_current_user(credentials)
    if user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Accesso riservato agli amministratori")
    return user

@api_router.get("/admin/users")
async def admin_get_users(user=Depends(get_admin_user)):
    users = await db.users.find(
        {},
        {"_id": 0, "password_hash": 0}
    ).sort("created_at", -1).to_list(500)
    for u in users:
        u["listings_count"] = await db.listings.count_documents({"seller_id": u["id"]})
        u["purchases_count"] = await db.transactions.count_documents({"buyer_id": u["id"]})
    return users

@api_router.delete("/admin/users/{user_id}")
async def admin_delete_user(user_id: str, user=Depends(get_admin_user)):
    target = await db.users.find_one({"id": user_id})
    if not target:
        raise HTTPException(status_code=404, detail="Utente non trovato")
    if target.get("role") == "admin":
        raise HTTPException(status_code=400, detail="Non puoi eliminare un admin")

    await db.users.delete_one({"id": user_id})
    await db.listings.update_many({"seller_id": user_id}, {"$set": {"status": "removed"}})

    return {"message": f"Utente {target['name']} eliminato e annunci rimossi"}

@api_router.get("/admin/listings")
async def admin_get_listings(user=Depends(get_admin_user)):
    """Get all listings for admin moderation"""
    listings = await db.listings.find({}, {"_id": 0}).sort("created_at", -1).to_list(500)
    for listing in listings:
        seller = await db.users.find_one({"id": listing.get("seller_id")}, {"_id": 0, "name": 1, "email": 1})
        listing["seller_name"] = seller.get("name", "Sconosciuto") if seller else "Sconosciuto"
        listing["seller_email"] = seller.get("email", "") if seller else ""
    return listings

@api_router.delete("/admin/listings/{listing_id}")
async def admin_delete_listing(listing_id: str, user=Depends(get_admin_user)):
    """Delete any listing (admin only)"""
    listing = await db.listings.find_one({"id": listing_id})
    if not listing:
        raise HTTPException(status_code=404, detail="Annuncio non trovato")
    await db.listings.delete_one({"id": listing_id})
    logger.info(f"Admin deleted listing: {listing_id} - {listing.get('title')}")
    return {"message": f"Annuncio '{listing.get('title')}' eliminato"}

@api_router.post("/admin/seed")
async def admin_seed():
    existing = await db.users.find_one({"email": ADMIN_EMAIL})
    if existing:
        await db.users.update_one({"email": ADMIN_EMAIL}, {"$set": {"role": "admin"}})
        return {"message": "Admin aggiornato", "email": ADMIN_EMAIL}
    admin_id = str(uuid.uuid4())
    admin_user = {
        "id": admin_id,
        "name": "Admin SCM",
        "email": ADMIN_EMAIL,
        "password_hash": pwd_context.hash("admin2024!"),
        "latitude": 41.9028,
        "longitude": 12.4964,
        "neighborhood": "Roma, Lazio",
        "regione": "Lazio",
        "provincia": "Roma",
        "location_updated_at": None,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "avatar": None,
        "role": "admin",
        "accepted_privacy_at": datetime.now(timezone.utc).isoformat(),
        "accepted_rules_at": datetime.now(timezone.utc).isoformat(),
    }
    await db.users.insert_one(admin_user)
    return {"message": "Admin creato", "email": ADMIN_EMAIL, "password": "admin2024!"}

# --- Chat Routes ---
@api_router.get("/chats")
async def get_chats(user=Depends(get_current_user)):
    chats = await db.chats.find(
        {"$or": [{"buyer_id": user["id"]}, {"seller_id": user["id"]}]},
        {"_id": 0, "messages": {"$slice": -1}}
    ).sort("created_at", -1).to_list(100)
    return chats

@api_router.get("/chats/{chat_id}")
async def get_chat(chat_id: str, user=Depends(get_current_user)):
    chat = await db.chats.find_one({"id": chat_id}, {"_id": 0})
    if not chat:
        raise HTTPException(status_code=404, detail="Chat non trovata")
    if user["id"] not in [chat["buyer_id"], chat["seller_id"]]:
        raise HTTPException(status_code=403, detail="Non autorizzato")
    return chat

@api_router.post("/chats/{chat_id}/messages")
async def send_message(chat_id: str, data: MessageCreate, user=Depends(get_current_user)):
    chat = await db.chats.find_one({"id": chat_id})
    if not chat:
        raise HTTPException(status_code=404, detail="Chat non trovata")
    if user["id"] not in [chat["buyer_id"], chat["seller_id"]]:
        raise HTTPException(status_code=403, detail="Non autorizzato")
    message = {
        "id": str(uuid.uuid4()),
        "sender_id": user["id"],
        "sender_name": user["name"],
        "text": data.text,
        "created_at": datetime.now(timezone.utc).isoformat()
    }
    await db.chats.update_one({"id": chat_id}, {"$push": {"messages": message}})
    return message

# --- Categories ---
@api_router.get("/categories")
async def get_categories():
    result = []
    for cat in CATEGORIES:
        count = await db.listings.count_documents({"category": cat, "status": "active"})
        result.append({"name": cat, "count": count})
    return result

# --- Seed Data ---
@api_router.post("/seed")
async def seed_data():
    existing = await db.listings.count_documents({})
    if existing > 0:
        return {"message": "Dati già presenti", "count": existing}

    seller_id = str(uuid.uuid4())
    seller = {
        "id": seller_id, "name": "Marco Rossi", "email": "marco@demo.it",
        "password_hash": pwd_context.hash("demo123"),
        "latitude": 41.8894, "longitude": 12.4726, "neighborhood": "Roma, Lazio",
        "regione": "Lazio", "provincia": "Roma",
        "location_updated_at": None, "created_at": datetime.now(timezone.utc).isoformat(), "avatar": None
    }
    seller2_id = str(uuid.uuid4())
    seller2 = {
        "id": seller2_id, "name": "Giulia Bianchi", "email": "giulia@demo.it",
        "password_hash": pwd_context.hash("demo123"),
        "latitude": 45.4642, "longitude": 9.1900, "neighborhood": "Milano, Lombardia",
        "regione": "Lombardia", "provincia": "Milano",
        "location_updated_at": None, "created_at": datetime.now(timezone.utc).isoformat(), "avatar": None
    }
    await db.users.insert_many([seller, seller2])

    sample_listings = [
        {"title": "iPhone 13 Pro", "description": "Perfette condizioni, batteria 89%. Include caricatore originale.", "price": 450.00, "category": "Elettronica", "condition": "Come nuovo", "seller_id": seller_id, "seller_name": "Marco Rossi", "seller_neighborhood": "Roma, Lazio", "latitude": 41.8894, "longitude": 12.4726},
        {"title": "MacBook Air M1", "description": "Usato poco, 256GB, grigio siderale. Ideale per studenti.", "price": 680.00, "category": "Elettronica", "condition": "Buono", "seller_id": seller2_id, "seller_name": "Giulia Bianchi", "seller_neighborhood": "Milano, Lombardia", "latitude": 45.4642, "longitude": 9.1900},
        {"title": "Giacca Pelle Vintage", "description": "Giacca in vera pelle anni '80, taglia M. Un pezzo unico.", "price": 85.00, "category": "Abbigliamento", "condition": "Buono", "seller_id": seller_id, "seller_name": "Marco Rossi", "seller_neighborhood": "Roma, Lazio", "latitude": 41.8894, "longitude": 12.4726},
        {"title": "Sneakers Nike Air Max", "description": "Taglia 42, usate poche volte. Colore bianco/nero.", "price": 55.00, "category": "Abbigliamento", "condition": "Come nuovo", "seller_id": seller2_id, "seller_name": "Giulia Bianchi", "seller_neighborhood": "Milano, Lombardia", "latitude": 45.4642, "longitude": 9.1900},
        {"title": "Libreria in Legno", "description": "Libreria Ikea Billy, colore noce. 80x200cm. Smontata.", "price": 40.00, "category": "Casa & Arredamento", "condition": "Buono", "seller_id": seller_id, "seller_name": "Marco Rossi", "seller_neighborhood": "Roma, Lazio", "latitude": 41.8894, "longitude": 12.4726},
        {"title": "Lampada Design", "description": "Lampada da tavolo stile industriale, funzionante.", "price": 25.00, "category": "Casa & Arredamento", "condition": "Discreto", "seller_id": seller2_id, "seller_name": "Giulia Bianchi", "seller_neighborhood": "Milano, Lombardia", "latitude": 45.4642, "longitude": 9.1900},
        {"title": "Bici da Corsa Bianchi", "description": "Telaio alluminio, cambio Shimano 105. Taglia 54.", "price": 320.00, "category": "Sport & Tempo Libero", "condition": "Buono", "seller_id": seller_id, "seller_name": "Marco Rossi", "seller_neighborhood": "Roma, Lazio", "latitude": 41.8894, "longitude": 12.4726},
        {"title": "Racchetta Tennis Wilson", "description": "Wilson Blade 98, corde recenti. Grip taglia 3.", "price": 60.00, "category": "Sport & Tempo Libero", "condition": "Come nuovo", "seller_id": seller2_id, "seller_name": "Giulia Bianchi", "seller_neighborhood": "Milano, Lombardia", "latitude": 45.4642, "longitude": 9.1900},
        {"title": "Collezione Harry Potter", "description": "Saga completa 7 libri, edizione italiana. Ottime condizioni.", "price": 35.00, "category": "Libri & Media", "condition": "Buono", "seller_id": seller_id, "seller_name": "Marco Rossi", "seller_neighborhood": "Roma, Lazio", "latitude": 41.8894, "longitude": 12.4726},
        {"title": "Vinili Jazz Collection", "description": "10 vinili jazz classici, Miles Davis, Coltrane. Perfetti.", "price": 75.00, "category": "Libri & Media", "condition": "Come nuovo", "seller_id": seller2_id, "seller_name": "Giulia Bianchi", "seller_neighborhood": "Milano, Lombardia", "latitude": 45.4642, "longitude": 9.1900},
        {"title": "Valigia Samsonite", "description": "Valigia grande, 4 ruote, colore nero. Usata 2 volte.", "price": 45.00, "category": "Altro", "condition": "Come nuovo", "seller_id": seller_id, "seller_name": "Marco Rossi", "seller_neighborhood": "Roma, Lazio", "latitude": 41.8894, "longitude": 12.4726},
        {"title": "Set Pentole Acciaio", "description": "Set 5 pentole acciaio inox, marca Lagostina.", "price": 50.00, "category": "Altro", "condition": "Buono", "seller_id": seller2_id, "seller_name": "Giulia Bianchi", "seller_neighborhood": "Milano, Lombardia", "latitude": 45.4642, "longitude": 9.1900},
    ]

    for item in sample_listings:
        item["id"] = str(uuid.uuid4())
        item["images"] = []
        item["status"] = "active"
        item["created_at"] = datetime.now(timezone.utc).isoformat()

    await db.listings.insert_many(sample_listings)
    return {"message": f"Seed completato: {len(sample_listings)} annunci creati"}

# --- Reports Routes ---
@api_router.post("/reports")
async def create_report(data: ReportCreate, user=Depends(get_current_user)):
    if data.reported_type not in ["user", "listing"]:
        raise HTTPException(status_code=400, detail="Tipo di segnalazione non valido")

    if data.reported_type == "user":
        reported = await db.users.find_one({"id": data.reported_id})
    else:
        reported = await db.listings.find_one({"id": data.reported_id})

    if not reported:
        raise HTTPException(status_code=404, detail="Elemento non trovato")

    report = {
        "id": str(uuid.uuid4()),
        "reporter_id": user["id"],
        "reporter_name": user["name"],
        "reported_type": data.reported_type,
        "reported_id": data.reported_id,
        "reason": data.reason,
        "description": data.description,
        "status": "pending",
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    await db.reports.insert_one(report)

    send_email(
        "support@secondchancemarket.store",
        f"Nuova Segnalazione: {data.reason}",
        f"<p>Nuova segnalazione da <b>{user['name']}</b> ({user['email']})</p>"
        f"<p>Tipo: {data.reported_type}</p>"
        f"<p>Motivo: {data.reason}</p>"
        f"<p>Descrizione: {data.description}</p>"
    )

    return {"message": "Segnalazione inviata. Grazie per aiutarci a mantenere la community sicura."}

@api_router.get("/admin/reports")
async def get_reports(user=Depends(get_current_user)):
    if user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Accesso non autorizzato")

    reports = await db.reports.find({}, {"_id": 0}).sort("created_at", -1).to_list(100)
    return reports

@api_router.put("/admin/reports/{report_id}")
async def update_report(report_id: str, status: str, user=Depends(get_current_user)):
    if user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Accesso non autorizzato")

    if status not in ["pending", "reviewed", "resolved"]:
        raise HTTPException(status_code=400, detail="Stato non valido")

    result = await db.reports.update_one(
        {"id": report_id},
        {"$set": {"status": status}}
    )
    if result.modified_count == 0:
        raise HTTPException(status_code=404, detail="Segnalazione non trovata")

    return {"message": "Stato aggiornato"}

# --- Ratings Routes ---
@api_router.post("/ratings")
async def create_rating(data: RatingCreate, user=Depends(get_current_user)):
    if not 1 <= data.rating <= 5:
        raise HTTPException(status_code=400, detail="La valutazione deve essere tra 1 e 5")

    transaction = await db.transactions.find_one({"id": data.transaction_id, "status": "completed"})
    if not transaction:
        raise HTTPException(status_code=404, detail="Transazione non trovata o non completata")

    if user["id"] == transaction["buyer_id"]:
        rated_id = transaction["seller_id"]
    elif user["id"] == transaction["seller_id"]:
        rated_id = transaction["buyer_id"]
    else:
        raise HTTPException(status_code=403, detail="Non puoi valutare questa transazione")

    existing = await db.ratings.find_one({
        "transaction_id": data.transaction_id,
        "rater_id": user["id"]
    })
    if existing:
        raise HTTPException(status_code=400, detail="Hai già valutato questa transazione")

    rating = {
        "id": str(uuid.uuid4()),
        "transaction_id": data.transaction_id,
        "rater_id": user["id"],
        "rater_name": user["name"],
        "rated_id": rated_id,
        "rating": data.rating,
        "comment": data.comment,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    await db.ratings.insert_one(rating)

    all_ratings = await db.ratings.find({"rated_id": rated_id}).to_list(1000)
    avg = sum(r["rating"] for r in all_ratings) / len(all_ratings)
    await db.users.update_one(
        {"id": rated_id},
        {"$set": {
            "rating_avg": round(avg, 1),
            "rating_count": len(all_ratings)
        }}
    )

    return {"message": "Valutazione inviata"}

@api_router.get("/users/{user_id}/ratings")
async def get_user_ratings(user_id: str):
    ratings = await db.ratings.find({"rated_id": user_id}, {"_id": 0}).sort("created_at", -1).to_list(50)
    return ratings

@api_router.get("/transactions/{transaction_id}/can-rate")
async def can_rate_transaction(transaction_id: str, user=Depends(get_current_user)):
    transaction = await db.transactions.find_one({"id": transaction_id, "status": "completed"})
    if not transaction:
        return {"can_rate": False, "reason": "Transazione non trovata o non completata"}

    if user["id"] not in [transaction["buyer_id"], transaction["seller_id"]]:
        return {"can_rate": False, "reason": "Non sei parte di questa transazione"}

    existing = await db.ratings.find_one({
        "transaction_id": transaction_id,
        "rater_id": user["id"]
    })
    if existing:
        return {"can_rate": False, "reason": "Hai già valutato questa transazione"}

    return {"can_rate": True}

# --- Valuation Service Routes ---
VALUATION_PRICE = 100

@api_router.post("/valuations/create-checkout")
async def create_valuation_checkout(data: ValuationRequest, user=Depends(get_current_user)):
    if not STRIPE_API_KEY:
        raise HTTPException(status_code=500, detail="STRIPE_API_KEY non configurata")

    if not data.images or len(data.images) == 0:
        raise HTTPException(status_code=400, detail="Almeno una foto è richiesta")

    valuation_id = str(uuid.uuid4())
    valuation = {
        "id": valuation_id,
        "user_id": user["id"],
        "user_name": user["name"],
        "user_email": user["email"],
        "images": data.images[:5],
        "category": data.category,
        "dating": data.dating,
        "condition": data.condition,
        "description": data.description,
        "brand": data.brand,
        "status": "pending_payment",
        "estimated_value": None,
        "operator_notes": "",
        "messages": [],
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    await db.valuations.insert_one(valuation)

    try:
        session = stripe.checkout.Session.create(
            payment_method_types=['card'],
            line_items=[{
                'price_data': {
                    'currency': 'eur',
                    'product_data': {
                        'name': 'Servizio Valutazione Oggetto',
                        'description': f'Valutazione professionale per: {data.category}',
                    },
                    'unit_amount': VALUATION_PRICE,
                },
                'quantity': 1,
            }],
            mode='payment',
            success_url=f"{data.origin_url}/valuation-success?session_id={{CHECKOUT_SESSION_ID}}&valuation_id={valuation_id}",
            cancel_url=f"{data.origin_url}/valuation-cancel?valuation_id={valuation_id}",
            metadata={
                'valuation_id': valuation_id,
                'user_id': user["id"],
            }
        )
        return {"checkout_url": session.url, "valuation_id": valuation_id}
    except Exception as e:
        await db.valuations.delete_one({"id": valuation_id})
        raise HTTPException(status_code=500, detail=str(e))

@api_router.get("/valuations/status/{session_id}")
async def check_valuation_payment(session_id: str, valuation_id: str):
    if not STRIPE_API_KEY:
        raise HTTPException(status_code=500, detail="STRIPE_API_KEY non configurata")

    try:
        session = stripe.checkout.Session.retrieve(session_id)
        if session.payment_status == 'paid':
            await db.valuations.update_one(
                {"id": valuation_id},
                {"$set": {
                    "status": "paid",
                    "stripe_session_id": session_id,
                    "paid_at": datetime.now(timezone.utc).isoformat(),
                }}
            )

            valuation = await db.valuations.find_one({"id": valuation_id})
            if valuation:
                send_email(
                    "support@secondchancemarket.store",
                    "Nuova Richiesta di Valutazione",
                    f"<p>Nuova valutazione pagata da <b>{valuation['user_name']}</b></p>"
                    f"<p>Categoria: {valuation['category']}</p>"
                    f"<p>Datazione: {valuation['dating']}</p>"
                    f"<p>Condizioni: {valuation['condition']}</p>"
                    f"<p>Descrizione: {valuation['description']}</p>"
                )

            return {"status": "paid", "message": "Pagamento confermato! Un operatore ti contatterà presto."}
        return {"status": "pending", "message": "Pagamento in attesa"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@api_router.get("/valuations")
async def get_user_valuations(user=Depends(get_current_user)):
    valuations = await db.valuations.find(
        {"user_id": user["id"]},
        {"_id": 0}
    ).sort("created_at", -1).to_list(50)
    return valuations

@api_router.get("/valuations/{valuation_id}")
async def get_valuation(valuation_id: str, user=Depends(get_current_user)):
    valuation = await db.valuations.find_one({"id": valuation_id}, {"_id": 0})
    if not valuation:
        raise HTTPException(status_code=404, detail="Valutazione non trovata")

    if valuation["user_id"] != user["id"] and user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Accesso non autorizzato")

    return valuation

@api_router.post("/valuations/{valuation_id}/messages")
async def send_valuation_message(valuation_id: str, data: ValuationMessage, user=Depends(get_current_user)):
    valuation = await db.valuations.find_one({"id": valuation_id})
    if not valuation:
        raise HTTPException(status_code=404, detail="Valutazione non trovata")

    if valuation["user_id"] != user["id"] and user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Accesso non autorizzato")

    message = {
        "id": str(uuid.uuid4()),
        "sender_id": user["id"],
        "sender_name": user["name"],
        "is_operator": user.get("role") == "admin",
        "text": data.text,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }

    await db.valuations.update_one(
        {"id": valuation_id},
        {"$push": {"messages": message}}
    )

    return {"message": "Messaggio inviato", "data": message}

@api_router.put("/valuations/{valuation_id}/complete")
async def complete_valuation(valuation_id: str, estimated_value: float, operator_notes: str = "", user=Depends(get_current_user)):
    if user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Solo operatori possono completare valutazioni")

    valuation = await db.valuations.find_one({"id": valuation_id})
    if not valuation:
        raise HTTPException(status_code=404, detail="Valutazione non trovata")

    await db.valuations.update_one(
        {"id": valuation_id},
        {"$set": {
            "status": "completed",
            "estimated_value": estimated_value,
            "operator_notes": operator_notes,
            "completed_at": datetime.now(timezone.utc).isoformat(),
        }}
    )

    send_email(
        valuation["user_email"],
        "La tua Valutazione è Pronta!",
        f"<p>Ciao {valuation['user_name']},</p>"
        f"<p>La valutazione del tuo oggetto è stata completata.</p>"
        f"<p><b>Valore stimato: €{estimated_value:.2f}</b></p>"
        f"<p>Note: {operator_notes}</p>"
        f"<p>Apri l'app per vedere i dettagli completi.</p>"
    )

    return {"message": "Valutazione completata"}

@api_router.get("/admin/valuations")
async def get_admin_valuations(user=Depends(get_current_user)):
    if user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Accesso non autorizzato")

    valuations = await db.valuations.find(
        {"status": {"$ne": "pending_payment"}},
        {"_id": 0}
    ).sort("created_at", -1).to_list(100)
    return valuations

app.include_router(api_router)

# --- Serve Admin Panel ---
@app.get("/api/admin-panel", response_class=HTMLResponse)
async def serve_admin_panel():
    admin_html_path = ROOT_DIR / "admin_panel.html"
    with open(admin_html_path, "r") as f:
        return HTMLResponse(content=f.read())

app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.on_event("startup")
async def startup():
    await db.users.create_index("email", unique=True)
    await db.users.create_index("id", unique=True)
    await db.listings.create_index("id", unique=True)
    await db.listings.create_index("category")
    await db.listings.create_index("seller_id")
    await db.listings.create_index("status")
    await db.transactions.create_index("id", unique=True)
    await db.chats.create_index("id", unique=True)
    await db.payment_transactions.create_index("id", unique=True)
    await db.payment_transactions.create_index("session_id", unique=True)
    await db.reports.create_index("id", unique=True)
    await db.reports.create_index("status")
    await db.ratings.create_index("id", unique=True)
    await db.ratings.create_index("rated_id")
    await db.ratings.create_index("transaction_id")
    await db.valuations.create_index("id", unique=True)
    await db.valuations.create_index("user_id")
    await db.valuations.create_index("status")
    logger.info("Second Chance Market API avviata con Stripe")

@app.on_event("shutdown")
async def shutdown_db_client():
    client.close()
