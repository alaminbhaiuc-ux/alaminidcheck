# -*- coding: utf-8 -*-
import os
import sys
import asyncio
import logging
import random
import string
from datetime import datetime, timedelta
from flask import Flask
from threading import Thread
from telethon import TelegramClient, events, Button
from telethon.sessions import StringSession
import requests
import re

# Configure encoding
if sys.stdout.encoding != 'utf-8':
    sys.stdout.reconfigure(encoding='utf-8')

# Logging setup
logging.basicConfig(
    format='[%(levelname) 5s/%(asctime)s] %(name)s: %(message)s',
    level=logging.INFO
)

# Get environment variables
API_ID = int(os.environ.get("API_ID", "0"))
API_HASH = os.environ.get("API_HASH", "")
SESSION_STRING = os.environ.get("SESSION_STRING", "")

# New environment variables for authorization and chat IDs
AUTHORIZED_USERS = os.environ.get("AUTHORIZED_USERS", "")  # Comma-separated user IDs
AUTHORIZED_GROUPS = os.environ.get("AUTHORIZED_GROUPS", "")  # Comma-separated group chat IDs

# Parse authorized users
authorized_user_ids = []
if AUTHORIZED_USERS:
    try:
        authorized_user_ids = [int(uid.strip()) for uid in AUTHORIZED_USERS.split(",") if uid.strip()]
    except:
        logging.warning("Error parsing AUTHORIZED_USERS")

# Parse authorized groups
authorized_group_ids = []
if AUTHORIZED_GROUPS:
    try:
        authorized_group_ids = [int(gid.strip()) for gid in AUTHORIZED_GROUPS.split(",") if gid.strip()]
    except:
        logging.warning("Error parsing AUTHORIZED_GROUPS")

# Validate environment variables
if not API_ID or API_ID == 0:
    logging.error("API_ID is not set! Please set it in environment variables.")
    sys.exit(1)

if not API_HASH:
    logging.error("API_HASH is not set! Please set it in environment variables.")
    sys.exit(1)

if not SESSION_STRING:
    logging.error("SESSION_STRING is not set! Please set it in environment variables.")
    sys.exit(1)

# Initialize Telethon with StringSession
client = TelegramClient(StringSession(SESSION_STRING), API_ID, API_HASH)

# Global variable to cache owner ID (FIX #1)
OWNER_ID = None

# Flask app
app = Flask(__name__)

@app.route('/')
def home():
    return "Free Fire Userbot is running!"

@app.route('/health')
def health():
    return {"status": "alive", "bot": "running"}

def run_flask():
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port, debug=False, use_reloader=False)

def unix_to_date(timestamp):
    try:
        timestamp = int(timestamp)
        return datetime.fromtimestamp(timestamp).strftime('%d %B %Y, %I:%M %p')
    except:
        return str(timestamp)

def format_number(num):
    try:
        return "{:,}".format(int(num))
    except:
        return str(num)

def format_time(seconds):
    """Convert seconds to readable time format"""
    try:
        seconds = int(seconds)
        hours = seconds // 3600
        minutes = (seconds % 3600) // 60
        secs = seconds % 60
        if hours > 0:
            return "{}h {}m {}s".format(hours, minutes, secs)
        elif minutes > 0:
            return "{}m {}s".format(minutes, secs)
        else:
            return "{}s".format(secs)
    except:
        return str(seconds)

def format_distance(meters):
    """Convert meters to readable distance format"""
    try:
        meters = int(meters)
        if meters >= 1000:
            km = meters / 1000
            return "{:.2f} km".format(km)
        else:
            return "{} m".format(meters)
    except:
        return str(meters)

def get_rank_tier(rank):
    if rank <= 100:
        return "Heroic"
    elif rank <= 500:
        return "Diamond"
    elif rank <= 1000:
        return "Platinum"
    elif rank <= 2000:
        return "Gold"
    else:
        return "Silver/Bronze"

def fetch_player_data(uid, server="bd"):
    try:
        url = "https://freefire-api-hkqw.onrender.com/get_player_personal_show?server={}&uid={}".format(server, uid)
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        logging.error("API Error: {}".format(e))
        return None

def fetch_player_stats(uid, matchmode="CAREER", gamemode="br", server="bd"):
    """Fetch player stats from API"""
    try:
        url = "https://freefire-api-hkqw.onrender.com/get_player_stats?server={}&uid={}&matchmode={}&gamemode={}".format(
            server, uid, matchmode.upper(), gamemode.lower()
        )
        response = requests.get(url, timeout=15)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        logging.error("Stats API Error: {}".format(e))
        return None

def calculate_kd(kills, deaths):
    """Calculate K/D ratio"""
    try:
        kills = int(kills)
        deaths = int(deaths)
        if deaths == 0:
            return "{:.2f}".format(float(kills))
        return "{:.2f}".format(kills / deaths)
    except:
        return "N/A"

