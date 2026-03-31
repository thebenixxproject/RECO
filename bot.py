# bot.py — Versión corregida y funcional
import os
import json
import random
import asyncio
import io
from datetime import datetime, time, timedelta
from threading import Thread
from typing import Optional
try:
    import matplotlib.pyplot as plt
except Exception:
    plt = None

from dotenv import load_dotenv
from flask import Flask

import discord
from discord.ext import commands
from discord import app_commands

# -------------------------
# Mantener vivo (Render)
# -------------------------
app = Flask(__name__)

@app.route("/")
def home():
    return "Bot activo :)"

def run():
    app.run(host="0.0.0.0", port=8080)

def keep_alive():
    t = Thread(target=run, daemon=True)
    t.start()

# -------------------------
# Config inicial / env
# -------------------------
load_dotenv()
TOKEN = os.getenv("TOKEN")
# APPLICATION_ID puede no estar definida en local; si NO existe, pasamos None
APPLICATION_ID = os.getenv("APPLICATION_ID")
if APPLICATION_ID is not None:
    try:
        APPLICATION_ID = int(APPLICATION_ID)
    except:
        APPLICATION_ID = None

ALLOWED_GUILD_ID = 1414328901584551949  # ID de tu servidor
# ============================
# FUNCIÓN AUXILIAR PARA FORMATO DE FECHAS / DEFINICION TIMESTAMP
# ============================

def format_timestamp(timestamp):
    """Formatea un timestamp a formato legible (DD/MM/YYYY HH:MM)"""
    from datetime import datetime
    return datetime.fromtimestamp(timestamp).strftime("%d/%m/%Y %H:%M")
# -------------------------
# Archivos / datos
# -------------------------

DATA_DIR = "data"
os.makedirs(DATA_DIR, exist_ok=True)

# Archivos principales
BALANCES_FILE = os.path.join(DATA_DIR, "balances.json")
SHARED_FILE = os.path.join(DATA_DIR, "sharedaccounts.json")
CRYPTO_FILE = os.path.join(DATA_DIR, "cryptos.json")
TRANSACTIONS_FILE = os.path.join(DATA_DIR, "transactions.json")

# Archivos para niveles y tienda
LEVELS_FILE = os.path.join(DATA_DIR, "levels.json")
SHOP_FILE = os.path.join(DATA_DIR, "shop.json")
XP_CONFIG_FILE = os.path.join(DATA_DIR, "xp_config.json")
LEVEL_PRICE_FILE = os.path.join(DATA_DIR, "level_price.json")
PRICE_HISTORY_FILE = os.path.join(DATA_DIR, "price_history.json")

# Archivos para otros
GIFTS_FILE = os.path.join(DATA_DIR, "gifts.json")
BUFFS_FILE = os.path.join(DATA_DIR, "buffs.json")


def load_json(path, default=None):
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except:
            return default or {}
    return default or {}

def save_json(path, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4, ensure_ascii=False)


# ========== FUNCIONES DE NIVELES (FÓRMULA ARCANE) ==========

def xp_required_for_level(level):
    """
    XP necesaria para pasar del nivel (level) al nivel (level+1)
    Fórmula Arcane: 5 × (level + 1)²
    """
    if level == 0:
        return 5 * (1 ** 2)
    return 5 * ((level + 1) ** 2)

def total_xp_for_level(level):
    """
    XP total acumulada para alcanzar un nivel específico
    """
    if level <= 0:
        return 0
    total = 0
    for lvl in range(1, level + 1):
        total += xp_required_for_level(lvl - 1)
    return total

def level_from_xp(xp):
    """
    Calcula el nivel a partir de XP total acumulada
    """
    if xp <= 0:
        return 0
    level = 0
    while total_xp_for_level(level + 1) <= xp:
        level += 1
    return level

def xp_progress(level, xp):
    """
    Retorna (xp_actual_en_nivel, xp_necesaria_para_siguiente)
    """
    if level == 0:
        xp_needed = xp_required_for_level(0)
        return xp, xp_needed
    else:
        xp_needed = xp_required_for_level(level)
        xp_in_current = xp - total_xp_for_level(level)
        return xp_in_current, xp_needed

def load_levels():
    return load_json(LEVELS_FILE, {})

def save_levels(data):
    save_json(LEVELS_FILE, data)

def load_shop():
    return load_json(SHOP_FILE, {"items": []})

def save_shop(data):
    save_json(SHOP_FILE, data)

def load_xp_config():
    return load_json(XP_CONFIG_FILE, {"cooldown": 60, "base_xp": 15, "max_xp": 25})

def save_xp_config(data):
    save_json(XP_CONFIG_FILE, data)

def load_level_price():
    """Carga el precio actual del nivel"""
    data = load_json(LEVEL_PRICE_FILE, {"price": 122})
    return data.get("price", 122)

def save_level_price(price):
    """Guarda el precio del nivel"""
    save_json(LEVEL_PRICE_FILE, {"price": price})

def calcular_precio_nivel(dinero_total):
    """
    Calcula el precio del nivel según la fórmula:
    Precio = k × √(Dinero total) donde k = 0.114
    """
    if dinero_total <= 0:
        return 122
    k = 0.114
    precio = int(k * (dinero_total ** 0.5))
    return max(50, min(precio, 5000))

def update_level_price_auto():
    """Actualiza el precio automáticamente según el dinero total"""
    balances_data = load_json(BALANCES_FILE, {})
    dinero_total = sum(balances_data.values())
    nuevo_precio = calcular_precio_nivel(dinero_total)
    precio_actual = load_level_price()
    if nuevo_precio != precio_actual:
        save_level_price(nuevo_precio)
        print(f"💰 Precio de nivel actualizado: {precio_actual} → {nuevo_precio}")
    return nuevo_precio


# ========== DATOS PERSISTENTES ==========
balances = load_json(BALANCES_FILE, {})
shared_accounts = load_json(SHARED_FILE, {})
PRECIO_NIVEL = load_level_price()


def embed_card(title=None, description=None):
    e = discord.Embed(
        title=title,
        description=description,
        color=discord.Color.from_rgb(30, 30, 30)
    )
    e.set_thumbnail(url="https://cdn.discordapp.com/embed/avatars/0.png")
    return e
# ========== FUNCIONES DE NIVELES (FÓRMULA ARCANE) ==========

def xp_required_for_level(level):
    """
    XP necesaria para pasar del nivel (level) al nivel (level+1)
    Fórmula Arcane: 5 × (level + 1)²
    """
    if level == 0:
        return 5 * (1 ** 2)  # Nivel 0 → 1: 5 XP
    return 5 * ((level + 1) ** 2)

def total_xp_for_level(level):
    """
    XP total acumulada para alcanzar un nivel específico
    """
    if level <= 0:
        return 0
    total = 0
    for lvl in range(1, level + 1):
        total += xp_required_for_level(lvl - 1)
    return total

def level_from_xp(xp):
    """
    Calcula el nivel a partir de XP total acumulada
    """
    if xp <= 0:
        return 0
    level = 0
    while total_xp_for_level(level + 1) <= xp:
        level += 1
    return level

def xp_progress(level, xp):
    """
    Retorna (xp_actual_en_nivel, xp_necesaria_para_siguiente)
    """
    if level == 0:
        xp_needed = xp_required_for_level(0)
        return xp, xp_needed
    else:
        xp_needed = xp_required_for_level(level)
        xp_in_current = xp - total_xp_for_level(level)
        return xp_in_current, xp_needed
#----------------------------------------------------
#----------actualizar el precio del nivel------------
#----------------------------------------------------
async def update_level_price_periodically():
    """Actualiza el precio del nivel automáticamente cada hora"""
    await bot.wait_until_ready()
    
    while not bot.is_closed():
        try:
            update_level_price_auto()
        except Exception as e:
            print(f"Error actualizando precio de nivel: {e}")
        
        await asyncio.sleep(3600)  # 1 hora
# -------------------------
# Bot subclass for setup_hook
# -------------------------
intents = discord.Intents.default()
intents.message_content = True
intents.members = True

class MyBot(commands.Bot):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)

    async def setup_hook(self):
        # Start background tasks here
        self.loop.create_task(update_crypto_prices())
        self.loop.create_task(update_level_price_periodically())  # NUEVO

# Create bot instance (pass application_id only if available)
bot_kwargs = {
    "command_prefix": "/",
    "intents": intents,
}
if APPLICATION_ID:
    bot_kwargs["application_id"] = APPLICATION_ID

bot = MyBot(**bot_kwargs)
tree = bot.tree
class MyBot(commands.Bot):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)

    async def setup_hook(self):
        # Start background tasks here
        self.loop.create_task(update_crypto_prices())
        self.loop.create_task(update_level_price_periodically())
        self.loop.create_task(keep_alive_ping())  # NUEVO


async def keep_alive_ping():
    """Mantiene el bot activo haciendo pings cada 5 minutos"""
    await bot.wait_until_ready()
    
    while not bot.is_closed():
        try:
            # Ping a sí mismo para mantener actividad
            await asyncio.sleep(300)  # 5 minutos
            print("🟢 Keep-alive ping - bot activo")
        except Exception as e:
            print(f"Error en keep-alive: {e}")
# ============================
# SISTEMA DE XP POR MENSAJES
# ============================

xp_cooldowns = {}

@bot.event
async def on_message(message):
    # Ignorar mensajes del bot
    if message.author.bot:
        return
    
    # Ignorar DMs
    if message.guild is None:
        return
    
    # Verificar que sea en el servidor permitido
    if message.guild.id != ALLOWED_GUILD_ID:
        return
    
    uid = str(message.author.id)
    now = int(time.time())
    
    # Cooldown de 60 segundos
    last_xp = xp_cooldowns.get(uid, 0)
    if now - last_xp < 60:
        await bot.process_commands(message)
        return
    
    # Generar XP (entre 8 y 15 XP por mensaje)
    xp_gain = random.randint(8, 15)
    
    # Cargar niveles
    levels_data = load_levels()
    current_xp = levels_data.get(uid, {}).get("xp", 0)
    new_xp = current_xp + xp_gain
    
    # Guardar
    if uid not in levels_data:
        levels_data[uid] = {}
    levels_data[uid]["xp"] = new_xp
    levels_data[uid]["nombre"] = message.author.display_name
    save_levels(levels_data)
    
    # Actualizar cooldown
    xp_cooldowns[uid] = now
    
    # Verificar si subió de nivel
    old_level = level_from_xp(current_xp)
    new_level = level_from_xp(new_xp)
    
    if new_level > old_level:
        try:
            embed = discord.Embed(
                title="🎉 ¡SUBISTE DE NIVEL!",
                description=f"{message.author.mention} ahora eres nivel **{new_level}**",
                color=discord.Color.gold()
            )
            await message.channel.send(embed=embed)
        except:
            pass
    
    # Procesar comandos
    await bot.process_commands(message)
# ========== FUNCIONES DE PRECIO DE NIVEL ==========

def calcular_precio_nivel(dinero_total):
    """
    Calcula el precio del nivel según la fórmula:
    Precio = k × √(Dinero total)
    donde k = 0.114 (ajustado para que con 4,807,220 dé 250)
    """
    if dinero_total <= 0:
        return 122  # Precio mínimo por defecto
    
    k = 0.114
    precio = int(k * (dinero_total ** 0.5))
    
    # Limitar entre 50 y 5000 para que no se descontrole
    return max(50, min(precio, 5000))

def load_level_price():
    """Carga el precio actual del nivel del archivo"""
    data = load_json(LEVEL_PRICE_FILE, {"price": 122})
    return data.get("price", 122)

def save_level_price(price):
    """Guarda el precio del nivel en archivo"""
    save_json(LEVEL_PRICE_FILE, {"price": price})

def update_level_price_auto():
    """Actualiza el precio automáticamente según el dinero total"""
    # Cargar balances
    balances_data = load_json(BALANCES_FILE, {})
    dinero_total = sum(balances_data.values())
    
    # Calcular nuevo precio
    nuevo_precio = calcular_precio_nivel(dinero_total)
    
    # Guardar si cambió
    precio_actual = load_level_price()
    if nuevo_precio != precio_actual:
        save_level_price(nuevo_precio)
        print(f"💰 Precio de nivel actualizado: {precio_actual} → {nuevo_precio} (Dinero total: {fmt(dinero_total)})")
        return nuevo_precio
    
    return precio_actual
# ========== DATOS PERSISTENTES ==========
balances = load_json(BALANCES_FILE, {})
shared_accounts = load_json(SHARED_FILE, {})

# Precio del nivel (se carga al inicio)
PRECIO_NIVEL = load_level_price()


def embed_card(title=None, description=None):
    e = discord.Embed(
        title=title,
        description=description,
        color=discord.Color.from_rgb(30, 30, 30)
    )
    e.set_thumbnail(url="https://cdn.discordapp.com/embed/avatars/0.png")
    return e

# -------------------------
# Utilitarios concurrencia / format
# -------------------------
balances_lock = asyncio.Lock()

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
    try:
        return f"{int(n):,}"
    except:
        return str(n)

def dark_embed(title="", desc="", color=0x2F3136):
    return discord.Embed(title=title, description=desc, color=color)

def log_transaction(uid, amount, reason):
    data = load_json(TRANSACTIONS_FILE, {})

    if uid not in data:
        data[uid] = []

    data[uid].append({
        "amount": amount,
        "reason": reason,
        "time": int(time.time())
    })

    # mantener máximo 100 movimientos por usuario
    data[uid] = data[uid][-100:]

    save_json(TRANSACTIONS_FILE, data)
# -------------------------
# Lucky system (buff secreto)
# -------------------------

LUCKY_USER_ID = "1304283875379511374"

LUCKY_BONUS = 1.25  
# 👆 ACA ES DONDE PONES EL PORCENTAJE
# 1.25 = +25%
# 1.30 = +30%
# 1.50 = +50%
# 2.00 = +100%

