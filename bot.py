from flask import Flask
from threading import Thread
import discord
from discord.ext import commands
from discord import app_commands
import os, json, asyncio, random
from datetime import datetime
from dotenv import load_dotenv
from typing import Optional

# -------------------------
# Mantener vivo (Render)
# -------------------------
from flask import Flask
from threading import Thread

app = Flask(__name__)

@app.route('/')
def home():
    return "Bot activo :)"

def run():
    app.run(host='0.0.0.0', port=8080)

def keep_alive():
    t = Thread(target=run)
    t.start()

# -------------------------
# Configuración
# -------------------------
load_dotenv()
TOKEN = os.getenv("TOKEN")
ALLOWED_GUILD_ID = 1437214142779097323

intents = discord.Intents.default()
intents.message_content = True
intents.members = True

bot = commands.Bot(command_prefix="/", intents=intents)
tree = bot.tree
# -------------------------
# Eventos
# -------------------------
@bot.event
async def on_ready():
    print(f"✅ Conectado como {bot.user}")
    guild = discord.Object(id=ALLOWED_GUILD_ID)

    try:
        # Intentar sincronizar comandos en el servidor específico
        synced = await tree.sync(guild=guild)
        print(f"🔁 {len(synced)} comandos sincronizados en el servidor {ALLOWED_GUILD_ID}.")
    except discord.errors.Forbidden:
        # Si no tiene permiso, sincroniza globalmente
        print("⚠️ No tengo permisos para sincronizar en el servidor. Sincronizando globalmente...")
        synced = await tree.sync()
        print(f"🌍 {len(synced)} comandos sincronizados globalmente.")
    except Exception as e:
        print(f"❌ Error inesperado al sincronizar comandos: {e}")

# -------------------------
# Comando de prueba
# -------------------------
@tree.command(name="ping", description="Prueba de conexión")
async def ping(interaction: discord.Interaction):
    await interaction.response.send_message("Pong! BETA 4")

# -------------------------
# Iniciar todo
# -------------------------

# Cargar variables del entorno
load_dotenv()
TOKEN = os.getenv("TOKEN")

# Configuración
MIN_BET = 10
MAX_BET = 1000000000000
ALLOWED_GUILD_ID = 1437214142779097323  # ✅ ID del servidor RESONA TEMP. 2

DAILY_AMOUNT = 10000
WORK_MIN = 1000
WORK_MAX = 5000
DATA_DIR = "."

import os, json

# Carpeta donde se guardan los datos
DATA_DIR = "data"
os.makedirs(DATA_DIR, exist_ok=True)

# Archivos
BALANCES_FILE = os.path.join(DATA_DIR, "balances.json")
SHARED_FILE = os.path.join(DATA_DIR, "sharedaccounts.json")

# Funciones para leer y guardar
def load_json(path, default=None):
    if os.path.exists(path):
        with open(path, "r") as f:
            return json.load(f)
    return default or {}

def save_json(path, data):
    with open(path, "w") as f:
        json.dump(data, f, indent=4)

# Cargar los datos existentes (o crear vacíos si no existen)
balances = load_json(BALANCES_FILE, {})
shared_accounts = load_json(SHARED_FILE, {})


# ----------------- SETUP BOT -----------------
intents = discord.Intents.default()
intents.message_content = True
intents.members = True

@bot.check
async def only_in_resona(ctx):
    if ctx.guild is None:
        await ctx.send("❌ Este bot solo funciona dentro del servidor **RESONA TEMP. 2**.")
        return False
    if ctx.guild.id != ALLOWED_GUILD_ID:
        await ctx.send("❌ Este bot solo está autorizado para usarse en el servidor **RESONA TEMP. 2**.")
        return False
    return True

# ----------------- CONFIG -----------------
from dotenv import load_dotenv
load_dotenv()
TOKEN = os.getenv("TOKEN")
DAILY_AMOUNT = 10000
WORK_MIN = 1000
WORK_MAX = 2000
DATA_DIR = "."  # deja "." para la carpeta actual

BALANCES_FILE = os.path.join(DATA_DIR, "balances.json")
SHARED_FILE = os.path.join(DATA_DIR, "sharedaccounts.json")

# ----------------- SETUP BOT -----------------
intents = discord.Intents.default()
intents.message_content = True
intents.members = True

# ----------------- UTIL / STORAGE -----------------
balances_lock = asyncio.Lock()
balances = {}
shared_accounts = {}

def load_json(path, default):
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except:
            return default
    else:
        return default

def save_json(path, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4, ensure_ascii=False)

# load data
balances = load_json(BALANCES_FILE, {})
shared_accounts = load_json(SHARED_FILE, {})

async def save_all():
    async with balances_lock:
        save_json(BALANCES_FILE, balances)
        save_json(SHARED_FILE, shared_accounts)

async def safe_add(user_id: str, amount: float):
    async with balances_lock:
        balances[user_id] = balances.get(user_id, 0) + amount
        save_json(BALANCES_FILE, balances)

async def safe_subtract(user_id: str, amount: float) -> bool:
    async with balances_lock:
        if balances.get(user_id, 0) < amount:
            return False
        balances[user_id] = balances.get(user_id, 0) - amount
        save_json(BALANCES_FILE, balances)
        return True

def fmt(n):
    # friendly formatting with thousands
    try:
        return f"{int(n):,}"
    except:
        return str(n)

def dark_embed(title="", desc="", color=0x2F3136):
    # default dark grey color 0x2F3136
    e = discord.Embed(title=title, description=desc, color=color)
    return e

# ----------------- HELPERS -----------------
def ensure_user(user_id: str):
    if user_id not in balances:
        balances[user_id] = 0