def calculate_winrate(wins, games):
    """Calculate win rate percentage"""
    try:
        wins = int(wins)
        games = int(games)
        if games == 0:
            return "0.00%"
        return "{:.2f}%".format((wins / games) * 100)
    except:
        return "N/A"

def calculate_headshot_rate(headshot_kills, kills):
    """Calculate headshot rate percentage"""
    try:
        headshot_kills = int(headshot_kills)
        kills = int(kills)
        if kills == 0:
            return "0.00%"
        return "{:.2f}%".format((headshot_kills / kills) * 100)
    except:
        return "N/A"

# ================ SAFE CALCULATOR FUNCTION ================

def safe_calculate(expression):
    """
    Safely evaluate mathematical expressions.
    Only allows numbers and basic math operators.
    """
    # Remove all spaces
    expression = expression.replace(" ", "")
    
    # Check for empty expression
    if not expression:
        raise ValueError("Empty expression")
    
    # Security: Only allow numbers, operators, parentheses, and decimal points
    allowed_pattern = r'^[\d+\-*/().%\s]+$'
    if not re.match(allowed_pattern, expression):
        raise ValueError("Invalid characters in expression")
    
    # Check for dangerous patterns (like multiple operators)
    dangerous_patterns = [
        r'[+\-*/]{2,}',  # Multiple operators in a row (except for negative numbers)
        r'^\*',           # Starting with *
        r'^\/',           # Starting with /
        r'\($',           # Ending with (
        r'^\)',           # Starting with )
    ]
    
    # Allow negative numbers at start or after operators
    clean_expr = expression.replace('(-', '(0-').replace('--', '+')
    if clean_expr.startswith('-'):
        clean_expr = '0' + clean_expr
    
    # Evaluate using Python's eval with restricted globals
    try:
        # Only allow safe math operations
        result = eval(clean_expr, {"__builtins__": {}}, {})
        return result
    except Exception as e:
        raise ValueError("Invalid expression: {}".format(str(e)))

def format_calc_result(result):
    """Format calculation result nicely"""
    if isinstance(result, float):
        # If it's a whole number stored as float, show as integer
        if result.is_integer():
            return "{:,}".format(int(result))
        else:
            # Round to 6 decimal places and format
            rounded = round(result, 6)
            return "{:,.6f}".format(rounded).rstrip('0').rstrip('.')
    elif isinstance(result, int):
        return "{:,}".format(result)
    else:
        return str(result)

# ================ EXISTING FORMAT FUNCTIONS ================

