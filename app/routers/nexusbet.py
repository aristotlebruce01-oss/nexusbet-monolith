from fastapi import APIRouter, Depends, HTTPException, status
# ... bring over any other necessary imports from server.py (models, schemas, db sessions)

router = APIRouter(
        tags=["NexusBet"]
)

from dotenv import load_dotenv
from pathlib import Path

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env')

import os
import uuid
import random
import asyncio
import logging
import json
import math
import csv
import requests
import hmac
import hashlib
import io
import re
import base64
from urllib.parse import quote
from datetime import datetime, timezone, timedelta
from typing import List, Optional, Literal, Any

import bcrypt
import jwt
from bson import ObjectId
from pymongo import UpdateOne, ReturnDocument
from fastapi import FastAPI, APIRouter, HTTPException, Request, Depends, Security, UploadFile, File
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.responses import JSONResponse, Response
from starlette.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
from pydantic import BaseModel, Field, EmailStr

# ------------------------------------------------------------------ setup
mongo_url = os.environ['MONGO_URL']
client = AsyncIOMotorClient(mongo_url)
db = client[os.environ['DB_NAME']]

JWT_ALGORITHM = "HS256"
STARTING_BALANCE = 0.0
STAFF_STARTING_DEMO_BALANCE = 1000.0
REFERRAL_COMMISSION_RATE = 0.70
# The 70% referral commission is earned only by Sub-Admins. Admin and
# Super Admin accounts may have referral codes for onboarding, but they do not
# receive referral commission.

LEAGUE_CATALOG = {
    "premier-league": {
        "name": "Premier League", "country": "England", "season": "2026/27",
        "provider_leagues": ["English Premier League", "Premier League"],
        "teams": [
            "Arsenal", "Aston Villa", "AFC Bournemouth", "Brentford", "Brighton & Hove Albion", "Chelsea",
            "Coventry City", "Crystal Palace", "Everton", "Fulham", "Hull City", "Ipswich Town", "Leeds United",
            "Liverpool", "Manchester City", "Manchester United", "Newcastle United", "Nottingham Forest", "Sunderland", "Tottenham Hotspur"
        ]
    },
    "laliga": {
        "name": "LaLiga", "country": "Spain", "season": "2026/27",
        "provider_leagues": ["Spanish La Liga", "La Liga"],
        "teams": [
            "Athletic Club", "Atlético de Madrid", "CA Osasuna", "Celta", "Deportivo Alavés", "Elche CF", "FC Barcelona",
            "Getafe CF", "Levante UD", "Málaga CF", "R. Racing Club", "Rayo Vallecano", "RC Deportivo",
            "RCD Espanyol de Barcelona", "Real Betis", "Real Madrid", "Real Sociedad", "Sevilla FC", "Valencia CF", "Villarreal CF"
        ]
    },
    "bundesliga": {
        "name": "Bundesliga", "country": "Germany", "season": "2026/27",
        "provider_leagues": ["German Bundesliga", "Bundesliga"],
        "teams": [
            "FC Augsburg", "1. FC Union Berlin", "SV Werder Bremen", "Borussia Dortmund", "SV Elversberg", "Eintracht Frankfurt",
            "Sport-Club Freiburg", "Hamburger SV", "TSG Hoffenheim", "1. FC Köln", "RB Leipzig", "Bayer 04 Leverkusen",
            "1. FSV Mainz 05", "Borussia Mönchengladbach", "FC Bayern München", "SC Paderborn 07", "FC Schalke 04", "VfB Stuttgart"
        ]
    },
    "serie-a": {
        "name": "Serie A", "country": "Italy", "season": "2026/27",
        "provider_leagues": ["Italian Serie A", "Serie A"],
        "teams": [
            "AC Milan", "Atalanta", "Bologna", "Cagliari", "Como", "Fiorentina", "Frosinone", "Genoa", "Inter",
            "Juventus", "Lazio", "Lecce", "Monza", "Napoli", "Parma", "Roma", "Sassuolo", "Torino", "Udinese", "Venezia"
        ]
    },
    "ligue-1": {
        "name": "Ligue 1", "country": "France", "season": "2026/27",
        "provider_leagues": ["French Ligue 1", "Ligue 1"],
        "teams": [
            "Angers SCO", "AJ Auxerre", "Stade Brestois 29", "Havre AC", "Le Mans FC", "RC Lens", "FC Lorient", "LOSC",
            "Olympique Lyonnais", "Olympique de Marseille", "AS Monaco", "OGC Nice", "Paris FC", "Paris Saint-Germain",
            "Stade Rennais F.C.", "RC Strasbourg Alsace", "Toulouse FC", "ESTAC Troyes"
        ]
    },
    "liga-portugal": {
        "name": "Liga Portugal", "country": "Portugal", "season": "2026/27",
        "provider_leagues": ["Portuguese Primeira Liga", "Primeira Liga", "Liga Portugal"],
        "teams": [
            "Académico de Viseu", "Casa Pia", "CD Nacional da Madeira", "CD Santa Clara", "Estoril Praia", "Estrela Amadora",
            "FC Alverca", "FC Arouca", "FC Famalicão", "FC Porto", "Gil Vicente", "Marítimo", "Moreirense", "Rio Ave",
            "SC Braga", "SL Benfica", "Sporting CP", "Vitória SC"
        ]
    },
    "eredivisie": {
        "name": "Eredivisie", "country": "Netherlands", "season": "2026/27",
        "provider_leagues": ["Dutch Eredivisie", "Eredivisie"],
        "teams": [
            "ADO Den Haag", "Ajax", "AZ Alkmaar", "Excelsior", "FC Groningen", "FC Twente", "FC Utrecht", "Feyenoord",
            "Fortuna Sittard", "Go Ahead Eagles", "NEC Nijmegen", "PEC Zwolle", "PSV Eindhoven", "SC Cambuur", "SC Heerenveen",
            "Sparta Rotterdam", "Telstar", "Willem II"
        ]
    },
    "scottish-premiership": {
        "name": "Scottish Premiership", "country": "Scotland", "season": "2026/27",
        "provider_leagues": ["Scottish Premier League", "Scottish Premiership"],
        "teams": [
            "Aberdeen FC", "Celtic", "Dundee", "Dundee United", "Falkirk", "Heart of Midlothian (Hearts)",
            "Hibernian", "Kilmarnock FC", "Motherwell", "Rangers", "St Johnstone", "St Mirren"
        ]
    },
    "super-lig": {
        "name": "Süper Lig", "country": "Turkey", "season": "2026/27",
        "provider_leagues": ["Turkish Super Lig", "Turkish Super League", "Super Lig"],
        "teams": [
            "Alanyaspor", "Amed SK", "Başakşehir", "Beşiktaş", "Çaykur Rizespor", "Çorum FK", "Erzurumspor FK", "Eyüpspor",
            "Fenerbahçe", "Galatasaray", "Gaziantep FK", "Gençlerbirliği", "Göztepe Izmir", "Kasımpaşa", "Kocaelispor",
            "Konyaspor", "Samsunspor", "Trabzonspor"
        ]
    },
    "super-league-greece": {
        "name": "Super League Greece", "country": "Greece", "season": "2026/27",
        "provider_leagues": ["Greek Super League", "Super League Greece"],
        "teams": [
            "A.E Kifisia", "AEK Athens", "Aris Thessaloniki", "Asteras Tripolis", "Atromitos", "Iraklis", "Kalamata", "Levadiakos",
            "OFI Crete", "Olympiacos", "Panathinaikos", "Panetolikos", "PAOK", "Volos NPS"
        ]
    },
    "belgian-pro-league": {
        "name": "Belgian Pro League", "country": "Belgium", "season": "2026/27",
        "provider_leagues": ["Belgian Pro League", "Belgian First Division A", "Jupiler Pro League"],
        "teams": [
            "Cercle Brugge", "Club Brugge", "KAA Gent", "KRC Genk", "KV Kortrijk", "KV Mechelen", "KVC Westerlo", "Lommel SK",
            "OH Leuven", "RAAL La Louviere", "Royal Antwerp", "RSC Anderlecht", "Sint-Truiden", "SK Beveren",
            "Sporting Charleroi", "Standard Liège", "Union Saint-Gilloise", "Zulte Waregem"
        ]
    }
}

TEAM_ALIASES = {
    "brighton & hove albion": ["Brighton & Hove Albion", "Brighton"],
    "afc bournemouth": ["AFC Bournemouth", "Bournemouth"],
    "atletico de madrid": ["Atlético de Madrid", "Atletico Madrid"],
    "deportivo alaves": ["Deportivo Alavés", "Alaves"],
    "r. racing club": ["R. Racing Club", "Racing Santander", "Racing Club"],
    "rc deportivo": ["RC Deportivo", "Deportivo La Coruna", "Deportivo"],
    "rcd espanyol de barcelona": ["RCD Espanyol de Barcelona", "Espanyol"],
    "celta": ["Celta", "Celta Vigo"],
    "stade rennais f.c.": ["Stade Rennais F.C.", "Stade Rennais", "Rennes"],
    "stade brestois 29": ["Stade Brestois 29", "Brest"],
    "havre ac": ["Havre AC", "Le Havre"],
    "losc": ["LOSC", "Lille"],
    "paris saint-germain": ["Paris Saint-Germain", "Paris SG", "PSG"],
    "olympique lyonnais": ["Olympique Lyonnais", "Lyon"],
    "olympique de marseille": ["Olympique de Marseille", "Marseille"],
    "fc bayern münchen": ["FC Bayern München", "Bayern Munich"],
    "bayer 04 leverkusen": ["Bayer 04 Leverkusen", "Bayer Leverkusen"],
    "1. fc köln": ["1. FC Köln", "FC Cologne", "Cologne"],
    "1. fsv mainz 05": ["1. FSV Mainz 05", "Mainz"],
    "1. fc union berlin": ["1. FC Union Berlin", "Union Berlin"],
    "sv werder bremen": ["SV Werder Bremen", "Werder Bremen"],
    "sport-club freiburg": ["Sport-Club Freiburg", "SC Freiburg", "Freiburg"],
    "sc paderborn 07": ["SC Paderborn 07", "Paderborn"],
    "fc schalke 04": ["FC Schalke 04", "Schalke 04", "Schalke"],
    "sv elversberg": ["SV Elversberg", "Elversberg"],
    "hamburger sv": ["Hamburger SV", "Hamburg"],
    "tsg hoffenheim": ["TSG Hoffenheim", "Hoffenheim"],
    "heart of midlothian hearts": ["Heart of Midlothian", "Hearts"],
    "sporting charleroi": ["Sporting Charleroi", "Charleroi"],
    "raal la louviere": ["RAAL La Louvière", "RAAL La Louviere"],
    "a e kifisia": ["A.E Kifisia", "Kifisia"],
    "aek athens": ["AEK Athens", "AEK"],
    "aris thessaloniki": ["Aris", "Aris Thessaloniki"],
    "ofi crete": ["OFI", "OFI Crete"],
    "volos nps": ["Volos", "Volos NPS"],
    "panetolikos": ["Panetolikos"],
    "amed sk": ["Amed SK", "Amedspor"],
    "goztepe izmir": ["Göztepe", "Goztepe"],
    "st johnstone": ["St Johnstone"],
    "aberdeen fc": ["Aberdeen", "Aberdeen FC"],
    "kilmarnock fc": ["Kilmarnock", "Kilmarnock FC"],
    "fc alverca": ["FC Alverca", "Alverca"],
    "fc famalicao": ["FC Famalicão", "Famalicao"],
    "vitoria sc": ["Vitória SC", "Vitoria Guimaraes", "Vitoria SC"],
}

def _team_key(value: str) -> str:
    import unicodedata
    value = unicodedata.normalize("NFKD", str(value or "")).encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9]+", " ", value).strip()

async def sync_league_catalog():
    """Sync current club crests from TheSportsDB into MongoDB.

    The official league sites are the authority for the 2026/27 membership and
    display names above. TheSportsDB is used only as the football-data source
    for provider team IDs and current crest URLs.
    """
    for slug, league in LEAGUE_CATALOG.items():
        try:
            url = "https://www.thesportsdb.com/api/v1/json/3/search_all_teams.php"
            provider_teams = []
            for provider_league in league.get("provider_leagues", []):
                try:
                    response = await asyncio.to_thread(requests.get, url, params={"l": provider_league}, timeout=12)
                    response.raise_for_status()
                    payload = response.json() or {}
                    if payload.get("teams"):
                        provider_teams = payload.get("teams") or []
                        break
                except Exception:
                    continue
            by_key = {_team_key(t.get("strTeam")): t for t in provider_teams if t.get("strTeam")}
            for name in league["teams"]:
                candidates = [name] + TEAM_ALIASES.get(_team_key(name), [])
                found = next((by_key.get(_team_key(c)) for c in candidates if by_key.get(_team_key(c))), None)
                if not found:
                    logger.warning("No TheSportsDB crest match for %s / %s", league["name"], name)
                    continue
                doc = {
                    "league_slug": slug, "league": league["name"], "country": league["country"], "season": league["season"],
                    "name": name, "provider": "TheSportsDB", "provider_team_id": found.get("idTeam"),
                    "api_football_id": found.get("idAPIfootball"), "logo_url": found.get("strBadge"),
                    "updated_at": datetime.now(timezone.utc).isoformat()
                }
                await db.teams.update_one({"league_slug": slug, "name": name, "season": league["season"]}, {"$set": doc}, upsert=True)
            await db.leagues.update_one({"slug": slug}, {"$set": {"slug": slug, "name": league["name"], "country": league["country"], "season": league["season"], "team_count": len(league["teams"]), "updated_at": datetime.now(timezone.utc).isoformat()}}, upsert=True)
        except Exception as exc:
            logger.warning("League crest sync failed for %s: %s", league["name"], exc)

async def team_asset(name: str, league: Optional[str] = None) -> dict:
    query = {"name": name}
    if league:
        query["league"] = league
    doc = await db.teams.find_one(query)
    if not doc:
        doc = await db.teams.find_one({"name": name})
    return {"name": name, "logo_url": doc.get("logo_url") if doc else None, "team_id": doc.get("provider_team_id") if doc else None} 
CODE_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
STAFF_ROLES = {"super_admin", "admin", "sub_admin"}
MANAGER_ROLES = {"super_admin", "admin"}


def gen_code(n: int = 8) -> str:
    return "".join(random.choices(CODE_ALPHABET, k=n))


async def unique_code(collection, field: str, n: int = 8) -> str:
    for _ in range(25):
        code = gen_code(n)
        if not await collection.find_one({field: code}):
            return code
    return gen_code(n + 2)



@router.get("/odds")
def get_live_sports_odds():
    """Fetch real bookmaker odds for configured football, basketball and tennis feeds."""
    api_key = os.getenv("ODDS_API_KEY")
    if not api_key:
        raise HTTPException(status_code=503, detail="Sports odds provider is not configured (ODDS_API_KEY missing).")
    sport_keys = [x.strip() for x in os.getenv(
        "ODDS_SPORT_KEYS",
        "soccer_epl,soccer_uefa_champs_league,basketball_nba,tennis_atp_french_open"
    ).split(",") if x.strip()]
    payload_events = []
    successful_feeds = 0
    failures = []
    for sport_key in sport_keys[:8]:
        try:
            response = requests.get(
                f"https://api.the-odds-api.com/v4/sports/{sport_key}/odds",
                params={"apiKey": api_key, "regions": os.getenv("ODDS_REGIONS", "uk,us,au"),
                        "markets": "h2h", "oddsFormat": "decimal", "dateFormat": "iso"},
                timeout=15,
            )
            if response.status_code == 404:
                continue
            response.raise_for_status()
            payload = response.json()
            if isinstance(payload, list):
                successful_feeds += 1
                payload_events.extend(payload)
        except requests.RequestException as exc:
            logging.warning("Odds provider request failed for %s: %s", sport_key, exc)
            failures.append(sport_key)
        except ValueError:
            failures.append(sport_key)
    if successful_feeds == 0:
        detail = "Unable to fetch odds from the configured sports feeds."
        if failures:
            detail = "The configured odds provider feeds are unavailable. Check ODDS_API_KEY and ODDS_SPORT_KEYS."
        raise HTTPException(status_code=502, detail=detail)

    matches = []
    seen_ids = set()
    for event in payload_events:
        event_id = event.get("id")
        if not event_id or event_id in seen_ids:
            continue
        seen_ids.add(event_id)
        bookmakers = []
        for bookmaker in event.get("bookmakers", []) or []:
            markets = []
            for market in bookmaker.get("markets", []) or []:
                if market.get("key") != "h2h":
                    continue
                outcomes = [{"name": str(o.get("name", "")), "price": o.get("price")}
                            for o in (market.get("outcomes", []) or [])
                            if o.get("name") and isinstance(o.get("price"), (int, float))]
                if outcomes:
                    markets.append({"key": "h2h", "outcomes": outcomes, "last_update": market.get("last_update")})
            if markets:
                bookmakers.append({"key": bookmaker.get("key"), "title": bookmaker.get("title"),
                                   "last_update": bookmaker.get("last_update"), "markets": markets})
        matches.append({"id": event_id, "sport_key": event.get("sport_key"),
                        "sport_title": event.get("sport_title"), "commence_time": event.get("commence_time"),
                        "home_team": event.get("home_team"), "away_team": event.get("away_team"),
                        "bookmakers": bookmakers})
    return {"matches": matches, "count": len(matches), "source": "The Odds API"}


@router.get("/live-scores")
def get_live_sports_scores():
    """Fetch current score data from The Odds API for configured sport keys."""
    api_key = os.getenv("ODDS_API_KEY")
    if not api_key:
        raise HTTPException(status_code=503, detail="Live sports provider is not configured (ODDS_API_KEY missing).")
    sport_keys = [x.strip() for x in os.getenv(
        "ODDS_LIVE_SPORT_KEYS",
        "soccer_epl,soccer_uefa_champs_league,basketball_nba,tennis_atp_french_open"
    ).split(",") if x.strip()]
    live_matches = []
    failures = []
    for sport_key in sport_keys[:8]:
        try:
            response = requests.get(
                f"https://api.the-odds-api.com/v4/sports/{sport_key}/scores",
                params={"apiKey": api_key, "daysFrom": 1, "dateFormat": "iso"},
                timeout=12,
            )
            if response.status_code == 404:
                continue
            response.raise_for_status()
            payload = response.json()
            for event in payload if isinstance(payload, list) else []:
                scores = event.get("scores") or []
                # Provider scores are only treated as live when not marked completed.
                if event.get("completed") is True or not scores:
                    continue
                score_map = {str(item.get("name", "")): item.get("score") for item in scores}
                live_matches.append({
                    "id": event.get("id"), "sport_key": event.get("sport_key", sport_key),
                    "sport_title": event.get("sport_title", sport_key),
                    "home_team": event.get("home_team"), "away_team": event.get("away_team"),
                    "commence_time": event.get("commence_time"), "scores": scores,
                    "home_score": score_map.get(str(event.get("home_team", ""))),
                    "away_score": score_map.get(str(event.get("away_team", ""))),
                    "completed": bool(event.get("completed", False)),
                    "last_update": event.get("last_update"),
                })
        except requests.RequestException as exc:
            logging.warning("Live scores provider request failed for %s: %s", sport_key, exc)
            failures.append(sport_key)
        except ValueError:
            failures.append(sport_key)
    if failures and not live_matches and len(failures) == min(len(sport_keys), 8):
        raise HTTPException(status_code=502, detail="Unable to fetch live scores from the configured sports provider.")
    return {"matches": live_matches, "count": len(live_matches), "source": "The Odds API"}