# ----------------- ADMIN COMMANDS -----------------
@tree.command(name="add", description="(Admin) Agregar monedas a un usuario")
@app_commands.describe(usuario="Usuario", cantidad="Cantidad a agregar")
async def add(interaction: discord.Interaction, usuario: discord.User, cantidad: int):
    if not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message(embed=dark_embed("🚫 Permisos", "Solo administradores pueden usar esto."), ephemeral=True)
        return
    if cantidad <= 0:
        await interaction.response.send_message(embed=dark_embed("❌ Monto inválido", "La cantidad debe ser positiva."), ephemeral=True)
        return
    uid = str(usuario.id)
    await safe_add(uid, cantidad)
    embed = dark_embed("💸 Monedas agregadas", f"Se agregaron **{fmt(cantidad)}** monedas a {usuario.mention}", 0x2ECC71)
    embed.set_footer(text=f"Acción por {interaction.user.display_name}")
    await interaction.response.send_message(embed=embed)

@tree.command(name="remove", description="(Admin) Quitar monedas a un usuario")
@app_commands.describe(usuario="Usuario", cantidad="Cantidad a quitar")
async def remove(interaction: discord.Interaction, usuario: discord.User, cantidad: int):
    if not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message(embed=dark_embed("🚫 Permisos", "Solo administradores pueden usar esto."), ephemeral=True)
        return
    if cantidad <= 0:
        await interaction.response.send_message(embed=dark_embed("❌ Monto inválido", "La cantidad debe ser positiva."), ephemeral=True)
        return
    uid = str(usuario.id)
    async with balances_lock:
        balances[uid] = max(0, balances.get(uid,0) - cantidad)
        save_json(BALANCES_FILE, balances)
    embed = dark_embed("💰 Monedas removidas", f"Se quitaron **{fmt(cantidad)}** monedas a {usuario.mention}", 0xE74C3C)
    embed.set_footer(text=f"Acción por {interaction.user.display_name}")
    await interaction.response.send_message(embed=embed)

@tree.command(name="set", description="(Admin) Establecer el balance exacto de un usuario")
@app_commands.describe(usuario="Usuario", cantidad="Nuevo balance")
async def setcoins(interaction: discord.Interaction, usuario: discord.User, cantidad: int):
    if not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message(embed=dark_embed("🚫 Permisos", "Solo administradores pueden usar esto."), ephemeral=True)
        return
    if cantidad < 0:
        await interaction.response.send_message(embed=dark_embed("❌ Monto inválido", "La cantidad no puede ser negativa."), ephemeral=True)
        return
    uid = str(usuario.id)
    async with balances_lock:
        balances[uid] = cantidad
        save_json(BALANCES_FILE, balances)
    embed = dark_embed("⚙️ Balance actualizado", f"{usuario.mention} ahora tiene **{fmt(cantidad)}** monedas.", 0x7289DA)
    embed.set_footer(text=f"Acción por {interaction.user.display_name}")
    await interaction.response.send_message(embed=embed)

# ----------------- ECONOMY Y /CRIME -----------------
@tree.command(name="transfer", description="Transferir monedas a otro usuario")
@app_commands.describe(usuario="Usuario destino", cantidad="Monto")
async def transfer(interaction: discord.Interaction, usuario: discord.User, cantidad: int):
    if cantidad < MIN_BET:
        await interaction.response.send_message(embed=dark_embed("❌ Monto muy bajo", f"El mínimo de apuesta/transferencia es **{MIN_BET}**."), ephemeral=True)
        return
    sender = str(interaction.user.id)
    receiver = str(usuario.id)
    async with balances_lock:
        if balances.get(sender,0) < cantidad:
            await interaction.response.send_message(embed=dark_embed("❌ Saldo insuficiente", "No tenés suficientes monedas."), ephemeral=True)
            return
        balances[sender] -= cantidad
        balances[receiver] = balances.get(receiver,0) + cantidad
        save_json(BALANCES_FILE, balances)
    embed = dark_embed("💸 Transferencia realizada", f"{interaction.user.mention} transfirió **{fmt(cantidad)}** a {usuario.mention}", 0x1ABC9C)
    await interaction.response.send_message(embed=embed)

from datetime import datetime, timedelta

# diccionario para cooldowns de crime
crime_cooldowns = {}

@tree.command(name="crime", description="Intentá cometer un crimen y ganá o perdé dinero 💰")
async def crime(interaction: discord.Interaction):
    user_id = str(interaction.user.id)
    now = datetime.utcnow()

    # ⏳ Chequear cooldown
    if user_id in crime_cooldowns and now < crime_cooldowns[user_id]:
        remaining = (crime_cooldowns[user_id] - now).seconds
        mins, secs = divmod(remaining, 60)
        embed = discord.Embed(
            title="⏳ Esperá un poco",
            description=f"Podés volver a intentar un crimen en **{mins}m {secs}s**.",
            color=discord.Color.orange()
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)
        return

    # 🕒 Registrar nuevo cooldown (10 minutos)
    crime_cooldowns[user_id] = now + timedelta(minutes=10)

    balance = balances.get(user_id, 0)

    # 🎲 Probabilidad: 40% éxito, 60% fracaso
    if random.random() < 0.4:  # 0.0–0.39 éxito
        reward = random.randint(4000, 8715)
        balances[user_id] = balance + reward
        save_json(BALANCES_FILE, balances)
        embed = discord.Embed(
            title="💸 Crimen exitoso",
            description=f"Escapaste sin ser visto y ganaste **{reward:,}** monedas.",
            color=discord.Color.green()
        )
    else:
        loss = 2000
        balances[user_id] = max(0, balance - loss)
        save_json(BALANCES_FILE, balances)
        embed = discord.Embed(
            title="🚔 Te atraparon robando",
            description=f"La policía te encontró y te quitó **{loss:,}** monedas.",
            color=discord.Color.red()
        )

    embed.set_footer(text="RECO • Casino")
    await interaction.response.send_message(embed=embed)