def format_br_stats(data, matchmode, uid):
    """Format Battle Royale stats beautifully"""
    try:
        stats_data = data.get("data", {})
        metadata = data.get("metadata", {})
        
        solo = stats_data.get("solostats", {})
        duo = stats_data.get("duostats", {})
        quad = stats_data.get("quadstats", {})
        
        lines = []
        lines.append("```")
        lines.append("🎮 FREE FIRE BATTLE ROYALE STATS")
        lines.append("═════════════════════════════════════")
        lines.append("")
        lines.append("🆔 Player ID: {}".format(uid))
        lines.append("📊 Match Mode: {}".format(matchmode.upper()))
        lines.append("🎯 Game Mode: Battle Royale")
        lines.append("🌍 Server: {}".format(metadata.get("server", "BD").upper()))
        lines.append("")
        
        # ═══════════════ SOLO STATS ═══════════════
        lines.append("👤 SOLO STATISTICS")
        lines.append("─────────────────────────────────────")
        solo_detailed = solo.get("detailedstats", {})
        if solo.get("gamesplayed") or solo.get("kills") or solo.get("wins"):
            games = solo.get("gamesplayed", 0)
            kills = solo.get("kills", 0)
            wins = solo.get("wins", 0)
            deaths = solo_detailed.get("deaths", 0)
            hs_kills = solo_detailed.get("headshotkills", 0)
            
            lines.append("🎮 Games Played: {}".format(format_number(games)))
            lines.append("🏆 Wins: {} ({})".format(format_number(wins), calculate_winrate(wins, games)))
            lines.append("💀 Kills: {}".format(format_number(kills)))
            lines.append("☠️ Deaths: {}".format(format_number(deaths)))
            lines.append("📈 K/D Ratio: {}".format(calculate_kd(kills, deaths)))
            lines.append("🎯 Headshot Kills: {} ({})".format(format_number(hs_kills), calculate_headshot_rate(hs_kills, kills)))
            lines.append("💥 Damage: {}".format(format_number(solo_detailed.get("damage", 0))))
            lines.append("🔫 Highest Kills: {}".format(solo_detailed.get("highestkills", 0)))
            lines.append("⏱️ Survival Time: {}".format(format_time(solo_detailed.get("survivaltime", 0))))
            lines.append("🏃 Distance: {}".format(format_distance(solo_detailed.get("distancetravelled", 0))))
            lines.append("📦 Pickups: {}".format(format_number(solo_detailed.get("pickups", 0))))
            lines.append("🚗 Road Kills: {}".format(solo_detailed.get("roadkills", 0)))
            lines.append("🔝 Top 10 Finishes: {}".format(solo_detailed.get("topntimes", 0)))
        else:
            lines.append("❌ No solo stats available")
        lines.append("")
        
        # ═══════════════ DUO STATS ═══════════════
        lines.append("👥 DUO STATISTICS")
        lines.append("─────────────────────────────────────")
        duo_detailed = duo.get("detailedstats", {})
        if duo.get("gamesplayed") or duo.get("kills") or duo.get("wins"):
            games = duo.get("gamesplayed", 0)
            kills = duo.get("kills", 0)
            wins = duo.get("wins", 0)
            deaths = duo_detailed.get("deaths", 0)
            hs_kills = duo_detailed.get("headshotkills", 0)
            
            lines.append("🎮 Games Played: {}".format(format_number(games)))
            lines.append("🏆 Wins: {} ({})".format(format_number(wins), calculate_winrate(wins, games)))
            lines.append("💀 Kills: {}".format(format_number(kills)))
            lines.append("☠️ Deaths: {}".format(format_number(deaths)))
            lines.append("📈 K/D Ratio: {}".format(calculate_kd(kills, deaths)))
            lines.append("🎯 Headshot Kills: {} ({})".format(format_number(hs_kills), calculate_headshot_rate(hs_kills, kills)))
            lines.append("💥 Damage: {}".format(format_number(duo_detailed.get("damage", 0))))
            lines.append("🔫 Highest Kills: {}".format(duo_detailed.get("highestkills", 0)))
            lines.append("👊 Knockdowns: {}".format(format_number(duo_detailed.get("knockdown", 0))))
            lines.append("💉 Revives: {}".format(duo_detailed.get("revives", 0)))
            lines.append("⏱️ Survival Time: {}".format(format_time(duo_detailed.get("survivaltime", 0))))
            lines.append("🏃 Distance: {}".format(format_distance(duo_detailed.get("distancetravelled", 0))))
            lines.append("📦 Pickups: {}".format(format_number(duo_detailed.get("pickups", 0))))
            lines.append("🚗 Road Kills: {}".format(duo_detailed.get("roadkills", 0)))
            lines.append("🔝 Top 10 Finishes: {}".format(duo_detailed.get("topntimes", 0)))
        else:
            lines.append("❌ No duo stats available")
        lines.append("")
        
        # ═══════════════ SQUAD STATS ═══════════════
        lines.append("👨‍👩‍👧‍👦 SQUAD STATISTICS")
        lines.append("─────────────────────────────────────")
        quad_detailed = quad.get("detailedstats", {})
        if quad.get("gamesplayed") or quad.get("kills") or quad.get("wins"):
            games = quad.get("gamesplayed", 0)
            kills = quad.get("kills", 0)
            wins = quad.get("wins", 0)
            deaths = quad_detailed.get("deaths", 0)
            hs_kills = quad_detailed.get("headshotkills", 0)
            
            lines.append("🎮 Games Played: {}".format(format_number(games)))
            lines.append("🏆 Wins: {} ({})".format(format_number(wins), calculate_winrate(wins, games)))
            lines.append("💀 Kills: {}".format(format_number(kills)))
            lines.append("☠️ Deaths: {}".format(format_number(deaths)))
            lines.append("📈 K/D Ratio: {}".format(calculate_kd(kills, deaths)))
            lines.append("🎯 Headshot Kills: {} ({})".format(format_number(hs_kills), calculate_headshot_rate(hs_kills, kills)))
            lines.append("💥 Damage: {}".format(format_number(quad_detailed.get("damage", 0))))
            lines.append("🔫 Highest Kills: {}".format(quad_detailed.get("highestkills", 0)))
            lines.append("👊 Knockdowns: {}".format(format_number(quad_detailed.get("knockdown", 0))))
            lines.append("💉 Revives: {}".format(quad_detailed.get("revives", 0)))
            lines.append("⏱️ Survival Time: {}".format(format_time(quad_detailed.get("survivaltime", 0))))
            lines.append("🏃 Distance: {}".format(format_distance(quad_detailed.get("distancetravelled", 0))))
            lines.append("📦 Pickups: {}".format(format_number(quad_detailed.get("pickups", 0))))
            lines.append("🚗 Road Kills: {}".format(quad_detailed.get("roadkills", 0)))
            lines.append("🔝 Top 10 Finishes: {}".format(quad_detailed.get("topntimes", 0)))
        else:
            lines.append("❌ No squad stats available")
        
        lines.append("")
        lines.append("═════════════════════════════════════")
        lines.append("```")
        return "\n".join(lines)
        
    except Exception as e:
        logging.error("BR Stats Format Error: {}".format(e))
        return "```\n❌ Error formatting BR stats: {}\n```".format(str(e))