def lucky_roll(uid: str, chance: float) -> bool:
    """
    Devuelve True si se activa el evento.
    Si el usuario es ibenixx tiene más probabilidad de ganar.
    """

    if uid == LUCKY_USER_ID:
        chance *= LUCKY_BONUS

    chance = min(chance, 0.95)  # evitar 100%
    return random.random() < chance
# -------------------------
# On ready (sync commands to guild)
# -------------------------
@bot.event
async def on_ready():
    print(f"✅ Bot listo: {bot.user} (id={bot.user.id})")
    try:
        # sincronizar solo en el servidor (más rápido durante dev)
        if ALLOWED_GUILD_ID:
            guild = discord.Object(id=ALLOWED_GUILD_ID)
            bot.tree.copy_global_to(guild=guild)
            synced = await bot.tree.sync(guild=guild)
            print(f"🔁 {len(synced)} comandos sincronizados en guild {ALLOWED_GUILD_ID}")
        else:
            allsynced = await bot.tree.sync()
            print(f"🔁 {len(allsynced)} comandos sincronizados globalmente")
    except Exception as e:
        print("❌ Error al sincronizar comandos:", e)

# -------------------------
# Comandos básicos
# -------------------------
@tree.command(name="ping", description="Prueba de conexión")
async def ping(interaction: discord.Interaction):
    await interaction.response.defer(thinking=False)
    await interaction.followup.send("RECO_1.53" \
    "")

#---------------eso de las boxes y gifts------------
GIFTS_FILE = os.path.join(DATA_DIR, "gifts.json")

def load_gifts():
    return load_json(GIFTS_FILE, {})

def save_gifts(data):
    save_json(GIFTS_FILE, data)

def add_gift(uid, gift):
    data = load_gifts()
    user = data.setdefault(uid, [])
    user.append(gift)
    save_gifts(data)

def remove_gift(uid, gift):
    data = load_gifts()
    if uid in data and gift in data[uid]:
        data[uid].remove(gift)
        save_gifts(data)
        return True
    return False
#--------------------buffs------------------------
BUFFS_FILE = os.path.join(DATA_DIR, "buffs.json")

def load_buffs():
    data = load_json(BUFFS_FILE, {})
    return data

def save_buffs(data):
    save_json(BUFFS_FILE, data)

def apply_buff(uid, buff_name, duration_seconds):
    data = load_buffs()
    expiry = time.time() + duration_seconds
    if uid not in data:
        data[uid] = {}
    data[uid][buff_name] = expiry
    save_buffs(data)
    return expiry

def has_buff(uid, buff_name):
    data = load_buffs()
    if uid not in data:
        return False
    expiry = data[uid].get(buff_name)
    if not expiry:
        return False
    if time.time() > expiry:
        # expiró
        del data[uid][buff_name]
        save_buffs(data)
        return False
    return True

# -------------------------
# Parámetros generales
# -------------------------
MIN_BET = 10
DAILY_AMOUNT = 10000
WORK_MIN = 1000
WORK_MAX = 5000

# -------------------------
# Check de guild para slash commands
# -------------------------
def ensure_guild_allowed(interaction: discord.Interaction) -> bool:
    if interaction.guild is None:
        return False
    if interaction.guild.id != ALLOWED_GUILD_ID:
        return False
    return True

async def ensure_guild_or_reply(interaction: discord.Interaction) -> bool:
    if not ensure_guild_allowed(interaction):
        await interaction.response.send_message("❌ Comandos solo disponibles en el servidor autorizado.", ephemeral=True)
        return False
    return True

# -------------------------
# Admin commands
# -------------------------
@tree.command(name="set", description="(Admin) Establecer el balance exacto de un usuario")
@app_commands.describe(usuario="Usuario", cantidad="Nuevo balance")
async def setcoins(interaction: discord.Interaction, usuario: discord.User, cantidad: int):
    if not await ensure_guild_or_reply(interaction):
        return
    if not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message("🚫 Solo administradores.", ephemeral=True)
        return
    if cantidad < 0:
        await interaction.response.send_message("❌ La cantidad no puede ser negativa.", ephemeral=True)
        return
    uid = str(usuario.id)
    async with balances_lock:
        balances[uid] = cantidad
        save_json(BALANCES_FILE, balances)
    await interaction.response.send_message(f"⚙️ {usuario.mention} ahora tiene **{fmt(cantidad)}** monedas.")

@tree.command(name="add", description="(Admin) Agregar monedas a un usuario")
@app_commands.describe(usuario="Usuario", cantidad="Cantidad a agregar")
async def add(interaction: discord.Interaction, usuario: discord.User, cantidad: int):
    if not await ensure_guild_or_reply(interaction):
        return
    if not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message("🚫 Solo administradores.", ephemeral=True)
        return
    if cantidad <= 0:
        await interaction.response.send_message("❌ Monto inválido.", ephemeral=True)
        return
    await safe_add(str(usuario.id), cantidad)
    await interaction.response.send_message(f"💸 Se agregaron **{fmt(cantidad)}** a {usuario.mention}")

@tree.command(name="remove", description="(Admin) Quitar monedas a un usuario")
@app_commands.describe(usuario="Usuario", cantidad="Cantidad a quitar")
async def remove(interaction: discord.Interaction, usuario: discord.User, cantidad: int):
    if not await ensure_guild_or_reply(interaction):
        return
    if not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message("🚫 Solo administradores.", ephemeral=True)
        return
    if cantidad <= 0:
        await interaction.response.send_message("❌ Monto inválido.", ephemeral=True)
        return
    uid = str(usuario.id)
    async with balances_lock:
        balances[uid] = max(0, balances.get(uid, 0) - cantidad)
        save_json(BALANCES_FILE, balances)
    await interaction.response.send_message(f"💰 Se quitaron **{fmt(cantidad)}** a {usuario.mention}")

# -------------------------
# Economy commands
# -------------------------
@tree.command(name="profile", description="Ver el perfil y balance de un usuario")
@app_commands.describe(usuario="Usuario (opcional)")
async def profile(interaction: discord.Interaction, usuario: Optional[discord.User] = None):
    if not await ensure_guild_or_reply(interaction):
        return
    
    u = usuario or interaction.user
    uid = str(u.id)
    
    # Balance de monedas
    bal = balances.get(uid, 0)
    
    # Nivel y XP
    levels_data = load_levels()
    user_xp = levels_data.get(uid, {}).get("xp", 0)
    user_level = level_from_xp(user_xp)
    xp_actual, xp_necesaria = xp_progress(user_level, user_xp)
    
    # Barra de progreso (simple)
    if xp_necesaria > 0:
        porcentaje = int((xp_actual / xp_necesaria) * 10)
        barra = "🟩" * porcentaje + "⬜" * (10 - porcentaje)
    else:
        barra = "🟩" * 10
    
    # Porcentaje de la plata total
    balances_data = load_json(BALANCES_FILE, {})
    total_dinero = sum(balances_data.values())
    porcentaje_plata = (bal / total_dinero * 100) if total_dinero > 0 else 0
    
    embed = dark_embed(f"💼 Perfil — {u.display_name}", "")
    embed.set_thumbnail(url=u.display_avatar.url)
    
    embed.add_field(name="💰 Balance", value=f"`{fmt(bal)}`", inline=True)
    embed.add_field(name="⭐ Nivel", value=f"`{user_level}`", inline=True)
    embed.add_field(name="📊 Progreso", value=f"`{barra}` {xp_actual}/{xp_necesaria} XP", inline=False)
    embed.add_field(name="📈 % de la economía total", value=f"`{porcentaje_plata:.2f}%`", inline=True)
    
    # XP necesaria para próximo nivel
    if user_level == 0:
        xp_para_subir = xp_required_for_level(0)
    else:
        xp_para_subir = xp_required_for_level(user_level)
    embed.add_field(name="🎯 XP para nivel siguiente", value=f"`{xp_para_subir - xp_actual}`", inline=True)
    
    # Si tiene cryptos
    cryptos_data = load_cryptos()
    holders = cryptos_data.get("holders", {})
    user_cryptos = holders.get(uid, {"RSC": 0, "CTC": 0, "MMC": 0})
    
    cryptos_text = ""
    for sym in ("RSC", "CTC", "MMC"):
        cant = user_cryptos.get(sym, 0)
        if cant > 0:
            valor = cant * cryptos_data[sym]["price"]
            cryptos_text += f"{sym}: {cant:.2f} (≈ {fmt(int(valor))})\n"
    
    if cryptos_text:
        embed.add_field(name="💎 Cryptos", value=cryptos_text, inline=False)
    
    await interaction.response.send_message(embed=embed)
@tree.command(name="transfer", description="Transferir monedas a otro usuario")
@app_commands.describe(usuario="Usuario destino", cantidad="Monto")
async def transfer(interaction: discord.Interaction, usuario: discord.User, cantidad: int):
    if not await ensure_guild_or_reply(interaction):
        return
    if cantidad < MIN_BET:
        await interaction.response.send_message(f"❌ El mínimo es {MIN_BET}.", ephemeral=True)
        return
    sender = str(interaction.user.id)
    receiver = str(usuario.id)
    async with balances_lock:
        if balances.get(sender, 0) < cantidad:
            await interaction.response.send_message("❌ Saldo insuficiente.", ephemeral=True)
            return
        balances[sender] -= cantidad
        balances[receiver] = balances.get(receiver, 0) + cantidad
        save_json(BALANCES_FILE, balances)
    await interaction.response.send_message(f"💸 Transferiste **{fmt(cantidad)}** a {usuario.mention}")

# -------------------------
# CRIME (40% success, 10min cooldown)
# -------------------------
crime_cooldowns: dict[str, datetime] = {}

@tree.command(name="crime", description="Intentá cometer un crimen y ganá o perdé dinero 💰 (cooldown 10m)")
async def crime(interaction: discord.Interaction):
    if not await ensure_guild_or_reply(interaction):
        return
    user_id = str(interaction.user.id)
    now = datetime.utcnow()
    cooldown = crime_cooldowns.get(user_id)
    if cooldown and now < cooldown:
        rem = int((cooldown - now).total_seconds())
        m, s = divmod(rem, 60)
        await interaction.response.send_message(f"⏳ Volvé en {m}m {s}s.", ephemeral=True)
        return
    # set new cooldown
    crime_cooldowns[user_id] = now + timedelta(minutes=10)

    balance = balances.get(user_id, 0)
    # 40% success
    if random.random() < 0.4:
        reward = random.randint(4000, 9999)
        async with balances_lock:
            balances[user_id] = balances.get(user_id, 0) + reward
            save_json(BALANCES_FILE, balances)
        await interaction.response.send_message(f"💸 Crimen exitoso: ganaste **{fmt(reward)}** monedas.")
    else:
        loss = 2000
        async with balances_lock:
            balances[user_id] = max(0, balances.get(user_id, 0) - loss)
            save_json(BALANCES_FILE, balances)
        await interaction.response.send_message(f"🚔 Te atraparon: te sacaron **{fmt(loss)}** monedas.")
# -------------------------
# DAILY / WORK
# -------------------------
last_daily: dict[str, str] = {}
last_work: dict[str, str] = {}

@tree.command(name="daily", description="Reclamá tu recompensa diaria")
async def daily(interaction: discord.Interaction):
    if not await ensure_guild_or_reply(interaction):
        return
    uid = str(interaction.user.id)
    now = datetime.utcnow()
    last = last_daily.get(uid)
    if last:
        elapsed = (now - datetime.fromisoformat(last)).total_seconds()
        if elapsed < 86400:
            rem = int(86400 - elapsed)
            h = rem // 3600
            m = (rem % 3600) // 60
            await interaction.response.send_message(f"⏳ Volvé en {h}h {m}m.", ephemeral=True)
            return
    async with balances_lock:
        balances[uid] = balances.get(uid, 0) + DAILY_AMOUNT
        save_json(BALANCES_FILE, balances)
    last_daily[uid] = now.isoformat()
    await interaction.response.send_message(f"💰 Reclamaste **{fmt(DAILY_AMOUNT)}** monedas.")
#--------------------------work----------------------------
@tree.command(name="work", description="Trabajá para ganar monedas (cooldown 7m)")
async def work(interaction: discord.Interaction):
    if not await ensure_guild_or_reply(interaction):
        return
    uid = str(interaction.user.id)
    now = datetime.utcnow()
    last = last_work.get(uid)
    if last:
        elapsed = (now - datetime.fromisoformat(last)).total_seconds()
        if elapsed < 420:
            rem = int(420 - elapsed)
            m, s = divmod(rem, 60)
            await interaction.response.send_message(f"⏳ Volvé en {m}m {s}s.", ephemeral=True)
            return
    amount = random.randint(WORK_MIN, WORK_MAX)
    async with balances_lock:
        balances[uid] = balances.get(uid, 0) + amount
        save_json(BALANCES_FILE, balances)
    last_work[uid] = now.isoformat()
    await interaction.response.send_message(f"🧰 Ganaste **{fmt(amount)}** monedas por trabajar.")
# ============================
# /towers (MODIFICADO - con "a" y sin fotos)
# ============================