# ----------------- SHARED ACCOUNTS (simple) -----------------
@tree.command(name="sharedaccounts", description="Crear/ver/operar cuentas compartidas: create, deposit, withdraw, view")
@app_commands.describe(action="create | deposit | withdraw | view", partner="Usuario (para create)", amount="Monto (para deposit/withdraw)")
async def sharedaccounts(interaction: discord.Interaction, action: str, partner: Optional[discord.User] = None, amount: Optional[int] = None):
    act = action.lower()
    user_id = str(interaction.user.id)
    if act == "create":
        if not partner:
            await interaction.response.send_message(embed=dark_embed("⚠️ Falta partner", "Mencioná con @ al usuario con quien querés crear la cuenta."), ephemeral=True)
            return
        p = str(partner.id)
        # create id deterministic
        shared_id = "_".join(sorted([user_id, p]))
        if shared_id in shared_accounts:
            await interaction.response.send_message(embed=dark_embed("⚠️ Ya existe", "Esa cuenta compartida ya existe."), ephemeral=True)
            return
        shared_accounts[shared_id] = {"users": [user_id, p], "balance": 0}
        save_json(SHARED_FILE, shared_accounts)
        embed = dark_embed("👥 Cuenta compartida creada", f"Cuenta entre {interaction.user.mention} y {partner.mention} creada.", 0x00B894)
        await interaction.response.send_message(embed=embed)
    elif act == "deposit":
        if amount is None or amount < 1:
            await interaction.response.send_message(embed=dark_embed("❌ Monto inválido", "Especificá un monto válido."), ephemeral=True)
            return
        # find user's shared
        found = None
        for sid, info in shared_accounts.items():
            if user_id in info["users"]:
                found = (sid, info); break
        if not found:
            await interaction.response.send_message(embed=dark_embed("⚠️ No encontrada", "No tenés ninguna cuenta compartida."), ephemeral=True)
            return
        sid, info = found
        async with balances_lock:
            if balances.get(user_id,0) < amount:
                await interaction.response.send_message(embed=dark_embed("❌ Saldo insuficiente", "No tenés suficientes monedas."), ephemeral=True)
                return
            balances[user_id] -= amount
            shared_accounts[sid]["balance"] = shared_accounts[sid].get("balance",0) + amount
            save_json(BALANCES_FILE, balances)
            save_json(SHARED_FILE, shared_accounts)
        embed = dark_embed("💳 Depositado", f"Depositaste **{fmt(amount)}** a la cuenta compartida.\nBalance compartido: **{fmt(shared_accounts[sid]['balance'])}**", 0x6C5CE7)
        await interaction.response.send_message(embed=embed)
    elif act == "withdraw":
        if amount is None or amount < 1:
            await interaction.response.send_message(embed=dark_embed("❌ Monto inválido", "Especificá un monto válido."), ephemeral=True)
            return
        found = None
        for sid, info in shared_accounts.items():
            if user_id in info["users"]:
                found = (sid, info); break
        if not found:
            await interaction.response.send_message(embed=dark_embed("⚠️ No encontrada", "No tenés ninguna cuenta compartida."), ephemeral=True)
            return
        sid, info = found
        if shared_accounts[sid].get("balance",0) < amount:
            await interaction.response.send_message(embed=dark_embed("❌ Saldo compartido insuficiente", "La cuenta no tiene ese monto."), ephemeral=True)
            return
        async with balances_lock:
            shared_accounts[sid]["balance"] -= amount
            balances[user_id] = balances.get(user_id,0) + amount
            save_json(BALANCES_FILE, balances)
            save_json(SHARED_FILE, shared_accounts)
        embed = dark_embed("💸 Retiro compartido", f"Retiraste **{fmt(amount)}** de la cuenta compartida.\nBalance compartido: **{fmt(shared_accounts[sid]['balance'])}**", 0xFDCB6E)
        await interaction.response.send_message(embed=embed)
    elif act == "view":
        found = []
        for sid, info in shared_accounts.items():
            if user_id in info["users"]:
                found.append((sid, info))
        if not found:
            await interaction.response.send_message(embed=dark_embed("⚠️ No tenés cuentas compartidas", "Usá `create` para abrir una."), ephemeral=True)
            return
        desc = ""
        for sid, info in found:
            users = []
            for u in info["users"]:
                try:
                    m = await interaction.guild.fetch_member(int(u))
                    users.append(m.display_name)
                except:
                    users.append(u)
            desc += f"**{', '.join(users)}** — Balance: **{fmt(info.get('balance',0))}**\n"
        embed = dark_embed("👥 Tus cuentas compartidas", desc, 0x00B894)
        await interaction.response.send_message(embed=embed)
    else:
        await interaction.response.send_message(embed=dark_embed("❌ Acción inválida", "Acciones válidas: create, deposit, withdraw, view"), ephemeral=True)

# ----------------- DAILY & WORK & PROFILE -----------------
last_daily = {}  # in-memory, but also store on save optionally
last_work = {}

@tree.command(name="daily", description="Reclamá tu recompensa diaria (10.000).")
async def daily(interaction: discord.Interaction):
    uid = str(interaction.user.id)
    now = datetime.utcnow()
    last = last_daily.get(uid)
    if last:
        elapsed = (now - datetime.fromisoformat(last)).total_seconds()
        if elapsed < 86400:
            rem = int(86400 - elapsed)
            h = rem//3600; m = (rem%3600)//60
            embed = dark_embed("⏳ Ya reclamaste", f"Volvé en **{h}h {m}m** para reclamar otra daily.", 0xE67E22)
            await interaction.response.send_message(embed=embed)
            return
    # give daily
    async with balances_lock:
        balances[uid] = balances.get(uid,0) + DAILY_AMOUNT
        save_json(BALANCES_FILE, balances)
    last_daily[uid] = now.isoformat()
    embed = dark_embed("💰 Daily reclamado", f"{interaction.user.mention} recibiste **{fmt(DAILY_AMOUNT)}** monedas. ¡A jugar! ✨", 0xF1C40F)
    embed.set_thumbnail(url=interaction.user.display_avatar.url)
    await interaction.response.send_message(embed=embed)