def format_cs_stats(data, matchmode, uid):
    """Format Clash Squad stats beautifully"""
    try:
        stats_data = data.get("data", {})
        metadata = data.get("metadata", {})
        
        cs = stats_data.get("csstats", {})
        cs_detailed = cs.get("detailedstats", {})
        
        lines = []
        lines.append("```")
        lines.append("⚔️ FREE FIRE CLASH SQUAD STATS")
        lines.append("═════════════════════════════════════")
        lines.append("")
        lines.append("🆔 Player ID: {}".format(uid))
        lines.append("📊 Match Mode: {}".format(matchmode.upper()))
        lines.append("🎯 Game Mode: Clash Squad")
        lines.append("🌍 Server: {}".format(metadata.get("server", "BD").upper()))
        lines.append("")
        
        if cs.get("gamesplayed") or cs.get("kills") or cs.get("wins"):
            games = cs.get("gamesplayed", 0)
            kills = cs.get("kills", 0)
            wins = cs.get("wins", 0)
            deaths = cs_detailed.get("deaths", 0)
            hs_kills = cs_detailed.get("headshotkills", 0)
            
            lines.append("📊 GENERAL STATISTICS")
            lines.append("─────────────────────────────────────")
            lines.append("🎮 Games Played: {}".format(format_number(games)))
            lines.append("🏆 Wins: {} ({})".format(format_number(wins), calculate_winrate(wins, games)))
            lines.append("💀 Kills: {}".format(format_number(kills)))
            lines.append("☠️ Deaths: {}".format(format_number(deaths)))
            lines.append("📈 K/D Ratio: {}".format(calculate_kd(kills, deaths)))
            lines.append("🎯 Headshot Kills: {} ({})".format(format_number(hs_kills), calculate_headshot_rate(hs_kills, kills)))
            lines.append("💥 Damage: {}".format(format_number(cs_detailed.get("damage", 0))))
            lines.append("👊 Knockdowns: {}".format(format_number(cs_detailed.get("knockdowns", 0))))
            lines.append("🤝 Assists: {}".format(format_number(cs_detailed.get("assists", 0))))
            lines.append("💉 Revivals: {}".format(format_number(cs_detailed.get("revivals", 0))))
            lines.append("⭐ MVP Count: {}".format(format_number(cs_detailed.get("mvpcount", 0))))
            lines.append("")
            
            lines.append("🔥 MULTI-KILL STATISTICS")
            lines.append("─────────────────────────────────────")
            lines.append("2️⃣ Double Kills: {}".format(format_number(cs_detailed.get("doublekills", 0))))
            lines.append("3️⃣ Triple Kills: {}".format(format_number(cs_detailed.get("triplekills", 0))))
            lines.append("4️⃣ Quadra Kills: {}".format(format_number(cs_detailed.get("fourkills", 0))))
            
            # Additional stats for ranked mode
            if matchmode.upper() == "RANKED":
                lines.append("")
                lines.append("🏅 RANKED STATISTICS")
                lines.append("─────────────────────────────────────")
                if cs_detailed.get("ratingpoints"):
                    lines.append("⭐ Rating Points: {:.2f}".format(cs_detailed.get("ratingpoints", 0)))
                if cs_detailed.get("ratingenabledgames"):
                    lines.append("🎮 Ranked Games: {}".format(cs_detailed.get("ratingenabledgames", 0)))
                if cs_detailed.get("streakwins"):
                    lines.append("🔥 Win Streak: {}".format(cs_detailed.get("streakwins", 0)))
                if cs_detailed.get("onegamemostkills"):
                    lines.append("🔫 Best Kills (1 Game): {}".format(cs_detailed.get("onegamemostkills", 0)))
                if cs_detailed.get("onegamemostdamage"):
                    lines.append("💥 Best Damage (1 Game): {}".format(format_number(cs_detailed.get("onegamemostdamage", 0))))
                if cs_detailed.get("headshotcount"):
                    lines.append("🎯 Total Headshots: {}".format(format_number(cs_detailed.get("headshotcount", 0))))
                if cs_detailed.get("hitcount"):
                    lines.append("🔫 Total Hits: {}".format(format_number(cs_detailed.get("hitcount", 0))))
                if cs_detailed.get("throwingkills"):
                    lines.append("💣 Grenade Kills: {}".format(cs_detailed.get("throwingkills", 0)))
        else:
            lines.append("❌ No Clash Squad stats available")
        
        lines.append("")
        lines.append("═════════════════════════════════════")
        lines.append("```")
        return "\n".join(lines)
        
    except Exception as e:
        logging.error("CS Stats Format Error: {}".format(e))
        return "```\n❌ Error formatting CS stats: {}\n```".format(str(e))