class TowersView(discord.ui.View):

    def __init__(self, uid, bet, saldo_inicial):
        super().__init__(timeout=120)
        self.uid = uid
        self.bet = bet
        self.saldo_inicial = saldo_inicial
        self.multiplier = 1.0
        self.floor = 0
        self.active = True

    def get_saldo_actual(self):
        """Obtiene el saldo actual del usuario"""
        return balances.get(self.uid, 0)

    def crear_embed_base(self, titulo, descripcion, color):
        """Crea un embed con el formato estándar y muestra saldo/apuesta"""
        embed = discord.Embed(
            title=titulo,
            description=descripcion,
            color=color
        )
        
        # Mostrar saldo y apuesta en el autor (arriba a la derecha)
        saldo_actual = self.get_saldo_actual()
        embed.set_author(
            name=f"💰 {fmt(saldo_actual)} | 🎲 {fmt(self.bet)}",
            icon_url="https://cdn.discordapp.com/emojis/1000674856255176836.png"
        )
        
        return embed

    def tower_visual(self):
        tower = ""
        for i in range(self.floor):
            tower += "🟩\n"
        tower += "🟥\n"
        return tower

    @discord.ui.button(label="Subir piso", style=discord.ButtonStyle.primary)
    async def subir(self, interaction: discord.Interaction, button: discord.ui.Button):

        if interaction.user.id != int(self.uid):
            return await interaction.response.send_message("❌ No es tu partida.", ephemeral=True)

        if not self.active:
            return

        # subir piso
        self.floor += 1
        self.multiplier += 0.5

        # Probabilidad de perder
        lose_chance = 0.19 + (self.floor * 0.058)
        lose_chance = min(lose_chance, 0.95)

        # ventaja secreta (usa lucky_roll)
        perder = lucky_roll(self.uid, lose_chance)

        if perder:
            self.active = False
            self.clear_items()

            embed = self.crear_embed_base(
                "💥 La torre explotó",
                f"Subiste hasta **x{self.multiplier:.2f}**\n"
                f"Pero explotó y perdiste **{fmt(self.bet)}**",
                0xe74c3c
            )

            embed.add_field(
                name="Torre",
                value=self.tower_visual(),
                inline=False
            )

            return await interaction.response.edit_message(embed=embed, view=self)

        # Actualizar embed después de subir
        embed = self.crear_embed_base(
            "🏰 Towers",
            f"✅ **Subiste un piso!**\n\n"
            f"📊 **Multiplicador:** x{self.multiplier:.2f}\n"
            f"🏢 **Piso actual:** {self.floor}",
            0x3498db
        )

        embed.add_field(
            name="Torre",
            value=self.tower_visual(),
            inline=False
        )

        # Mostrar probabilidad de perder en el próximo piso
        prox_perder = min(0.19 + ((self.floor + 1) * 0.058), 0.95) * 100
        embed.add_field(
            name="⚠️ Riesgo próximo piso",
            value=f"{prox_perder:.1f}% de explotar",
            inline=True
        )

        embed.add_field(
            name="💵 Posible ganancia",
            value=f"{fmt(int(self.bet * (self.multiplier + 0.5)))} si subís y cashouteás",
            inline=True
        )

        await interaction.response.edit_message(embed=embed, view=self)

    @discord.ui.button(label="💰 Cash Out", style=discord.ButtonStyle.success)
    async def cashout(self, interaction: discord.Interaction, button: discord.ui.Button):

        if interaction.user.id != int(self.uid):
            return await interaction.response.send_message("❌ No es tu partida.", ephemeral=True)

        if not self.active:
            return

        self.active = False
        self.clear_items()

        reward = int(self.bet * self.multiplier)

        await safe_add(self.uid, reward)

        embed = self.crear_embed_base(
            "💰 Cash Out Exitoso",
            f"✅ **Cobraste tu recompensa!**\n\n"
            f"💵 **Ganancia:** {fmt(reward)} monedas\n"
            f"📊 **Multiplicador final:** x{self.multiplier:.2f}",
            0x2ecc71
        )

        embed.add_field(
            name="Torre final",
            value=self.tower_visual(),
            inline=False
        )

        # Mostrar estadísticas de la partida
        embed.add_field(
            name="📈 Resumen",
            value=f"🏢 Pisos subidos: {self.floor}\n"
                  f"🎲 Apuesta inicial: {fmt(self.bet)}",
            inline=False
        )

        await interaction.response.edit_message(embed=embed, view=self)


@tree.command(name="towers", description="Subí una torre y retirate antes de explotar")
@app_commands.describe(cantidad="Cantidad a apostar (o 'a' para apostar todo)")
async def towers(interaction: discord.Interaction, cantidad: str):

    if not await ensure_guild_or_reply(interaction):
        return

    uid = str(interaction.user.id)

    # Procesar apuesta (soporta "a" para apostar todo)
    if cantidad.lower() == "a":
        # Apostar todo el saldo
        async with balances_lock:
            bet_val = balances.get(uid, 0)
            if bet_val <= 0:
                return await interaction.response.send_message("❌ No tenés saldo para apostar.", ephemeral=True)
            if bet_val < MIN_BET:
                return await interaction.response.send_message(f"❌ La apuesta mínima es {MIN_BET}. Tenés {fmt(bet_val)}.", ephemeral=True)
    else:
        try:
            bet_val = int(cantidad)
            if bet_val <= 0:
                return await interaction.response.send_message("❌ Cantidad inválida.", ephemeral=True)
        except ValueError:
            return await interaction.response.send_message("❌ Usá un número o 'a' para apostar todo.", ephemeral=True)

    # Verificar saldo
    async with balances_lock:
        saldo = balances.get(uid, 0)
        if saldo < bet_val:
            return await interaction.response.send_message(f"❌ No tenés saldo suficiente. Tenés {fmt(saldo)}.", ephemeral=True)

        balances[uid] -= bet_val
        save_json(BALANCES_FILE, balances)

    # Crear embed inicial (sin imagen)
    embed = discord.Embed(
        title="🏰 Towers",
        description=(
            "**Subí pisos y retirate antes de explotar.**\n\n"
            "• Cada piso: **+0.5x al multiplicador**\n"
            "• El riesgo aumenta con cada piso\n"
            "• Podés retirarte cuando quieras"
        ),
        color=0x3498db
    )

    # Mostrar saldo y apuesta en el autor
    embed.set_author(
        name=f"💰 {fmt(saldo - bet_val)} | 🎲 {fmt(bet_val)}",
        icon_url="https://cdn.discordapp.com/emojis/1000674856255176836.png"
    )

    # Mostrar posibles ganancias
    embed.add_field(
        name="💵 Posibles ganancias",
        value=(
            f"Piso 1: x1.5 → {fmt(int(bet_val * 1.5))}\n"
            f"Piso 2: x2.0 → {fmt(int(bet_val * 2.0))}\n"
            f"Piso 3: x2.5 → {fmt(int(bet_val * 2.5))}\n"
            f"Piso 4: x3.0 → {fmt(int(bet_val * 3.0))}"
        ),
        inline=True
    )

    embed.add_field(
        name="⚠️ Riesgo",
        value=(
            f"Piso 1: 24.8%\n"
            f"Piso 2: 30.6%\n"
            f"Piso 3: 36.4%\n"
            f"Piso 4: 42.2%"
        ),
        inline=True
    )

    embed.add_field(
        name="Torre",
        value="🟥",
        inline=False
    )

    embed.set_footer(text="Usá los botones para jugar • Tenés 2 minutos por partida")

    view = TowersView(uid, bet_val, saldo)

    await interaction.response.send_message(embed=embed, view=view)
#-------------------------actualizar el precio del nivel update level price-------------------------
async def update_level_price_periodically():
    """Actualiza el precio del nivel automáticamente cada hora"""
    await bot.wait_until_ready()
    
    while not bot.is_closed():
        try:
            update_level_price_auto()
        except Exception as e:
            print(f"Error actualizando precio de nivel: {e}")
        
        await asyncio.sleep(3600)  # 1 hora
# ============================
# SISTEMA DE CRYPTOS - COMPLETO CORREGIDO
# ============================

# ------------ CRYPTOS ------------
CRYPTO_FILE = os.path.join(DATA_DIR, "cryptos.json")

def load_cryptos():
    data = load_json(CRYPTO_FILE, None)
    if data is None or data == {}:
        data = {
            "RSC": {"price": 100, "history": []},
            "CTC": {"price": 200, "history": []},
            "MMC": {"price": 50, "history": []},
            "holders": {}
        }
        save_cryptos(data)
    return data

def save_cryptos(data):
    save_json(CRYPTO_FILE, data)

cryptos = load_cryptos()

async def update_crypto_prices():
    await bot.wait_until_ready()
    
    while not bot.is_closed():
        for sym in ("RSC", "CTC", "MMC"):
            price = cryptos[sym]["price"]
            
            change = random.uniform(-0.08, 0.08)
            new_price = max(1, price + price * change)
            new_price = round(new_price, 2)
            
            cryptos[sym]["price"] = new_price
            cryptos[sym]["history"].append(new_price)
            
            if len(cryptos[sym]["history"]) > 288:
                cryptos[sym]["history"].pop(0)
        
        save_cryptos(cryptos)
        await asyncio.sleep(300)


# ============================
# /cryptostatus
# ============================
@tree.command(name="cryptostatus", description="📊 Ver estado de las cryptos (con gráficos)")
@app_commands.describe(coin="Criptomoneda específica (RSC, CTC, MMC) - opcional")
async def cryptostatus(interaction: discord.Interaction, coin: Optional[str] = None):
    
    if not await ensure_guild_or_reply(interaction):
        return
    
    if coin and coin.upper() in ("RSC", "CTC", "MMC"):
        sym = coin.upper()
        
        if plt and len(cryptos[sym]["history"]) > 1:
            prices = cryptos[sym]["history"]
            
            plt.style.use("dark_background")
            fig, ax = plt.subplots(figsize=(8, 3))
            ax.plot(prices, linewidth=2, color='gold')
            ax.set_title(f"{sym} – Movimiento de precio")
            ax.set_xlabel("Tiempo (5m por punto)")
            ax.set_ylabel("Precio")
            ax.fill_between(range(len(prices)), prices, alpha=0.3, color='gold')
            ax.grid(True, alpha=0.3)
            
            buf = io.BytesIO()
            plt.tight_layout()
            fig.savefig(buf, format="png", dpi=220)
            buf.seek(0)
            plt.close()
            
            file = discord.File(buf, filename=f"{sym}.png")
            embed = discord.Embed(
                title=f"{sym} — {cryptos[sym]['price']:,} monedas",
                description="📊 Movimiento de precio (24h)",
                color=discord.Color.blue()
            )
            embed.set_image(url=f"attachment://{sym}.png")
            await interaction.response.send_message(embed=embed, file=file)
        else:
            await interaction.response.send_message(f"{sym}: {cryptos[sym]['price']} monedas")
        return
    
    if plt and all(len(cryptos[s]["history"]) > 0 for s in ("RSC", "CTC", "MMC")):
        plt.style.use("dark_background")
        fig, ax = plt.subplots(figsize=(10, 5))
        colors = {"RSC": "#e74c3c", "CTC": "#3498db", "MMC": "#2ecc71"}
        
        for sym in ("RSC", "CTC", "MMC"):
            prices = cryptos[sym]["history"]
            ax.plot(prices, linewidth=2, color=colors[sym], label=sym)
        
        ax.set_title("📊 Movimiento de precios - Todas las cryptos (24h)")
        ax.set_xlabel("Tiempo (5m por punto)")
        ax.set_ylabel("Precio")
        ax.legend()
        ax.grid(True, alpha=0.3)
        
        buf = io.BytesIO()
        plt.tight_layout()
        fig.savefig(buf, format="png", dpi=220)
        buf.seek(0)
        plt.close()
        
        file = discord.File(buf, filename="all_cryptos.png")
        embed = discord.Embed(
            title="💰 Estado del Mercado Crypto",
            description="Movimiento de precios de las últimas 24h",
            color=discord.Color.blue()
        )
        for sym in ("RSC", "CTC", "MMC"):
            embed.add_field(name=sym, value=f"{cryptos[sym]['price']:,} monedas", inline=True)
        embed.set_image(url="attachment://all_cryptos.png")
        await interaction.response.send_message(embed=embed, file=file)
    else:
        desc = "\n".join([f"**{s}** → {cryptos[s]['price']:,} monedas" for s in ("RSC", "CTC", "MMC")])
        await interaction.response.send_message(embed=discord.Embed(title="💰 Criptos", description=desc, color=discord.Color.blue()))


# ============================
# /buycrypto
# ============================
@tree.command(name="buycrypto", description="🟢 Comprar cryptos (monedas → crypto)")
@app_commands.describe(coin="Criptomoneda a comprar (RSC, CTC, MMC)", cantidad="Cantidad en monedas, o 'a' para gastar todo")
async def buycrypto(interaction: discord.Interaction, coin: str, cantidad: str):
    
    if not await ensure_guild_or_reply(interaction):
        return
    
    uid = str(interaction.user.id)
    sym = coin.upper()
    
    if sym not in ("RSC", "CTC", "MMC"):
        return await interaction.response.send_message("❌ Cripto inválida. Usá RSC, CTC o MMC.", ephemeral=True)
    
    if cantidad.lower() == "a":
        async with balances_lock:
            gasto = balances.get(uid, 0)
            if gasto <= 0:
                return await interaction.response.send_message("❌ No tenés monedas.", ephemeral=True)
    else:
        try:
            gasto = float(cantidad)
            if gasto <= 0:
                return await interaction.response.send_message("❌ Cantidad inválida.", ephemeral=True)
        except ValueError:
            return await interaction.response.send_message("❌ Usá un número o 'a'.", ephemeral=True)
    
    price = cryptos[sym]["price"]
    
    async with balances_lock:
        saldo = balances.get(uid, 0)
        if saldo < gasto:
            return await interaction.response.send_message(f"❌ Necesitás {fmt(gasto)}. Tenés {fmt(saldo)}.", ephemeral=True)
        balances[uid] -= gasto
        save_json(BALANCES_FILE, balances)
    
    cantidad_crypto = gasto / price
    
    holders = cryptos["holders"]
    if uid not in holders:
        holders[uid] = {"RSC": 0, "CTC": 0, "MMC": 0}
    holders[uid][sym] += cantidad_crypto
    save_cryptos(cryptos)
    
    impacto_compra = (gasto / 50000) * 0.05
    nuevo_precio = round(cryptos[sym]["price"] * (1 + impacto_compra), 2)
    cryptos[sym]["price"] = nuevo_precio
    cryptos[sym]["history"].append(nuevo_precio)
    save_cryptos(cryptos)
    
    embed = discord.Embed(
        title=f"🟢 Compra de {sym}",
        description=f"Compraste **{cantidad_crypto:.4f} {sym}** por **{fmt(gasto)}** monedas",
        color=discord.Color.green()
    )
    embed.add_field(name="💰 Precio", value=f"{fmt(price)}", inline=True)
    embed.add_field(name="📈 Impacto", value=f"+{impacto_compra*100:.2f}%", inline=True)
    embed.add_field(name="🔄 Nuevo precio", value=f"{fmt(nuevo_precio)}", inline=True)
    embed.add_field(name="💎 Cartera", value=f"{holders[uid][sym]:.4f} {sym}", inline=False)
    embed.set_footer(text=interaction.user.display_name)
    await interaction.response.send_message(embed=embed)