@tree.command(name="work", description="Trabajá y ganá entre 1.000 y 5.000 monedas (cooldown diario).")
async def work(interaction: discord.Interaction):
    uid = str(interaction.user.id)
    now = datetime.utcnow()
    last = last_work.get(uid)
    if last:
        elapsed = (now - datetime.fromisoformat(last)).total_seconds()
        if elapsed < 420:
            rem = int(420 - elapsed)
            h = rem//3600; m = (rem%3600)//60
            embed = dark_embed("⏳ Ya trabajaste hoy", f"Volvé en **{h}h {m}m** para trabajar otra vez.", 0xE67E22)
            await interaction.response.send_message(embed=embed)
            return
    amount = random.randint(WORK_MIN, WORK_MAX)
    async with balances_lock:
        balances[uid] = balances.get(uid,0) + amount
        save_json(BALANCES_FILE, balances)
    last_work[uid] = now.isoformat()
    embed = dark_embed("🧰 Trabajo completado", f"{interaction.user.mention} ganaste **{fmt(amount)}** monedas por trabajar.", 0x9B59B6)
    await interaction.response.send_message(embed=embed)

@tree.command(name="profile", description="Ver el perfil y balance de un usuario")
@app_commands.describe(usuario="Usuario (opcional)")
async def profile(interaction: discord.Interaction, usuario: Optional[discord.User] = None):
    u = usuario or interaction.user
    uid = str(u.id)
    bal = balances.get(uid, 0)
    embed = dark_embed(f"💼 Perfil — {u.display_name}", f"**💰 Balance:** {fmt(bal)}", 0x2F3136)
    embed.set_thumbnail(url=u.display_avatar.url)
    embed.set_footer(text="RECO • Economía del servidor")
    await interaction.response.send_message(embed=embed)
#------------------ CRYPTO GAMES -----------------
import matplotlib.pyplot as plt
from datetime import datetime
import io
import discord

CRYPTO_FILE = os.path.join(DATA_DIR, "cryptos.json")

# -------------------- Carga inicial --------------------
def load_cryptos():
    if os.path.exists(CRYPTO_FILE):
        with open(CRYPTO_FILE, "r") as f:
            return json.load(f)
    return {
        "RSC": {"price": 900, "history": [900]},
        "CTC": {"price": 500, "history": [500]},
        "MMC": {"price": 250, "history": [250]},
        "holders": {}
    }

def save_cryptos(data):
    with open(CRYPTO_FILE, "w") as f:
        json.dump(data, f, indent=4)

cryptos = load_cryptos()

# -------------------- Actualización de precios --------------------
async def update_crypto_prices():
    """Se ejecuta cada 5 minutos para variar precios."""
    while True:
        now = datetime.utcnow()
        weekday = now.weekday()  # 0=Lunes ... 6=Domingo
        weekend = weekday >= 4  # Viernes-Sábado-Domingo
        for symbol in ["RSC", "CTC", "MMC"]:
            c = cryptos[symbol]
            base = c["price"]
            # subida/bajada más fuerte si es fin de semana
            factor = random.uniform(-0.03, 0.05) if weekend else random.uniform(-0.01, 0.015)
            new_price = max(50, round(base * (1 + factor), 2))
            c["price"] = new_price
            c["history"].append(new_price)
            # limitar historial a 288 puntos (~24h si cada 5min)
            if len(c["history"]) > 288:
                c["history"].pop(0)
        save_cryptos(cryptos)
        await asyncio.sleep(300)  # cada 5 minutos