bearer_scheme = HTTPBearer(auto_error=False)

# Demo wagering is enabled. All stakes use the platform's demo wallet balance;
# no external payment provider or real-money settlement is connected.


logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("nexusbet")


# ------------------------------------------------------------------ auth utils
def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(plain: str, hashed: str) -> bool:
    return bcrypt.checkpw(plain.encode("utf-8"), hashed.encode("utf-8"))


def get_jwt_secret() -> str:
    return os.environ["JWT_SECRET"]


def create_access_token(user_id: str, email: str) -> str:
    payload = {
        "sub": user_id,
        "email": email,
        "exp": datetime.now(timezone.utc) + timedelta(days=7),
        "type": "access",
    }
    return jwt.encode(payload, get_jwt_secret(), algorithm=JWT_ALGORITHM)


def public_user(doc: dict) -> dict:
    role = doc.get("role", "user")
    return {
        "id": str(doc["_id"]),
        "email": doc["email"],
        "phone": doc.get("phone", ""),
        "name": doc.get("name", ""),
        "role": role,
        "balance": round(doc.get("balance", 0.0), 2),
        "total_deposited": round(doc.get("total_deposited", 0.0), 2),
        "referral_code": doc.get("referral_code", ""),
        "commission_total": round(doc.get("commission_total", 0.0), 2) if role == "sub_admin" else 0.0,
        "demo_balance": round(doc.get("balance", 0.0), 2) if role in STAFF_ROLES else None,
        "permissions": doc.get("permissions", []),
    }


async def get_current_user(
    request: Request,
    credentials: Optional[HTTPAuthorizationCredentials] = Security(bearer_scheme),
) -> dict:
    token = request.cookies.get("access_token")
    if not token and credentials is not None:
        token = credentials.credentials
    if not token:
        auth_header = request.headers.get("Authorization", "")
        if auth_header.startswith("Bearer "):
            token = auth_header[7:]
    if not token:
        raise HTTPException(status_code=401, detail="Not authenticated")
    try:
        payload = jwt.decode(token, get_jwt_secret(), algorithms=[JWT_ALGORITHM])
        if payload.get("type") != "access":
            raise HTTPException(status_code=401, detail="Invalid token type")
        user = await db.users.find_one({"_id": ObjectId(payload["sub"])})
        if not user:
            raise HTTPException(status_code=401, detail="User not found")
        return user
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid token")


async def require_admin(user: dict = Depends(get_current_user)) -> dict:
    if user.get("role") not in MANAGER_ROLES:
        raise HTTPException(status_code=403, detail="Admin access required")
    return user


async def require_super_admin(user: dict = Depends(get_current_user)) -> dict:
    if user.get("role") != "super_admin":
        raise HTTPException(status_code=403, detail="Super Admin access required")
    return user


async def require_staff(user: dict = Depends(get_current_user)) -> dict:
    if user.get("role") not in STAFF_ROLES:
        raise HTTPException(status_code=403, detail="Staff access required")
    return user

ROLE_PERMISSIONS = {
    "user_management": {"users.view", "users.manage"},
    "sports_odds": {"events.view", "events.manage", "odds.manage"},
    "payments": {"transactions.view", "transactions.review"},
    "reports": {"reports.view", "transactions.view"},
    "promotions": {"promotions.manage"},
}
ALL_SUBADMIN_PERMISSIONS = sorted(set().union(*ROLE_PERMISSIONS.values()))

def default_subadmin_permissions():
    return []

def require_permission(permission: str = ""):
    async def dependency(user: dict = Depends(get_current_user)):
        if user.get("role") in MANAGER_ROLES:
            return user
        if user.get("role") != "sub_admin" or (permission and permission not in user.get("permissions", [])):
            raise HTTPException(status_code=403, detail=f"Permission required: {permission}")
        return user
    return dependency

DEFAULT_PAYMENT_METHODS = {
    "mtn": {"id": "mtn", "label": "MTN MoMo", "provider": "mtn", "active": True},
    "telecel": {"id": "telecel", "label": "Telecel Cash", "provider": "vod", "active": True},
    "airteltigo": {"id": "airteltigo", "label": "AirtelTigo Money", "provider": "atl", "active": True},
}

DEFAULT_SETTINGS = {
    "min_deposit": 30.0,
    "min_withdrawal": 1000.0,
    "first_deposit_bonus_cap": 100.0,
    "payment_methods": DEFAULT_PAYMENT_METHODS,
}


FIRST_DEPOSIT_BONUS_CAP = 100.0


async def get_settings() -> dict:
    doc = await db.settings.find_one({"_id": "global"})
    if not doc:
        return dict(DEFAULT_SETTINGS)

    # One-time migration: move the previous production defaults to GHS 30.
    # The marker prevents a future administrator choice of GHS 200 (or any
    # other value) from being overwritten on subsequent settings reads.
    # One-time migration: move the previous first-deposit bonus cap from GHS 100 to GHS 50.
    # The marker preserves any later administrator-selected cap.
    if not doc.get("first_deposit_bonus_migrated_to_50", False):
        stored_bonus_cap = doc.get("first_deposit_bonus_cap", 100.0)
        try:
            if float(stored_bonus_cap) == 100.0:
                await db.settings.update_one(
                    {"_id": "global", "first_deposit_bonus_migrated_to_50": {"$ne": True}},
                    {"$set": {"first_deposit_bonus_cap": 50.0, "first_deposit_bonus_migrated_to_50": True}},
                )
                doc["first_deposit_bonus_cap"] = 50.0
            else:
                await db.settings.update_one(
                    {"_id": "global", "first_deposit_bonus_migrated_to_50": {"$ne": True}},
                    {"$set": {"first_deposit_bonus_migrated_to_50": True}},
                )
        except (TypeError, ValueError):
            await db.settings.update_one(
                {"_id": "global", "first_deposit_bonus_migrated_to_50": {"$ne": True}},
                {"$set": {"first_deposit_bonus_migrated_to_50": True}},
            )

    if not doc.get("min_deposit_migrated_to_30", False):
        stored_minimum = doc.get("min_deposit", 200.0)
        try:
            if float(stored_minimum) in (1.0, 5.0, 200.0, 300.0):
                await db.settings.update_one(
                    {"_id": "global", "min_deposit_migrated_to_30": {"$ne": True}},
                    {"$set": {"min_deposit": 30.0, "min_deposit_migrated_to_30": True}},
                )
                doc["min_deposit"] = 30.0
            else:
                await db.settings.update_one(
                    {"_id": "global", "min_deposit_migrated_to_30": {"$ne": True}},
                    {"$set": {"min_deposit_migrated_to_30": True}},
                )
        except (TypeError, ValueError):
            await db.settings.update_one(
                {"_id": "global", "min_deposit_migrated_to_30": {"$ne": True}},
                {"$set": {"min_deposit_migrated_to_30": True}},
            )

    result = {k: doc.get(k, DEFAULT_SETTINGS[k]) for k in DEFAULT_SETTINGS}
    # Be defensive about legacy or malformed database values. A missing/None
    # payment_methods object (or a non-dict entry) must not break settings reads.
    stored_payment_methods = doc.get("payment_methods")
    if not isinstance(stored_payment_methods, dict):
        stored_payment_methods = {}
    result["payment_methods"] = {}
    for key, defaults in DEFAULT_PAYMENT_METHODS.items():
        stored_method = stored_payment_methods.get(key)
        if not isinstance(stored_method, dict):
            stored_method = {}
        result["payment_methods"][key] = {**defaults, **stored_method}
    return result


def public_payment_methods(settings: dict, include_inactive: bool = False) -> list:
    methods = []
    for key in ("mtn", "telecel", "airteltigo"):
        cfg = dict(settings["payment_methods"][key])
        if include_inactive or cfg.get("active", True):
            methods.append({"id": key, "label": cfg["label"], "active": bool(cfg.get("active", True))})
    return methods


# ------------------------------------------------------------------ models
class RegisterInput(BaseModel):
    name: str = Field(min_length=1, max_length=40)
    email: EmailStr
    phone: str = Field(min_length=7, max_length=25)
    password: str = Field(min_length=6, max_length=128)
    confirm_password: str = Field(min_length=6, max_length=128)
    referral_code: str = Field(min_length=4, max_length=40)

class LoginInput(BaseModel):
    identifier: str = Field(min_length=3, max_length=120)
    password: str

class EventInput(BaseModel):
    sport: str = Field(min_length=2, max_length=40)
    league: str = Field(min_length=2, max_length=80)
    home: str = Field(min_length=1, max_length=80)
    away: str = Field(min_length=1, max_length=80)
    odds_home: float = Field(gt=1.0, le=1000)
    odds_draw: Optional[float] = Field(default=None, gt=1.0, le=1000)
    odds_away: float = Field(gt=1.0, le=1000)
    kickoff_at: Optional[datetime] = None
    home_logo_url: Optional[str] = Field(default=None, max_length=2_800_000)
    away_logo_url: Optional[str] = Field(default=None, max_length=2_800_000)

class EventControlInput(BaseModel):
    status: Optional[Literal["open", "live", "halftime", "paused", "finished", "cancelled"]] = None
    minute: Optional[int] = Field(default=None, ge=0, le=120)
    home_score: Optional[int] = Field(default=None, ge=0, le=99)
    away_score: Optional[int] = Field(default=None, ge=0, le=99)
    halftime_home_score: Optional[int] = Field(default=None, ge=0, le=99)
    halftime_away_score: Optional[int] = Field(default=None, ge=0, le=99)

class VirtualMatchInput(BaseModel):
    home: str = Field(min_length=1, max_length=80)
    away: str = Field(min_length=1, max_length=80)
    league: str = Field(default="Virtual Football", min_length=2, max_length=80)
    kickoff_at: Optional[datetime] = None
    status: Literal["scheduled", "live", "halftime", "finished", "paused", "cancelled"] = "scheduled"
    minute: int = Field(default=0, ge=0, le=94)
    home_score: int = Field(default=0, ge=0, le=99)
    away_score: int = Field(default=0, ge=0, le=99)
    odds_home: float = Field(default=2.0, gt=1.0, le=1000)
    odds_draw: float = Field(default=3.2, gt=1.0, le=1000)
    odds_away: float = Field(default=3.0, gt=1.0, le=1000)
    halftime_home_score: Optional[int] = Field(default=None, ge=0, le=99)
    halftime_away_score: Optional[int] = Field(default=None, ge=0, le=99)

class VirtualBulkInput(BaseModel):
    matches: List[VirtualMatchInput] = Field(min_length=1, max_length=5000)

class VirtualControlInput(BaseModel):
    status: Optional[Literal["scheduled", "live", "halftime", "finished", "paused", "cancelled"]] = None
    minute: Optional[int] = Field(default=None, ge=0, le=94)
    home_score: Optional[int] = Field(default=None, ge=0, le=99)
    away_score: Optional[int] = Field(default=None, ge=0, le=99)
    odds_home: Optional[float] = Field(default=None, gt=1.0, le=1000)
    odds_draw: Optional[float] = Field(default=None, gt=1.0, le=1000)
    odds_away: Optional[float] = Field(default=None, gt=1.0, le=1000)
    halftime_home_score: Optional[int] = Field(default=None, ge=0, le=99)
    halftime_away_score: Optional[int] = Field(default=None, ge=0, le=99)

class DepositInput(BaseModel):
    amount: float = Field(gt=0, le=1000000)
    method: Literal["mtn", "telecel", "airteltigo"]
    phone_number: str = Field(min_length=7, max_length=25)




class WithdrawInput(BaseModel):
    amount: float = Field(gt=0, le=1000000)
    method: Literal["mtn", "telecel", "airteltigo"] = "mtn"
    destination: str = Field(min_length=4, max_length=120)
    phone_number: str = Field(min_length=7, max_length=25)

class SettingsInput(BaseModel):
    min_deposit: Optional[float] = Field(default=None, ge=0.01, le=1000000)
    min_withdrawal: Optional[float] = Field(default=None, ge=0.01, le=1000000)

class RoleInput(BaseModel):
    role: str

class PermissionsInput(BaseModel):
    permissions: List[str] = Field(default_factory=list)