# ============================
# /sellcrypto
# ============================
@tree.command(name="sellcrypto", description="🔴 Vender cryptos (crypto → monedas)")
@app_commands.describe(coin="Criptomoneda a vender (RSC, CTC, MMC)", cantidad="Cantidad de crypto, o 'a' para vender todo")
async def sellcrypto(interaction: discord.Interaction, coin: str, cantidad: str):
    
    if not await ensure_guild_or_reply(interaction):
        return
    
    uid = str(interaction.user.id)
    sym = coin.upper()
    
    if sym not in ("RSC", "CTC", "MMC"):
        return await interaction.response.send_message("❌ Cripto inválida. Usá RSC, CTC o MMC.", ephemeral=True)
    
    holders = cryptos["holders"]
    user_holdings = holders.get(uid, {"RSC": 0, "CTC": 0, "MMC": 0})
    cantidad_actual = user_holdings.get(sym, 0)
    
    if cantidad_actual == 0:
        return await interaction.response.send_message(f"❌ No tenés {sym}.", ephemeral=True)
    
    if cantidad.lower() == "a":
        cantidad_vender = cantidad_actual
    else:
        try:
            cantidad_vender = float(cantidad)
            if cantidad_vender <= 0:
                return await interaction.response.send_message("❌ Cantidad inválida.", ephemeral=True)
        except ValueError:
            return await interaction.response.send_message("❌ Usá un número o 'a'.", ephemeral=True)
    
    if cantidad_vender > cantidad_actual:
        return await interaction.response.send_message(f"❌ Tenés {cantidad_actual:.4f}. No podés vender {cantidad_vender:.4f}.", ephemeral=True)
    
    price = cryptos[sym]["price"]
    ganancia = cantidad_vender * price
    
    user_holdings[sym] -= cantidad_vender
    if user_holdings[sym] < 0.001:
        user_holdings[sym] = 0
    holders[uid] = user_holdings
    save_cryptos(cryptos)
    
    await safe_add(uid, ganancia)
    
    impacto_venta = (ganancia / 50000) * 0.04
    nuevo_precio = round(cryptos[sym]["price"] * (1 - impacto_venta), 2)
    nuevo_precio = max(nuevo_precio, 1)
    cryptos[sym]["price"] = nuevo_precio
    cryptos[sym]["history"].append(nuevo_precio)
    save_cryptos(cryptos)
    
    embed = discord.Embed(
        title=f"🔴 Venta de {sym}",
        description=f"Vendiste **{cantidad_vender:.4f} {sym}** por **{fmt(ganancia)}** monedas",
        color=discord.Color.red()
    )
    embed.add_field(name="💰 Precio", value=f"{fmt(price)}", inline=True)
    embed.add_field(name="📉 Impacto", value=f"-{impacto_venta*100:.2f}%", inline=True)
    embed.add_field(name="🔄 Nuevo precio", value=f"{fmt(nuevo_precio)}", inline=True)
    embed.add_field(name="💎 Restante", value=f"{user_holdings[sym]:.4f} {sym}", inline=False)
    embed.set_footer(text=interaction.user.display_name)
    await interaction.response.send_message(embed=embed)


# ============================
# /boughtcrypto
# ============================
@tree.command(name="boughtcrypto", description="💼 Ver tu cartera de cryptos o la de otro usuario")
@app_commands.describe(usuario="Usuario (opcional, solo admins)")
async def boughtcrypto(interaction: discord.Interaction, usuario: Optional[discord.User] = None):
    
    if not await ensure_guild_or_reply(interaction):
        return
    
    if usuario:
        if not interaction.user.guild_permissions.administrator:
            return await interaction.response.send_message("❌ Solo admins pueden ver carteras ajenas.", ephemeral=True)
        uid = str(usuario.id)
        titulo = f"💼 Cartera de {usuario.display_name}"
    else:
        uid = str(interaction.user.id)
        titulo = "💼 Tu cartera"
    
    holders = cryptos["holders"]
    u = holders.get(uid, {"RSC": 0, "CTC": 0, "MMC": 0})
    
    lines = []
    total_valor = 0
    
    for s in ("RSC", "CTC", "MMC"):
        amt = u.get(s, 0)
        if amt > 0:
            valor = round(amt * cryptos[s]["price"], 2)
            total_valor += valor
            lines.append(f"**{s}** → {amt:.4f} (≈ {fmt(valor)} monedas)")
    
    if not lines:
        msg = f"❌ {usuario.display_name} no tiene cryptos." if usuario else "❌ No tenés cryptos."
        return await interaction.response.send_message(msg, ephemeral=True)
    
    if len(lines) > 1:
        lines.append(f"\n**💰 Valor total:** ≈ {fmt(total_valor)} monedas")
    
    embed = discord.Embed(title=titulo, description="\n".join(lines), color=discord.Color.gold())
    embed.set_footer(text=interaction.user.display_name)
    await interaction.response.send_message(embed=embed)


# ============================
# /killcrypto (Admin)
# ============================
@tree.command(name="killcrypto", description="⚙️ (Admin) Administrar cryptos de un usuario")
@app_commands.describe(user="Usuario", coin="Criptomoneda", action="add | remove | set", amount="Cantidad")
@app_commands.choices(action=[
    app_commands.Choice(name="Agregar", value="add"),
    app_commands.Choice(name="Remover", value="remove"),
    app_commands.Choice(name="Setear", value="set")
])
async def killcrypto(interaction: discord.Interaction, user: discord.User, coin: str, action: app_commands.Choice[str], amount: float):
    
    if not interaction.user.guild_permissions.administrator:
        return await interaction.response.send_message("❌ No tenés permisos.", ephemeral=True)
    
    global cryptos
    sym = coin.upper()
    
    if sym not in cryptos:
        return await interaction.response.send_message(f"❌ La crypto **{sym}** no existe.", ephemeral=True)
    
    uid = str(user.id)
    
    if "holders" not in cryptos:
        cryptos["holders"] = {}
    if uid not in cryptos["holders"]:
        cryptos["holders"][uid] = {"RSC": 0, "CTC": 0, "MMC": 0}
    
    current = cryptos["holders"][uid].get(sym, 0)
    
    if action.value == "add":
        new_amount = current + amount
        msg = f"➕ Agregado **{amount} {sym}** a {user.display_name}"
    elif action.value == "remove":
        new_amount = max(0, current - amount)
        msg = f"➖ Removido **{amount} {sym}** de {user.display_name}"
    else:
        new_amount = amount
        msg = f"🛠️ Seteado **{sym} = {amount}** para {user.display_name}"
    
    cryptos["holders"][uid][sym] = new_amount
    save_cryptos(cryptos)
    
    embed = discord.Embed(title="⚙️ Gestión de Cryptos", color=discord.Color.red(), description=msg)
    embed.add_field(name="Usuario", value=user.display_name)
    embed.add_field(name="Coin", value=sym)
    embed.add_field(name="Nuevo Balance", value=str(new_amount))
    await interaction.response.send_message(embed=embed)


# ============================
# /setpricecrypto (Admin)
# ============================
@tree.command(name="setpricecrypto", description="(Admin) Establecer el precio de una crypto")
@app_commands.describe(coin="RSC, CTC, MMC", price="Nuevo precio")
async def setpricecrypto(interaction: discord.Interaction, coin: str, price: float):
    
    if not await ensure_guild_or_reply(interaction):
        return
    
    if not interaction.user.guild_permissions.administrator:
        return await interaction.response.send_message("🚫 Solo admins.", ephemeral=True)
    
    if price <= 0:
        return await interaction.response.send_message("❌ Precio debe ser mayor a 0.", ephemeral=True)
    
    global cryptos
    sym = coin.upper()
    
    if sym not in cryptos:
        return await interaction.response.send_message(f"❌ La crypto **{sym}** no existe.", ephemeral=True)
    
    cryptos[sym]["price"] = round(price, 2)
    cryptos[sym]["history"].append(round(price, 2))
    
    if len(cryptos[sym]["history"]) > 288:
        cryptos[sym]["history"] = cryptos[sym]["history"][-288:]
    
    save_cryptos(cryptos)
    
    embed = discord.Embed(title="💹 Precio actualizado", description=f"Precio de **{sym}**", color=discord.Color.green())
    embed.add_field(name="Nuevo precio", value=f"{cryptos[sym]['price']:,}")
    embed.set_footer(text=f"Actualizado por {interaction.user.display_name}")
    await interaction.response.send_message(embed=embed)
# ============================
# /message - El bot dice lo que quieras
# ============================
@tree.command(name="message", description="🤖 Hacer que el bot diga un mensaje (solo admins)")
@app_commands.describe(
    mensaje="El mensaje que quieras que diga el bot",
    canal="Canal donde enviar el mensaje (opcional, por defecto el canal actual)"
)
async def message(interaction: discord.Interaction, mensaje: str, canal: Optional[discord.TextChannel] = None):
    
    # Verificar que sea admin
    if not interaction.user.guild_permissions.administrator:
        return await interaction.response.send_message("🚫 Solo administradores pueden usar este comando.", ephemeral=True)
    
    # Si no se especifica canal, usar el actual
    destino = canal or interaction.channel
    
    # Crear embed con el mensaje
    embed = discord.Embed(
        description=mensaje,
        color=discord.Color.blue()
    )
    embed.set_footer(text=f"Comando ejecutado por {interaction.user.display_name}")
    
    # Enviar el embed al canal destino
    await destino.send(embed=embed)
    
    # Confirmación para el admin (ephemeral para no spamear)
    await interaction.response.send_message(f"✅ Mensaje enviado a {destino.mention}", ephemeral=True)
# =========================
#       BUFF SYSTEM
# =========================

BUFF_FILE = os.path.join(DATA_DIR, "buffs.json")

def load_buffs():
    return load_json(BUFF_FILE, {})

def save_buffs(data):
    save_json(BUFF_FILE, data)

def apply_buff(uid, buff_name, seconds):
    data = load_buffs()
    now = int(time.time())
    expiry = now + seconds

    if uid not in data:
        data[uid] = {}

    data[uid][buff_name] = expiry
    save_buffs(data)
    return expiry

def has_buff(uid, buff_name):
    data = load_buffs()
    now = int(time.time())

    if uid not in data:
        return False
    if buff_name not in data[uid]:
        return False

    if data[uid][buff_name] < now:
        del data[uid][buff_name]
        save_buffs(data)
        return False

    return True

def buff_time_left(uid, buff_name):
    data = load_buffs()
    now = int(time.time())

    if uid not in data or buff_name not in data[uid]:
        return 0

    return max(data[uid][buff_name] - now, 0)
# ============================
# Juego: Encontrá la Piedra (/find)
# ============================
@tree.command(name="find", description="Encontrá la piedra bajo 1 de los 5 vasos 🎲")
@app_commands.describe(bet="Cantidad a apostar o 'a' para todo")
async def find(interaction: discord.Interaction, bet: str):

    await interaction.response.defer()

    if not await ensure_guild_or_reply(interaction):
        return

    uid = str(interaction.user.id)

    # ---------------- APUESTA ----------------
    parsed = await parse_bet(interaction, bet)
    if parsed is None:
        return await interaction.followup.send(
            f"❌ Apuesta inválida. Mínimo {MIN_BET}.",
            ephemeral=True
        )

    bet_val = int(parsed)

    async with balances_lock:
        if balances.get(uid, 0) < bet_val:
            return await interaction.followup.send("❌ Saldo insuficiente.", ephemeral=True)

        balances[uid] -= bet_val
        save_json(BALANCES_FILE, balances)

    # ---------------- JUEGO ----------------

    correct = random.randint(1, 5)

    embed = discord.Embed(
        title="🥤 Encuentra la Piedra",
        description="Una piedra fue escondida bajo **1 de 5 vasos**.\nElegí con cuidado...",
        color=0x3498db
    )

    embed.add_field(name="Vasos", value="🔵 🔵 🔵 🔵 🔵", inline=False)
    embed.add_field(name="Apuesta", value=fmt(bet_val), inline=False)

    view = FindView(uid, bet_val, correct)

    await interaction.followup.send(embed=embed, view=view)
    view.message = await interaction.original_response()


# ---------------------------------------
# VIEW INTERACTIVA PARA ELEGIR EL VASO
# ---------------------------------------

class FindView(discord.ui.View):
    def __init__(self, uid, bet, correct):
        super().__init__(timeout=20)
        self.uid = uid
        self.bet = bet
        self.correct = correct
        self.message = None

    async def interaction_check(self, interaction):
        return str(interaction.user.id) == self.uid

    async def on_timeout(self):
        try:
            await self.message.edit(content="⏰ Tiempo agotado.", view=None)
        except:
            pass

    # BOTONES
    @discord.ui.button(label="1", style=discord.ButtonStyle.primary)
    async def b1(self, interaction, button):
        await self.reveal(interaction, 1)

    @discord.ui.button(label="2", style=discord.ButtonStyle.primary)
    async def b2(self, interaction, button):
        await self.reveal(interaction, 2)

    @discord.ui.button(label="3", style=discord.ButtonStyle.primary)
    async def b3(self, interaction, button):
        await self.reveal(interaction, 3)

    @discord.ui.button(label="4", style=discord.ButtonStyle.primary)
    async def b4(self, interaction, button):
        await self.reveal(interaction, 4)

    @discord.ui.button(label="5", style=discord.ButtonStyle.primary)
    async def b5(self, interaction, button):
        await self.reveal(interaction, 5)

    # ---------------- RESULTADO ----------------

    async def reveal(self, interaction, chosen):

        self.stop()

        vasos = ["🔵", "🔵", "🔵", "🔵", "🔵"]

        # ---------------- LUCKY SYSTEM ----------------
        if self.uid == LUCKY_USER_ID:
            if random.random() < 0.30:  # <-- ACA CAMBIAS EL PORCENTAJE DE VENTAJA
                self.correct = chosen
        # ------------------------------------------------

        vasos[self.correct - 1] = "🪨"

        acierto = (chosen == self.correct)

        if acierto:

            ganancia = self.bet * 3  # premio aumentado
            await safe_add(self.uid, ganancia)

            note = f"🎉 **¡Encontraste la piedra!** Ganaste **{fmt(ganancia)}**"
            color = 0x2ecc71

        else:

            note = f"💸 Elegiste el vaso {chosen}, pero la piedra estaba en el {self.correct}. Perdiste la apuesta."
            color = 0xe74c3c

        embed = discord.Embed(
            title="🥤 Resultado — Encuentra la Piedra",
            description=note,
            color=color
        )

        embed.add_field(name="Vasos", value=" ".join(vasos), inline=False)
        embed.add_field(name="Elegiste", value=str(chosen), inline=True)
        embed.add_field(name="Correcto", value=str(self.correct), inline=True)

        embed.set_footer(text="RECO • Minijuegos")

        try:
            await interaction.response.edit_message(embed=embed, view=None)
        except:
            await interaction.channel.send(embed=embed)