# -------------------- Comando principal /crypto --------------------
@tree.command(name="crypto", description="Sistema de criptomonedas del casino 💰")
@app_commands.describe(action="status, buy o bought", coin="RSC, CTC o MMC", quantity="Cantidad a comprar")
async def crypto(interaction: discord.Interaction, action: str, coin: Optional[str] = None, quantity: Optional[float] = None):
    user_id = str(interaction.user.id)
    action = action.lower()

    if action == "status":
        if not coin or coin.upper() not in ["RSC", "CTC", "MMC"]:
            embed = discord.Embed(
                title="💹 Estado de criptos",
                description="\n".join([f"**{s}** → {cryptos[s]['price']:,} monedas" for s in ["RSC", "CTC", "MMC"]]),
                color=discord.Color.blue()
            )
            await interaction.response.send_message(embed=embed)
            return

        # gráfico de historial
        symbol = coin.upper()
        prices = cryptos[symbol]["history"]
        plt.figure()
        plt.plot(prices, label=symbol, linewidth=2)
        plt.title(f"{symbol} - Últimas 24h")
        plt.xlabel("Tiempo")
        plt.ylabel("Precio (monedas)")
        plt.legend()
        buf = io.BytesIO()
        plt.savefig(buf, format="png")
        buf.seek(0)
        plt.close()

        file = discord.File(buf, filename=f"{symbol}.png")
        embed = discord.Embed(
            title=f"💰 {symbol} — Precio actual: {cryptos[symbol]['price']:,} monedas",
            color=discord.Color.gold()
        )
        embed.set_image(url=f"attachment://{symbol}.png")
        await interaction.response.send_message(embed=embed, file=file)

    elif action == "buy":
        if not coin or coin.upper() not in ["RSC", "CTC", "MMC"]:
            await interaction.response.send_message("❌ Cripto inválida (usá RSC, CTC o MMC).", ephemeral=True)
            return
        if not quantity or quantity <= 0:
            await interaction.response.send_message("❌ Cantidad inválida.", ephemeral=True)
            return

        symbol = coin.upper()
        price = cryptos[symbol]["price"]
        cost = price * quantity

        async with balances_lock:
            if balances.get(user_id, 0) < cost:
                await interaction.response.send_message(embed=discord.Embed(
                    title="💸 Fondos insuficientes",
                    description=f"Necesitás **{cost:,.2f}** monedas.",
                    color=discord.Color.red()
                ))
                return
            balances[user_id] -= cost
            save_json(BALANCES_FILE, balances)

        # registrar compra
        holders = cryptos["holders"].setdefault(user_id, {"RSC": 0, "CTC": 0, "MMC": 0})
        holders[symbol] += quantity
        save_cryptos(cryptos)

        embed = discord.Embed(
            title="✅ Compra realizada",
            description=f"Compraste **{quantity:.4f} {symbol}** por **{cost:,.2f}** monedas.",
            color=discord.Color.green()
        )
        await interaction.response.send_message(embed=embed)

    elif action == "bought":
        user_holdings = cryptos["holders"].get(user_id, {})
        if not any(user_holdings.values()):
            await interaction.response.send_message("❌ No tenés criptos todavía.", ephemeral=True)
            return
        desc = "\n".join([f"**{s}** → {amt:.4f} (≈ {amt * cryptos[s]['price']:.2f} monedas)" for s, amt in user_holdings.items() if amt > 0])
        embed = discord.Embed(
            title=f"💼 Criptos de {interaction.user.name}",
            description=desc,
            color=discord.Color.teal()
        )
        await interaction.response.send_message(embed=embed)

    else:
        await interaction.response.send_message("❌ Acción inválida. Usá: status, buy o bought.", ephemeral=True)

# -------------------- Loop de actualización --------------------
bot.loop.create_task(update_crypto_prices())
# ----------------- CASINO GAMES -----------------
# Helpers for cards
CARD_VALUES = {
    'A': 11, '2':2,'3':3,'4':4,'5':5,'6':6,'7':7,'8':8,'9':9,'10':10,'J':10,'Q':10,'K':10
}
SUITS = ['♠','♥','♦','♣']
DECK = [r + s for r in CARD_VALUES.keys() for s in SUITS]

def draw_from(deck, n=1):
    res = []
    for _ in range(n):
        res.append(deck.pop())
    return res

def hand_value(cards):
    total = 0
    aces = 0
    for c in cards:
        rank = c[:-1] if len(c) > 2 else c[0]
        val = CARD_VALUES.get(rank, 0)
        total += val
        if rank == 'A':
            aces += 1
    while total > 21 and aces:
        total -= 10
        aces -= 1
    return total

# ---------- Roulette ----------
@tree.command(name="roulette", description="Apostá a color (red/black/green) o número (0-36). Min 100.")
@app_commands.describe(bet="Monto", choice="red | black | green | 0-36")
async def roulette(interaction: discord.Interaction, bet: int, choice: str):

        # 🟢 Si el usuario pone 'a', apostamos todo
    if bet.lower() == "a":
        bet = balance
    else:
        try:
            bet = float(bet)
        except ValueError:
            await interaction.response.send_message(
                embed=discord.Embed(
                    title="❌ Apuesta inválida",
                    description="Usá un número o 'a' para apostar todo.",
                    color=discord.Color.red(),
                )
            )
            return

    if bet < MIN_BET:
        await interaction.response.send_message(embed=dark_embed("❌ Monto muy bajo", f"Mínimo: {MIN_BET}"), ephemeral=True)
        return
    uid = str(interaction.user.id)
    async with balances_lock:
        if balances.get(uid,0) < bet:
            await interaction.response.send_message(embed=dark_embed("❌ Saldo insuficiente", "No tenés suficiente saldo."), ephemeral=True)
            return
        balances[uid] -= bet
        save_json(BALANCES_FILE, balances)
    wheel = random.randint(0,36)
    color = "green" if wheel == 0 else ("red" if wheel % 2 == 1 else "black")
    win = 0
    c = choice.lower().strip()
    if c in ("red","black","green"):
        if c == color:
            if color == "green":
                win = bet * 35
            else:
                win = bet * 2
    else:
        try:
            num = int(c)
            if 0 <= num <= 36 and num == wheel:
                win = bet * 36
        except:
            pass
    if win > 0:
        await safe_add(uid, win)
        embed = dark_embed("🎡 Roulette — ¡Ganaste!", f"El resultado fue **{wheel}** ({color}).\nGanaste **{fmt(int(win))}**", 0x2ECC71)
    else:
        embed = dark_embed("🎡 Roulette — Perdiste", f"El resultado fue **{wheel}** ({color}).\nPerdiste **{fmt(int(bet))}**", 0xE74C3C)
    await interaction.response.send_message(embed=embed)