def format_player_profile(data):
    try:
        basic = data.get("basicinfo", {})
        pet = data.get("petinfo", {})
        social = data.get("socialinfo", {})
        credit = data.get("creditscoreinfo", {})
        
        nickname = basic.get("nickname", "N/A")
        player_id = basic.get("accountid", "N/A")
        region = basic.get("region", "N/A")
        account_type = basic.get("accounttype", "N/A")
        level = basic.get("level", "N/A")
        exp = format_number(basic.get("exp", 0))
        likes = format_number(basic.get("liked", 0))
        created_at = unix_to_date(basic.get("createat", "N/A"))
        last_login = unix_to_date(basic.get("lastloginat", "N/A"))
        
        br_rank = basic.get("rank", "N/A")
        rank_points = format_number(basic.get("rankingpoints", 0))
        max_rank = basic.get("maxrank", "N/A")
        cs_rank = basic.get("csrank", "N/A")
        cs_points = basic.get("csrankingpoints", 0)
        hippo_rank = basic.get("hipporank", "N/A")
        
        if br_rank != "N/A":
            rank_tier = get_rank_tier(int(br_rank))
        else:
            rank_tier = "N/A"
        
        pet_name = pet.get("name", "N/A")
        pet_id = pet.get("id", "N/A")
        pet_level = pet.get("level", "N/A")
        pet_exp = format_number(pet.get("exp", 0))
        pet_skin = pet.get("skinid", "N/A")
        pet_skill = pet.get("selectedskillid", "N/A")
        
        signature = social.get("signature", "N/A")
        
        veteran_expire = basic.get("veteranexpiretime", "")
        if veteran_expire:
            veteran_date = unix_to_date(veteran_expire)
        else:
            veteran_date = "N/A"
        
        credit_score = credit.get("creditscore", "N/A")
        
        if region == "BD":
            region_display = "🇧🇩 Bangladesh"
        else:
            region_display = "🌍 " + str(region)
        
        if account_type == 1:
            acc_type = "Garena (1)"
        else:
            acc_type = "Guest (" + str(account_type) + ")"
        
        lines = []
        lines.append("```")
        lines.append("🎮 Free Fire Player Profile")
        lines.append("═══════════════════════════════")
        lines.append("")
        lines.append("👤 Nickname: " + str(nickname))
        lines.append("🆔 Player ID: " + str(player_id))
        lines.append("🌍 Region: " + region_display)
        lines.append("🧾 Account Type: " + acc_type)
        lines.append("🏅 Level: " + str(level))
        lines.append("✨ EXP: " + str(exp))
        lines.append("❤️ Likes: " + str(likes))
        lines.append("📅 Created On: 🗓️ " + str(created_at))
        lines.append("🔑 Last Login: ⏱️ " + str(last_login))
        lines.append("")
        lines.append("🏆 Rank Information")
        lines.append("═══════════════════════════════")
        lines.append("🎯 Battle Royale Rank: " + str(br_rank) + " 🏵️ (" + rank_tier + ")")
        lines.append("⭐ Ranking Points: " + str(rank_points))
        lines.append("🚀 Max Rank: " + str(max_rank))
        lines.append("⚔️ Clash Squad Rank: " + str(cs_rank))
        lines.append("🎯 CS Points: " + str(cs_points))
        lines.append("🦈 Hippo Rank: " + str(hippo_rank))
        lines.append("")
        lines.append("🐾 Pet Information")
        lines.append("═══════════════════════════════")
        lines.append("🐶 Pet Name: " + str(pet_name))
        lines.append("🆔 Pet ID: " + str(pet_id))
        lines.append("📈 Level: " + str(pet_level) + " — EXP: " + str(pet_exp))
        lines.append("🎨 Skin ID: " + str(pet_skin))
        lines.append("💥 Selected Skill ID: " + str(pet_skill))
        lines.append("")
        lines.append("✍️ Social Information")
        lines.append("═══════════════════════════════")
        lines.append("💬 Signature: \"" + str(signature) + "\"")
        lines.append("")
        lines.append("🛡️ Veteran Status")
        lines.append("═══════════════════════════════")
        lines.append("🎖️ Expires: 🗓️ " + str(veteran_date))
        lines.append("")
        lines.append("⭐ Credit Score")
        lines.append("═══════════════════════════════")
        lines.append("🏅 Score: " + str(credit_score) + "/100")
        lines.append("```")
        
        return "\n".join(lines)
        
    except Exception as e:
        logging.error("Format Error: {}".format(e))
        return "```\nError formatting data: {}\n```".format(str(e))

# ================ FIXED AUTHORIZATION CHECKER ================