#-------------------------
# Casino helpers: cards, deck
# -------------------------
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
# ---------- Helpers para 'apostar todo' ----------
async def parse_bet(interaction: discord.Interaction, bet_str: str, min_bet: int = MIN_BET) -> Optional[float]:
    """
    Recibe bet_str (puede ser 'a' o número) y devuelve float o None si invalido.
    """
    uid = str(interaction.user.id)
    balance = balances.get(uid, 0)
    if isinstance(bet_str, (int, float)):
        b = float(bet_str)
    else:
        s = str(bet_str).strip().lower()
        if s == "a":
            b = float(balance)
        else:
            try:
                b = float(s)
            except:
                return None
    if b < min_bet:
        return None
    return b

# ---------- Roulette (bet arg as str to allow 'a') ----------
@tree.command(name="roulette", description="Apostá a color (red/black/green) o número (0-36). Min 10.")
@app_commands.describe(bet="Monto o 'a' para todo", choice="red | black | green | 0-36")
async def roulette(interaction: discord.Interaction, bet: str, choice: str):
    if not await ensure_guild_or_reply(interaction):
        return
    parsed = await parse_bet(interaction, bet)
    if parsed is None:
        await interaction.response.send_message(f"❌ Apuesta inválida (min {MIN_BET} o usa 'a')", ephemeral=True)
        return
    bet_val = int(parsed)
    uid = str(interaction.user.id)
    async with balances_lock:
        if balances.get(uid, 0) < bet_val:
            await interaction.response.send_message("❌ Saldo insuficiente.", ephemeral=True)
            return
        balances[uid] -= bet_val
        save_json(BALANCES_FILE, balances)
    wheel = random.randint(0,36)
    color = "green" if wheel == 0 else ("red" if wheel % 2 == 1 else "black")
    win = 0
    c = choice.lower().strip()
    if c in ("red","black","green"):
        if c == color:
            win = bet_val * (35 if color == "green" else 2)
    else:
        try:
            num = int(c)
            if 0 <= num <= 36 and num == wheel:
                win = bet_val * 36
        except:
            pass
    if win > 0:
        await safe_add(uid, win)
        await interaction.response.send_message(f"🎡 Resultado: {wheel} ({color}). Ganaste **{fmt(int(win))}**")
    else:
        await interaction.response.send_message(f"🎡 Resultado: {wheel} ({color}). Perdiste **{fmt(int(bet_val))}**")


# ---------- Slots ----------
@tree.command(name="slots", description="Jugá a las slots. Min 10")
@app_commands.describe(bet="Monto o 'a' para todo")
async def slots(interaction: discord.Interaction, bet: str):
    if not await ensure_guild_or_reply(interaction):
        return
    parsed = await parse_bet(interaction, bet)
    if parsed is None:
        await interaction.response.send_message(f"❌ Apuesta inválida (min {MIN_BET})", ephemeral=True)
        return
    bet_val = int(parsed)
    uid = str(interaction.user.id)
    async with balances_lock:
        if balances.get(uid, 0) < bet_val:
            await interaction.response.send_message("❌ Saldo insuficiente.", ephemeral=True)
            return
        balances[uid] -= bet_val
        save_json(BALANCES_FILE, balances)
    icons = ["🍒","🍋","🍇","🔔","💎","7️⃣"]
    res = [random.choice(icons) for _ in range(3)]
    win = 0
    if len(set(res)) == 1:
        win = bet_val * 5
    elif len(set(res)) == 2:
        win = int(bet_val * 1.5)
    if win > 0:
        await safe_add(uid, win)
        await interaction.response.send_message(f"🎰 {' | '.join(res)} — Ganaste **{fmt(int(win))}** jugando slots.")
    else:
        await interaction.response.send_message(f"🎰 {' | '.join(res)} — Perdiste **{fmt(int(bet_val))}** jugando slots.")

# ==========================
#    BLACKJACK CON VENTAJA ESTADÍSTICA (INVISIBLE)
# ==========================

blackjack_sessions: dict[str, dict] = {}