# ---------- Russian Roulette ----------
@tree.command(name="russianroulette", description="1/6 de perder, si ganas cobrás x5. Min 100")
@app_commands.describe(bet="Monto")
async def russianroulette(interaction: discord.Interaction, bet: int):

        # 🟢 Si el usuario pone 'a', apostamos todo
    if bet.lower() == "a":
        bet = balance
    else:
        try:
            bet = float(bet)
        except ValueError:
            await interaction.response.send_message(
                embed=discord.Embed(
                    title="❌ Apuesta inválida",
                    description="Usá un número o 'a' para apostar todo.",
                    color=discord.Color.red(),
                )
            )
            return

    if bet < MIN_BET:
        await interaction.response.send_message(embed=dark_embed("❌ Monto muy bajo", f"Mínimo: {MIN_BET}"), ephemeral=True)
        return
    uid = str(interaction.user.id)
    async with balances_lock:
        if balances.get(uid,0) < bet:
            await interaction.response.send_message(embed=dark_embed("❌ Saldo insuficiente", "No tenés suficiente saldo."), ephemeral=True)
            return
        balances[uid] -= bet
        save_json(BALANCES_FILE, balances)
    chamber = random.randint(1,6)
    if chamber == 1:
        embed = dark_embed("💀 Russian Roulette — Perdiste", f"La bala salió. Perdiste **{fmt(bet)}**", 0x991818)
    else:
        payout = bet * 5
        await safe_add(uid, payout)
        embed = dark_embed("🔫 Russian Roulette — Ganaste", f"Tu disparo no fue fatal. Cobraste **{fmt(int(payout))}**", 0x2ECC71)
    await interaction.response.send_message(embed=embed)

# ---------- Slots ----------
@tree.command(name="slots", description="Jugá a las slots. Min 100")
@app_commands.describe(bet="Monto")
async def slots(interaction: discord.Interaction, bet: int):

        # 🟢 Si el usuario pone 'a', apostamos todo
    if bet.lower() == "a":
        bet = balance
    else:
        try:
            bet = float(bet)
        except ValueError:
            await interaction.response.send_message(
                embed=discord.Embed(
                    title="❌ Apuesta inválida",
                    description="Usá un número o 'a' para apostar todo.",
                    color=discord.Color.red(),
                )
            )
            return

    if bet < MIN_BET:
        await interaction.response.send_message(embed=dark_embed("❌ Monto muy bajo", f"Mínimo: {MIN_BET}"), ephemeral=True)
        return
    uid = str(interaction.user.id)
    async with balances_lock:
        if balances.get(uid,0) < bet:
            await interaction.response.send_message(embed=dark_embed("❌ Saldo insuficiente", "No tenés suficiente saldo."), ephemeral=True)
            return
        balances[uid] -= bet
        save_json(BALANCES_FILE, balances)
    icons = ["🍒","🍋","🍇","🔔","💎","7️⃣"]
    res = [random.choice(icons) for _ in range(3)]
    win = 0
    if len(set(res)) == 1:
        win = bet * 5
    elif len(set(res)) == 2:
        win = int(bet * 1.5)
    if win > 0:
        await safe_add(uid, win)
        embed = dark_embed("🎰 Slots — ¡Ganaste!", f"{' | '.join(res)}\nRecibiste **{fmt(int(win))}**", 0x2ECC71)
    else:
        embed = dark_embed("🎰 Slots — Perdiste", f"{' | '.join(res)}\nPerdiste **{fmt(int(bet))}**", 0xE74C3C)
    await interaction.response.send_message(embed=embed)

# ---------- Blackjack (interactivo) ----------
blackjack_sessions = {}  # uid -> session data