async def is_authorized(event):
    """Check if user and chat are authorized"""
    global OWNER_ID
    
    # Get sender ID - handle None case (FIX #3)
    user_id = event.sender_id
    if user_id is None:
        return False
    
    chat_id = event.chat_id
    
    # Use cached owner ID instead of calling API every time (FIX #1)
    # Owner always has access everywhere
    if user_id == OWNER_ID:
        return True
    
    # Check if it's a private chat
    if event.is_private:
        # In private chats, check if user is authorized
        if not authorized_user_ids:
            return False
        return user_id in authorized_user_ids
    else:
        # In groups/channels (FIX #2)
        # First check if user is individually authorized (they can use bot anywhere)
        if user_id in authorized_user_ids:
            return True
        
        # Then check if group is authorized (all users in that group can use)
        if authorized_group_ids and chat_id in authorized_group_ids:
            return True
        
        # If neither user nor group is authorized, deny access
        return False

# ================ COMMANDS ================

@client.on(events.NewMessage(pattern=r'(?i)^\.Cid\s+(\d+)$'))
async def cid_command(event):
    # Check authorization - silently ignore if not authorized
    if not await is_authorized(event):
        return
    
    try:
        uid = event.pattern_match.group(1)
        
        processing_msg = await event.reply("🔍 Fetching player details...")
        
        data = fetch_player_data(uid)
        
        if data is None:
            await processing_msg.edit("```\nError: Unable to fetch data from API.\n```")
            return
        
        if "error" in data or "basicinfo" not in data:
            await processing_msg.edit("```\nError: Player not found. UID: {}\n```".format(uid))
            return
        
        formatted_profile = format_player_profile(data)
        
        await processing_msg.edit(formatted_profile)
        
    except Exception as e:
        logging.error("Command Error: {}".format(e))
        await event.reply("```\nError: {}\n```".format(str(e)))

@client.on(events.NewMessage(pattern=r'(?i)^\.ps\s+(\d+)\s+(\w+)\s+(\w+)$'))
async def player_stats_command(event):
    """Get player stats - .ps (uid) (matchmode) (gamemode)"""
    # Check authorization - silently ignore if not authorized
    if not await is_authorized(event):
        return
    
    try:
        uid = event.pattern_match.group(1)
        matchmode = event.pattern_match.group(2).upper()
        gamemode = event.pattern_match.group(3).lower()
        
        # Validate matchmode
        valid_matchmodes = ["CAREER", "NORMAL", "RANKED"]
        if matchmode not in valid_matchmodes:
            await event.reply("```\n❌ Invalid Match Mode!\n\nValid options: CAREER, NORMAL, RANKED\n\nExample: .ps 1710824990 CAREER br\n```")
            return
        
        # Validate gamemode
        valid_gamemodes = ["br", "cs"]
        if gamemode not in valid_gamemodes:
            await event.reply("```\n❌ Invalid Game Mode!\n\nValid options: br, cs\n\nExample: .ps 1710824990 CAREER br\n```")
            return
        
        processing_msg = await event.reply("🔍 Fetching player stats for UID: {}...\n📊 Mode: {} | 🎯 Game: {}".format(uid, matchmode, gamemode.upper()))
        
        data = fetch_player_stats(uid, matchmode, gamemode)
        
        if data is None:
            await processing_msg.edit("```\n❌ Error: Unable to fetch data from API.\nPlease try again later.\n```")
            return
        
        if not data.get("success", False):
            await processing_msg.edit("```\n❌ Error: API returned failure.\nUID: {}\nPlease check if the UID is correct.\n```".format(uid))
            return
        
        # Format stats based on gamemode
        if gamemode == "br":
            formatted_stats = format_br_stats(data, matchmode, uid)
        else:
            formatted_stats = format_cs_stats(data, matchmode, uid)
        
        await processing_msg.edit(formatted_stats)
        
    except Exception as e:
        logging.error("Player Stats Command Error: {}".format(e))
        await event.reply("```\n❌ Error: {}\n```".format(str(e)))

@client.on(events.NewMessage(pattern=r'(?i)^\.ps$'))
async def player_stats_help(event):
    """Show help for .ps command when used without arguments"""
    # Check authorization - silently ignore if not authorized
    if not await is_authorized(event):
        return
    
    help_lines = []
    help_lines.append("```")
    help_lines.append("📊 Player Stats Command Usage")
    help_lines.append("═════════════════════════════════════")
    help_lines.append("")
    help_lines.append("Format: .ps [UID] [MATCHMODE] [GAMEMODE]")
    help_lines.append("")
    help_lines.append("📋 MATCH MODES:")
    help_lines.append("  • CAREER  - All-time statistics")
    help_lines.append("  • RANKED  - Ranked match stats")
    help_lines.append("  • NORMAL  - Normal match stats")
    help_lines.append("")
    help_lines.append("🎮 GAME MODES:")
    help_lines.append("  • br - Battle Royale")
    help_lines.append("  • cs - Clash Squad")
    help_lines.append("")
    help_lines.append("📝 EXAMPLES:")
    help_lines.append("  .ps 1710824990 CAREER br")
    help_lines.append("  .ps 1710824990 RANKED cs")
    help_lines.append("  .ps 1710824990 NORMAL br")
    help_lines.append("```")
    await event.reply("\n".join(help_lines))