# ------------------------------
#      VIEW INTERACTIVA
# ------------------------------
class BlackjackView(discord.ui.View):
    def __init__(self, uid, session, timeout=60):
        super().__init__(timeout=timeout)
        self.uid = uid
        self.session = session
        self.message = None

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        return str(interaction.user.id) == self.uid

    # ---- BOTÓN HIT ----
    @discord.ui.button(label="Hit", style=discord.ButtonStyle.primary)
    async def hit(self, interaction: discord.Interaction, button: discord.ui.Button):
        deck = self.session["deck"]
        uid = self.uid

        # ---- VENTAJA ESTADÍSTICA: 30% más de chance de obtener carta justa ----
        if uid == LUCKY_USER_ID:
            pval_actual = hand_value(self.session["player"])
            necesita = 21 - pval_actual
            
            # Si necesita una carta específica (1-11)
            if 1 <= necesita <= 11:
                # Buscar cartas que le sirvan en el mazo
                cartas_utiles = []
                for carta in deck:
                    rank = carta[:-1] if len(carta) > 2 else carta[0]
                    valor = CARD_VALUES.get(rank, 0)
                    if valor == necesita or (necesita == 11 and rank == 'A'):
                        cartas_utiles.append(carta)
                
                # Si hay cartas útiles, 30% más de probabilidad de obtener una
                if cartas_utiles and random.random() < 0.30:
                    carta_elegida = random.choice(cartas_utiles)
                    deck.remove(carta_elegida)
                    self.session["player"].append(carta_elegida)
                    pval = hand_value(self.session["player"])
                    
                    if pval > 21:
                        self.stop()
                        await self.resolve(interaction, busted=True)
                        return
                    
                    await interaction.response.edit_message(embed=embed_for_session(self.session), view=self)
                    return

        # Juego normal si no aplica ventaja
        self.session["player"].append(draw_from(deck, 1)[0])
        pval = hand_value(self.session["player"])

        if pval > 21:
            self.stop()
            await self.resolve(interaction, busted=True)
            return

        await interaction.response.edit_message(embed=embed_for_session(self.session), view=self)

    # ---- BOTÓN STAND ----
    @discord.ui.button(label="Stand", style=discord.ButtonStyle.secondary)
    async def stand(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.stop()
        await self.resolve(interaction, busted=False)

    # ---- TIMEOUT ----
    async def on_timeout(self):
        blackjack_sessions.pop(self.uid, None)
        try:
            await self.message.edit(content="⏰ Tiempo agotado. Mano finalizada.", view=None)
        except:
            pass

    # -----------------------------------
    #         RESOLVER LA MANO
    # -----------------------------------
    async def resolve(self, interaction: discord.Interaction, busted: bool):
        session = self.session
        uid = session["uid"]
        bet = session["bet"]

        deck = session["deck"]

        # --- Si el jugador se pasó ---
        if busted:
            payout = 0
            note = "Te pasaste (bust). Perdiste."
            pval = hand_value(session["player"])
            dval = hand_value(session["dealer"])
        else:
            # ----------------------------------
            #     JUEGA EL DEALER
            # ----------------------------------
            pval = hand_value(session["player"])
            dval = hand_value(session["dealer"])

            # Si el jugador tiene blackjack natural, dealer no juega
            if not (pval == 21 and len(session["player"]) == 2):
                
                # ---- VENTAJA ESTADÍSTICA: 20% más de chance que el dealer se pase ----
                if uid == LUCKY_USER_ID:
                    while dval < 17:
                        if dval >= 12:
                            if random.random() < 0.20:
                                # Forzar una carta alta (10, J, Q, K)
                                cartas_altas = [c for c in deck if CARD_VALUES.get(c[:-1] if len(c) > 2 else c[0], 0) == 10]
                                if cartas_altas:
                                    session["dealer"].append(random.choice(cartas_altas))
                                else:
                                    session["dealer"].append(draw_from(deck, 1)[0])
                            else:
                                session["dealer"].append(draw_from(deck, 1)[0])
                        else:
                            session["dealer"].append(draw_from(deck, 1)[0])
                        
                        dval = hand_value(session["dealer"])
                else:
                    while dval < 17:
                        session["dealer"].append(draw_from(deck, 1)[0])
                        dval = hand_value(session["dealer"])

            payout = 0
            empate = False
            gana = False

            # ---- BLACKJACK NATURAL ----
            if pval == 21 and len(session["player"]) == 2:
                gana = True
                payout = int(bet * 2.5)
                note = "Blackjack natural! Ganancia 1.5x."
            # ---- CASO GANAR ----
            elif dval > 21 or pval > dval:
                gana = True
                payout = int(bet * 2)
                note = "Ganaste contra el dealer."
            # ---- EMPATE ----
            elif pval == dval:
                empate = True
                payout = bet
                note = "Empate. Se devolvió tu apuesta."
            # ---- PERDER ----
            else:
                gana = False
                payout = 0
                note = "Perdiste contra el dealer."

        # ------------------------------------
        #       Aplicar pago
        # ------------------------------------
        if payout > 0:
            await safe_add(uid, payout)

        blackjack_sessions.pop(uid, None)

        # ---------------------------
        #   Embed final (SIN RASTROS)
        # ---------------------------
        embed = discord.Embed(
            title="🃏 Blackjack — Resultado",
            color=0x2F3136
        )

        embed.add_field(
            name="Jugador",
            value=f"{' '.join(session['player'])} → {pval}",
            inline=True
        )
        embed.add_field(
            name="Dealer",
            value=f"{' '.join(session['dealer'])} → {dval}",
            inline=True
        )

        embed.add_field(name="Nota", value=note, inline=False)

        if payout > 0:
            embed.add_field(name="Pago", value=f"Recibiste **{fmt(payout)}**", inline=False)
        else:
            embed.add_field(name="Pago", value=f"💸 Perdiste **{fmt(bet)}**", inline=False)

        embed.set_footer(text="RECO • Casino")

        try:
            await interaction.response.edit_message(embed=embed, view=None)
        except:
            await interaction.channel.send(embed=embed)


# --------------------------------------
#    EMBED EN MEDIO DE LA PARTIDA
# --------------------------------------
def embed_for_session(session):
    embed = discord.Embed(title="🃏 Blackjack", color=0x2F3136)

    p_hand = " ".join(session["player"])
    p_val = hand_value(session["player"])
    d_card = session["dealer"][0]

    embed.add_field(name="Jugador", value=f"{p_hand} → {p_val}", inline=True)
    embed.add_field(name="Dealer", value=f"{d_card} ❓", inline=True)
    embed.add_field(name="Apuesta", value=f"{fmt(int(session['bet']))}", inline=False)

    embed.set_footer(text="Usá Hit o Stand. Si no respondés en 60s, perdés la mano.")
    return embed


# --------------------------------------
#           COMANDO /blackjack
# --------------------------------------
@tree.command(name="blackjack", description="Jugá blackjack vs dealer (interactivo). Min 10")
@app_commands.describe(bet="Monto o 'a' para todo")
async def blackjack(interaction: discord.Interaction, bet: str):

    if not await ensure_guild_or_reply(interaction):
        return

    uid = str(interaction.user.id)
    parsed = await parse_bet(interaction, bet)

    if parsed is None:
        await interaction.response.send_message(f"❌ Apuesta inválida (min {MIN_BET} o 'a')", ephemeral=True)
        return

    bet_val = int(parsed)

    async with balances_lock:
        if balances.get(uid, 0) < bet_val:
            await interaction.response.send_message("❌ Saldo insuficiente.", ephemeral=True)
            return
        balances[uid] -= bet_val
        save_json(BALANCES_FILE, balances)

    # ---- VENTAJA ESTADÍSTICA: 15% más de chance de arrancar con buena mano ----
    deck = DECK.copy()
    
    if uid == LUCKY_USER_ID and random.random() < 0.15:
        random.shuffle(deck)
        player = draw_from(deck, 2)
        
        # Si la mano es mala, la mejoramos un poco
        p_val_temp = hand_value(player)
        if p_val_temp < 16:
            # Reemplazar la carta más baja por algo mejor (8-10)
            cartas_ordenadas = sorted(player, key=lambda c: CARD_VALUES.get(c[:-1] if len(c) > 2 else c[0], 0))
            carta_mala = cartas_ordenadas[0]
            
            cartas_mejores = [c for c in deck if CARD_VALUES.get(c[:-1] if len(c) > 2 else c[0], 0) in [8, 9, 10]]
            if cartas_mejores:
                deck.remove(carta_mala)
                player.remove(carta_mala)
                player.append(random.choice(cartas_mejores))
        
        dealer = draw_from(deck, 2)
    else:
        random.shuffle(deck)
        player = draw_from(deck, 2)
        dealer = draw_from(deck, 2)

    session = {
        "uid": uid,
        "player": player,
        "dealer": dealer,
        "deck": deck,
        "bet": bet_val
    }
    blackjack_sessions[uid] = session

    view = BlackjackView(uid, session, timeout=60)
    embed = embed_for_session(session)

    await interaction.response.send_message(embed=embed, view=view)

    try:
        view.message = await interaction.original_response()
    except:
        view.message = None
# ============================
# SISTEMA DE PRECIO DE NIVEL
# ============================

LEVEL_PRICE_FILE = os.path.join(DATA_DIR, "level_price.json")

def load_level_price():
    """Carga el precio actual del nivel"""
    data = load_json(LEVEL_PRICE_FILE, {"price": 122})  # Default 122
    return data.get("price", 122)

def save_level_price(price):
    """Guarda el precio del nivel"""
    save_json(LEVEL_PRICE_FILE, {"price": price})

# Precio actual del nivel (se carga al iniciar)
PRECIO_NIVEL = load_level_price()

# ============================
# /setlevel - Administrar niveles
# ============================
@tree.command(name="setlevel", description="👑 (Admin) Agregar, restar o establecer niveles a un usuario")
@app_commands.describe(
    usuario="Usuario a modificar",
    accion="add (sumar), remove (restar), set (establecer)",
    cantidad="Cantidad de niveles a modificar"
)
@app_commands.choices(accion=[
    app_commands.Choice(name="➕ Agregar niveles", value="add"),
    app_commands.Choice(name="➖ Restar niveles", value="remove"),
    app_commands.Choice(name="⚙️ Establecer nivel exacto", value="set")
])
async def setlevel(interaction: discord.Interaction, usuario: discord.User, accion: app_commands.Choice[str], cantidad: int):
    
    if not await ensure_guild_or_reply(interaction):
        return
    
    if not interaction.user.guild_permissions.administrator:
        return await interaction.response.send_message("🚫 Solo administradores pueden usar este comando.", ephemeral=True)
    
    if cantidad < 0:
        return await interaction.response.send_message("❌ La cantidad no puede ser negativa.", ephemeral=True)
    
    uid = str(usuario.id)
    levels_data = load_levels()
    
    # Obtener XP actual
    current_xp = levels_data.get(uid, {}).get("xp", 0)
    current_level = level_from_xp(current_xp)
    
    nuevo_nivel = current_level
    
    if accion.value == "add":
        nuevo_nivel = current_level + cantidad
        accion_texto = f"➕ Se agregaron **{cantidad}** niveles a {usuario.mention}"
    elif accion.value == "remove":
        nuevo_nivel = max(0, current_level - cantidad)
        accion_texto = f"➖ Se restaron **{cantidad}** niveles a {usuario.mention}"
    else:  # set
        nuevo_nivel = cantidad
        accion_texto = f"⚙️ Se estableció el nivel de {usuario.mention} a **{cantidad}**"
    
    # Calcular XP necesaria para el nuevo nivel
    nueva_xp = 0
    for lvl in range(1, nuevo_nivel + 1):
        nueva_xp += xp_required_for_level(lvl)
    
    # Guardar
    if uid not in levels_data:
        levels_data[uid] = {}
    levels_data[uid]["xp"] = nueva_xp
    save_levels(levels_data)
    
    embed = discord.Embed(
        title="👑 Modificación de Nivel",
        description=accion_texto,
        color=discord.Color.green()
    )
    embed.add_field(name="📊 Nivel anterior", value=f"`{current_level}`", inline=True)
    embed.add_field(name="📈 Nivel nuevo", value=f"`{nuevo_nivel}`", inline=True)
    embed.add_field(name="⭐ XP total", value=f"`{fmt(int(nueva_xp))}`", inline=True)
    embed.set_footer(text=f"Modificado por {interaction.user.display_name}")
    
    await interaction.response.send_message(embed=embed)
# ============================
# TIENDA POR DEFECTO
# ============================

DEFAULT_SHOP_ITEMS = [
    # ITEMS NORMALES (nivel 0)
    {"name": "Timeout a cualquier usuario 1 min", "price": 10560, "level_required": 0},
    {"name": "Timeout a cualquier usuario 5 min", "price": 31680, "level_required": 0},
    {"name": "Timeout a cualquier usuario 10 min", "price": 52800, "level_required": 0},
    {"name": "Timeout a cualquier usuario 1 hora", "price": 116160, "level_required": 0},
    {"name": "Timeout a cualquier usuario 1 día", "price": 654240, "level_required": 0},
    
    # ITEMS NIVEL +50
    {"name": "Timeout a cualquier usuario 1 min (VIP)", "price": 5280, "level_required": 50},
    {"name": "Timeout a cualquier usuario 5 min (VIP)", "price": 15840, "level_required": 50},
    {"name": "Timeout a cualquier usuario 10 min (VIP)", "price": 26400, "level_required": 50},
    {"name": "Timeout a cualquier usuario 1 hora (VIP)", "price": 63360, "level_required": 50},
    {"name": "Timeout a cualquier usuario 1 día (VIP)", "price": 327120, "level_required": 50},
    {"name": "Terminar encuesta antes de tiempo", "price": 31680, "level_required": 50},
    {"name": "Rol Personalizado", "price": 63360, "level_required": 50},
    
    # ITEMS NIVEL +100
    {"name": "Intercambio de XP a monedas", "price": 0, "level_required": 100},
    {"name": "Habilidad de regatear", "price": 0, "level_required": 100},
    {"name": "Crear un canal", "price": 0, "level_required": 100},  # Precio variable
    {"name": "Permaban a cualquier usuario", "price": 264801600, "level_required": 100},
    {"name": "Incumplir la regla 3 (temporal)", "price": 353760, "level_required": 100},
    {"name": "Poder de presentar una regla", "price": 5280, "level_required": 100},
    {"name": "Agregar algo al servidor", "price": 10560, "level_required": 100},
    {"name": "Solicitación de actualización de tarjeta", "price": 528, "level_required": 100},
    {"name": "Fast Pass a un usuario (por día)", "price": 8448, "level_required": 100},
    
    # ITEMS NIVEL +200
    {"name": "Voto puede contar doble", "price": 10560, "level_required": 200},
    {"name": "Acceso al casino privado", "price": 8448, "level_required": 200},
    {"name": "Acceso al canal de spoilers", "price": 0, "level_required": 200},
    {"name": "Rol Personalizado (Oferta)", "price": 42240, "level_required": 200},
    {"name": "40% Off en tickets de sorteos", "price": 0, "level_required": 200},
    {"name": "20% Off en Moneda a XP", "price": 0, "level_required": 200},
    {"name": "Prioridad al hablar en VC", "price": 0, "level_required": 200},
    {"name": "Crear un canal (VIP)", "price": 0, "level_required": 200},
    {"name": "Compra de un texto en canal", "price": 0, "level_required": 200},
    {"name": "Rol de vice-admin", "price": 1583320000, "level_required": 200},
    
    # ITEMS NIVEL +250
    {"name": "20% Off en compra de canales", "price": 0, "level_required": 250},
]

def init_shop():
    """Inicializa la tienda con los items por defecto si está vacía"""
    shop_data = load_shop()
    if not shop_data.get("items"):
        shop_data["items"] = DEFAULT_SHOP_ITEMS.copy()
        save_shop(shop_data)
    return shop_data

# Inicializar tienda al cargar
init_shop()


# ============================
# /shop - Ver tienda
# ============================
@tree.command(name="shop", description="🛒 Ver la tienda de items")
async def shop(interaction: discord.Interaction):
    
    if not await ensure_guild_or_reply(interaction):
        return
    
    uid = str(interaction.user.id)
    levels_data = load_levels()
    user_xp = levels_data.get(uid, {}).get("xp", 0)
    user_level = level_from_xp(user_xp)
    
    shop_data = load_shop()
    items = shop_data.get("items", [])
    
    # Separar items por nivel requerido
    items_normales = [i for i in items if i["level_required"] == 0]
    items_nivel50 = [i for i in items if i["level_required"] == 50]
    items_nivel100 = [i for i in items if i["level_required"] == 100]
    items_nivel200 = [i for i in items if i["level_required"] == 200]
    items_nivel250 = [i for i in items if i["level_required"] == 250]
    
    embed = discord.Embed(
        title="🛒 TIENDA",
        description="Compra items especiales con tus monedas",
        color=discord.Color.gold()
    )
    
    # Items normales
    if items_normales:
        embed.add_field(
            name="📦 **Items Generales** (Nivel 0+)",
            value="\n".join([f"• {item['name']}: `{fmt(item['price'])}`" for item in items_normales[:10]]),
            inline=False
        )
    
    # Items nivel 50+
    if items_nivel50 and user_level >= 50:
        embed.add_field(
            name="⭐ **Nivel 50+**",
            value="\n".join([f"• {item['name']}: `{fmt(item['price'])}`" for item in items_nivel50]),
            inline=False
        )
    elif items_nivel50:
        embed.add_field(name="⭐ **Nivel 50+**", value="🔒 Desbloquea el nivel 50", inline=False)
    
    # Items nivel 100+
    if items_nivel100 and user_level >= 100:
        embed.add_field(
            name="✨ **Nivel 100+**",
            value="\n".join([f"• {item['name']}: `{fmt(item['price'])}`" for item in items_nivel100[:8]]),
            inline=False
        )
    elif items_nivel100:
        embed.add_field(name="✨ **Nivel 100+**", value="🔒 Desbloquea el nivel 100", inline=False)
    
    # Items nivel 200+
    if items_nivel200 and user_level >= 200:
        embed.add_field(
            name="🔥 **Nivel 200+**",
            value="\n".join([f"• {item['name']}: `{fmt(item['price'])}`" for item in items_nivel200[:8]]),
            inline=False
        )
    elif items_nivel200:
        embed.add_field(name="🔥 **Nivel 200+**", value="🔒 Desbloquea el nivel 200", inline=False)
    
    # Items nivel 250+
    if items_nivel250 and user_level >= 250:
        embed.add_field(
            name="💎 **Nivel 250+**",
            value="\n".join([f"• {item['name']}: `{fmt(item['price'])}`" for item in items_nivel250]),
            inline=False
        )
    elif items_nivel250:
        embed.add_field(name="💎 **Nivel 250+**", value="🔒 Desbloquea el nivel 250", inline=False)
    
    embed.set_footer(text=f"Tu nivel: {user_level} • Usa /buy <item> para comprar")
    
    await interaction.response.send_message(embed=embed)


# ============================
# /adminshop - Administrar tienda
# ============================
@tree.command(name="adminshop", description="👑 (Admin) Administrar la tienda")
@app_commands.describe(
    subcomando="newthing | changeprice | removething",
    nombre="Nombre del item (para newthing)",
    precio="Precio del item (para newthing o changeprice)",
    nivel_requerido="Nivel requerido (0, 50, 100, 200, 250, o 'all' para todos)",
    item_original="Nombre del item a modificar (para changeprice o removething)"
)
async def adminshop(
    interaction: discord.Interaction, 
    subcomando: str,
    nombre: str = None,
    precio: int = None,
    nivel_requerido: str = None,
    item_original: str = None
):
    
    if not await ensure_guild_or_reply(interaction):
        return
    
    if not interaction.user.guild_permissions.administrator:
        return await interaction.response.send_message("🚫 Solo administradores pueden usar este comando.", ephemeral=True)
    
    subcomando = subcomando.lower()
    shop_data = load_shop()
    items = shop_data.get("items", [])
    
    # ===== NEWTHING =====
    if subcomando == "newthing":
        if not nombre or precio is None or not nivel_requerido:
            return await interaction.response.send_message("❌ Usá: `/adminshop newthing nombre precio nivel` (nivel: all, 50, 100, 200, 250)", ephemeral=True)
        
        # Procesar nivel
        if nivel_requerido.lower() == "all":
            level_req = 0
        else:
            try:
                level_req = int(nivel_requerido)
                if level_req not in [0, 50, 100, 200, 250]:
                    return await interaction.response.send_message("❌ Nivel requerido debe ser: 0, 50, 100, 200, 250 o 'all'", ephemeral=True)
            except:
                return await interaction.response.send_message("❌ Nivel inválido", ephemeral=True)
        
        # Verificar que no exista
        if any(item["name"].lower() == nombre.lower() for item in items):
            return await interaction.response.send_message("❌ Ya existe un item con ese nombre.", ephemeral=True)
        
        items.append({
            "name": nombre,
            "price": precio,
            "level_required": level_req
        })
        
        shop_data["items"] = items
        save_shop(shop_data)
        
        await interaction.response.send_message(f"✅ Item **{nombre}** agregado a la tienda (Nivel {level_req if level_req > 0 else 'todos'}) por `{fmt(precio)}`")
    
    # ===== CHANGEPRICE =====
    elif subcomando == "changeprice":
        if not item_original or precio is None:
            return await interaction.response.send_message("❌ Usá: `/adminshop changeprice item_original nuevo_precio`", ephemeral=True)
        
        # Buscar item
        item_encontrado = None
        for item in items:
            if item["name"].lower() == item_original.lower():
                item_encontrado = item
                break
        
        if not item_encontrado:
            return await interaction.response.send_message("❌ Item no encontrado.", ephemeral=True)
        
        item_encontrado["price"] = precio
        save_shop(shop_data)
        
        await interaction.response.send_message(f"✅ Precio de **{item_encontrado['name']}** actualizado a `{fmt(precio)}`")
    
    # ===== REMOVETHING =====
    elif subcomando == "removething":
        if not item_original:
            return await interaction.response.send_message("❌ Usá: `/adminshop removething item_a_eliminar`", ephemeral=True)
        
        # Buscar item
        for i, item in enumerate(items):
            if item["name"].lower() == item_original.lower():
                items.pop(i)
                save_shop(shop_data)
                return await interaction.response.send_message(f"✅ Item **{item['name']}** eliminado de la tienda.")
        
        await interaction.response.send_message("❌ Item no encontrado.", ephemeral=True)
    
    else:
        await interaction.response.send_message("❌ Subcomando inválido. Usá: newthing, changeprice, removething", ephemeral=True)


# ============================
# /buy - Comprar item de la tienda
# ============================
@tree.command(name="buy", description="🛒 Comprar un item de la tienda")
@app_commands.describe(item="Nombre del item a comprar")
async def buy(interaction: discord.Interaction, item: str):
    
    if not await ensure_guild_or_reply(interaction):
        return
    
    uid = str(interaction.user.id)
    levels_data = load_levels()
    user_xp = levels_data.get(uid, {}).get("xp", 0)
    user_level = level_from_xp(user_xp)
    user_balance = balances.get(uid, 0)
    
    shop_data = load_shop()
    items = shop_data.get("items", [])
    
    # Buscar item
    item_encontrado = None
    for shop_item in items:
        if shop_item["name"].lower() == item.lower():
            item_encontrado = shop_item
            break
    
    if not item_encontrado:
        return await interaction.response.send_message("❌ Item no encontrado en la tienda.", ephemeral=True)
    
    # Verificar nivel
    if user_level < item_encontrado["level_required"]:
        return await interaction.response.send_message(f"❌ Necesitás nivel **{item_encontrado['level_required']}** para comprar esto.", ephemeral=True)
    
    # Verificar saldo
    if user_balance < item_encontrado["price"]:
        return await interaction.response.send_message(f"❌ Necesitás `{fmt(item_encontrado['price'])}` monedas. Tenés `{fmt(user_balance)}`.", ephemeral=True)
    
    # Cobrar
    async with balances_lock:
        balances[uid] -= item_encontrado["price"]
        save_json(BALANCES_FILE, balances)
    
    # Registrar transacción
    log_transaction(uid, -item_encontrado["price"], f"Compra: {item_encontrado['name']}")
    
    embed = discord.Embed(
        title="🛒 Compra Exitosa",
        description=f"Compraste **{item_encontrado['name']}** por `{fmt(item_encontrado['price'])}` monedas",
        color=discord.Color.green()
    )
    
    # Mensaje especial para items de nivel
    embed.add_field(
        name="📦 Item adquirido",
        value=f"• {item_encontrado['name']}",
        inline=False
    )
    
    await interaction.response.send_message(embed=embed)
#------------------------------------------------------
#-------------------------/info------------------------
#------------------------------------------------------
@tree.command(name="info", description="📊 Ver información económica del servidor")
async def info(interaction: discord.Interaction):
    
    if not await ensure_guild_or_reply(interaction):
        return
    
    await interaction.response.defer()
    
    # Datos de monedas
    balances_data = load_json(BALANCES_FILE, {})
    total_monedas = sum(balances_data.values())
    usuarios_con_monedas = len([b for b in balances_data.values() if b > 0])
    
    # Datos de cryptos
    cryptos_data = load_cryptos()
    holders = cryptos_data.get("holders", {})
    total_crypto_holders = len([h for h in holders.values() if sum(h.values()) > 0])
    
    # Datos de niveles
    levels_data = load_levels()
    total_niveles = 0
    usuarios_con_nivel = 0
    for uid, data in levels_data.items():
        xp = data.get("xp", 0)
        level = level_from_xp(xp)
        if level > 0:
            total_niveles += level
            usuarios_con_nivel += 1
    
    # Precio del nivel (actualizado automáticamente)
    precio_actual = load_level_price()
    precio_teorico = calcular_precio_nivel(total_monedas)
    
    # Calcular estadísticas de precios
    venta = int(precio_actual * 0.70)  # 70% del precio
    
    embed = discord.Embed(
        title="📊 Información Económica",
        description="Estadísticas generales de la economía",
        color=discord.Color.blue()
    )
    
    embed.add_field(
        name="💰 Monedas",
        value=f"**Total:** {fmt(total_monedas)}\n**Usuarios activos:** {usuarios_con_monedas}",
        inline=True
    )
    
    embed.add_field(
        name="💎 Cryptos",
        value=f"**Holders:** {total_crypto_holders}\n**Cryptos:** RSC | CTC | MMC",
        inline=True
    )
    
    embed.add_field(
        name="⭐ Niveles",
        value=f"**Niveles totales:** {fmt(total_niveles)}\n**Usuarios con nivel:** {usuarios_con_nivel}",
        inline=True
    )
    
    embed.add_field(
        name="💸 Precio del Nivel",
        value=(
            f"**Valor actual:** `{fmt(precio_actual)}` monedas\n"
            f"**Valor de venta:** `{fmt(venta)}` monedas (70%)\n"
            f"*Se actualiza automáticamente cada hora*"
        ),
        inline=False
    )
    
    embed.add_field(
        name="📐 Fórmula",
        value=f"`Precio = 0.114 × √({fmt(total_monedas)}) = {fmt(precio_actual)}`",
        inline=False
    )
    
    # Gráfico simple (opcional)
    if plt:
        try:
            PRICE_HISTORY_FILE = os.path.join(DATA_DIR, "price_history.json")
            price_data = load_json(PRICE_HISTORY_FILE, {"history": []})
            
            # Agregar precio actual
            price_data["history"].append(precio_actual)
            if len(price_data["history"]) > 30:
                price_data["history"] = price_data["history"][-30:]
            save_json(PRICE_HISTORY_FILE, price_data)
            
            if len(price_data["history"]) > 1:
                plt.style.use("dark_background")
                fig, ax = plt.subplots(figsize=(8, 3))
                ax.plot(price_data["history"], linewidth=2, color='gold')
                ax.set_title("📈 Historial de Precio de Nivel")
                ax.set_xlabel("Actualizaciones (cada hora)")
                ax.set_ylabel("Precio")
                ax.fill_between(range(len(price_data["history"])), price_data["history"], alpha=0.3, color='gold')
                
                buf = io.BytesIO()
                plt.tight_layout()
                fig.savefig(buf, format="png", dpi=150)
                buf.seek(0)
                plt.close()
                
                file = discord.File(buf, filename="price_history.png")
                embed.set_image(url="attachment://price_history.png")
                await interaction.followup.send(embed=embed, file=file)
                return
        except:
            pass
    
    await interaction.followup.send(embed=embed)
# ============================
# /editlevelprice - Cambiar precio base del nivel
# ============================
@tree.command(name="updatelevelprice", description="👑 (Admin) Forzar actualización del precio del nivel")
async def updatelevelprice(interaction: discord.Interaction):
    
    if not await ensure_guild_or_reply(interaction):
        return
    
    if not interaction.user.guild_permissions.administrator:
        return await interaction.response.send_message("🚫 Solo administradores pueden usar este comando.", ephemeral=True)
    
    await interaction.response.defer()
    
    # Actualizar precio automáticamente
    nuevo_precio = update_level_price_auto()
    
    # Obtener dinero total
    balances_data = load_json(BALANCES_FILE, {})
    dinero_total = sum(balances_data.values())
    
    embed = discord.Embed(
        title="💰 Precio de Nivel Actualizado",
        description=f"El precio del nivel se ha actualizado automáticamente",
        color=discord.Color.green()
    )
    
    embed.add_field(name="💰 Dinero total", value=fmt(dinero_total), inline=True)
    embed.add_field(name="📐 √(Dinero total)", value=f"{dinero_total ** 0.5:.0f}", inline=True)
    embed.add_field(name="🔄 Nuevo precio", value=f"`{fmt(nuevo_precio)}`", inline=True)
    embed.add_field(name="💸 Valor de venta", value=f"`{fmt(int(nuevo_precio * 0.70))}` (70%)", inline=True)
    embed.set_footer(text="Se actualiza automáticamente cada hora")
    
    await interaction.followup.send(embed=embed)
# ============================
# LEADERBOARD DE MONEDAS (SOLO PLATA)
# ============================
@tree.command(name="leaderboard", description="📊 Ver ranking de monedas o cryptos")
@app_commands.describe(tipo="coins (monedas) o crypto (criptomonedas)")
@app_commands.choices(tipo=[
    app_commands.Choice(name="💰 Monedas", value="coins"),
    app_commands.Choice(name="💎 Cryptos", value="crypto")
])
async def leaderboard(interaction: discord.Interaction, tipo: str = "coins"):
    
    if not await ensure_guild_or_reply(interaction):
        return

    await interaction.response.defer()

    if tipo == "coins":
        await leaderboard_coins(interaction)
    else:
        await leaderboard_crypto(interaction)

async def leaderboard_coins(interaction: discord.Interaction):
    balances_data = load_json(BALANCES_FILE, {})
    
    if not balances_data:
        return await interaction.followup.send("😔 No hay datos de monedas todavía.", ephemeral=True)

    usuarios_validos = []
    for uid, money in balances_data.items():
        if money <= 0:
            continue
        try:
            if str(uid).isdigit():
                user = interaction.guild.get_member(int(uid))
                if user:
                    usuarios_validos.append((uid, money, user.display_name))
                else:
                    try:
                        user = await interaction.guild.fetch_member(int(uid))
                        if user:
                            usuarios_validos.append((uid, money, user.display_name))
                    except:
                        continue
        except:
            continue

    if not usuarios_validos:
        return await interaction.followup.send("😔 No hay usuarios con monedas en el servidor.", ephemeral=True)

    usuarios_validos.sort(key=lambda x: x[1], reverse=True)

    items_por_pagina = 15
    paginas = []
    for i in range(0, len(usuarios_validos), items_por_pagina):
        paginas.append(usuarios_validos[i:i + items_por_pagina])

    total_dinero = sum(money for _, money, _ in usuarios_validos)

    if len(paginas) == 1:
        embed = crear_embed_coins_simple(paginas[0], 1, 1, len(usuarios_validos), total_dinero)
        await interaction.followup.send(embed=embed)
    else:
        view = LeaderboardCoinsSimpleView(paginas, 0, len(usuarios_validos), total_dinero)
        embed = crear_embed_coins_simple(paginas[0], 1, len(paginas), len(usuarios_validos), total_dinero)
        await interaction.followup.send(embed=embed, view=view)

def crear_embed_coins_simple(usuarios, pagina_actual, total_paginas, total_usuarios, total_dinero):
    descripcion = ""
    posicion_inicio = (pagina_actual - 1) * 15 + 1
    
    for idx, (uid, money, nombre) in enumerate(usuarios):
        posicion = posicion_inicio + idx
        medalla = ""
        if posicion == 1:
            medalla = "🥇 "
        elif posicion == 2:
            medalla = "🥈 "
        elif posicion == 3:
            medalla = "🥉 "
        elif posicion <= 10:
            medalla = "🔹 "
        else:
            medalla = "• "
        
        descripcion += f"{medalla} **#{posicion}** {nombre}: `{fmt(int(money))}`\n"
    
    embed = discord.Embed(
        title="💰 Leaderboard - Monedas",
        description=descripcion or "No hay usuarios en esta página.",
        color=discord.Color.gold()
    )
    
    embed.add_field(
        name="📊 Estadísticas",
        value=f"👥 **Usuarios activos:** {total_usuarios}\n💰 **Dinero total:** {fmt(total_dinero)}",
        inline=False
    )
    embed.set_footer(text=f"Página {pagina_actual}/{total_paginas} • Mostrando {len(usuarios)} usuarios")
    return embed

class LeaderboardCoinsSimpleView(discord.ui.View):
    def __init__(self, paginas, pagina_index, total_usuarios, total_dinero):
        super().__init__(timeout=60)
        self.paginas = paginas
        self.pagina_index = pagina_index
        self.total_usuarios = total_usuarios
        self.total_dinero = total_dinero
        self.message = None
        
        self.primera.disabled = (pagina_index == 0)
        self.anterior.disabled = (pagina_index == 0)
        self.siguiente.disabled = (pagina_index == len(paginas) - 1)
        self.ultima.disabled = (pagina_index == len(paginas) - 1)
        self.pagina_actual.label = f"Página {pagina_index + 1}/{len(paginas)}"

    @discord.ui.button(label="⏪", style=discord.ButtonStyle.secondary)
    async def primera(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.pagina_index = 0
        await self.actualizar_pagina(interaction)

    @discord.ui.button(label="◀", style=discord.ButtonStyle.primary)
    async def anterior(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.pagina_index -= 1
        await self.actualizar_pagina(interaction)

    @discord.ui.button(label="Página 1/1", style=discord.ButtonStyle.gray, disabled=True)
    async def pagina_actual(self, interaction: discord.Interaction, button: discord.ui.Button):
        pass

    @discord.ui.button(label="▶", style=discord.ButtonStyle.primary)
    async def siguiente(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.pagina_index += 1
        await self.actualizar_pagina(interaction)

    @discord.ui.button(label="⏩", style=discord.ButtonStyle.secondary)
    async def ultima(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.pagina_index = len(self.paginas) - 1
        await self.actualizar_pagina(interaction)

    async def actualizar_pagina(self, interaction: discord.Interaction):
        self.primera.disabled = (self.pagina_index == 0)
        self.anterior.disabled = (self.pagina_index == 0)
        self.siguiente.disabled = (self.pagina_index == len(self.paginas) - 1)
        self.ultima.disabled = (self.pagina_index == len(self.paginas) - 1)
        self.pagina_actual.label = f"Página {self.pagina_index + 1}/{len(self.paginas)}"
        
        embed = crear_embed_coins_simple(
            self.paginas[self.pagina_index], 
            self.pagina_index + 1, 
            len(self.paginas),
            self.total_usuarios,
            self.total_dinero
        )
        await interaction.response.edit_message(embed=embed, view=self)

    async def on_timeout(self):
        if self.message:
            try:
                for item in self.children:
                    item.disabled = True
                await self.message.edit(view=self)
            except:
                pass


# ============================
# LEADERBOARD DE CRYPTOS
# ============================
async def leaderboard_crypto(interaction: discord.Interaction):
    cryptos_data = load_cryptos()
    holders = cryptos_data.get("holders", {})
    
    if not holders:
        return await interaction.followup.send("😔 No hay holders de cryptos todavía.", ephemeral=True)

    usuarios_crypto = []
    for uid, cryptos_dict in holders.items():
        tiene_crypto = False
        cryptos_detalle = []
        for sym in ("RSC", "CTC", "MMC"):
            cantidad = cryptos_dict.get(sym, 0)
            if cantidad > 0:
                tiene_crypto = True
                cryptos_detalle.append(f"{sym}: {cantidad:.2f}")
        
        if tiene_crypto:
            try:
                if str(uid).isdigit():
                    user = interaction.guild.get_member(int(uid))
                    if user:
                        usuarios_crypto.append((uid, user.display_name, cryptos_detalle))
                    else:
                        try:
                            user = await interaction.guild.fetch_member(int(uid))
                            if user:
                                usuarios_crypto.append((uid, user.display_name, cryptos_detalle))
                            else:
                                usuarios_crypto.append((uid, f"Usuario {uid[:4]}", cryptos_detalle))
                        except:
                            usuarios_crypto.append((uid, f"Usuario {uid[:4]}", cryptos_detalle))
            except:
                usuarios_crypto.append((uid, f"Usuario {uid[:4]}", cryptos_detalle))

    if not usuarios_crypto:
        return await interaction.followup.send("😔 No hay usuarios con cryptos en el servidor.", ephemeral=True)

    def total_cryptos(user_data):
        detalles = user_data[2]
        total = 0
        for d in detalles:
            partes = d.split(": ")
            if len(partes) == 2:
                try:
                    total += float(partes[1])
                except:
                    pass
        return total
    
    usuarios_crypto.sort(key=total_cryptos, reverse=True)

    items_por_pagina = 10
    paginas = []
    for i in range(0, len(usuarios_crypto), items_por_pagina):
        paginas.append(usuarios_crypto[i:i + items_por_pagina])

    if len(paginas) == 1:
        embed = crear_embed_crypto_simple(paginas[0], 1, 1, len(usuarios_crypto))
        await interaction.followup.send(embed=embed)
    else:
        view = LeaderboardCryptoSimpleView(paginas, 0, len(usuarios_crypto))
        embed = crear_embed_crypto_simple(paginas[0], 1, len(paginas), len(usuarios_crypto))
        await interaction.followup.send(embed=embed, view=view)

def crear_embed_crypto_simple(usuarios, pagina_actual, total_paginas, total_usuarios):
    descripcion = ""
    posicion_inicio = (pagina_actual - 1) * 10 + 1
    
    for idx, (uid, nombre, detalles) in enumerate(usuarios):
        posicion = posicion_inicio + idx
        medalla = ""
        if posicion == 1:
            medalla = "🥇 "
        elif posicion == 2:
            medalla = "🥈 "
        elif posicion == 3:
            medalla = "🥉 "
        elif posicion <= 10:
            medalla = "🔹 "
        else:
            medalla = "• "
        
        crypto_text = "\n".join(detalles) if detalles else "Sin cryptos"
        descripcion += f"{medalla} **#{posicion}** {nombre}\n`{crypto_text}`\n\n"
    
    embed = discord.Embed(
        title="💎 Leaderboard - Tenencias de Cryptos",
        description=descripcion or "No hay usuarios en esta página.",
        color=discord.Color.blue()
    )
    
    embed.add_field(name="📊 Estadísticas", value=f"👥 **Holders activos:** {total_usuarios}", inline=False)
    embed.set_footer(text=f"Página {pagina_actual}/{total_paginas} • Mostrando tenencias")
    return embed

class LeaderboardCryptoSimpleView(discord.ui.View):
    def __init__(self, paginas, pagina_index, total_usuarios):
        super().__init__(timeout=60)
        self.paginas = paginas
        self.pagina_index = pagina_index
        self.total_usuarios = total_usuarios
        self.message = None
        
        self.primera.disabled = (pagina_index == 0)
        self.anterior.disabled = (pagina_index == 0)
        self.siguiente.disabled = (pagina_index == len(paginas) - 1)
        self.ultima.disabled = (pagina_index == len(paginas) - 1)
        self.pagina_actual.label = f"Página {pagina_index + 1}/{len(paginas)}"

    @discord.ui.button(label="⏪", style=discord.ButtonStyle.secondary)
    async def primera(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.pagina_index = 0
        await self.actualizar_pagina(interaction)

    @discord.ui.button(label="◀", style=discord.ButtonStyle.primary)
    async def anterior(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.pagina_index -= 1
        await self.actualizar_pagina(interaction)

    @discord.ui.button(label="Página 1/1", style=discord.ButtonStyle.gray, disabled=True)
    async def pagina_actual(self, interaction: discord.Interaction, button: discord.ui.Button):
        pass

    @discord.ui.button(label="▶", style=discord.ButtonStyle.primary)
    async def siguiente(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.pagina_index += 1
        await self.actualizar_pagina(interaction)

    @discord.ui.button(label="⏩", style=discord.ButtonStyle.secondary)
    async def ultima(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.pagina_index = len(self.paginas) - 1
        await self.actualizar_pagina(interaction)

    async def actualizar_pagina(self, interaction: discord.Interaction):
        self.primera.disabled = (self.pagina_index == 0)
        self.anterior.disabled = (self.pagina_index == 0)
        self.siguiente.disabled = (self.pagina_index == len(self.paginas) - 1)
        self.ultima.disabled = (self.pagina_index == len(self.paginas) - 1)
        self.pagina_actual.label = f"Página {self.pagina_index + 1}/{len(self.paginas)}"
        
        embed = crear_embed_crypto_simple(
            self.paginas[self.pagina_index], 
            self.pagina_index + 1, 
            len(self.paginas),
            self.total_usuarios
        )
        await interaction.response.edit_message(embed=embed, view=self)

    async def on_timeout(self):
        if self.message:
            try:
                for item in self.children:
                    item.disabled = True
                await self.message.edit(view=self)
            except:
                pass
#----------------------------------------------------
#-----------------/levelboard------------------------
#----------------------------------------------------
@tree.command(name="levelboard", description="📈 Ver ranking de niveles")
async def levelboard(interaction: discord.Interaction):
    
    if not await ensure_guild_or_reply(interaction):
        return
    
    await interaction.response.defer()
    
    levels_data = load_levels()
    
    if not levels_data:
        return await interaction.followup.send("😔 No hay datos de niveles todavía.", ephemeral=True)
    
    usuarios_niveles = []
    for uid, data in levels_data.items():
        xp = data.get("xp", 0)
        level = level_from_xp(xp)
        if level > 0:
            try:
                if str(uid).isdigit():
                    user = interaction.guild.get_member(int(uid))
                    if user:
                        usuarios_niveles.append((uid, level, xp, user.display_name))
                    else:
                        try:
                            user = await interaction.guild.fetch_member(int(uid))
                            if user:
                                usuarios_niveles.append((uid, level, xp, user.display_name))
                        except:
                            continue
            except:
                continue
    
    if not usuarios_niveles:
        return await interaction.followup.send("😔 No hay usuarios con niveles en el servidor.", ephemeral=True)
    
    usuarios_niveles.sort(key=lambda x: x[1], reverse=True)
    
    total_niveles = sum(level for _, level, _, _ in usuarios_niveles)
    nivel_mas_alto = usuarios_niveles[0][1]
    promedio_nivel = total_niveles // len(usuarios_niveles) if usuarios_niveles else 0
    
    items_por_pagina = 15
    paginas = []
    for i in range(0, len(usuarios_niveles), items_por_pagina):
        paginas.append(usuarios_niveles[i:i + items_por_pagina])
    
    if len(paginas) == 1:
        embed = crear_embed_levelboard(paginas[0], 1, 1, len(usuarios_niveles), total_niveles, nivel_mas_alto, promedio_nivel)
        await interaction.followup.send(embed=embed)
    else:
        view = LevelboardView(paginas, 0, len(usuarios_niveles), total_niveles, nivel_mas_alto, promedio_nivel)
        embed = crear_embed_levelboard(paginas[0], 1, len(paginas), len(usuarios_niveles), total_niveles, nivel_mas_alto, promedio_nivel)
        await interaction.followup.send(embed=embed, view=view)

def crear_embed_levelboard(usuarios, pagina_actual, total_paginas, total_usuarios, total_niveles, nivel_mas_alto, promedio_nivel):
    descripcion = ""
    posicion_inicio = (pagina_actual - 1) * 15 + 1
    
    for idx, (uid, level, xp, nombre) in enumerate(usuarios):
        posicion = posicion_inicio + idx
        medalla = ""
        if posicion == 1:
            medalla = "👑 "
        elif posicion == 2:
            medalla = "🥈 "
        elif posicion == 3:
            medalla = "🥉 "
        else:
            medalla = "🔹 "
        
        descripcion += f"{medalla} **#{posicion}** {nombre} • Nivel `{level}`\n"
    
    embed = discord.Embed(
        title="📈 Leaderboard - Niveles",
        description=descripcion or "No hay usuarios en esta página.",
        color=discord.Color.purple()
    )
    
    stats = (
        f"👥 **Usuarios con nivel:** {total_usuarios}\n"
        f"⭐ **Nivel más alto:** {nivel_mas_alto}\n"
        f"📊 **Promedio de nivel:** {promedio_nivel}\n"
        f"📚 **Total de niveles sumados:** {total_niveles}"
    )
    
    embed.add_field(name="📊 Estadísticas", value=stats, inline=False)
    embed.set_footer(text=f"Página {pagina_actual}/{total_paginas} • Mostrando {len(usuarios)} usuarios")
    return embed

class LevelboardView(discord.ui.View):
    def __init__(self, paginas, pagina_index, total_usuarios, total_niveles, nivel_mas_alto, promedio_nivel):
        super().__init__(timeout=60)
        self.paginas = paginas
        self.pagina_index = pagina_index
        self.total_usuarios = total_usuarios
        self.total_niveles = total_niveles
        self.nivel_mas_alto = nivel_mas_alto
        self.promedio_nivel = promedio_nivel
        self.message = None
        
        self.primera.disabled = (pagina_index == 0)
        self.anterior.disabled = (pagina_index == 0)
        self.siguiente.disabled = (pagina_index == len(paginas) - 1)
        self.ultima.disabled = (pagina_index == len(paginas) - 1)
        self.pagina_actual.label = f"Página {pagina_index + 1}/{len(paginas)}"

    @discord.ui.button(label="⏪", style=discord.ButtonStyle.secondary)
    async def primera(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.pagina_index = 0
        await self.actualizar_pagina(interaction)

    @discord.ui.button(label="◀", style=discord.ButtonStyle.primary)
    async def anterior(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.pagina_index -= 1
        await self.actualizar_pagina(interaction)

    @discord.ui.button(label="Página 1/1", style=discord.ButtonStyle.gray, disabled=True)
    async def pagina_actual(self, interaction: discord.Interaction, button: discord.ui.Button):
        pass

    @discord.ui.button(label="▶", style=discord.ButtonStyle.primary)
    async def siguiente(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.pagina_index += 1
        await self.actualizar_pagina(interaction)

    @discord.ui.button(label="⏩", style=discord.ButtonStyle.secondary)
    async def ultima(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.pagina_index = len(self.paginas) - 1
        await self.actualizar_pagina(interaction)

    async def actualizar_pagina(self, interaction: discord.Interaction):
        self.primera.disabled = (self.pagina_index == 0)
        self.anterior.disabled = (self.pagina_index == 0)
        self.siguiente.disabled = (self.pagina_index == len(self.paginas) - 1)
        self.ultima.disabled = (self.pagina_index == len(self.paginas) - 1)
        self.pagina_actual.label = f"Página {self.pagina_index + 1}/{len(self.paginas)}"
        
        embed = crear_embed_levelboard(
            self.paginas[self.pagina_index], 
            self.pagina_index + 1, 
            len(self.paginas),
            self.total_usuarios,
            self.total_niveles,
            self.nivel_mas_alto,
            self.promedio_nivel
        )
        await interaction.response.edit_message(embed=embed, view=self)

    async def on_timeout(self):
        if self.message:
            try:
                for item in self.children:
                    item.disabled = True
                await self.message.edit(view=self)
            except:
                pass
# ============================
# SISTEMA DE XP POR MENSAJES (CORREGIDO)
# ============================

# Cooldown para XP (evitar spam)
xp_cooldowns = {}

@bot.event
async def on_message(message):
    # Ignorar mensajes del bot
    if message.author.bot:
        return
    
    # Ignorar DMs
    if message.guild is None:
        return
    
    # Verificar que sea en el servidor permitido
    if message.guild.id != ALLOWED_GUILD_ID:
        return
    
    uid = str(message.author.id)
    now = int(time.time())
    
    # Cooldown de 60 segundos entre mensajes que dan XP
    last_xp = xp_cooldowns.get(uid, 0)
    if now - last_xp < 60:
        await bot.process_commands(message)
        return
    
    # Generar XP (entre 8 y 15 XP por mensaje)
    xp_gain = random.randint(8, 15)
    
    # Cargar niveles
    levels_data = load_levels()
    current_xp = levels_data.get(uid, {}).get("xp", 0)
    new_xp = current_xp + xp_gain
    
    # Guardar nombre del usuario
    if uid not in levels_data:
        levels_data[uid] = {}
    levels_data[uid]["xp"] = new_xp
    levels_data[uid]["nombre"] = message.author.display_name
    save_levels(levels_data)
    
    # Actualizar cooldown
    xp_cooldowns[uid] = now
    
    # Verificar si subió de nivel
    old_level = level_from_xp(current_xp)
    new_level = level_from_xp(new_xp)
    
    if new_level > old_level:
        # Notificar subida de nivel
        try:
            embed = discord.Embed(
                title="🎉 ¡SUBISTE DE NIVEL!",
                description=f"{message.author.mention} ahora eres nivel **{new_level}**",
                color=discord.Color.gold()
            )
            await message.channel.send(embed=embed)
        except:
            pass
    
    # Procesar comandos (importante para que otros comandos funcionen)
    await bot.process_commands(message)
# -------------------------
# RUN
# -------------------------
if __name__ == "__main__":
    # ensure data files exist
    save_json(BALANCES_FILE, balances)
    save_json(SHARED_FILE, shared_accounts)
    save_cryptos(cryptos)
    keep_alive()
    if not TOKEN:
        print("❌ TOKEN no encontrado en variables de entorno")
    else:
        bot.run(TOKEN)