class BlackjackView(discord.ui.View):
    def __init__(self, uid, session, timeout=60):
        super().__init__(timeout=timeout)
        self.uid = uid
        self.session = session
        self.message = None

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        return str(interaction.user.id) == self.uid

    @discord.ui.button(label="Hit", style=discord.ButtonStyle.primary)
    async def hit(self, interaction: discord.Interaction, button: discord.ui.Button):
        deck = self.session["deck"]
        self.session["player"].append(draw_from(deck, 1)[0])
        pval = hand_value(self.session["player"])
        if pval > 21:
            self.stop()
            await self.resolve(interaction, busted=True)
            return
        await interaction.response.edit_message(embed=embed_for_session(self.session), view=self)

    @discord.ui.button(label="Stand", style=discord.ButtonStyle.secondary)
    async def stand(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.stop()
        await self.resolve(interaction, busted=False)

    async def on_timeout(self):
        self.stop()
        try:
            await self.message.edit(content="⏰ Se acabó el tiempo. El dealer gana por inactividad.", view=None)
        except:
            pass
        blackjack_sessions.pop(self.uid, None)

    async def resolve(self, interaction: discord.Interaction, busted: bool):
        session = self.session
        deck = session["deck"]

        # dealer draw
        dval = hand_value(session["dealer"])
        while dval < 17:
            session["dealer"].append(draw_from(deck, 1)[0])
            dval = hand_value(session["dealer"])

        pval = hand_value(session["player"])
        bet = session["bet"]
        payout = 0
        note = ""

        if busted:
            payout = 0
            note = "Te pasaste (bust). Perdiste."
        else:
            if pval == 21 and len(session["player"]) == 2:
                payout = int(bet * 2.5)
                note = "Blackjack! Cobraste 1.5x de ganancia."
            elif dval > 21 or pval > dval:
                payout = int(bet * 2)
                note = "Ganaste contra el dealer."
            elif pval == dval:
                payout = bet
                note = "Empate. Se devolvió la apuesta."
            else:
                payout = 0
                note = "Perdiste contra el dealer."

        if payout > 0:
            await safe_add(session["uid"], payout)

        blackjack_sessions.pop(session["uid"], None)

        embed = discord.Embed(title="🃏 Blackjack — Resultado", color=0x2F3136)
        embed.add_field(name="Jugador", value=f"{' '.join(session['player'])} → {pval}", inline=True)
        embed.add_field(name="Dealer", value=f"{' '.join(session['dealer'])} → {dval}", inline=True)
        embed.add_field(name="Nota", value=note, inline=False)

        if payout > 0:
            pago_texto = f"Recibiste **{fmt(int(payout))}** (incluye apuesta si aplica)"
        else:
            pago_texto = f"💸 Perdiste **{fmt(int(bet))}** de tu apuesta"

        embed.add_field(name="Pago", value=pago_texto, inline=False)
        embed.set_footer(text="RECO • Casino")

        try:
            await interaction.response.edit_message(embed=embed, view=None)
        except:
            await interaction.channel.send(embed=embed)


def embed_for_session(session):
    embed = discord.Embed(title="🃏 Blackjack", color=0x2F3136)
    embed.add_field(name="Jugador", value=f"{' '.join(session['player'])} → {hand_value(session['player'])}", inline=True)
    embed.add_field(name="Dealer", value=f"{session['dealer'][0]} ❓", inline=True)
    embed.add_field(name="Apuesta", value=f"{fmt(int(session['bet']))}", inline=False)
    embed.set_footer(text="Usá Hit o Stand. Si no respondés en 60s, perdés la mano.")
    return embed


@tree.command(name="blackjack", description="Jugá blackjack vs dealer (interactivo). Min 100")
@app_commands.describe(bet="Monto a apostar (número o 'a' para apostar todo)")
async def blackjack(interaction: discord.Interaction, bet: str):
    uid = str(interaction.user.id)
    balance = balances.get(uid, 0)

    # 🟢 Apuesta "a" = todo
    if bet.lower() == "a":
        bet = balance
    else:
        try:
            bet = int(bet)
        except ValueError:
            await interaction.response.send_message(
                embed=discord.Embed(
                    title="❌ Apuesta inválida",
                    description="Usá un número o 'a' para apostar todo.",
                    color=discord.Color.red(),
                ),
                ephemeral=True
            )
            return

    if bet < MIN_BET:
        await interaction.response.send_message(embed=dark_embed("❌ Monto muy bajo", f"Mínimo: {MIN_BET}"), ephemeral=True)
        return

    async with balances_lock:
        if balances.get(uid, 0) < bet:
            await interaction.response.send_message(embed=dark_embed("❌ Saldo insuficiente", "No tenés suficiente saldo."), ephemeral=True)
            return
        balances[uid] -= bet
        save_json(BALANCES_FILE, balances)

    # Crear sesión
    deck = DECK.copy()
    random.shuffle(deck)
    player = draw_from(deck, 2)
    dealer = draw_from(deck, 2)
    session = {"uid": uid, "player": player, "dealer": dealer, "deck": deck, "bet": bet}
    blackjack_sessions[uid] = session

    view = BlackjackView(uid, session, timeout=60)
    embed = embed_for_session(session)

    await interaction.response.send_message(embed=embed, view=view)
    view.message = await interaction.original_response()


# ---------- Crash (interactivo con cashout) ----------
@tree.command(name="crash", description="Apostá y tratá de no crashear 💥")
@app_commands.describe(bet="Monto a apostar (o 'a' para todo)", target="Multiplicador que querés alcanzar (ej: 2.5)")
async def crash(interaction: discord.Interaction, bet: str, target: float):
    user_id = str(interaction.user.id)
    balance = balances.get(user_id, 0)

    # 🟢 Si el usuario pone 'a', apostamos todo
    if bet.lower() == "a":
        bet = balance
    else:
        try:
            bet = float(bet)
        except ValueError:
            await interaction.response.send_message(
                embed=discord.Embed(
                    title="❌ Apuesta inválida",
                    description="Usá un número o 'a' para apostar todo.",
                    color=discord.Color.red(),
                )
            )
            return

    if bet < 100:
        await interaction.response.send_message(embed=discord.Embed(
            title="💥 Apuesta mínima: 100 monedas",
            color=discord.Color.dark_red()
        ))
        return
    if target <= 1.0:
        await interaction.response.send_message(embed=discord.Embed(
            title="❌ Objetivo inválido",
            description="El multiplicador debe ser mayor a 1.0",
            color=discord.Color.dark_red()
        ))
        return
    if balance < bet:
        await interaction.response.send_message(embed=discord.Embed(
            title="❌ Saldo insuficiente",
            color=discord.Color.red()
        ))
        return

    await safe_subtract(user_id, bet)

    # Crash point aleatorio (entre 1.0 y 10.0 con sesgo a valores bajos)
    crash_point = round(random.uniform(1.0, random.uniform(2.0, 10.0)), 2)

    # Mandamos el primer mensaje y guardamos el objeto del mensaje
    embed = discord.Embed(
        title="🚀 Crash en progreso...",
        description="El multiplicador está subiendo... ⏳",
        color=discord.Color.dark_gray()
    )
    await interaction.response.send_message(embed=embed)
    msg = await interaction.original_response()  # ✅ este es el mensaje editable

    multiplier = 1.0
    while multiplier < crash_point:
        await asyncio.sleep(0.6)
        multiplier = round(multiplier + random.uniform(0.1, 0.3), 2)
        embed = discord.Embed(
            title="🚀 Crash en progreso...",
            description=f"**x{multiplier}**",
            color=discord.Color.dark_gray()
        )
        await msg.edit(embed=embed)

    # Resultado final
    if crash_point >= target:
        payout = bet * target
        await safe_add(user_id, payout)
        result = discord.Embed(
            title="💎 Crash — ¡Ganaste!",
            description=f"💥 El crash llegó a **x{crash_point}**\nCobraste **{payout:,.2f}** monedas",
            color=discord.Color.green()
        )
    else:
        result = discord.Embed(
            title="💥 Crash — Perdiste",
            description=f"❌ Crash en **x{crash_point}** antes de tu objetivo de **x{target}**\nPerdiste **{bet:,.2f}** monedas",
            color=discord.Color.red()
        )

    result.set_footer(text="RECO • Casino")
    await msg.edit(embed=result)

# ---------- Battles (High Card) ----------
active_battles = {}  # guild -> battle dict

@tree.command(name="battle_start", description="Iniciar batalla (High Card). Crea una sala.")
@app_commands.describe(min_players="Jugadores mínimos (default 2)", timeout="Segundos para unirse (default 30)")
async def battle_start(interaction: discord.Interaction, min_players: int = 2, timeout: int = 30):
    guild = str(interaction.guild.id)
    if guild in active_battles and active_battles[guild]["state"] == "open":
        await interaction.response.send_message(embed=dark_embed("⚠️ Ya hay una batalla abierta", "Usá /battle_join para unirte."), ephemeral=True)
        return
    active_battles[guild] = {"creator": str(interaction.user.id), "players": {}, "pot": 0, "state": "open", "min_players": max(2,min_players)}
    embed = dark_embed("🎴 Batalla abierta", f"{interaction.user.mention} abrió una batalla.\nUsá `/battle_join <amount>` para entrar.\nTiempo: {timeout}s", 0x8E44AD)
    await interaction.response.send_message(embed=embed)
    await asyncio.sleep(timeout)
    battle = active_battles.get(guild)
    if not battle or battle["state"] != "open":
        return
    if len(battle["players"]) < battle["min_players"]:
        # refund
        for uid, info in battle["players"].items():
            await safe_add(uid, info["amount"])
        active_battles.pop(guild, None)
        await interaction.channel.send(embed=dark_embed("⚠️ Batalla cancelada", "No se alcanzó el mínimo de jugadores. Apuestas devueltas.", 0xE67E22))
        return
    # start battle
    battle["state"] = "running"
    deck = DECK.copy()
    random.shuffle(deck)
    results = []
    for uid, info in battle["players"].items():
        card = draw_from(deck,1)[0]
        val = hand_value([card])
        results.append((uid, info["amount"], card, val))
    maxv = max(r[3] for r in results)
    winners = [r for r in results if r[3] == maxv]
    split = battle["pot"] / len(winners)
    for w in winners:
        await safe_add(w[0], int(split))
    desc = ""
    for uid, amt, card, val in results:
        try:
            member = await interaction.guild.fetch_member(int(uid))
            name = member.display_name
        except:
            name = uid
        desc += f"**{name}**: {card} → {val} (apostó {fmt(int(amt))})\n"
    win_names = ", ".join([(await interaction.guild.fetch_member(int(w[0]))).display_name for w in winners])
    embed = discord.Embed(title="🏆 Battle Results", description=desc, color=0xF39C12)
    embed.add_field(name="Ganador(es)", value=f"{win_names}\nCada uno ganó **{fmt(int(split))}**", inline=False)
    await interaction.channel.send(embed=embed)
    active_battles.pop(guild, None)
#----------BATTLE JOIN----------
@tree.command(name="battle_join", description="Unite a la batalla abierta")
@app_commands.describe(amount="Apuesta")
async def battle_join(interaction: discord.Interaction, amount: int):
    if amount < MIN_BET:
        await interaction.response.send_message(embed=dark_embed("❌ Monto muy bajo", f"Mínimo: {MIN_BET}"), ephemeral=True)
        return
    guild = str(interaction.guild.id)
    if guild not in active_battles or active_battles[guild]["state"] != "open":
        await interaction.response.send_message(embed=dark_embed("⚠️ No hay batalla abierta", "Usá /battle_start para crear una."), ephemeral=True)
        return
    uid = str(interaction.user.id)
    async with balances_lock:
        if balances.get(uid,0) < amount:
            await interaction.response.send_message(embed=dark_embed("❌ Saldo insuficiente", "No tenés suficientes monedas."), ephemeral=True)
            return
        balances[uid] -= amount
        save_json(BALANCES_FILE, balances)
    active_battles[guild]["players"][uid] = {"amount": amount}
    active_battles[guild]["pot"] += amount
    await interaction.response.send_message(embed=dark_embed("🎴 Te uniste a la batalla", f"Apostaste **{fmt(amount)}**. Pot: **{fmt(int(active_battles[guild]['pot']))}**", 0x1ABC9C))
#-------------------LEADERBOARD-------------------
@tree.command(name="leaderboard", description="📊 Ver el top 10 de los jugadores más ricos del servidor")
async def leaderboard(interaction: discord.Interaction):
    # Ordenar balances
    sorted_balances = sorted(balances.items(), key=lambda x: x[1], reverse=True)
    top = sorted_balances[:10]

    embed = discord.Embed(
        title="🏆 Top 10 Jugadores Más Ricos",
        color=discord.Color.dark_gold(),
        description="💰 *Los más poderosos del casino RECO...*"
    )

    for i, (user_id, coins) in enumerate(top, start=1):
        try:
            user = await interaction.client.fetch_user(int(user_id))
            name = user.display_name
        except:
            name = f"Usuario {user_id}"

        medal = "🥇" if i == 1 else "🥈" if i == 2 else "🥉" if i == 3 else "💸"
        embed.add_field(
            name=f"{medal} {i}. {name}",
            value=f"**{coins:,.0f} monedas**",
            inline=False
        )

    embed.set_footer(text="RECO • Ranking económico global")
    await interaction.response.send_message(embed=embed)

# ----------------- READY -----------------
@bot.event
async def on_ready():
    await tree.sync()
    print(f"Comandos sincronizados. Bot listo como {bot.user}")

# ----------------- RUN -----------------
def load_json(filename):
    if os.path.exists(filename):
        with open(filename, "r") as f:
            return json.load(f)
    return {}

def save_json(filename, data):
    with open(filename, "w") as f:
        json.dump(data, f, indent=4)

# cargar balances sin reiniciar
balances = load_json(BALANCES_FILE)
shared_accounts = load_json(SHARED_FILE)

if __name__ == "__main__":
    load_dotenv()
    TOKEN = os.getenv("TOKEN")
    keep_alive()  # importante: antes del bot.run()
    bot.run(TOKEN)