# ================ NEW CALCULATOR COMMAND ================

@client.on(events.NewMessage(pattern=r'(?i)^\.c\s+(.+)$'))
async def calculator_command(event):
    """Calculator command - .c (expression)"""
    # Check authorization - silently ignore if not authorized
    if not await is_authorized(event):
        return
    
    try:
        expression = event.pattern_match.group(1).strip()
        
        # Security: Only allow numbers, operators, parentheses, decimal points, and spaces
        allowed_chars = set('0123456789+-*/().% ')
        if not all(char in allowed_chars for char in expression):
            await event.reply("```\n❌ Invalid characters in expression!\n\nAllowed: Numbers, +, -, *, /, (, ), ., %\n\nExample: .c 120+22\n```")
            return
        
        # Prevent empty expression
        if not expression or expression.isspace():
            await event.reply("```\n❌ Empty expression!\n\nExample: .c 120+22\n```")
            return
        
        # Calculate using safe function
        result = safe_calculate(expression)
        formatted_result = format_calc_result(result)
        
        lines = []
        lines.append("```")
        lines.append("🧮 Calculator")
        lines.append("═══════════════════════════════")
        lines.append("📝 Expression: {}".format(expression))
        lines.append("✅ Result: {}".format(formatted_result))
        lines.append("```")
        
        await event.reply("\n".join(lines))
        
    except ZeroDivisionError:
        await event.reply("```\n❌ Error: Division by zero!\n```")
    except ValueError as ve:
        await event.reply("```\n❌ Error: {}\n\nExample: .c 120+22\n```".format(str(ve)))
    except SyntaxError:
        await event.reply("```\n❌ Error: Invalid expression syntax!\n\nExample: .c 120+22\n```")
    except Exception as e:
        logging.error("Calculator Command Error: {}".format(e))
        await event.reply("```\n❌ Error: {}\n```".format(str(e)))

@client.on(events.NewMessage(pattern=r'(?i)^\.c$'))
async def calculator_help(event):
    """Show help for .c command when used without arguments"""
    # Check authorization - silently ignore if not authorized
    if not await is_authorized(event):
        return
    
    help_lines = []
    help_lines.append("```")
    help_lines.append("🧮 Calculator Command Usage")
    help_lines.append("═════════════════════════════════════")
    help_lines.append("")
    help_lines.append("Format: .c [expression]")
    help_lines.append("")
    help_lines.append("📋 OPERATORS:")
    help_lines.append("  • +  Addition")
    help_lines.append("  • -  Subtraction")
    help_lines.append("  • *  Multiplication")
    help_lines.append("  • /  Division")
    help_lines.append("  • %  Modulo (remainder)")
    help_lines.append("  • () Parentheses for grouping")
    help_lines.append("")
    help_lines.append("📝 EXAMPLES:")
    help_lines.append("  .c 120+22         → 142")
    help_lines.append("  .c 100-50         → 50")
    help_lines.append("  .c 25*4           → 100")
    help_lines.append("  .c 100/5          → 20")
    help_lines.append("  .c 10%3           → 1")
    help_lines.append("  .c (10+5)*2       → 30")
    help_lines.append("  .c 10+20*3-5      → 65")
    help_lines.append("  .c 2.5*4          → 10")
    help_lines.append("  .c (100+50)/2*3   → 225")
    help_lines.append("```")
    await event.reply("\n".join(help_lines))

# ================ EXISTING COMMANDS CONTINUED ================