class StaffCreateInput(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    email: EmailStr
    phone: str = Field(default="", max_length=40)
    password: str = Field(min_length=6, max_length=128)
    role: Literal["admin", "sub_admin"]

class StaffUpdateInput(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=80)
    email: Optional[EmailStr] = None
    phone: Optional[str] = Field(default=None, max_length=40)
    password: Optional[str] = Field(default=None, min_length=6, max_length=128)

class DemoCreditInput(BaseModel):
    amount: float = Field(gt=0, le=1000000000)

class PayoutAccountsInput(BaseModel):
    mtn_name: str = Field(default="", max_length=100)
    mtn_number: str = Field(default="", max_length=30)
    telecel_name: str = Field(default="", max_length=100)
    telecel_number: str = Field(default="", max_length=30)
    bank_name: str = Field(default="", max_length=120)
    bank_account_name: str = Field(default="", max_length=120)
    bank_account_number: str = Field(default="", max_length=60)
    bank_branch: str = Field(default="", max_length=120)

class DepositCleanupInput(BaseModel):
    before: datetime

class BetInput(BaseModel):
    event_id: str = Field(min_length=1, max_length=100)
    market: Literal["match_result", "double_chance", "correct_score", "ht_draw_ft", "goals_over_under", "both_teams_score"] = "match_result"
    selection: str = Field(min_length=1, max_length=80)
    stake: float = Field(gt=0, le=100000)

class TicketSelection(BaseModel):
    event_id: str = Field(min_length=1, max_length=100)
    market: Literal["match_result", "double_chance", "correct_score", "ht_draw_ft", "goals_over_under", "both_teams_score"] = "match_result"
    selection: str = Field(min_length=1, max_length=80)

class TicketInput(BaseModel):
    selections: List[TicketSelection] = Field(min_length=1, max_length=30)
    stake: float = Field(default=0, ge=0, le=100000)

class TicketVerifyInput(BaseModel):
    identifier: str = Field(min_length=4, max_length=120)

class BetSettlementInput(BaseModel):
    result: Literal["home", "draw", "away", "void"]

# ------------------------------------------------------------------ virtual football
def virtual_minute(doc: dict) -> int:
    if doc.get("status") in ("finished", "cancelled"):
        return int(doc.get("minute", 94))
    if doc.get("status") in ("halftime", "paused"):
        return int(doc.get("minute", 45))
    if doc.get("status") != "live" or not doc.get("clock_started_at"):
        return int(doc.get("minute", 0))
    started = datetime.fromisoformat(doc["clock_started_at"])
    elapsed = max(0, int((datetime.now(timezone.utc) - started).total_seconds() // 60))
    base = int(doc.get("clock_base_minute", 0))
    if base < 45:
        first_half_elapsed = min(45, base + elapsed)
        if base + elapsed <= 45:
            return first_half_elapsed
        second_half_elapsed = base + elapsed - 45
        if second_half_elapsed <= 15:
            return 45
        return min(94, 46 + second_half_elapsed - 16)
    return min(94, base + elapsed)

def virtual_phase(doc: dict) -> str:
    if doc.get("status") != "live":
        return doc.get("status", "scheduled")
    if not doc.get("clock_started_at"):
        return "live"
    started = datetime.fromisoformat(doc["clock_started_at"])
    elapsed = max(0, int((datetime.now(timezone.utc) - started).total_seconds() // 60))
    base = int(doc.get("clock_base_minute", 0))
    total = base + elapsed
    if base < 45 and total > 45 and total <= 60:
        return "halftime"
    if virtual_minute(doc) >= 94:
        return "finished"
    return "live"

def virtual_public(doc: dict) -> dict:
    minute = virtual_minute(doc)
    status = doc.get("status", "scheduled")
    phase = virtual_phase(doc)
    return {"id": doc["id"], "home": doc["home"], "away": doc["away"], "league": doc.get("league", "Virtual Football"),
            "kickoff_at": doc.get("kickoff_at"), "status": status, "phase": phase, "minute": minute,
            "score": {"home": doc.get("home_score", 0), "away": doc.get("away_score", 0)},
            "halftime_score": {"home": doc.get("halftime_home_score"), "away": doc.get("halftime_away_score")},
            "result": doc.get("result"),
            "booking_code": doc.get("booking_code") or f"NBM-{doc['id'][:8].upper()}",
            "odds": {"home": round(doc.get("odds_home", 2), 2), "draw": round(doc.get("odds_draw", 3.2), 2), "away": round(doc.get("odds_away", 3), 2)}}

@router.get("/virtual-football/matches")
async def list_virtual_matches(status: Optional[str] = None, limit: int = 200, skip: int = 0):
    query = {"sport": "Virtual Football"}
    if status in {"scheduled", "live", "halftime", "finished", "paused", "cancelled"}: query["status"] = status
    docs = await db.events.find(query).sort("kickoff_at", 1).skip(max(0, skip)).limit(min(max(limit, 1), 1000)).to_list(min(max(limit, 1), 1000))
    # Finalize clock-driven matches as soon as the public feed reaches FT.
    for doc in docs:
        # Simulated virtual matches occasionally score while live. The next goal
        # timestamp is persisted so polling frequency cannot cause rapid scoring.
        if doc.get("status") == "live" and not doc.get("score_controlled", False):
            now_dt = datetime.now(timezone.utc)
            next_goal = doc.get("next_virtual_goal_at")
            try:
                due = bool(next_goal and datetime.fromisoformat(next_goal) <= now_dt)
            except (TypeError, ValueError):
                due = False
            if not next_goal:
                due = False
                await db.events.update_one({"id": doc["id"]}, {"$set": {"next_virtual_goal_at": (now_dt + timedelta(seconds=random.randint(18, 55))).isoformat()}})
            elif due and virtual_phase(doc) != "finished":
                # A small number of score events per match keeps the feed believable.
                home_score = int(doc.get("home_score", 0)); away_score = int(doc.get("away_score", 0))
                if random.random() < 0.72 and home_score + away_score < 7:
                    if random.random() < 0.5:
                        home_score += 1
                    else:
                        away_score += 1
                await db.events.update_one({"id": doc["id"], "status": "live"}, {"$set": {
                    "home_score": home_score, "away_score": away_score,
                    "next_virtual_goal_at": (now_dt + timedelta(seconds=random.randint(22, 70))).isoformat()
                }})
                doc["home_score"] = home_score; doc["away_score"] = away_score
                doc["next_virtual_goal_at"] = (now_dt + timedelta(seconds=30)).isoformat()
        if doc.get("status") == "live" and virtual_phase(doc) == "finished":
            home_score = int(doc.get("home_score", 0)); away_score = int(doc.get("away_score", 0))
            result = "home" if home_score > away_score else "away" if away_score > home_score else "draw"
            await db.events.update_one({"id": doc["id"], "status": "live"}, {"$set": {"status": "finished", "minute": 94, "result": result, "clock_started_at": None}})
            await settle_event_bets(doc["id"], result)
            await settle_ticket_event(doc["id"], result)
            doc = await db.events.find_one({"id": doc["id"]}) or doc
        elif doc.get("status") == "live" and virtual_phase(doc) == "halftime":
            # Keep the public phase accurate while preserving the live status.
            pass
    return [virtual_public(d) for d in docs]

@router.post("/admin/virtual-football/matches")
async def create_virtual_match(body: VirtualMatchInput, staff: dict = Depends(require_permission("events.manage"))):
    doc = body.model_dump()
    doc.update({"id": str(uuid.uuid4()), "sport": "Virtual Football", "kickoff_at": (body.kickoff_at or datetime.now(timezone.utc)).isoformat(),
                "clock_base_minute": body.minute, "clock_started_at": datetime.now(timezone.utc).isoformat() if body.status == "live" else None,
                "next_virtual_goal_at": (datetime.now(timezone.utc) + timedelta(seconds=random.randint(18, 55))).isoformat() if body.status == "live" else None, "created_at": datetime.now(timezone.utc).isoformat()})
    await db.events.insert_one(doc)
    return virtual_public(doc)

@router.post("/admin/virtual-football/bulk")
async def bulk_virtual_matches(body: VirtualBulkInput, staff: dict = Depends(require_permission("events.manage"))):
    now = datetime.now(timezone.utc).isoformat(); docs = []
    for item in body.matches:
        d = item.model_dump(); d.update({"id": str(uuid.uuid4()), "sport": "Virtual Football", "kickoff_at": (item.kickoff_at or datetime.now(timezone.utc)).isoformat(),
            "clock_base_minute": item.minute, "clock_started_at": now if item.status == "live" else None, "next_virtual_goal_at": (datetime.now(timezone.utc) + timedelta(seconds=random.randint(18, 55))).isoformat() if item.status == "live" else None, "created_at": now})
        docs.append(d)
    if docs: await db.events.insert_many(docs)
    return {"created": len(docs), "matches": [virtual_public(d) for d in docs]}

@router.post("/admin/virtual-football/bulk-csv")
async def bulk_virtual_csv(file: UploadFile = File(...), staff: dict = Depends(require_permission("events.manage"))):
    raw = await file.read()
    if len(raw) > 5 * 1024 * 1024: raise HTTPException(status_code=413, detail="CSV file is larger than 5MB")
    try: rows = list(csv.DictReader(io.StringIO(raw.decode("utf-8-sig"))))
    except Exception as exc: raise HTTPException(status_code=400, detail=f"Invalid CSV: {exc}")
    if not rows or len(rows) > 5000: raise HTTPException(status_code=400, detail="CSV must contain 1 to 5000 matches")
    matches = []
    for i, r in enumerate(rows, 2):
        try:
            matches.append(VirtualMatchInput(home=r["home"], away=r["away"], league=r.get("league") or "Virtual Football",
                kickoff_at=datetime.fromisoformat(r["kickoff_at"]) if r.get("kickoff_at") else None, status=r.get("status") or "scheduled",
                minute=int(r.get("minute") or 0), home_score=int(r.get("home_score") or 0), away_score=int(r.get("away_score") or 0),
                halftime_home_score=int(r["halftime_home_score"]) if r.get("halftime_home_score") not in (None, "") else None,
                halftime_away_score=int(r["halftime_away_score"]) if r.get("halftime_away_score") not in (None, "") else None,
                odds_home=float(r.get("odds_home") or 2), odds_draw=float(r.get("odds_draw") or 3.2), odds_away=float(r.get("odds_away") or 3)))
        except Exception as exc: raise HTTPException(status_code=400, detail=f"Invalid row {i}: {exc}")
    return await bulk_virtual_matches(VirtualBulkInput(matches=matches), staff)

@router.patch("/admin/virtual-football/matches/{match_id}")
async def control_virtual_match(match_id: str, body: VirtualControlInput, staff: dict = Depends(require_permission("events.manage"))):
    current = await db.events.find_one({"id": match_id, "sport": "Virtual Football"})
    if not current: raise HTTPException(status_code=404, detail="Virtual match not found")
    values = {k: v for k, v in body.model_dump(exclude_none=True).items()}
    # Once staff manually changes either score, stop the simulated goal generator
    # so all future score changes are under explicit Admin control.
    if "home_score" in values or "away_score" in values:
        values["score_controlled"] = True
    if values.get("status") == "live" and current.get("status") != "live":
        base_minute = int(values.get("minute", virtual_minute(current) if current.get("status") in ("paused", "halftime") else current.get("minute", 0)))
        values["minute"] = base_minute
        values["clock_started_at"] = datetime.now(timezone.utc).isoformat()
        values["clock_base_minute"] = base_minute
        values["next_virtual_goal_at"] = (datetime.now(timezone.utc) + timedelta(seconds=random.randint(18, 55))).isoformat()
    if values.get("status") in ("paused", "halftime", "finished", "cancelled"):
        values["minute"] = virtual_minute(current)
        values["clock_base_minute"] = values["minute"]
        values["clock_started_at"] = None
    await db.events.update_one({"id": match_id}, {"$set": values})
    updated = await db.events.find_one({"id": match_id})
    if values.get("status") == "finished":
        home_score = int(updated.get("home_score", 0)); away_score = int(updated.get("away_score", 0))
        result = "home" if home_score > away_score else "away" if away_score > home_score else "draw"
        await db.events.update_one({"id": match_id}, {"$set": {"result": result}})
        await settle_event_bets(match_id, result)
        updated = await db.events.find_one({"id": match_id})
    return virtual_public(updated)

# ------------------------------------------------------------------ demo wagering and settlement

def bet_public(doc: dict, event: Optional[dict] = None) -> dict:
    return {
        "id": doc["id"], "event_id": doc["event_id"], "user_id": doc["user_id"],
        "market": doc.get("market", "match_result"), "selection": doc["selection"], "stake": round(doc["stake"], 2),
        "odds": round(doc["odds"], 2), "potential_win": round(doc["potential_win"], 2),
        "status": doc["status"], "result": doc.get("result"),
        "payout": round(doc.get("payout", 0.0), 2), "created_at": doc["created_at"],
        "settled_at": doc.get("settled_at"), "reference": doc.get("reference"),
        "event": ({"id": event.get("id"), "home": event.get("home"), "away": event.get("away"),
                   "sport": event.get("sport"), "status": event.get("status"),
                   "minute": virtual_minute(event) if event.get("sport") == "Virtual Football" else None,
                   "score": {"home": event.get("home_score", 0), "away": event.get("away_score", 0)},
                   "halftime_score": {"home": event.get("halftime_home_score"), "away": event.get("halftime_away_score")},
                   "result": event.get("result")} if event else None),
    }


CORRECT_SCORE_OPTIONS = {"0-0","1-0","0-1","1-1","2-0","0-2","2-1","1-2","2-2","3-0","0-3","3-1","1-3","3-2","2-3","3-3"}
def _poisson(n: int, lam: float) -> float:
    import math
    return math.exp(-lam) * (lam ** n) / math.factorial(n)

def _goal_lambdas(event: dict):
    home = max(1.05, float(event.get("odds_home") or 1.9))
    away = max(1.05, float(event.get("odds_away") or 3.6))
    seed = sum(ord(c) for c in str(event.get("id") or f"{event.get('home')}-{event.get('away')}"))
    total = 2.45 + ((seed % 13) - 6) * 0.025
    strength = away / home
    lh = max(0.65, min(2.35, total * (0.5 + 0.5 * strength / (1 + strength))))
    return lh, max(0.45, total - lh)

def _fixture_market_price(event: dict, selection: str) -> float:
    import re
    lh, la = _goal_lambdas(event); margin = 1.08
    if selection in CORRECT_SCORE_OPTIONS:
        h, a = map(int, selection.split("-")); prob = _poisson(h, lh) * _poisson(a, la)
        return round(max(2.8, min(80.0, margin / max(prob, 0.0001))), 2)
    if selection.startswith(("over_", "under_")):
        line = float(selection.split("_")[1]); threshold = int(line)
        over = sum(_poisson(h,lh)*_poisson(a,la) for h in range(6) for a in range(6) if h+a > threshold)
        prob = over if selection.startswith("over_") else 1-over
        return round(max(1.12, min(9.0, margin/max(prob,0.02))), 2)
    if selection in {"yes", "no"}:
        both=(1-__import__("math").exp(-lh))*(1-__import__("math").exp(-la))
        return round(max(1.18,min(4.8,margin/max(both if selection=="yes" else 1-both,0.03))),2)
    if selection in {"win1","win2"}:
        seed=sum(ord(c) for c in str(event.get("id") or event.get("home","")))
        return round((6.1+(seed%17)*0.11) if selection=="win1" else (6.4+(seed%19)*0.10),2)
    raise HTTPException(status_code=400, detail="Unsupported selection")

def selection_odds(event: dict, selection: str) -> float:
    sport = str(event.get("sport", "Football")).strip().lower()
    if selection not in {"home", "draw", "away"}:
        raise HTTPException(status_code=400, detail="Selection must be home, draw, or away")
    if sport in {"basketball", "tennis"} and selection == "draw":
        raise HTTPException(status_code=400, detail=f"Draw odds are not available for {sport.title()}; choose a winner.")
    defaults = {"home": 1.85, "draw": 3.40, "away": 3.75}
    raw = {"home": event.get("odds_home"), "draw": event.get("odds_draw"), "away": event.get("odds_away")}[selection]
    try:
        value = float(raw)
    except (TypeError, ValueError):
        if sport in {"basketball", "tennis"} and selection == "draw":
            raise HTTPException(status_code=400, detail="Draw odds are unavailable for this sport")
        value = defaults[selection]
    return value if value > 0 else defaults[selection]

def market_odds(event: dict, market: str, selection: str) -> float:
    if market == "match_result": return selection_odds(event, selection)
    if market == "double_chance":
        aliases = {"dc_team_1": 1.25, "dc_team_2": 1.45, "1X": 1.25, "X2": 1.45}
        if selection not in aliases: raise HTTPException(status_code=400, detail="Unsupported double chance selection")
        return aliases[selection]
    if market == "correct_score" and selection not in CORRECT_SCORE_OPTIONS:
        raise HTTPException(status_code=400, detail="Unsupported correct score selection")
    if market == "ht_draw_ft" and selection not in {"home","draw","away","win1","win2","ht_draw_ft_home","ht_draw_ft_draw","ht_draw_ft_away"}:
        raise HTTPException(status_code=400, detail="Unsupported half-time/full-time selection")
    if market in {"correct_score","goals_over_under","both_teams_score","ht_draw_ft"}:
        return _fixture_market_price(event, selection)
    raise HTTPException(status_code=400, detail="Unsupported betting market")

def selection_wins(bet: dict, event: dict, result: str) -> bool:
    market = bet.get("market", "match_result")
    selection = bet.get("selection")
    if market == "match_result":
        return selection == result
    if market == "double_chance":
        if selection in {"dc_team_1", "1X"}:
            return result in {"home", "draw"}
        if selection in {"dc_team_2", "X2"}:
            return result in {"away", "draw"}
        return False
    if market == "correct_score":
        final_score = f"{int(event.get('home_score', 0))}-{int(event.get('away_score', 0))}"
        return selection == final_score
    if market == "both_teams_score":
        both = int(event.get("home_score",0)) > 0 and int(event.get("away_score",0)) > 0
        return both if selection == "yes" else not both if selection == "no" else False
    if market == "goals_over_under":
        total = int(event.get("home_score",0)) + int(event.get("away_score",0))
        try: line = float(selection.split("_",1)[1])
        except (ValueError, IndexError): return False
        return total > line if selection.startswith("over_") else total < line if selection.startswith("under_") else False
    if market == "ht_draw_ft":
        ht_home = event.get("halftime_home_score")
        ht_away = event.get("halftime_away_score")
        if ht_home is None or ht_away is None or int(ht_home) != int(ht_away):
            return False
        return selection in {"home", "win1", "ht_draw_ft_home"} and result == "home" or selection in {"draw", "ht_draw_ft_draw"} and result == "draw" or selection in {"away", "win2", "ht_draw_ft_away"} and result == "away"
    return False


async def settle_event_bets(event_id: str, result: str):
    """Settle open demo bets exactly once, even if settlement is triggered twice."""
    now = datetime.now(timezone.utc).isoformat()
    while True:
        bet = await db.bets.find_one_and_update(
            {"event_id": event_id, "status": "open"},
            {"$set": {"status": "settling", "settling_at": now}},
            return_document=ReturnDocument.AFTER,
        )
        if not bet:
            break
        if result == "void":
            payout = round(bet["stake"], 2)
            status = "void"
        elif selection_wins(bet, await db.events.find_one({"id": event_id}) or {}, result):
            payout = round(bet["potential_win"], 2)
            status = "won"
        else:
            payout = 0.0
            status = "lost"
        if payout:
            await db.users.update_one(
                {"_id": ObjectId(bet["user_id"])},
                {"$inc": {"balance": payout}},
            )
        await db.transactions.insert_one({
            "id": str(uuid.uuid4()),
            "reference": f"NB-SET-{bet['id'][:10].upper()}",
            "user_id": bet["user_id"],
            "type": "bet_settlement",
            "amount": payout,
            "method": "demo_wallet",
            "status": "completed",
            "bet_id": bet["id"],
            "created_at": now,
        })
        await db.bets.update_one(
            {"_id": bet["_id"], "status": "settling"},
            {"$set": {
                "status": status,
                "result": result,
                "payout": payout,
                "settled_at": now,
            }, "$unset": {"settling_at": ""}},
        )


@router.post("/bets")
async def place_demo_bet(body: BetInput, user: dict = Depends(get_current_user)):
    event = await db.events.find_one({"id": body.event_id})
    if not event:
        raise HTTPException(status_code=404, detail="Event not found")
    is_virtual = event.get("sport") == "Virtual Football"
    if (is_virtual and event.get("status") not in ("scheduled", "live")) or (not is_virtual and event.get("status") not in ("open", "live")):
        raise HTTPException(status_code=400, detail="Betting is closed for this event")
    odds = market_odds(event, body.market, body.selection)
    stake = round(body.stake, 2)
    updated = await db.users.find_one_and_update(
        {"_id": user["_id"], "balance": {"$gte": stake}},
        {"$inc": {"balance": -stake}}, return_document=ReturnDocument.AFTER,
    )
    if not updated:
        raise HTTPException(status_code=400, detail="Insufficient demo wallet balance")
    now = datetime.now(timezone.utc).isoformat()
    bet = {"id": str(uuid.uuid4()), "reference": f"NB-B-{uuid.uuid4().hex[:10].upper()}",
           "user_id": str(user["_id"]), "event_id": body.event_id, "market": body.market, "selection": body.selection,
           "stake": stake, "odds": odds, "potential_win": round(stake * odds, 2),
           "status": "open", "created_at": now}
    try:
        await db.bets.insert_one(bet)
        await db.transactions.insert_one({"id": str(uuid.uuid4()), "reference": bet["reference"],
            "user_id": str(user["_id"]), "type": "bet_stake", "amount": stake,
            "method": "demo_wallet", "status": "completed", "bet_id": bet["id"], "created_at": now})
    except Exception:
        await db.users.update_one({"_id": user["_id"]}, {"$inc": {"balance": stake}})
        raise HTTPException(status_code=503, detail="Bet could not be recorded; stake restored")
    return {"bet": bet_public(bet, event), "balance": round(updated.get("balance", 0.0), 2), "demo": True}


@router.get("/bets")
async def list_demo_bets(user: dict = Depends(get_current_user)):
    docs = await db.bets.find({"user_id": str(user["_id"])}).sort("created_at", -1).to_list(200)
    result = []
    for d in docs:
        event = await db.events.find_one({"id": d["event_id"]})
        result.append(bet_public(d, event))
    return result


@router.patch("/admin/events/{event_id}/control")
async def control_event(event_id: str, body: EventControlInput, staff: dict = Depends(require_permission("events.manage"))):
    current = await db.events.find_one({"id": event_id, "sport": {"$ne": "Virtual Football"}})
    if not current:
        raise HTTPException(status_code=404, detail="Sports event not found")

    values = {k: v for k, v in body.model_dump(exclude_none=True).items()}
    requested_status = values.get("status")

    # Start Live always starts a fresh 94-minute real-time clock. Score changes
    # made by Admin before/while live are preserved.
    if requested_status == "live":
        # Resume from a paused minute; a fresh match starts at minute 1.
        resume_minute = int(current.get("minute", 0) or 0) if current.get("status") in ("paused", "halftime") else 1
        values["minute"] = max(1, min(94, resume_minute))
        values["clock_base_minute"] = values["minute"]
        values["clock_started_at"] = datetime.now(timezone.utc).isoformat()
        values.pop("result", None)

    if requested_status == "halftime":
        # Freeze the live clock and preserve the exact score at the HT whistle.
        ht_minute = live_event_minute(current)
        values["minute"] = ht_minute
        values["clock_base_minute"] = ht_minute
        values["clock_started_at"] = None
        values["halftime_home_score"] = int(current.get("home_score", 0) or 0)
        values["halftime_away_score"] = int(current.get("away_score", 0) or 0)

    if requested_status == "paused":
        values["minute"] = live_event_minute(current)
        values["clock_base_minute"] = values["minute"]
        values["clock_started_at"] = None

    # Finish Match freezes the event at 94 minutes and settles every ticket
    # leg against the exact score currently stored on the event.
    if requested_status == "finished":
        home_score = int(values.get("home_score", current.get("home_score", 0)) or 0)
        away_score = int(values.get("away_score", current.get("away_score", 0)) or 0)
        values["home_score"] = home_score
        values["away_score"] = away_score
        values["minute"] = 94
        values["clock_base_minute"] = 94
        values["clock_started_at"] = None
        values["result"] = "home" if home_score > away_score else "away" if away_score > home_score else "draw"

    # Any score update while live keeps the already-running clock.
    if requested_status is None and current.get("status") == "live":
        values.pop("minute", None)

    await db.events.update_one({"id": event_id}, {"$set": values})
    updated = await db.events.find_one({"id": event_id})

    if requested_status == "finished":
        await settle_event_bets(event_id, values["result"])
        await settle_ticket_event(event_id, values["result"])
        updated = await db.events.find_one({"id": event_id})

    updated = await hydrate_event_team_assets(updated)
    return event_public(updated)


@router.post("/events/{event_id}/booking-code")
async def generate_event_booking_code(event_id: str, user: dict = Depends(get_current_user)):
    event = await db.events.find_one({"id": event_id})
    if not event:
        raise HTTPException(status_code=404, detail="Match not found")
    code = f"NBM-{uuid.uuid4().hex[:10].upper()}"
    await db.events.update_one({"id": event_id}, {"$set": {"booking_code": code}})
    return {"event_id": event_id, "booking_code": code}


@router.post("/admin/events/{event_id}/settle")
async def settle_event(event_id: str, body: BetSettlementInput, staff: dict = Depends(require_permission("events.manage"))):
    event = await db.events.find_one({"id": event_id})
    if not event:
        raise HTTPException(status_code=404, detail="Event not found")
    await db.events.update_one({"id": event_id}, {"$set": {"status": "finished", "result": body.result}})
    await settle_event_bets(event_id, body.result)
    await settle_ticket_event(event_id, body.result)
    return {"ok": True, "event_id": event_id, "result": body.result}



# ------------------------------------------------------------------ booking tickets / multiples
async def ticket_public(doc: dict):
    # Be defensive with tickets created by older versions. One malformed legacy
    # leg must never make the whole /tickets response fail with HTTP 500.
    ticket_id = doc.get("id") or str(doc.get("_id"))
    raw_legs = doc.get("selections") if isinstance(doc.get("selections"), list) else []
    legs=[]
    for leg in raw_legs:
        if not isinstance(leg, dict):
            continue
        event_id = leg.get("event_id")
        ev = await db.events.find_one({"id": event_id}) if event_id else None
        try:
            minute = virtual_minute(ev) if ev and ev.get("sport")=="Virtual Football" else live_event_minute(ev) if ev else None
        except (TypeError, ValueError):
            minute = 0
        try:
            score_home = int(ev.get("home_score", 0) or 0) if ev else 0
            score_away = int(ev.get("away_score", 0) or 0) if ev else 0
        except (TypeError, ValueError):
            score_home, score_away = 0, 0
        home_name = ev.get("home") if ev else leg.get("home", "Home")
        away_name = ev.get("away") if ev else leg.get("away", "Away")
        legs.append({**leg, "event_id": event_id or "", "home": home_name, "away": away_name,
                     "league": ev.get("league") if ev else leg.get("league"),
                     "status": leg.get("status", "pending"),
                     "event_status": ev.get("status") if ev else "finished",
                     "minute": minute,
                     "score": {"home": score_home, "away": score_away}})
    try:
        stake = round(float(doc.get("stake",0) or 0),2)
        total_odds = round(float(doc.get("total_odds",1) or 1),2)
        potential_win = round(float(doc.get("potential_win",0) or 0),2)
        payout = round(float(doc.get("payout",0) or 0),2)
    except (TypeError, ValueError):
        stake, total_odds, potential_win, payout = 0.0, 1.0, 0.0, 0.0
    return {"id":ticket_id, "booking_code":doc.get("booking_code", ""),
            "verify_code":doc.get("verify_code") or doc.get("booking_code", ""),
            "status":doc.get("status","booked"),
            "bet_type":"Multiple" if len(legs)>1 else "Singles", "stake":stake,
            "total_odds":total_odds, "potential_win":potential_win,
            "payout":payout, "created_at":doc.get("created_at"), "settled_at":doc.get("settled_at"), "selections":legs}

async def settle_ticket_event(event_id: str, result: str):
    tickets = await db.tickets.find({"selections.event_id": event_id, "status": {"$in":["open","pending"]}}).to_list(500)
    for ticket in tickets:
        changed=False
        for leg in ticket.get("selections",[]):
            if leg.get("event_id") != event_id or leg.get("status") not in ("open","pending"): continue
            ev=await db.events.find_one({"id":event_id}) or {}
            pseudo={"market":leg["market"],"selection":leg["selection"]}
            leg["status"]="won" if selection_wins(pseudo,ev,result) else "lost"; leg["result"]=result; changed=True
        if not changed: continue
        if any(l.get("status")=="lost" for l in ticket.get("selections",[])):
            ticket["status"]="lost"
        elif all(l.get("status")=="won" for l in ticket.get("selections",[])):
            ticket["status"]="won"
            if ticket.get("stake",0)>0 and not ticket.get("paid",False):
                ticket["payout"]=round(ticket["potential_win"],2)
                await db.users.update_one({"_id":ObjectId(ticket["user_id"])},{"$inc":{"balance":ticket["payout"]}})
                ticket["paid"]=True
                await db.transactions.insert_one({"id":str(uuid.uuid4()),"reference":f"NB-SET-{ticket['id'][:10].upper()}","user_id":ticket["user_id"],"type":"bet_settlement","amount":ticket["payout"],"method":"demo_wallet","status":"completed","ticket_id":ticket["id"],"created_at":datetime.now(timezone.utc).isoformat()})
        await db.tickets.update_one({"_id":ticket["_id"]},{"$set":{"selections":ticket["selections"],"status":ticket["status"],"payout":ticket.get("payout",0),"paid":ticket.get("paid",False),"settled_at":datetime.now(timezone.utc).isoformat() if ticket["status"] in ("won","lost") else None}})

@router.post("/tickets")
async def create_ticket(body: TicketInput, user: dict = Depends(get_current_user)):
    ids=[x.event_id for x in body.selections]
    if len(ids)!=len(set(ids)): raise HTTPException(status_code=400, detail="A ticket cannot contain the same match twice")
    selections=[]; total=1.0
    supported_markets = {
        "match_result", "double_chance", "correct_score",
        "ht_draw_ft", "goals_over_under", "both_teams_score",
    }
    for item in body.selections:
        ev = await db.events.find_one({"id": item.event_id})
        if not ev:
            raise HTTPException(status_code=404, detail=f"Match {item.event_id} not found")
        if ev.get("status") not in ("open", "scheduled", "live"):
            raise HTTPException(status_code=400, detail=f"{ev.get('home', 'Selected match')} vs {ev.get('away', '')} is no longer open")
        if item.market not in supported_markets:
            raise HTTPException(status_code=400, detail=f"Unsupported market: {item.market}")
        # Always validate and price the selection on the server. Never trust an
        # odds value supplied by the browser; persist the same price used by the
        # booking code and subsequent placement.
        try:
            odds = round(float(market_odds(ev, item.market, item.selection)), 2)
        except HTTPException:
            raise
        except (TypeError, ValueError, OverflowError):
            raise HTTPException(status_code=400, detail=f"Invalid selection for {item.market}")
        if not math.isfinite(odds) or odds <= 1.0:
            raise HTTPException(status_code=400, detail=f"Odds unavailable for {item.market} selection {item.selection}")
        total *= odds
        selections.append({
            "event_id": item.event_id,
            "market": item.market,
            "selection": item.selection,
            "odds": odds,
            "status": "pending",
            "result": None,
        })
    code=f"NBM-{uuid.uuid4().hex[:10].upper()}"; now=datetime.now(timezone.utc).isoformat()
    doc={"id":str(uuid.uuid4()),"booking_code":code,"user_id":str(user["_id"]),"selections":selections,"total_odds":round(total,2),"stake":0.0,"potential_win":0.0,"payout":0.0,"status":"booked","created_at":now}
    await db.tickets.insert_one(doc)
    return {"ticket":await ticket_public(doc)}

@router.get("/tickets/verify/{booking_code}")
async def verify_ticket(booking_code:str):
    doc=await db.tickets.find_one({"booking_code":booking_code.strip().upper()})
    if not doc: raise HTTPException(status_code=404, detail="Booking code not found")
    return {"ticket":await ticket_public(doc)}

@router.post("/tickets/verify")
async def verify_ticket_status(body: TicketVerifyInput):
    """Public ticket verification endpoint used by the Verify Ticket modal.

    It accepts either the public booking/verify code or the ticket UUID and returns
    a normalized status: Won, Lost, Pending, or Invalid. No wallet/auth data is
    exposed by this endpoint.
    """
    identifier = body.identifier.strip()
    if not identifier:
        return {"verification": {"status": "Invalid", "message": "Enter a Ticket ID or Verify Code.", "ticket": None}}

    doc = await db.tickets.find_one({"$or": [
        {"verify_code": identifier.upper()},
        {"booking_code": identifier.upper(), "status": "booked"},
        {"id": identifier},
    ]})
    if not doc:
        return {"verification": {"status": "Invalid", "message": "We could not find a ticket with that Ticket ID or Verify Code.", "ticket": None}}

    public = await ticket_public(doc)
    raw_status = str(public.get("status", "pending")).lower()
    status = "Won" if raw_status == "won" else "Lost" if raw_status == "lost" else "Pending"
    message = {
        "Won": "Congratulations! This ticket is verified as a winner and the payout shown below is the recorded winning payout.",
        "Lost": "This ticket has been settled and did not win.",
        "Pending": "This ticket is valid but has not reached a final result yet.",
    }[status]
    verified_at = datetime.now(timezone.utc).isoformat()
    ticket = {
        "ticket_id": public["id"],
        "id": public["id"],
        "verify_code": public.get("verify_code") or public.get("booking_code", ""),
        "booking_code": public.get("booking_code", ""),
        "status": public.get("status", "pending"),
        "stake": public.get("stake", 0),
        "total_odds": public.get("total_odds", 0),
        "payout": public.get("payout", 0),
        "potential_win": public.get("potential_win", 0),
        "created_at": public.get("created_at"),
        "settled_at": public.get("settled_at"),
        "verification_timestamp": verified_at,
        "selections": public.get("selections", []),
    }
    return {"verification": {"status": status, "message": message, "verified_at": verified_at, "ticket": ticket}}

@router.post("/tickets/{booking_code}/place")
async def place_ticket(booking_code:str, body:dict, user:dict=Depends(get_current_user)):
    # A booking code is a reusable shareable bet template. Every user who
    # places it gets a separate ticket/verify code, stake, wallet deduction
    # and settlement record. The original booking remains reusable.
    code = booking_code.strip().upper()
    template = await db.tickets.find_one({"booking_code": code, "status": "booked"})
    if not template:
        raise HTTPException(status_code=404, detail="Booking code not found or no longer available")

    try:
        stake = round(float(body.get("stake", 0)), 2)
    except (TypeError, ValueError, OverflowError):
        raise HTTPException(status_code=400, detail="Enter a valid stake amount")
    if not math.isfinite(stake) or stake <= 0:
        raise HTTPException(status_code=400, detail="Enter a valid stake amount")
    if stake < 200:
        raise HTTPException(status_code=400, detail="Minimum stake is GHS 200.00. Please enter a stake of GHS 200.00 or more to place bet.")

    # Do not allow a shared booking to be placed after any of its matches
    # have closed/finished. This protects all users using the same code.
    for leg in template.get("selections", []):
        event = await db.events.find_one({"id": leg.get("event_id")})
        if not event or event.get("status") not in ("open", "scheduled", "live"):
            raise HTTPException(status_code=400, detail="One of the matches in this booking is no longer available")

    updated=await db.users.find_one_and_update({"_id":user["_id"],"balance":{"$gte":stake}},{"$inc":{"balance":-stake}},return_document=ReturnDocument.AFTER)
    if not updated: raise HTTPException(status_code=400, detail="Insufficient demo wallet balance. Go to deposit.")

    ticket_id=str(uuid.uuid4())
    verify_code=f"NBV-{uuid.uuid4().hex[:10].upper()}"
    now=datetime.now(timezone.utc).isoformat()
    placed={
        "id":ticket_id,
        "booking_code":code,
        "verify_code":verify_code,
        "user_id":str(user["_id"]),
        "selections":[dict(x) for x in template.get("selections", [])],
        "total_odds":round(float(template.get("total_odds",1) or 1),2),
        "stake":stake,
        "potential_win":round(stake*float(template.get("total_odds",1) or 1),2),
        "payout":0.0,
        "status":"open",
        "created_at":now,
        "source_booking_id":template.get("id"),
    }
    await db.tickets.insert_one(placed)
    await db.transactions.insert_one({"id":str(uuid.uuid4()),"reference":f"NB-T-{ticket_id[:10].upper()}","user_id":str(user["_id"]),"type":"bet_stake","amount":stake,"method":"demo_wallet","status":"completed","ticket_id":ticket_id,"booking_code":code,"created_at":now})
    return {"ticket":await ticket_public(placed),"balance":round(updated.get("balance",0),2)}

@router.get("/tickets")
async def list_tickets(user:dict=Depends(get_current_user)):
    docs=await db.tickets.find({"user_id":str(user["_id"]), "status":{"$ne":"booked"}}).sort("created_at",-1).to_list(200)
    result=[]
    for d in docs:
        try:
            result.append(await ticket_public(d))
        except Exception as exc:
            logger.exception("Skipping malformed ticket %s: %s", d.get("id") or d.get("_id"), exc)
    return result

@router.delete("/tickets/history")
async def clear_ticket_history(user: dict = Depends(get_current_user)):
    """Delete only this user's settled tickets; financial transaction records remain intact."""
    result = await db.tickets.delete_many({
        "user_id": str(user["_id"]),
        "status": {"$in": ["won", "lost", "void", "cancelled"]}
    })
    return {"ok": True, "deleted": result.deleted_count, "note": "Wallet and audit transaction records were not deleted."}


@router.delete("/tickets/{ticket_id}")
async def delete_settled_ticket(ticket_id: str, user: dict = Depends(get_current_user)):
    result = await db.tickets.delete_one({
        "id": ticket_id,
        "user_id": str(user["_id"]),
        "status": {"$in": ["won", "lost", "void", "cancelled"]}
    })
    if result.deleted_count != 1:
        raise HTTPException(status_code=404, detail="Settled ticket not found")
    return {"ok": True}

# ------------------------------------------------------------------ auth routes
@router.post("/auth/register")
async def register(body: RegisterInput):
    if body.password != body.confirm_password:
        raise HTTPException(status_code=400, detail="Passwords do not match")
    email = body.email.lower()
    phone = body.phone.strip()
    referral_code = body.referral_code.strip().upper()
    referrer = await db.users.find_one({"referral_code": referral_code, "role": {"$in": ["admin", "sub_admin"]}})
    if not referrer:
        raise HTTPException(status_code=400, detail="A valid Admin or Sub-Admin referral code is required to create an account")
    if await db.users.find_one({"$or": [{"email": email}, {"phone": phone}]}):
        raise HTTPException(status_code=400, detail="Email or phone number is already registered")
    doc = {"email": email, "phone": phone, "password_hash": hash_password(body.password), "name": body.name,
           "role": "user", "balance": STARTING_BALANCE, "total_deposited": 0.0,
           "referral_code_used": referral_code, "referred_by": str(referrer["_id"]),
           "created_at": datetime.now(timezone.utc).isoformat()}
    res = await db.users.insert_one(doc); doc["_id"] = res.inserted_id
    token = create_access_token(str(res.inserted_id), email)
    return {"token": token, "user": public_user(doc), "referrer": {"name": referrer.get("name", ""), "role": referrer.get("role")}}

@router.post("/auth/login")
async def login(body: LoginInput):
    identifier = body.identifier.strip().lower()
    user = await db.users.find_one({"$or": [{"email": identifier}, {"phone": body.identifier.strip()}]})
    if not user or not verify_password(body.password, user["password_hash"]):
        raise HTTPException(status_code=401, detail="Invalid email/phone number or password")
    token = create_access_token(str(user["_id"]), user.get("email", ""))
    return {"token": token, "user": public_user(user)}

@router.get("/auth/me")
async def me(user: dict = Depends(get_current_user)):
    return public_user(user)


# ------------------------------------------------------------------ cashier (simulated)
def txn_public(d: dict) -> dict:
    return {
        "id": d["id"], "type": d["type"], "amount": round(d["amount"], 2),
        "method": d.get("method"),
        "status": d["status"], "reference": d.get("reference"), "created_at": d["created_at"],
        "reviewed_at": d.get("reviewed_at"), "reviewed_by": d.get("reviewed_by"),
        "review_reason": d.get("review_reason"), "destination": d.get("destination"),
        "payout_status": d.get("payout_status"), "payout_id": d.get("payout_id"),
        "payout_error": d.get("payout_error"),
        "sender_name": d.get("sender_name"), "sender_phone": d.get("sender_phone"),
        "sender_account_name": d.get("sender_account_name"), "transaction_reference": d.get("transaction_reference"),
        "proof_data_url": d.get("proof_data_url"), "audit_history": d.get("audit_history", []),
    }


@router.get("/wallet/status")
async def wallet_status(user: dict = Depends(get_current_user)):
    s = await get_settings()
    fresh = await db.users.find_one({"_id": user["_id"]})
    total_dep = fresh.get("total_deposited", 0.0)
    deposit_count_result = await db.transactions.aggregate([
        {"$match": {"user_id": str(user["_id"]), "type": "deposit", "status": {"$in": ["approved", "credited"]}}},
        {"$count": "count"},
    ]).to_list(1)
    deposit_count = int(deposit_count_result[0]["count"] if deposit_count_result else 0)
    deposits_required = 3
    # Staff accounts are exempt from the three-approved-deposit rule in the
    # withdrawal endpoint too. Keep the real deposit_count for display/audit,
    # but do not block staff in the wallet status response.
    is_staff = user.get("role", "user") in STAFF_ROLES
    deposits_remaining = 0 if is_staff else max(0, deposits_required - deposit_count)
    can_withdraw = fresh.get("balance", 0.0) >= s["min_withdrawal"] and deposits_remaining == 0
    reserved = await db.transactions.aggregate([
        {"$match": {"user_id": str(user["_id"]), "type": "withdrawal", "status": {"$in": ["pending", "processing"]}}},
        {"$group": {"_id": None, "amount": {"$sum": "$amount"}}},
    ]).to_list(1)
    reserved_balance = round((reserved[0]["amount"] if reserved else 0.0), 2)
    return {
        "balance": round(fresh.get("balance", 0.0), 2),
        "available_balance": round(fresh.get("balance", 0.0), 2),
        "reserved_withdrawals": reserved_balance,
        "total_deposited": round(total_dep, 2),
        "deposit_count": deposit_count,
        "deposits_required": deposits_required,
        "deposits_remaining": deposits_remaining,
        "withdrawal_deposit_requirement_met": deposits_remaining == 0,
        "can_withdraw": can_withdraw,
        "first_deposit_bonus_available": not bool(fresh.get("first_deposit_bonus_awarded", False)),
        "first_deposit_bonus_cap": round(float(s.get("first_deposit_bonus_cap", FIRST_DEPOSIT_BONUS_CAP)), 2),
        "min_deposit": s["min_deposit"],
        "min_withdrawal": s["min_withdrawal"],
    }


@router.get("/wallet/payment-methods")
async def wallet_payment_methods(user: dict = Depends(get_current_user)):
    settings = await get_settings()
    return public_payment_methods(settings)



ALPHAPAY_BASE_URL = os.getenv("ALPHAPAY_BASE_URL", "https://api.alphapay.me").rstrip("/")
ALPHAPAY_NETWORKS = {
    "mtn": "mtn_gh",
    "telecel": "vodafone_gh",
    "airteltigo": "tigo_gh",
}


async def _alphapay_request(method: str, path: str, payload: Optional[dict] = None, extra_headers: Optional[dict] = None):
    api_key = os.getenv("ALPHAPAY_API_KEY", "").strip()
    if not api_key:
        raise HTTPException(status_code=503, detail="AlphaPay is not configured yet. Please contact support.")

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "Accept": "application/json",
    }
    if extra_headers:
        headers.update(extra_headers)

    # Optional static outbound proxy for all AlphaPay HTTP traffic.
    # requests uses a scheme-to-proxy mapping for its `proxies` argument.
    # Leave it unset to preserve the existing direct-connection behavior.
    static_proxy_url = os.getenv("STATIC_PROXY_URL", "").strip()
    request_proxies = (
        {"http": static_proxy_url, "https": static_proxy_url}
        if static_proxy_url else None
    )

    def _request():
        return requests.request(
            method,
            f"{ALPHAPAY_BASE_URL}{path}",
            headers=headers,
            json=payload,
            timeout=30,
            proxies=request_proxies,
        )

    try:
        response = await asyncio.to_thread(_request)
        # Keep the exact response body for diagnostics. Do not log request headers
        # or API keys. AlphaPay response bodies can contain customer data, so
        # restrict access to production logs and apply an appropriate retention policy.
        raw_response_body = response.text or ""
        try:
            parsed = json.loads(raw_response_body) if raw_response_body else {}
            data = parsed if isinstance(parsed, dict) else {"response": parsed}
        except (TypeError, ValueError):
            data = {"message": raw_response_body}
        logging.getLogger(__name__).info(
            "AlphaPay HTTP response method=%s path=%s http_status=%s raw_body=%s",
            method, path, response.status_code, raw_response_body
        )
    except requests.RequestException as exc:
        logger = logging.getLogger(__name__)
        logger.exception("AlphaPay network request failed (%s %s)", method, path)
        raise HTTPException(status_code=502, detail="Could not reach AlphaPay. Please try again.") from exc
    except Exception as exc:
        logger = logging.getLogger(__name__)
        logger.exception("Unexpected AlphaPay request error (%s %s)", method, path)
        raise HTTPException(status_code=502, detail="Could not reach AlphaPay. Please try again.") from exc

    if response.status_code >= 400:
        message = data.get("message") or data.get("detail") or data.get("error") or "AlphaPay rejected the payment request."
        code = data.get("code") or data.get("error_code")
        logger = logging.getLogger(__name__)
        logger.error("AlphaPay API rejected request: HTTP %s, code=%s, message=%s", response.status_code, str(code or "-"), str(message)[:300])
        suffix = f" (AlphaPay code: {code})" if code else ""
        raise HTTPException(status_code=502, detail=f"AlphaPay rejected the request: {str(message)[:300]}{suffix}")

    if isinstance(data, dict):
        result_meta = data.get("result") if isinstance(data.get("result"), dict) else {}
        if data.get("success") is False or str(result_meta.get("resultStatus", "")).upper() == "F":
            message = result_meta.get("resultMessage") or data.get("message") or "AlphaPay rejected the payment request."
            logger = logging.getLogger(__name__)
            logger.error("AlphaPay business rejection: %s", str(message)[:300])
            raise HTTPException(status_code=502, detail=f"AlphaPay rejected the request: {str(message)[:300]}")
    return data if isinstance(data, dict) else {}


# AlphaPay payout API. Set ALPHAPAY_BASE_URL to the provider's sandbox base URL
# when testing; production defaults to https://api.alphapay.me.
ALPHAPAY_PAYOUT_INITIALIZE_PATH = os.getenv(
    "ALPHAPAY_PAYOUT_INITIALIZE_PATH", "/api/v1/payouts/initialize"
)
ALPHAPAY_PAYOUT_STATUS_PATH = os.getenv(
    "ALPHAPAY_PAYOUT_STATUS_PATH", "/api/v1/payouts/{payout_id}"
)


async def trigger_alphapay_payout(payload: dict, idempotency_key: str) -> dict:
    """Create one AlphaPay payout using the shared requests+STATIC_PROXY_URL helper."""
    try:
        parsed_key = uuid.UUID(str(idempotency_key))
    except (TypeError, ValueError, AttributeError) as exc:
        raise HTTPException(status_code=400, detail="A valid UUID idempotency key is required") from exc
    if not isinstance(payload, dict) or not payload:
        raise HTTPException(status_code=400, detail="A valid payout payload is required")
    return await _alphapay_request(
        "POST", ALPHAPAY_PAYOUT_INITIALIZE_PATH, payload,
        extra_headers={"Idempotency-Key": str(parsed_key)},
    )


async def get_alphapay_payout_status(payout_id: str) -> dict:
    payout_id = str(payout_id or "").strip()
    if not payout_id:
        raise HTTPException(status_code=400, detail="AlphaPay payout ID is required")
    path = ALPHAPAY_PAYOUT_STATUS_PATH.format(payout_id=quote(payout_id, safe=""))
    return await _alphapay_request("GET", path)


def _alphapay_payload_data(payload: dict) -> dict:
    value = payload.get("data")
    return value if isinstance(value, dict) else payload


def _alphapay_state(payload: dict) -> str:
    data = _alphapay_payload_data(payload)
    return str(
        data.get("status")
        or data.get("payment_status")
        or payload.get("status")
        or payload.get("payment_status")
        or ""
    ).strip().lower()


async def _complete_alphapay_deposit(reference: str, amount: float, currency: str = "GHS"):
    txn = await db.transactions.find_one({
        "type": "deposit", "gateway": "alphapay",
        "$or": [
            {"gateway_reference": reference},
            {"alphapay_reference": reference},
            {"reference": reference},
        ],
    })
    if not txn or currency.upper() != "GHS":
        return False
    if not math.isclose(float(txn.get("amount", 0)), float(amount), rel_tol=0, abs_tol=0.01):
        return False
    if txn.get("credited") or txn.get("status") == "credited":
        return True
    if txn.get("status") == "pending":
        claimed = await db.transactions.find_one_and_update(
            {"id": txn["id"], "status": "pending", "credited": False},
            {"$set": {"status": "processing", "provider_confirmed_at": datetime.now(timezone.utc).isoformat()}},
            return_document=ReturnDocument.AFTER,
        )
        if not claimed:
            fresh = await db.transactions.find_one({"id": txn["id"]})
            return bool(fresh and fresh.get("credited"))
    elif txn.get("status") != "processing":
        return False

    user_id = ObjectId(txn["user_id"])
    target_user = await db.users.find_one({"_id": user_id})
    if not target_user:
        return False
    bonus_cap = float((await get_settings()).get("first_deposit_bonus_cap", FIRST_DEPOSIT_BONUS_CAP))
    bonus = min(float(txn["amount"]), bonus_cap) if not target_user.get("first_deposit_bonus_awarded", False) else 0.0
    base_update = {
        "$inc": {"balance": float(txn["amount"]), "total_deposited": float(txn["amount"])},
        "$addToSet": {"credited_deposit_ids": txn["id"]},
    }
    if bonus:
        bonus_update = {
            "$inc": {"balance": float(txn["amount"]) + bonus, "total_deposited": float(txn["amount"])},
            "$set": {"first_deposit_bonus_awarded": True},
            "$addToSet": {"credited_deposit_ids": txn["id"]},
        }
        result = await db.users.update_one(
            {"_id": user_id, "credited_deposit_ids": {"$ne": txn["id"]}, "first_deposit_bonus_awarded": {"$ne": True}},
            bonus_update,
        )
        if not result.modified_count:
            bonus = 0.0
            result = await db.users.update_one(
                {"_id": user_id, "credited_deposit_ids": {"$ne": txn["id"]}}, base_update
            )
    else:
        result = await db.users.update_one(
            {"_id": user_id, "credited_deposit_ids": {"$ne": txn["id"]}}, base_update
        )
    if not result.modified_count:
        already_credited = await db.users.find_one(
            {"_id": user_id, "credited_deposit_ids": txn["id"]}, {"_id": 1}
        )
        if not already_credited:
            return False
        bonus = 0.0
    now = datetime.now(timezone.utc).isoformat()
    await db.transactions.update_one(
        {"id": txn["id"], "status": "processing"},
        {"$set": {"status": "credited", "credited": True, "credited_at": now, "bonus_amount": round(bonus, 2)}},
    )
    if bonus:
        await db.transactions.insert_one({
            "id": str(uuid.uuid4()), "reference": f"NB-B-{uuid.uuid4().hex[:10].upper()}",
            "user_id": txn["user_id"], "type": "first_deposit_bonus", "amount": round(bonus, 2),
            "method": "promotion", "status": "credited", "deposit_reference": txn.get("reference"),
            "created_at": now, "promotion": "100% first deposit bonus up to GHS 100",
        })
    referred_by = target_user.get("referred_by")
    if referred_by and ObjectId.is_valid(str(referred_by)) and result.modified_count:
        referrer = await db.users.find_one({"_id": ObjectId(str(referred_by)), "role": "sub_admin"})
        if referrer:
            commission = round(float(txn["amount"]) * REFERRAL_COMMISSION_RATE, 2)
            await db.users.update_one({"_id": referrer["_id"]}, {"$inc": {"commission_total": commission}})
            await db.transactions.insert_one({
                "id": str(uuid.uuid4()), "reference": f"NB-C-{uuid.uuid4().hex[:10].upper()}",
                "user_id": str(referrer["_id"]), "type": "referral_commission", "amount": commission,
                "deposit_amount": float(txn["amount"]), "referred_user_id": txn["user_id"],
                "method": "referral", "status": "earned", "commission_rate": REFERRAL_COMMISSION_RATE,
                "created_at": now, "deposit_reference": txn.get("reference"),
            })
    await db.audit_logs.insert_one({
        "type": "deposit", "action": "automatically_credited", "deposit_id": txn["id"],
        "user_id": txn["user_id"], "amount": txn["amount"], "method": txn["method"],
        "gateway": "alphapay", "gateway_reference": reference, "bonus_amount": round(bonus, 2), "at": now,
    })
    return True


@router.post("/wallet/deposit")
async def deposit(body: DepositInput, user: dict = Depends(get_current_user)):
    if not math.isfinite(body.amount) or body.amount <= 0:
        raise HTTPException(status_code=400, detail="Amount must be a valid positive number")
    settings = await get_settings()
    if body.amount < settings["min_deposit"]:
        raise HTTPException(status_code=400, detail=f"Minimum deposit is GHS {settings['min_deposit']:.2f}")
    method_cfg = settings["payment_methods"].get(body.method)
    if not method_cfg or not method_cfg.get("active", True):
        raise HTTPException(status_code=400, detail="This mobile money provider is currently unavailable.")
    if not user.get("email"):
        raise HTTPException(status_code=400, detail="Add a valid email address to your account before depositing.")
    phone = re.sub(r"[^0-9]", "", body.phone_number)
    if phone.startswith("0") and len(phone) == 10:
        phone = "233" + phone[1:]
    elif phone.startswith("233") and len(phone) == 12:
        pass
    else:
        raise HTTPException(status_code=400, detail="Enter a valid Ghana mobile number, e.g. 0241234567.")
    internal_id = str(uuid.uuid4())
    reference = f"NB-D-{uuid.uuid4().hex[:12].upper()}"
    now = datetime.now(timezone.utc).isoformat()
    await db.transactions.insert_one({
        "id": internal_id, "reference": reference, "user_id": str(user["_id"]),
        "type": "deposit", "amount": round(body.amount, 2), "method": body.method,
        "phone_number": phone, "status": "initiating", "credited": False,
        "gateway": "alphapay", "created_at": now,
    })
    # AlphaPay's current Softpay contract requires amount as a decimal string,
    # a description, and a customer object. The returned AlphaPay `id` is the
    # UUID required by the payment-verification endpoint.
    full_name = str(user.get("name") or user.get("full_name") or "NexusBet customer").strip()
    name_parts = full_name.split()
    first_name = name_parts[0] if name_parts else "NexusBet"
    last_name = " ".join(name_parts[1:]) if len(name_parts) > 1 else "Customer"
    payload = {
        "amount": f"{body.amount:.2f}",
        "currency": "GHS",
        "country": "GH",
        "description": f"NexusBet wallet deposit {reference}",
        "customer": {
            "phone": f"+{phone}",
            "email": user["email"],
            "first_name": first_name,
            "last_name": last_name,
        },
        "network": ALPHAPAY_NETWORKS[body.method],
        "metadata": {"nexusbet_reference": reference},
    }
    # Structured outbound diagnostics: never include authorization headers, API
    # keys, full MSISDNs, or other secrets in this record.
    softpay_path = "/api/v1/payments/softpay/"
    outbound_phone = str(payload.get("customer", {}).get("phone", ""))
    if outbound_phone.startswith("+233"):
        phone_format = "+233"
        phone_prefix = "+233"
    elif outbound_phone.startswith("233"):
        phone_format = "233"
        phone_prefix = "233"
    elif outbound_phone.startswith("0"):
        phone_format = "0"
        phone_prefix = "0"
    else:
        phone_format = "other"
        phone_prefix = outbound_phone[:2]
    phone_digits = re.sub(r"\D", "", outbound_phone)
    masked_phone = (
        f"{phone_prefix}{'*' * max(0, len(outbound_phone) - len(phone_prefix) - 2)}{outbound_phone[-2:]}"
        if outbound_phone else ""
    )
    outbound_metadata = payload.get("metadata")
    outbound_reference = (
        outbound_metadata.get("nexusbet_reference")
        if isinstance(outbound_metadata, dict) else None
    )
    outbound_diagnostic = {
        "event": "alphapay_softpay_outbound",
        "method": "POST",
        "target_path": softpay_path,
        "network": payload.get("network"),
        "phone": {
            "format_prefix": phone_format,
            "masked": masked_phone,
            "character_length": len(outbound_phone),
            "digit_count": len(phone_digits),
        },
        "payload_schema": {
            "amount": {"type": type(payload.get("amount")).__name__},
            "metadata": {
                "type": type(outbound_metadata).__name__,
                "keys": sorted(outbound_metadata.keys()) if isinstance(outbound_metadata, dict) else [],
            },
            "reference": {
                "type": type(outbound_reference).__name__ if outbound_reference is not None else "NoneType",
                "source": "metadata.nexusbet_reference",
            },
        },
    }
    logging.getLogger(__name__).info(
        "AlphaPay outbound diagnostic %s",
        json.dumps(outbound_diagnostic, sort_keys=True, separators=(",", ":")),
    )

    try:
        result = await _alphapay_request(
            "POST",
            softpay_path,
            payload,
            extra_headers={"Idempotency-Key": internal_id},
        )
    except HTTPException:
        await db.transactions.update_one({"id": internal_id}, {"$set": {"status": "failed"}})
        raise

    data = _alphapay_payload_data(result)
    provider_id = str(data.get("id") or data.get("payment_id") or "").strip()
    state = _alphapay_state(result) or "pending"
    checkout_url = data.get("checkout_url") or data.get("payment_url") or ""
    if not provider_id:
        logging.getLogger(__name__).error("AlphaPay softpay response did not contain a payment id; response keys=%s", sorted(data.keys()))
        await db.transactions.update_one({"id": internal_id}, {"$set": {"status": "failed", "provider_status": "missing_payment_id"}})
        raise HTTPException(status_code=502, detail="AlphaPay response did not include a payment reference. Please contact support before retrying.")
    if state in ("failed", "failure", "cancelled", "canceled", "rejected", "expired"):
        await db.transactions.update_one(
            {"id": internal_id}, {"$set": {"gateway_reference": provider_id, "alphapay_reference": reference, "status": "failed", "provider_status": state}}
        )
        raise HTTPException(status_code=502, detail=str(data.get("message") or "AlphaPay could not initiate this payment."))
    await db.transactions.update_one(
        {"id": internal_id},
        {"$set": {
            "gateway_reference": provider_id,
            "alphapay_reference": reference,
            "gateway_checkout_url": checkout_url,
            "status": "pending",
            "provider_status": state,
        }},
    )
    return {
        "id": internal_id,
        "reference": provider_id,
        "merchant_reference": reference,
        "status": state,
        "checkout_url": checkout_url,
        "message": data.get("message") or "Approve the payment prompt on your mobile money phone. If a secure checkout link is provided, open it to complete payment.",
    }


@router.get("/wallet/deposit/verify/{reference}")
async def verify_wallet_deposit(reference: str, user: dict = Depends(get_current_user)):
    txn = await db.transactions.find_one({
        "type": "deposit", "gateway": "alphapay", "gateway_reference": reference,
        "user_id": str(user["_id"]),
    })
    if not txn:
        raise HTTPException(status_code=404, detail="Deposit reference not found.")
    if txn.get("credited"):
        return {"status": "credited", "message": "Payment confirmed and wallet credited."}
    verify_path = f"/api/v1/payments/{quote(reference, safe='')}/verify/"
    result = await _alphapay_request("GET", verify_path)
    data = _alphapay_payload_data(result)
    state = _alphapay_state(result)
    if state in ("success", "successful", "succeeded", "completed", "paid"):
        paid_amount = data.get("requested_amount", data.get("amount", data.get("paid_amount", txn["amount"])))
        currency = data.get("currency", "GHS")
        try:
            paid_amount = float(paid_amount)
        except (TypeError, ValueError):
            paid_amount = -1
        if await _complete_alphapay_deposit(reference, paid_amount, str(currency)):
            return {"status": "credited", "message": "Payment confirmed and wallet credited."}
    if state in ("failed", "failure", "abandoned", "cancelled", "canceled", "rejected", "expired"):
        await db.transactions.update_one(
            {"id": txn["id"], "status": "pending"},
            {"$set": {"status": "failed", "provider_status": state}},
        )
        return {"status": "failed", "message": "The mobile money payment was not completed."}
    return {"status": "pending", "message": "Payment is still awaiting mobile money confirmation."}


@router.post("/payments/alphapay/webhook")
async def alphapay_webhook(request: Request):
    secret = os.getenv("ALPHAPAY_WEBHOOK_SECRET", "").strip()
    if not secret:
        raise HTTPException(status_code=503, detail="AlphaPay webhook is not configured")
    raw = await request.body()
    signature = request.headers.get("x-webhook-signature", "")
    timestamp = request.headers.get("x-webhook-timestamp", "")
    if not signature or not timestamp:
        raise HTTPException(status_code=401, detail="Missing AlphaPay webhook signature")
    try:
        # AlphaPay sends X-Webhook-Timestamp as a Unix timestamp in seconds.
        sent_at_seconds = int(timestamp)
        if abs(datetime.now(timezone.utc).timestamp() - sent_at_seconds) > 300:
            raise HTTPException(status_code=401, detail="Expired AlphaPay webhook")
    except (TypeError, ValueError):
        raise HTTPException(status_code=401, detail="Invalid AlphaPay webhook timestamp")
    expected = hmac.new(secret.encode(), timestamp.encode() + b"." + raw, hashlib.sha256).hexdigest()
    if not hmac.compare_digest(signature, expected):
        raise HTTPException(status_code=401, detail="Invalid AlphaPay webhook signature")
    try:
        event = json.loads(raw.decode("utf-8"))
        if not isinstance(event, dict):
            raise ValueError("Webhook JSON root must be an object")
    except Exception:
        logging.getLogger(__name__).warning(
            "AlphaPay webhook received a validly signed but invalid JSON body; byte_length=%s",
            len(raw),
        )
        raise HTTPException(status_code=400, detail="Invalid webhook payload")
    # Log only after signature and timestamp verification. This captures the
    # exact provider event for reconciliation; protect logs because event data
    # may include customer identifiers. Never log the webhook signature/secret.
    logging.getLogger(__name__).info(
        "AlphaPay verified webhook received raw_body=%s", raw.decode("utf-8", errors="replace")
    )
    event_name = str(event.get("event") or "").lower()
    data = event.get("data") if isinstance(event.get("data"), dict) else event
    reference = str(data.get("id") or data.get("reference") or data.get("merchant_reference") or "")
    state = str(data.get("status") or "").lower()
    if event_name in ("transaction.success", "payment.success", "payment.succeeded") or state in ("success", "successful", "succeeded", "completed", "paid"):
        try:
            amount = float(data.get("amount", data.get("paid_amount", 0)))
        except (TypeError, ValueError):
            amount = 0
        await _complete_alphapay_deposit(reference, amount, str(data.get("currency") or "GHS"))
    elif event_name in ("transaction.failed", "transaction.cancelled", "payment.failed", "payment.cancelled") or state in ("failed", "cancelled", "canceled", "rejected", "expired"):
        await db.transactions.update_one(
            {
                "type": "deposit", "gateway": "alphapay", "status": "pending",
                "$or": [
                    {"gateway_reference": reference},
                    {"alphapay_reference": reference},
                    {"reference": reference},
                ],
            },
            {"$set": {"status": "failed", "provider_status": state or event_name}},
        )
    return {"received": True}


@router.post("/wallet/deposit/manual")
async def legacy_manual_deposit_rejected(request: Request):
    raise HTTPException(status_code=410, detail="Manual deposits are disabled. Use the automatic mobile money checkout.")


def _alphapay_payout_state(payload: dict) -> str:
    data = _alphapay_payload_data(payload)
    return str(
        data.get("status") or data.get("payout_status") or data.get("transaction_status")
        or payload.get("status") or "pending"
    ).strip().lower()


async def _apply_alphapay_payout_status(txn: dict, provider_payload: dict, reviewed_by: str = "system") -> dict:
    """Persist a provider status exactly once; failed payouts refund the reserved wallet amount."""
    data = _alphapay_payload_data(provider_payload)
    provider_state = _alphapay_payout_state(provider_payload)
    provider_id = str(
        data.get("id") or data.get("payout_id") or data.get("payoutId")
        or data.get("transaction_id") or txn.get("payout_id") or ""
    ).strip()
    now = datetime.now(timezone.utc).isoformat()
    success_states = {"success", "successful", "succeeded", "completed", "paid"}
    failure_states = {"failed", "failure", "rejected", "cancelled", "canceled", "declined", "expired"}

    if provider_state in success_states:
        update = await db.transactions.update_one(
            {"id": txn["id"], "type": "withdrawal", "status": "processing", "payout_status": {"$ne": "success"}},
            {"$set": {"status": "paid", "payout_status": "success", "provider_status": provider_state,
                      "payout_id": provider_id or txn.get("payout_id"), "paid_at": now,
                      "payout_response": provider_payload, "reviewed_by": reviewed_by}},
        )
        fresh = await db.transactions.find_one({"id": txn["id"]})
        return {"status": fresh.get("status", "processing"), "payout_status": fresh.get("payout_status", provider_state),
                "payout_id": fresh.get("payout_id"), "provider": data}

    if provider_state in failure_states:
        session = await client.start_session()
        try:
            async with session.start_transaction():
                fresh = await db.transactions.find_one(
                    {"id": txn["id"], "type": "withdrawal", "status": "processing", "refunded": {"$ne": True}},
                    session=session,
                )
                if fresh:
                    changed = await db.transactions.update_one(
                        {"id": txn["id"], "status": "processing", "refunded": {"$ne": True}},
                        {"$set": {"status": "failed", "payout_status": "failed", "provider_status": provider_state,
                                  "payout_id": provider_id or txn.get("payout_id"), "payout_response": provider_payload,
                                  "payout_failed_at": now, "refunded": True}},
                        session=session,
                    )
                    if changed.modified_count == 1:
                        await db.users.update_one(
                            {"_id": ObjectId(fresh["user_id"])},
                            {"$inc": {"balance": round(float(fresh["amount"]), 2)}},
                            session=session,
                        )
                        await db.audit_logs.insert_one({
                            "type": "withdrawal", "action": "alphapay_payout_failed_refunded",
                            "transaction_id": txn["id"], "user_id": fresh["user_id"],
                            "amount": fresh["amount"], "provider_status": provider_state, "at": now,
                        }, session=session)
        finally:
            await session.end_session()
        fresh = await db.transactions.find_one({"id": txn["id"]})
        return {"status": fresh.get("status", "failed"), "payout_status": fresh.get("payout_status", "failed"),
                "payout_id": fresh.get("payout_id"), "provider": data}

    # PENDING / PROCESSING / INITIATED / UNKNOWN remain reserved and are never marked paid.
    await db.transactions.update_one(
        {"id": txn["id"], "type": "withdrawal", "status": "processing"},
        {"$set": {"payout_status": provider_state or "pending", "provider_status": provider_state or "pending",
                  "payout_id": provider_id or txn.get("payout_id"), "payout_response": provider_payload,
                  "payout_last_checked_at": now}},
    )
    fresh = await db.transactions.find_one({"id": txn["id"]})
    return {"status": fresh.get("status", "processing"), "payout_status": fresh.get("payout_status", provider_state),
            "payout_id": fresh.get("payout_id"), "provider": data}


@router.post("/wallet/withdraw")
async def withdraw(body: WithdrawInput, user: dict = Depends(get_current_user)):
    if not math.isfinite(body.amount):
        raise HTTPException(status_code=400, detail="Amount must be a finite number")
    destination = body.destination.strip()
    if len(destination) < 4:
        raise HTTPException(status_code=400, detail="A valid payout destination is required")
    s = await get_settings()
    if body.amount < s["min_withdrawal"]:
        raise HTTPException(status_code=400, detail=f"Minimum withdrawal is GHS {s['min_withdrawal']:.0f}")

    # The three-approved-deposit rule applies only to regular customer accounts.
    # Admin, Super Admin, and Sub-Admin accounts are staff and are exempt.
    if user.get("role", "user") not in STAFF_ROLES:
        deposit_count_result = await db.transactions.aggregate([
            {"$match": {"user_id": str(user["_id"]), "type": "deposit", "status": {"$in": ["approved", "credited"]}}},
            {"$count": "count"},
        ]).to_list(1)
        deposit_count = int(deposit_count_result[0]["count"] if deposit_count_result else 0)
        if deposit_count < 3:
            raise HTTPException(status_code=400, detail="MAKE 3 MORE DEPOSIT BEFORE YOU CAN WITHDRAW YOUR WINNINGS")

    # Reserve the amount atomically so two simultaneous requests cannot
    # spend the same available balance. The amount remains reserved while
    # the demo withdrawal moves through pending -> processing -> paid.
    updated = await db.users.find_one_and_update(
        {"_id": user["_id"], "balance": {"$gte": body.amount}},
        {"$inc": {"balance": -round(body.amount, 2)}},
        return_document=ReturnDocument.AFTER,
    )
    if not updated:
        raise HTTPException(status_code=400, detail="Insufficient balance")
    new_balance = round(updated.get("balance", 0.0), 2)
    txn = {
        "id": str(uuid.uuid4()), "reference": f"NB-W-{uuid.uuid4().hex[:10].upper()}", "user_id": str(user["_id"]), "type": "withdrawal",
        "amount": round(body.amount, 2), "method": body.method,
        "destination": destination, "phone_number": body.phone_number, "status": "pending", "created_at": datetime.now(timezone.utc).isoformat(),
    }
    try:
        await db.transactions.insert_one(txn)
    except Exception:
        # Compensate if the transaction record cannot be created after the
        # balance reservation, so a failed request cannot consume funds.
        await db.users.update_one(
            {"_id": user["_id"]},
            {"$inc": {"balance": round(body.amount, 2)}},
        )
        raise HTTPException(status_code=503, detail="Withdrawal could not be recorded; no funds were taken")
    return {"balance": new_balance, "withdrawn": round(body.amount, 2), "status": "pending", "reference": txn["reference"]}


@router.get("/wallet/transactions")
async def wallet_transactions(user: dict = Depends(get_current_user)):
    docs = await db.transactions.find({"user_id": str(user["_id"])}).sort("created_at", -1).to_list(200)
    return [txn_public(d) for d in docs]


# ------------------------------------------------------------------ referrals, staff wallets & settlement accounts

def role_label(role: str) -> str:
    return {"super_admin": "Super Admin", "admin": "Admin", "sub_admin": "Sub-Admin", "user": "User"}.get(role, role)


def staff_public(doc: dict) -> dict:
    return {
        "id": str(doc["_id"]), "name": doc.get("name", ""), "email": doc.get("email", ""),
        "phone": doc.get("phone", ""), "role": doc.get("role", "user"),
        "role_label": role_label(doc.get("role", "user")),
        "balance": round(doc.get("balance", 0.0), 2),
        "demo_balance": round(doc.get("balance", 0.0), 2) if doc.get("role") in STAFF_ROLES else None,
        "referral_code": doc.get("referral_code", ""),
        "commission_total": round(doc.get("commission_total", 0.0), 2),
        "permissions": doc.get("permissions", []), "created_at": doc.get("created_at"),
    }


@router.get("/referrals/me")
async def referral_profile(user: dict = Depends(require_staff)):
    if user.get("role") not in ("admin", "sub_admin"):
        # Super Admin can also have a referral code, but this endpoint remains useful for the staff UI.
        if user.get("role") != "super_admin":
            raise HTTPException(status_code=403, detail="Referral tools are for staff accounts")
    code = user.get("referral_code")
    if not code:
        code = await unique_code(db.users, "referral_code", 8)
        await db.users.update_one({"_id": user["_id"]}, {"$set": {"referral_code": code}})
    deposits = await db.transactions.count_documents({"type": "deposit", "status": "approved", "user_id": {"$in": [str(x["_id"]) async for x in db.users.find({"referred_by": str(user["_id"])}, {"_id": 1})]}})
    rate = REFERRAL_COMMISSION_RATE if user.get("role") == "sub_admin" else 0.0
    return {"referral_code": code, "role": user.get("role"), "commission_rate": rate, "commission_total": round(user.get("commission_total", 0.0), 2) if user.get("role") == "sub_admin" else 0.0, "referred_deposit_count": deposits}


@router.get("/staff/commissions")
async def staff_commissions(user: dict = Depends(require_staff)):
    if user.get("role") != "sub_admin":
        return {"commission_rate": 0.0, "today": 0.0, "all_time": 0.0, "ledger": []}
    docs = await db.transactions.find({"type": "referral_commission", "user_id": str(user["_id"])}).sort("created_at", -1).to_list(1000)
    referred_ids = [d.get("referred_user_id") for d in docs if d.get("referred_user_id") and ObjectId.is_valid(d.get("referred_user_id"))]
    users = {}
    if referred_ids:
        async for u in db.users.find({"_id": {"$in": [ObjectId(x) for x in referred_ids]}}):
            users[str(u["_id"])] = {"name": u.get("name", ""), "email": u.get("email", ""), "phone": u.get("phone", "")}
    rows = [{"id": d["id"], "created_at": d["created_at"], "deposit_amount": round(d.get("deposit_amount", 0), 2),
             "commission": round(d.get("amount", 0), 2), "user": users.get(d.get("referred_user_id"), {}), "deposit_reference": d.get("deposit_reference")} for d in docs]
    today = datetime.now(timezone.utc).date().isoformat()
    today_total = round(sum(x["commission"] for x in rows if str(x["created_at"]).startswith(today)), 2)
    all_time = round(sum(x["commission"] for x in rows), 2)
    return {"commission_rate": REFERRAL_COMMISSION_RATE, "today": today_total, "all_time": all_time, "ledger": rows}


@router.get("/admin/commission-ledger")
async def admin_commission_ledger(admin: dict = Depends(require_admin)):
    docs = await db.transactions.find({"type": "referral_commission"}).sort("created_at", -1).to_list(2000)
    referred_ids = [d.get("referred_user_id") for d in docs if d.get("referred_user_id") and ObjectId.is_valid(str(d.get("referred_user_id")))]
    staff_ids = [d.get("user_id") for d in docs if d.get("user_id") and ObjectId.is_valid(str(d.get("user_id")))]
    ids = {str(x) for x in referred_ids + staff_ids}
    lookup = {}
    if ids:
        async for u in db.users.find({"_id": {"$in": [ObjectId(x) for x in ids]}}):
            lookup[str(u["_id"])] = {"name": u.get("name", ""), "email": u.get("email", ""), "phone": u.get("phone", ""), "referral_code": u.get("referral_code", ""), "role": u.get("role", "")}
    rows = [{
        "id": d.get("id", str(d.get("_id", ""))), "created_at": d.get("created_at"),
        "deposit_amount": round(float(d.get("deposit_amount", 0) or 0), 2),
        "commission": round(float(d.get("amount", 0) or 0), 2),
        "staff": lookup.get(str(d.get("user_id")), {}),
        "user": lookup.get(str(d.get("referred_user_id")), {}),
        "deposit_reference": d.get("deposit_reference"),
        "commission_rate": d.get("commission_rate", REFERRAL_COMMISSION_RATE)
    } for d in docs]
    today = datetime.now(timezone.utc).date().isoformat()
    return {"today": round(sum(r["commission"] for r in rows if str(r.get("created_at", "")).startswith(today)), 2),
            "all_time": round(sum(r["commission"] for r in rows), 2), "ledger": rows}


@router.post("/staff/demo-credit")
async def demo_credit(body: DemoCreditInput, user: dict = Depends(require_staff)):
    amount = round(float(body.amount), 2)
    updated = await db.users.find_one_and_update({"_id": user["_id"], "role": {"$in": list(STAFF_ROLES)}}, {"$inc": {"balance": amount}}, return_document=ReturnDocument.AFTER)
    if not updated:
        raise HTTPException(status_code=403, detail="Demo credits are only available to staff accounts")
    now = datetime.now(timezone.utc).isoformat()
    await db.transactions.insert_one({"id": str(uuid.uuid4()), "reference": f"NB-DEMO-{uuid.uuid4().hex[:10].upper()}", "user_id": str(user["_id"]), "type": "demo_credit", "amount": amount, "method": "staff_demo", "status": "completed", "created_at": now})
    return {"ok": True, "demo_balance": round(updated.get("balance", 0.0), 2)}


@router.get("/admin/payout-accounts")
async def read_payout_accounts(staff: dict = Depends(require_staff)):
    doc = await db.settings.find_one({"_id": "payout_accounts"}) or {}
    fields = ["mtn_name", "mtn_number", "telecel_name", "telecel_number", "bank_name", "bank_account_name", "bank_account_number", "bank_branch"]
    return {k: doc.get(k, "") for k in fields}


@router.put("/admin/payout-accounts")
async def update_payout_accounts(body: PayoutAccountsInput, admin: dict = Depends(require_admin)):
    values = {k: v.strip() for k, v in body.model_dump().items()}
    values["updated_at"] = datetime.now(timezone.utc).isoformat()
    values["updated_by"] = str(admin["_id"])
    await db.settings.update_one({"_id": "payout_accounts"}, {"$set": values}, upsert=True)
    return await read_payout_accounts(admin)


@router.post("/admin/deposits/cleanup")
async def cleanup_deposit_logs(body: DepositCleanupInput, super_admin: dict = Depends(require_super_admin)):
    cutoff = body.before
    if cutoff.tzinfo is None:
        cutoff = cutoff.replace(tzinfo=timezone.utc)
    cutoff_iso = cutoff.astimezone(timezone.utc).isoformat()
    result = await db.transactions.update_many(
        {"type": "deposit", "created_at": {"$lt": cutoff_iso}, "deposit_log_deleted_at": {"$exists": False}},
        {"$set": {"deposit_log_deleted_at": datetime.now(timezone.utc).isoformat(), "deposit_log_deleted_by": str(super_admin["_id"]), "deposit_log_deleted": True}},
    )
    return {"ok": True, "soft_deleted": result.modified_count, "before": cutoff_iso, "balances_untouched": True}


@router.get("/staff/invite/{token}")
async def inspect_staff_invite(token: str):
    invite = await db.settings.find_one({"_id": f"staff_invite:{token}"})
    if not invite:
        raise HTTPException(status_code=404, detail="Invitation link is invalid or expired")
    expires_at = datetime.fromisoformat(invite["expires_at"])
    if expires_at < datetime.now(timezone.utc):
        raise HTTPException(status_code=410, detail="Invitation link has expired")
    target = await db.users.find_one({"_id": ObjectId(invite["user_id"])}) if ObjectId.is_valid(invite.get("user_id", "")) else None
    if not target:
        raise HTTPException(status_code=404, detail="Invited staff account no longer exists")
    return {"valid": True, "name": target.get("name", ""), "email": target.get("email", ""), "role": target.get("role"), "role_label": role_label(target.get("role", "user")), "expires_at": invite["expires_at"]}


@router.get("/admin/staff")
async def list_staff(manager: dict = Depends(require_admin)):
    docs = await db.users.find({"role": {"$in": ["super_admin", "admin", "sub_admin"]}}).sort("created_at", -1).to_list(500)
    return [staff_public(d) for d in docs]


@router.post("/admin/staff")
async def create_staff(body: StaffCreateInput, manager: dict = Depends(require_admin)):
    if manager.get("role") == "admin" and body.role != "sub_admin":
        raise HTTPException(status_code=403, detail="Admins can only create Sub-Admin accounts")
    email = body.email.lower()
    if await db.users.find_one({"email": email}):
        raise HTTPException(status_code=400, detail="Email is already registered")
    referral_code = await unique_code(db.users, "referral_code", 8)
    now = datetime.now(timezone.utc).isoformat()
    doc = {"email": email, "phone": body.phone.strip(), "password_hash": hash_password(body.password), "name": body.name.strip(),
           "role": body.role, "balance": STAFF_STARTING_DEMO_BALANCE, "demo_balance": STAFF_STARTING_DEMO_BALANCE,
           "commission_total": 0.0, "referral_code": referral_code, "permissions": default_subadmin_permissions() if body.role == "sub_admin" else ALL_SUBADMIN_PERMISSIONS,
           "created_at": now, "created_by": str(manager["_id"])}
    res = await db.users.insert_one(doc); doc["_id"] = res.inserted_id
    return staff_public(doc)


@router.put("/admin/staff/{user_id}")
async def update_staff(user_id: str, body: StaffUpdateInput, manager: dict = Depends(require_admin)):
    if not ObjectId.is_valid(user_id):
        raise HTTPException(status_code=400, detail="Invalid user id")
    target = await db.users.find_one({"_id": ObjectId(user_id)})
    if not target or target.get("role") not in STAFF_ROLES:
        raise HTTPException(status_code=404, detail="Staff account not found")
    if target.get("role") == "super_admin" and manager.get("role") != "super_admin":
        raise HTTPException(status_code=403, detail="Admins cannot modify Super Admin accounts")
    values = {}
    for key in ("name", "email", "phone"):
        value = getattr(body, key, None)
        if value is not None:
            values[key] = str(value).lower() if key == "email" else str(value).strip()
    if body.password:
        values["password_hash"] = hash_password(body.password)
    if values.get("email") and await db.users.find_one({"email": values["email"], "_id": {"$ne": target["_id"]}}):
        raise HTTPException(status_code=400, detail="Email is already registered")
    if values:
        await db.users.update_one({"_id": target["_id"]}, {"$set": values})
    updated = await db.users.find_one({"_id": target["_id"]})
    return staff_public(updated)


@router.delete("/admin/staff/{user_id}")
async def delete_staff(user_id: str, manager: dict = Depends(require_admin)):
    if not ObjectId.is_valid(user_id):
        raise HTTPException(status_code=400, detail="Invalid user id")
    target = await db.users.find_one({"_id": ObjectId(user_id)})
    if not target or target.get("role") not in STAFF_ROLES:
        raise HTTPException(status_code=404, detail="Staff account not found")
    if target.get("role") == "super_admin":
        raise HTTPException(status_code=403, detail="Super Admin accounts cannot be deleted")
    if manager.get("role") == "admin" and target.get("role") != "sub_admin":
        raise HTTPException(status_code=403, detail="Admins can only remove Sub-Admins")
    await db.users.delete_one({"_id": target["_id"]})
    return {"ok": True}


@router.post("/admin/staff/{user_id}/invite")
async def create_staff_invite(user_id: str, expires_hours: int = 24, manager: dict = Depends(require_admin)):
    if not ObjectId.is_valid(user_id):
        raise HTTPException(status_code=400, detail="Invalid user id")
    target = await db.users.find_one({"_id": ObjectId(user_id), "role": {"$in": ["admin", "sub_admin"]}})
    if not target:
        raise HTTPException(status_code=404, detail="Staff account not found")
    if manager.get("role") == "admin" and target.get("role") != "sub_admin":
        raise HTTPException(status_code=403, detail="Admins can only invite Sub-Admins")
    expires_hours = max(1, min(expires_hours, 720))
    token = uuid.uuid4().hex + uuid.uuid4().hex
    expires_at = datetime.now(timezone.utc) + timedelta(hours=expires_hours)
    await db.settings.update_one({"_id": f"staff_invite:{token}"}, {"$set": {"user_id": str(target["_id"]), "expires_at": expires_at.isoformat(), "created_by": str(manager["_id"])}}, upsert=True)
    return {"token": token, "expires_at": expires_at.isoformat(), "role": target.get("role"), "referral_code": target.get("referral_code", "")}


# ------------------------------------------------------------------ settings & staff
@router.get("/settings")
async def read_settings(user: dict = Depends(get_current_user)):
    settings = await get_settings()
    return {k: settings[k] for k in ("min_deposit", "min_withdrawal", "first_deposit_bonus_cap")}


@router.put("/admin/settings")
async def update_settings(body: SettingsInput, admin: dict = Depends(require_admin)):
    updates = {k: v for k, v in body.model_dump().items() if v is not None}
    if "min_deposit" in updates and updates["min_deposit"] < 0.01:
        raise HTTPException(status_code=400, detail="Minimum deposit must be at least GHS 0.01")
    if "min_withdrawal" in updates and updates["min_withdrawal"] < 0.01:
        raise HTTPException(status_code=400, detail="Minimum withdrawal must be at least GHS 0.01")
    if updates:
        if "min_deposit" in updates:
            updates["min_deposit_migrated_to_30"] = True
        await db.settings.update_one({"_id": "global"}, {"$set": updates}, upsert=True)
    return await get_settings()


@router.get("/admin/transactions")
async def admin_transactions(status: Optional[str] = None, transaction_type: Optional[str] = None,
                             staff: dict = Depends(require_permission("transactions.view"))):
    query = {"deposit_log_deleted": {"$ne": True}}
    if status:
        query["status"] = status
    if transaction_type:
        query["type"] = transaction_type
    docs = await db.transactions.find(query).sort("created_at", -1).to_list(500)
    user_ids = list({d.get("user_id") for d in docs if d.get("user_id")})
    users = {}
    if user_ids:
        async for u in db.users.find({"_id": {"$in": [ObjectId(uid) for uid in user_ids if ObjectId.is_valid(uid)]}}):
            users[str(u["_id"])] = {"email": u.get("email", ""), "name": u.get("name", "")}
    return [{**txn_public(d), "user": users.get(d.get("user_id"), {})} for d in docs]


@router.post("/admin/transactions/{transaction_id}/review")
async def review_transaction(transaction_id: str, action: Literal["approve", "reject"],
                             reason: str = "", staff: dict = Depends(require_admin)):
    txn = await db.transactions.find_one({"id": transaction_id})
    if not txn:
        raise HTTPException(status_code=404, detail="Transaction not found")
    if txn.get("type") not in ("deposit", "withdrawal"):
        raise HTTPException(status_code=400, detail="This transaction type cannot be reviewed here")
    if txn.get("type") == "deposit":
        raise HTTPException(status_code=409, detail="Deposits are verified and credited automatically by AlphaPay. Manual deposit review is disabled.")
    # Withdrawal approvals/rejections must start from PENDING only. PROCESSING
    # means a provider request may already be in flight; never issue another payout.
    if txn.get("status") != "pending":
        raise HTTPException(status_code=409, detail="Transaction is already processing or has been reviewed")

    user_id = txn.get("user_id")
    amount = txn.get("amount")
    if not user_id or not ObjectId.is_valid(user_id):
        raise HTTPException(status_code=400, detail="Transaction has an invalid user reference")
    if not isinstance(amount, (int, float)) or not math.isfinite(float(amount)) or float(amount) <= 0:
        raise HTTPException(status_code=400, detail="Transaction has an invalid amount")

    reason = reason.strip()[:500]
    if action == "reject" and not reason:
        raise HTTPException(status_code=400, detail="A rejection reason is required")
    reviewed_at = datetime.now(timezone.utc).isoformat()
    audit_entry = {"action": action, "reason": reason, "reviewed_at": reviewed_at, "reviewed_by": str(staff["_id"])}

    if txn.get("type") == "deposit":
        if action == "reject":
            result = await db.transactions.update_one(
                {"id": transaction_id, "status": "pending", "credited": False},
                {"$set": {"status": "rejected", "reviewed_at": reviewed_at, "reviewed_by": str(staff["_id"]), "review_reason": reason},
                 "$push": {"audit_history": audit_entry}},
            )
            if result.modified_count != 1:
                raise HTTPException(status_code=409, detail="Deposit was already reviewed")
            await db.audit_logs.insert_one({"type":"deposit","action":"rejected","deposit_id":transaction_id,"user_id":user_id,"amount":amount,"method":txn.get("method"),"reviewed_by":str(staff["_id"]),"reason":reason,"at":reviewed_at})
            return {"ok": True, "status": "rejected"}

        # Approval and wallet credit happen in one MongoDB transaction. The
        # pending+uncurated filter makes a second approval impossible.
        session = await client.start_session()
        try:
            async with session.start_transaction():
                fresh_txn = await db.transactions.find_one({"id": transaction_id, "status": "pending", "credited": False}, session=session)
                if not fresh_txn:
                    raise HTTPException(status_code=409, detail="Deposit was already reviewed or credited")
                target = await db.users.find_one({"_id": ObjectId(user_id)}, session=session)
                if not target:
                    raise HTTPException(status_code=404, detail="Deposit user not found")

                bonus_amount = 0.0
                settings = await get_settings()
                bonus_cap = round(float(settings.get("first_deposit_bonus_cap", FIRST_DEPOSIT_BONUS_CAP)), 2)
                bonus_filter = {"_id": target["_id"], "first_deposit_bonus_awarded": {"$ne": True}}
                bonus_amount = min(float(amount), bonus_cap)
                bonus_result = await db.users.update_one(
                    bonus_filter,
                    {"$inc": {"balance": float(amount) + bonus_amount, "total_deposited": float(amount)}, "$set": {"first_deposit_bonus_awarded": True}},
                    session=session,
                )
                first_bonus = bonus_result.modified_count == 1
                if not first_bonus:
                    bonus_amount = 0.0
                    await db.users.update_one({"_id": target["_id"]}, {"$inc": {"balance": float(amount), "total_deposited": float(amount)}}, session=session)

                result = await db.transactions.update_one(
                    {"id": transaction_id, "status": "pending", "credited": False},
                    {"$set": {"status": "approved", "credited": True, "reviewed_at": reviewed_at, "reviewed_by": str(staff["_id"]), "review_reason": reason, "first_deposit_bonus": first_bonus, "bonus_amount": round(bonus_amount,2)}, "$push": {"audit_history": audit_entry}},
                    session=session,
                )
                if result.modified_count != 1:
                    raise HTTPException(status_code=409, detail="Deposit was already reviewed")

                if first_bonus and bonus_amount > 0:
                    await db.transactions.insert_one({"id":str(uuid.uuid4()),"reference":f"NB-B-{uuid.uuid4().hex[:10].upper()}","user_id":user_id,"type":"first_deposit_bonus","amount":round(bonus_amount,2),"method":"promotion","status":"credited","deposit_reference":fresh_txn["reference"],"created_at":reviewed_at,"promotion":"100% first deposit bonus up to GHS 100"}, session=session)

                referrer_id = target.get("referred_by")
                if referrer_id and ObjectId.is_valid(referrer_id):
                    referrer = await db.users.find_one({"_id": ObjectId(referrer_id), "role": "sub_admin"}, session=session)
                    if referrer:
                        commission = round(float(amount) * REFERRAL_COMMISSION_RATE, 2)
                        await db.users.update_one({"_id": referrer["_id"]}, {"$inc": {"commission_total": commission}}, session=session)
                        await db.transactions.insert_one({"id":str(uuid.uuid4()),"reference":f"NB-C-{uuid.uuid4().hex[:10].upper()}","user_id":str(referrer["_id"]),"type":"referral_commission","amount":commission,"deposit_amount":float(amount),"referred_user_id":user_id,"method":"referral","status":"earned","commission_rate":REFERRAL_COMMISSION_RATE,"created_at":reviewed_at,"deposit_reference":fresh_txn["reference"]}, session=session)

                await db.audit_logs.insert_one({"type":"deposit","action":"approved","deposit_id":transaction_id,"user_id":user_id,"amount":float(amount),"method":fresh_txn.get("method"),"reviewed_by":str(staff["_id"]),"reviewed_at":reviewed_at,"bonus_amount":round(bonus_amount,2),"at":reviewed_at}, session=session)
        finally:
            await session.end_session()
        return {"ok": True, "status": "approved", "credited_amount": round(float(amount) + bonus_amount, 2), "bonus_amount": round(bonus_amount, 2)}

    # Withdrawal review flow: claim PENDING -> PROCESSING atomically before
    # contacting AlphaPay. A second admin click cannot pass this compare-and-set.
    if action == "approve":
        idempotency_key = str(uuid.uuid5(uuid.NAMESPACE_URL, f"nexusbet:alphapay:payout:{transaction_id}"))
        # Validate local payout details before claiming the transaction, so a
        # malformed phone/network does not leave a withdrawal stuck PROCESSING.
        phone_raw = str(txn.get("phone_number") or txn.get("destination") or "").strip()
        phone_digits = re.sub(r"\D", "", phone_raw)
        if phone_digits.startswith("0") and len(phone_digits) == 10:
            phone_digits = "233" + phone_digits[1:]
        if not (phone_digits.startswith("233") and len(phone_digits) == 12):
            raise HTTPException(status_code=400, detail="Withdrawal has an invalid Ghana mobile number; payout was not sent")
        network = ALPHAPAY_NETWORKS.get(str(txn.get("method") or "mtn").lower())
        if not network:
            raise HTTPException(status_code=400, detail="Unsupported AlphaPay payout network; payout was not sent")
        claimed = await db.transactions.find_one_and_update(
            {"id": transaction_id, "type": "withdrawal", "status": "pending"},
            {"$set": {"status": "processing", "payout_status": "initiating",
                      "payout_idempotency_key": idempotency_key, "reviewed_at": reviewed_at,
                      "reviewed_by": str(staff["_id"]), "review_reason": reason},
             "$push": {"audit_history": audit_entry}},
            return_document=ReturnDocument.AFTER,
        )
        if not claimed:
            raise HTTPException(status_code=409, detail="Withdrawal is already processing or has been reviewed")

        payout_phone = "+" + phone_digits
        payout_user = await db.users.find_one({"_id": ObjectId(user_id)})
        full_name = str((payout_user or {}).get("name") or (payout_user or {}).get("full_name") or "NexusBet customer").strip()
        name_parts = full_name.split()
        payout_payload = {
            "amount": f"{float(amount):.2f}",
            "currency": "GHS",
            "country": "GH",
            "method": network,
            # Match AlphaPay's customer object shape already used by NexusBet's
            # AlphaPay mobile-money deposit integration.
            "customer": {
                "phone": payout_phone,
                "first_name": name_parts[0] if name_parts else "NexusBet",
                "last_name": " ".join(name_parts[1:]) if len(name_parts) > 1 else "Customer",
                "email": (payout_user or {}).get("email"),
            },
        }
        # Do not release funds on timeout/unknown response: AlphaPay may have
        # accepted the payout. Reconcile using the status endpoint and same key.
        try:
            provider_result = await trigger_alphapay_payout(payout_payload, idempotency_key)
        except HTTPException as exc:
            await db.transactions.update_one(
                {"id": transaction_id, "status": "processing"},
                {"$set": {"payout_status": "unknown", "payout_error": str(exc.detail),
                          "payout_idempotency_key": idempotency_key}},
            )
            raise HTTPException(status_code=502, detail="AlphaPay payout outcome is not confirmed. The withdrawal remains processing; check payout status before retrying.") from exc

        result = await _apply_alphapay_payout_status(claimed, provider_result, str(staff["_id"]))
        await db.audit_logs.insert_one({
            "type": "withdrawal", "action": "alphapay_payout_initialized",
            "transaction_id": transaction_id, "user_id": user_id, "amount": float(amount),
            "reviewed_by": str(staff["_id"]), "payout_id": result.get("payout_id"),
            "payout_status": result.get("payout_status"), "at": datetime.now(timezone.utc).isoformat(),
        })
        return {"ok": True, **result, "message": "AlphaPay payout request submitted; final status may require confirmation."}

    result = await db.transactions.update_one(
        {"id": transaction_id, "type": "withdrawal", "status": "pending"},
        {"$set": {"status": "rejected", "reviewed_at": reviewed_at, "reviewed_by": str(staff["_id"]), "review_reason": reason}, "$push": {"audit_history": audit_entry}},
    )
    if result.modified_count != 1:
        raise HTTPException(status_code=409, detail="Transaction was already reviewed")
    # Withdrawal amounts are deducted at request time; return them once on rejection.
    await db.users.update_one({"_id": ObjectId(user_id)}, {"$inc": {"balance": float(amount)}})
    return {"ok": True, "status": "rejected"}


@router.get("/admin/transactions/{transaction_id}/payout-status")
async def refresh_alphapay_payout_status(transaction_id: str, staff: dict = Depends(require_admin)):
    txn = await db.transactions.find_one({"id": transaction_id, "type": "withdrawal"})
    if not txn:
        raise HTTPException(status_code=404, detail="Withdrawal transaction not found")
    if txn.get("status") in ("paid", "failed", "rejected"):
        return {"ok": True, "status": txn.get("status"), "payout_status": txn.get("payout_status"),
                "payout_id": txn.get("payout_id"), "message": "Withdrawal already has a final status."}
    payout_id = txn.get("payout_id")
    if not payout_id:
        raise HTTPException(status_code=409, detail="AlphaPay has not returned a payout ID yet. Keep this withdrawal processing and contact AlphaPay if the request timed out.")
    provider_result = await get_alphapay_payout_status(payout_id)
    result = await _apply_alphapay_payout_status(txn, provider_result, str(staff["_id"]))
    return {"ok": True, **result}


@router.get("/admin/users")
async def list_users(admin: dict = Depends(require_permission("users.view"))):
    docs = await db.users.find().sort("created_at", -1).to_list(500)
    referrer_ids = [d.get("referred_by") for d in docs if d.get("referred_by") and ObjectId.is_valid(str(d.get("referred_by")))]
    referrers = {}
    if referrer_ids:
        async for ref in db.users.find({"_id": {"$in": [ObjectId(x) for x in set(referrer_ids)]}}):
            referrers[str(ref["_id"])] = {"code": ref.get("referral_code", ""), "name": ref.get("name", ""), "role": ref.get("role", "")}
    return [
        {"id": str(d["_id"]), "email": d["email"], "name": d.get("name", ""),
         "role": d.get("role", "user"), "permissions": d.get("permissions", []), "balance": round(d.get("balance", 0.0), 2),
         "referral_code": d.get("referral_code", ""), "referral_used": referrers.get(str(d.get("referred_by")), {}).get("code", d.get("referral_code_used", d.get("referral_used", ""))),
         "referrer_name": referrers.get(str(d.get("referred_by")), {}).get("name", ""),
         "commission_total": round(d.get("commission_total", 0.0), 2),
         "phone": d.get("phone", ""), "created_at": d.get("created_at") }
        for d in docs
    ]


@router.delete("/admin/users/{user_id}")
async def delete_global_user(user_id: str, admin: dict = Depends(require_permission("users.manage"))):
    if not ObjectId.is_valid(user_id):
        raise HTTPException(status_code=400, detail="Invalid user id")
    target = await db.users.find_one({"_id": ObjectId(user_id)})
    if not target:
        raise HTTPException(status_code=404, detail="User not found")
    if str(target["_id"]) == str(admin["_id"]):
        raise HTTPException(status_code=400, detail="You cannot delete your own account here")
    if target.get("role") in {"super_admin", "admin", "sub_admin"}:
        raise HTTPException(status_code=403, detail="Global User Profiles can only delete regular user accounts; use Staff & Access Control for staff.")
    await db.users.delete_one({"_id": target["_id"]})
    return {"ok": True}


@router.put("/admin/users/{user_id}/role")
async def set_user_role(user_id: str, body: RoleInput, admin: dict = Depends(require_permission("users.manage"))):
    if body.role not in ("user", "sub_admin", "admin"):
        raise HTTPException(status_code=400, detail="Invalid role")
    if not ObjectId.is_valid(user_id):
        raise HTTPException(status_code=400, detail="Invalid user id")
    target = await db.users.find_one({"_id": ObjectId(user_id)})
    if not target:
        raise HTTPException(status_code=404, detail="User not found")
    if target.get("role") == "super_admin":
        raise HTTPException(status_code=403, detail="Super Admin accounts cannot be modified")
    if admin.get("role") == "admin" and target.get("role") == "admin":
        raise HTTPException(status_code=403, detail="Admins cannot modify or demote Admin accounts")
    if admin.get("role") == "admin" and body.role == "admin":
        raise HTTPException(status_code=403, detail="Only Super Admins can create or promote Admin accounts")
    updates = {"role": body.role}
    if body.role in ("admin", "sub_admin") and not target.get("referral_code"):
        updates["referral_code"] = await unique_code(db.users, "referral_code", 8)
    updates["permissions"] = [] if body.role == "sub_admin" else ALL_SUBADMIN_PERMISSIONS
    await db.users.update_one({"_id": target["_id"]}, {"$set": updates})
    return {"ok": True, "role": body.role, "permissions": updates["permissions"], "referral_code": updates.get("referral_code", target.get("referral_code", ""))}


@router.get("/admin/reports/summary")
async def reports_summary(staff: dict = Depends(require_permission("reports.view"))):
    pending = await db.transactions.count_documents({"status": "pending"})
    approved_deposits = await db.transactions.aggregate([
        {"$match": {"type": "deposit", "status": "approved"}},
        {"$group": {"_id": None, "total": {"$sum": "$amount"}, "count": {"$sum": 1}}},
    ]).to_list(1)
    withdrawals = await db.transactions.aggregate([
        {"$match": {"type": "withdrawal", "status": "paid"}},
        {"$group": {"_id": None, "total": {"$sum": "$amount"}, "count": {"$sum": 1}}},
    ]).to_list(1)
    return {
        "pending_transactions": pending,
        "approved_deposits": {"count": approved_deposits[0]["count"] if approved_deposits else 0, "total": round(approved_deposits[0]["total"] if approved_deposits else 0, 2)},
        "paid_withdrawals": {"count": withdrawals[0]["count"] if withdrawals else 0, "total": round(withdrawals[0]["total"] if withdrawals else 0, 2)},
        "users": await db.users.count_documents({}),
        "events": await db.events.count_documents({}),
    }

@router.get("/admin/promotions")
async def read_promotions(admin: dict = Depends(require_permission("promotions.manage"))):
    doc = await db.settings.find_one({"_id": "promotions"}) or {}
    return {"enabled": bool(doc.get("enabled", False)), "message": doc.get("message", "")[:200]}

@router.put("/admin/promotions")
async def update_promotions(enabled: bool, message: str = "", admin: dict = Depends(require_permission("promotions.manage"))):
    message = message.strip()[:200]
    await db.settings.update_one({"_id": "promotions"}, {"$set": {"enabled": enabled, "message": message}}, upsert=True)
    return {"enabled": enabled, "message": message}

# ------------------------------------------------------------------ sports events
def live_event_minute(doc: dict) -> int:
    """Return the real-time minute for admin-controlled live matches.

    A match runs at real time: one minute of match time equals one real minute,
    from 0 through 94. Admin controls start the clock; finishing the match
    freezes it at 94.
    """
    status = doc.get("status")
    if status == "finished":
        return min(94, max(0, int(doc.get("minute", 94) or 0)))
    if status != "live" or not doc.get("clock_started_at"):
        return min(94, max(0, int(doc.get("minute", 0) or 0)))
    try:
        started = datetime.fromisoformat(str(doc["clock_started_at"]))
        elapsed = max(0, int((datetime.now(timezone.utc) - started).total_seconds() // 60))
    except (TypeError, ValueError):
        elapsed = 0
    # Start Live displays minute 1 immediately. The clock then advances once
    # per real minute and remains within 1–94. The elapsed timer itself is still
    # a full 94 real minutes, so a match is never accelerated.
    base = min(94, max(1, int(doc.get("clock_base_minute", 1) or 1)))
    return min(94, base + elapsed)


def validate_uploaded_crest(value: Optional[str]) -> Optional[str]:
    """Validate and retain small image data URLs in MongoDB (Render disk is ephemeral)."""
    if value in (None, ""):
        return None
    match = re.fullmatch(r"data:(image/png|image/jpeg|image/webp);base64,([A-Za-z0-9+/]+={0,2})", value)
    if not match:
        raise HTTPException(status_code=400, detail="Team crest must be a PNG, JPG or WEBP image.")
    try:
        raw = base64.b64decode(match.group(2), validate=True)
    except Exception:
        raise HTTPException(status_code=400, detail="The uploaded team crest is not a valid image.")
    if not raw or len(raw) > 2 * 1024 * 1024:
        raise HTTPException(status_code=413, detail="Each team crest must be 2MB or smaller.")
    mime = match.group(1)
    valid_signature = (
        (mime == "image/png" and raw.startswith(b"\x89PNG\r\n\x1a\n")) or
        (mime == "image/jpeg" and raw.startswith(b"\xff\xd8\xff")) or
        (mime == "image/webp" and len(raw) >= 12 and raw[:4] == b"RIFF" and raw[8:12] == b"WEBP")
    )
    if not valid_signature:
        raise HTTPException(status_code=400, detail="The file content does not match its image type.")
    return value


def event_crest_url(event_id: str, side: str) -> str:
    return f"/events/{event_id}/crest/{side}"


async def save_event_crest(event_id: str, side: str, data_url: Optional[str]) -> None:
    key = f"{event_id}:{side}"
    if not data_url:
        await db.event_crests.delete_one({"_id": key})
        return
    header, encoded = data_url.split(",", 1)
    mime = header[5:].split(";", 1)[0]
    raw = base64.b64decode(encoded, validate=True)
    await db.event_crests.update_one(
        {"_id": key},
        {"$set": {"content_type": mime, "data": raw, "updated_at": datetime.now(timezone.utc).isoformat()}},
        upsert=True,
    )


def event_public(doc: dict) -> dict:
    minute = live_event_minute(doc)
    return {
        "id": doc["id"],
        "sport": doc["sport"],
        "league": doc["league"],
        "home": doc["home"],
        "away": doc["away"],
        "odds": {
            "home": round(doc["odds_home"], 2),
            "draw": round(doc["odds_draw"], 2) if doc.get("odds_draw") is not None else None,
            "away": round(doc["odds_away"], 2),
        },
        "status": doc["status"],
        "phase": "halftime" if doc.get("status") == "halftime" else ("live" if doc.get("status") == "live" else ("paused" if doc.get("status") == "paused" else ("finished" if doc.get("status") == "finished" else "scheduled"))),
        "minute": minute,
        "score": {"home": int(doc.get("home_score", 0) or 0), "away": int(doc.get("away_score", 0) or 0)},
        "halftime_score": {"home": doc.get("halftime_home_score"), "away": doc.get("halftime_away_score")},
        "result": doc.get("result"),
        "booking_code": doc.get("booking_code") or f"NBM-{doc['id'][:8].upper()}",
        "kickoff_at": doc.get("kickoff_at"),
        "created_at": doc.get("created_at"),
        "home_logo_url": doc.get("home_logo_url"),
        "away_logo_url": doc.get("away_logo_url"),
    }

async def hydrate_event_team_assets(doc: dict) -> dict:
    if not doc.get("sport") or str(doc.get("sport")).lower() == "virtual football":
        return doc
    home = await team_asset(doc.get("home", ""), doc.get("league"))
    away = await team_asset(doc.get("away", ""), doc.get("league"))
    # Uploaded event-specific crests always take precedence over catalogue logos.
    updates = {"home_logo_url": doc.get("home_logo_url") or home.get("logo_url"), "away_logo_url": doc.get("away_logo_url") or away.get("logo_url"), "home_team_id": home.get("team_id"), "away_team_id": away.get("team_id")}
    if any(v is not None for v in updates.values()):
        await db.events.update_one({"_id": doc["_id"]}, {"$set": updates})
        doc.update(updates)
    return doc

@router.get("/leagues")
async def list_leagues():
    rows=[]
    for slug, league in LEAGUE_CATALOG.items():
        teams = await db.teams.find({"league_slug": slug, "season": league["season"]}).sort("name", 1).to_list(30)
        if not teams:
            teams=[{"name":name, "logo_url":None, "provider_team_id":None} for name in league["teams"]]
        rows.append({"slug":slug,"name":league["name"],"country":league["country"],"season":league["season"],"team_count":len(league["teams"]),"teams":[{"name":t.get("name"),"logo_url":t.get("logo_url"),"team_id":t.get("provider_team_id")} for t in teams]})
    return rows

@router.get("/leagues/{slug}")
async def league_detail(slug: str):
    league=LEAGUE_CATALOG.get(slug)
    if not league:
        raise HTTPException(status_code=404, detail="League not found")
    teams=await db.teams.find({"league_slug":slug,"season":league["season"]}).sort("name",1).to_list(30)
    if not teams:
        teams=[{"name":name,"logo_url":None,"provider_team_id":None} for name in league["teams"]]
    return {"slug":slug,"name":league["name"],"country":league["country"],"season":league["season"],"team_count":len(league["teams"]),"teams":[{"name":t.get("name"),"logo_url":t.get("logo_url"),"team_id":t.get("provider_team_id")} for t in teams]}

@router.get("/events/{event_id}/crest/{side}")
async def get_event_crest(event_id: str, side: str):
    if side not in {"home", "away"}:
        raise HTTPException(status_code=404, detail="Team crest not found")
    crest = await db.event_crests.find_one({"_id": f"{event_id}:{side}"})
    if not crest:
        raise HTTPException(status_code=404, detail="Team crest not found")
    return Response(
        content=bytes(crest["data"]),
        media_type=crest.get("content_type", "application/octet-stream"),
        headers={"Cache-Control": "public, max-age=3600"},
    )


@router.get("/events")
async def list_events(sport: Optional[str] = None, q: Optional[str] = None,
                      status: Optional[str] = "open", limit: int = 40, skip: int = 0):
    query = {}
    if status in ("open", "live", "paused", "finished", "cancelled"):
        query["status"] = status
    elif status == "all":
        query["status"] = {"$in": ["open", "live", "paused", "finished", "cancelled"]}
    if sport and sport != "all":
        query["sport"] = sport
    if q:
        query["$or"] = [
            {"home": {"$regex": q, "$options": "i"}},
            {"away": {"$regex": q, "$options": "i"}},
            {"league": {"$regex": q, "$options": "i"}},
        ]
    limit = max(1, min(limit, 120))
    docs = await db.events.find(query).sort("created_at", -1).skip(max(0, skip)).limit(limit).to_list(limit)
    docs = await asyncio.gather(*(hydrate_event_team_assets(d) for d in docs))
    return [event_public(d) for d in docs]

@router.get("/events/meta")
async def events_meta():
    pipeline = [
        {"$match": {"status": "open"}},
        {"$group": {"_id": "$sport", "count": {"$sum": 1}}},
        {"$sort": {"count": -1}},
    ]
    rows = await db.events.aggregate(pipeline).to_list(50)
    sports = [{"sport": r["_id"], "count": r["count"]} for r in rows if r["_id"]]
    return {"sports": sports, "total": sum(s["count"] for s in sports)}


@router.post("/admin/events")
async def create_event(body: EventInput, staff: dict = Depends(require_permission("events.manage"))):
    uuid_event_id = uuid.uuid4()
    home_crest = validate_uploaded_crest(body.home_logo_url)
    away_crest = validate_uploaded_crest(body.away_logo_url)
    doc = {
        "id": str(uuid_event_id),
        "sport": body.sport,
        "league": body.league,
        "home": body.home,
        "away": body.away,
        "home_logo_url": event_crest_url(str(uuid_event_id), "home") if home_crest else None,
        "away_logo_url": event_crest_url(str(uuid_event_id), "away") if away_crest else None,
        "odds_home": body.odds_home,
        "odds_draw": body.odds_draw if body.sport.strip().lower() not in {"basketball", "tennis"} else None,
        "odds_away": body.odds_away,
        "status": "open",
        "minute": 0,
        "home_score": 0,
        "away_score": 0,
        "halftime_home_score": None,
        "halftime_away_score": None,
        "result": None,
        "booking_code": f"NBM-{uuid.uuid4().hex[:8].upper()}",
        "kickoff_at": body.kickoff_at.isoformat() if body.kickoff_at else None,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    await db.events.insert_one(doc)
    if home_crest:
        await save_event_crest(doc["id"], "home", home_crest)
    if away_crest:
        await save_event_crest(doc["id"], "away", away_crest)
    doc = await hydrate_event_team_assets(doc)
    return event_public(doc)


@router.put("/admin/events/{event_id}")
async def update_event(event_id: str, body: EventInput, staff: dict = Depends(require_permission("events.manage"))):
    values = {
        "sport": body.sport.strip(), "league": body.league.strip(),
        "home": body.home.strip(), "away": body.away.strip(),
        "odds_home": round(body.odds_home, 2),
        "odds_draw": round(body.odds_draw, 2) if body.odds_draw is not None and body.sport.strip().lower() not in {"basketball", "tennis"} else None,
        "odds_away": round(body.odds_away, 2),
        "kickoff_at": body.kickoff_at.isoformat() if body.kickoff_at else None,
    }
    if "home_logo_url" in body.model_fields_set:
        home_crest = validate_uploaded_crest(body.home_logo_url)
        await save_event_crest(event_id, "home", home_crest)
        values["home_logo_url"] = event_crest_url(event_id, "home") if home_crest else None
    if "away_logo_url" in body.model_fields_set:
        away_crest = validate_uploaded_crest(body.away_logo_url)
        await save_event_crest(event_id, "away", away_crest)
        values["away_logo_url"] = event_crest_url(event_id, "away") if away_crest else None
    if not all(values[k] for k in ("sport", "league", "home", "away")):
        raise HTTPException(status_code=400, detail="Sport, league and team names are required")
    result = await db.events.update_one({"id": event_id}, {"$set": values})
    if result.matched_count != 1:
        raise HTTPException(status_code=404, detail="Event not found")
    doc = await db.events.find_one({"id": event_id})
    doc = await hydrate_event_team_assets(doc)
    return event_public(doc)


@router.delete("/admin/events/{event_id}")
async def delete_event(event_id: str, staff: dict = Depends(require_permission("events.manage"))):
    await db.events.delete_one({"id": event_id})
    await db.event_crests.delete_many({"_id": {"$in": [f"{event_id}:home", f"{event_id}:away"]}})
    return {"ok": True}


@router.get("/admin/permissions")
async def available_permissions(admin: dict = Depends(require_admin)):
    return {"permissions": ALL_SUBADMIN_PERMISSIONS, "groups": ROLE_PERMISSIONS}


@router.put("/admin/users/{user_id}/permissions")
async def set_user_permissions(user_id: str, body: PermissionsInput, admin: dict = Depends(require_admin)):
    if not ObjectId.is_valid(user_id):
        raise HTTPException(status_code=400, detail="Invalid user id")
    target = await db.users.find_one({"_id": ObjectId(user_id)})
    if not target:
        raise HTTPException(status_code=404, detail="User not found")
    if target.get("role") != "sub_admin":
        raise HTTPException(status_code=400, detail="Permissions can only be assigned to sub-admins")
    permissions = sorted(set(body.permissions))
    invalid = [p for p in permissions if p not in ALL_SUBADMIN_PERMISSIONS]
    if invalid:
        raise HTTPException(status_code=400, detail={"invalid_permissions": invalid})
    await db.users.update_one({"_id": ObjectId(user_id)}, {"$set": {"permissions": permissions}})
    return {"ok": True, "permissions": permissions}


# ------------------------------------------------------------------ startup and demo data
async def seed_admin():
    admin_email = os.environ["ADMIN_EMAIL"].lower()
    admin_password = os.environ["ADMIN_PASSWORD"]
    existing = await db.users.find_one({"email": admin_email})
    if existing is None:
        referral_code = await unique_code(db.users, "referral_code", 8)
        await db.users.insert_one({
            "email": admin_email,
            "password_hash": hash_password(admin_password),
            "name": "Super Admin",
            "role": "super_admin",
            "balance": STAFF_STARTING_DEMO_BALANCE,
            "total_deposited": 0.0,
            "commission_total": 0.0,
            "referral_code": referral_code,
            "permissions": ALL_SUBADMIN_PERMISSIONS,
            "created_at": datetime.now(timezone.utc).isoformat(),
        })
    else:
        updates = {"role": "super_admin" if existing.get("role") == "admin" else existing.get("role", "super_admin")}
        if not existing.get("referral_code"):
            updates["referral_code"] = await unique_code(db.users, "referral_code", 8)
        updates["commission_total"] = existing.get("commission_total", 0.0)
        if not verify_password(admin_password, existing["password_hash"]):
            updates["password_hash"] = hash_password(admin_password)
        await db.users.update_one({"email": admin_email}, {"$set": updates})


async def normalize_legacy_football_events():
    # Replace the fake football team names shipped by earlier builds while
    # preserving event IDs so existing tickets continue to resolve.
    replacements = {
        "Cyber City FC": "Arsenal", "Neon United": "Manchester United",
        "Real Volt": "FC Barcelona", "Atletico Pulse": "Real Madrid",
        "Inter Circuit": "Inter", "AC Matrix": "AC Milan",
    }
    for old, new in replacements.items():
        await db.events.update_many({"home": old}, {"$set": {"home": new}})
        await db.events.update_many({"away": old}, {"$set": {"away": new}})


async def seed_events():
    if await db.events.count_documents({}) > 0:
        return
    samples = [
        ("Football", "Premier League", "Arsenal", "Manchester United", 2.10, 3.40, 3.25),
        ("Football", "LaLiga", "FC Barcelona", "Real Madrid", 1.85, 3.60, 4.10),
        ("Basketball", "NBA Nexus", "Los Angeles Lakers", "Chicago Bulls", 1.65, 12.0, 2.30),
        ("Tennis", "Grand Circuit", "A. Volkov", "M. Reyes", 1.55, 15.0, 2.55),
        ("eSports", "Valorant Masters", "Team Flux", "Team Cipher", 1.95, 20.0, 1.90),
        ("Football", "Serie A", "Inter", "AC Milan", 2.40, 3.20, 2.95),
    ]
    for sport, league, home, away, oh, od, oa in samples:
        await db.events.insert_one({
            "id": str(uuid.uuid4()),
            "sport": sport, "league": league, "home": home, "away": away,
            "odds_home": oh, "odds_draw": od, "odds_away": oa,
            "status": "open", "result": None,
            "created_at": datetime.now(timezone.utc).isoformat(),
        })





@router.get("/")
async def root():
    return {"message": "NexusBet API"}