@client.on(events.NewMessage(pattern=r'(?i)^\.cd$'))
async def chatid_command(event):
    """Get chat ID or user details"""
    # Check authorization - silently ignore if not authorized
    if not await is_authorized(event):
        return
    
    try:
        chat = await event.get_chat()
        
        # Check if it's a private chat
        if event.is_private:
            # Get the other user's details
            user = await client.get_entity(event.chat_id)
            
            lines = []
            lines.append("```")
            lines.append("👤 User Details")
            lines.append("═══════════════════════════════")
            lines.append("🆔 User ID: {}".format(user.id))
            lines.append("📛 First Name: {}".format(user.first_name or "N/A"))
            lines.append("📝 Last Name: {}".format(user.last_name or "N/A"))
            lines.append("🔗 Username: @{}".format(user.username if user.username else "N/A"))
            lines.append("📱 Phone: {}".format(user.phone if hasattr(user, 'phone') and user.phone else "N/A"))
            lines.append("🤖 Is Bot: {}".format("Yes" if user.bot else "No"))
            lines.append("✅ Verified: {}".format("Yes" if getattr(user, 'verified', False) else "No"))
            lines.append("🚫 Restricted: {}".format("Yes" if getattr(user, 'restricted', False) else "No"))
            lines.append("📵 Scam: {}".format("Yes" if getattr(user, 'scam', False) else "No"))
            lines.append("```")
            
            await event.reply("\n".join(lines))
        else:
            # It's a group or channel
            lines = []
            lines.append("```")
            lines.append("💬 Chat Details")
            lines.append("═══════════════════════════════")
            lines.append("🆔 Chat ID: {}".format(event.chat_id))
            lines.append("📛 Title: {}".format(chat.title if hasattr(chat, 'title') else "N/A"))
            lines.append("🔗 Username: @{}".format(chat.username if hasattr(chat, 'username') and chat.username else "N/A"))
            
            # Determine chat type
            if hasattr(chat, 'megagroup') and chat.megagroup:
                chat_type = "Supergroup"
            elif hasattr(chat, 'broadcast') and chat.broadcast:
                chat_type = "Channel"
            elif hasattr(chat, 'gigagroup') and chat.gigagroup:
                chat_type = "Gigagroup"
            else:
                chat_type = "Group"
            
            lines.append("📊 Type: {}".format(chat_type))
            
            # Members count (if available)
            if hasattr(chat, 'participants_count'):
                lines.append("👥 Members: {}".format(format_number(chat.participants_count)))
            
            lines.append("```")
            
            await event.reply("\n".join(lines))
        
    except Exception as e:
        logging.error("Chat ID Command Error: {}".format(e))
        await event.reply("```\nError: {}\n```".format(str(e)))

@client.on(events.NewMessage(pattern=r'(?i)^\.ping$'))
async def ping_command(event):
    # Check authorization - silently ignore if not authorized
    if not await is_authorized(event):
        return
    
    await event.reply("```\n🏓 Pong! Bot is alive!\n```")

@client.on(events.NewMessage(pattern=r'(?i)^\.help$'))
async def help_command(event):
    # Check authorization - silently ignore if not authorized
    if not await is_authorized(event):
        return
    
    help_lines = []
    help_lines.append("```")
    help_lines.append("🤖 Free Fire Userbot Commands")
    help_lines.append("═══════════════════════════════")
    help_lines.append("")
    help_lines.append(".Cid [UID]")
    help_lines.append("  → Get Free Fire player profile")
    help_lines.append("  → Example: .Cid 2716319203")
    help_lines.append("")
    help_lines.append(".ps [UID] [MATCHMODE] [GAMEMODE]")
    help_lines.append("  → Get player statistics")
    help_lines.append("  → Match Modes: CAREER, NORMAL, RANKED")
    help_lines.append("  → Game Modes: br (Battle Royale), cs (Clash Squad)")
    help_lines.append("  → Example: .ps 1710824990 CAREER br")
    help_lines.append("  → Example: .ps 1710824990 RANKED cs")
    help_lines.append("")
    help_lines.append(".c [expression]")
    help_lines.append("  → Calculator for math expressions")
    help_lines.append("  → Supports: +, -, *, /, %, ()")
    help_lines.append("  → Example: .c 120+22")
    help_lines.append("  → Example: .c (10+5)*2")
    help_lines.append("")
    help_lines.append(".cd")
    help_lines.append("  → Get chat/user ID details")
    help_lines.append("")
    help_lines.append(".ping")
    help_lines.append("  → Check if bot is alive")
    help_lines.append("")
    help_lines.append(".help")
    help_lines.append("  → Show this help message")
    help_lines.append("```")
    await event.reply("\n".join(help_lines))

async def main():
    global OWNER_ID  # Declare global to modify it
    
    try:
        # Connect to Telegram
        await client.connect()
        
        # Check if authorized
        if not await client.is_user_authorized():
            logging.error("Session string is invalid or expired!")
            logging.error("Please generate a new session string.")
            sys.exit(1)
        
        # Cache owner ID at startup (FIX #1 - only call once)
        me = await client.get_me()
        OWNER_ID = me.id
        
        logging.info("Userbot started successfully!")
        logging.info("User: {} (@{})".format(me.first_name, me.username if me.username else "No username"))
        logging.info("ID: {}".format(me.id))
        logging.info("Authorized Users: {}".format(authorized_user_ids if authorized_user_ids else "Owner only"))
        logging.info("Authorized Groups: {}".format(authorized_group_ids if authorized_group_ids else "None"))
        logging.info("Ready! Commands: .Cid, .ps, .c, .cd, .ping, .help")
        
        # Keep the client running
        await client.run_until_disconnected()
        
    except Exception as e:
        logging.error("Start Error: {}".format(e))
        sys.exit(1)

if __name__ == "__main__":
    # Start Flask in a separate thread
    flask_thread = Thread(target=run_flask)
    flask_thread.daemon = True
    flask_thread.start()
    
    logging.info("Flask started")
    
    # Start the Telegram client
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logging.info("Bot stopped")
    except Exception as e:
        logging.error("Fatal: {}".format(e))
        sys.exit(1)
