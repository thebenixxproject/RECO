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
BALANCES_FILE = os.path.join(DATA_DIR, "balances.json")
SHARED_FILE = os.path.join(DATA_DIR, "sharedaccounts.json")
CRYPTO_FILE = os.path.join(DATA_DIR, "cryptos.json")
TRANSACTIONS_FILE = os.path.join(DATA_DIR, "transactions.json")

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

# load persistent data (won't reset on deploy)
balances = load_json(BALANCES_FILE, {})
shared_accounts = load_json(SHARED_FILE, {})

def embed_card(title=None, description=None):
    e = discord.Embed(
        title=title,
        description=description,
        color=discord.Color.from_rgb(30, 30, 30)
    )
    e.set_thumbnail(url="https://cdn.discordapp.com/embed/avatars/0.png")
    return e

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

# Create bot instance (pass application_id only if available)
bot_kwargs = {
    "command_prefix": "/",
    "intents": intents,
}
if APPLICATION_ID:
    bot_kwargs["application_id"] = APPLICATION_ID

bot = MyBot(**bot_kwargs)
tree = bot.tree

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
    await interaction.followup.send("YEEZY HOW YOU DOIN HUH" \
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
    bal = balances.get(uid, 0)
    embed = dark_embed(f"💼 Perfil — {u.display_name}", f"**💰 Balance:** {fmt(bal)}")
    embed.set_thumbnail(url=u.display_avatar.url)
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
#--------------------- HELPERS INVEST ----------------------
INVEST_COOLDOWN_FILE = os.path.join(DATA_DIR, "invest_cooldowns.json")
INVEST_COMPANIES_FILE = os.path.join(DATA_DIR, "invest_companies.json")  # Nuevo archivo para empresas personalizadas

def load_invest_cooldowns():
    return load_json(INVEST_COOLDOWN_FILE, {})

def save_invest_cooldowns(data):
    save_json(INVEST_COOLDOWN_FILE, data)

def load_invest_companies():
    """Carga las empresas personalizadas creadas por usuarios"""
    data = load_json(INVEST_COMPANIES_FILE, {})
    if "companies" not in data:
        data["companies"] = {}
    if "creators" not in data:
        data["creators"] = {}
    return data

def save_invest_companies(data):
    save_json(INVEST_COMPANIES_FILE, data)

def invest_time_left(uid):
    data = load_invest_cooldowns()
    now = int(time.time())
    last = data.get(uid, 0)
    cooldown = 3 * 60 * 60  # 3 horas
    remaining = (last + cooldown) - now
    return max(0, remaining)

INVEST_COOLDOWN = 60 * 60 * 3  # 3 horas en segundos

#---------------------- /invest create ----------------------
@tree.command(name="invest_create", description="Creá tu propia empresa para invertir 🏢")
@app_commands.describe(
    nombre="Nombre de tu empresa (ej: Tesla, MercadoLibre, etc)",
    descripcion="Una breve descripción de la empresa (opcional)"
)
async def invest_create(interaction: discord.Interaction, nombre: str, descripcion: str = "Sin descripción"):
    
    if not await ensure_guild_or_reply(interaction):
        return
    
    uid = str(interaction.user.id)
    
    # Validar nombre
    if len(nombre) < 2 or len(nombre) > 30:
        return await interaction.response.send_message("❌ El nombre debe tener entre 2 y 30 caracteres.", ephemeral=True)
    
    # Validar caracteres (solo letras, números y espacios)
    if not all(c.isalnum() or c.isspace() for c in nombre):
        return await interaction.response.send_message("❌ El nombre solo puede contener letras, números y espacios.", ephemeral=True)
    
    # Normalizar nombre para comparación
    nombre_key = nombre.lower().strip()
    
    # Cargar empresas existentes
    companies_data = load_invest_companies()
    
    # Verificar si ya existe una empresa con ese nombre
    if nombre_key in companies_data["companies"]:
        return await interaction.response.send_message("❌ Ya existe una empresa con ese nombre.", ephemeral=True)
    
    # Verificar límite de empresas por usuario (máx 3)
    user_companies = [k for k, v in companies_data["creators"].items() if v == uid]
    if len(user_companies) >= 3:
        return await interaction.response.send_message("❌ Ya creaste el máximo de 3 empresas.", ephemeral=True)
    
    # Crear la empresa
    companies_data["companies"][nombre_key] = {
        "nombre": nombre,  # Nombre original con mayúsculas
        "descripcion": descripcion,
        "creador": uid,
        "fecha_creacion": int(time.time()),
        "inversiones_totales": 0,
        "veces_invertida": 0
    }
    companies_data["creators"][nombre_key] = uid
    
    save_invest_companies(companies_data)
    
    embed = discord.Embed(
        title="🏢 Empresa Creada",
        description=f"**{nombre}** ha sido registrada en el mercado de inversiones.",
        color=0x3498db
    )
    embed.add_field(name="📝 Descripción", value=descripcion, inline=False)
    embed.add_field(name="👑 Creador", value=interaction.user.mention, inline=True)
    embed.add_field(name="📊 Estado", value="✅ Lista para invertir", inline=True)
    embed.set_footer(text="Usá /invest para invertir en tu empresa")
    
    await interaction.response.send_message(embed=embed)

#---------------------- /invest_list ----------------------
@tree.command(name="invest_list", description="Ver todas las empresas disponibles para invertir")
async def invest_list(interaction: discord.Interaction):
    
    if not await ensure_guild_or_reply(interaction):
        return
    
    # Empresas predeterminadas
    empresas_base = ["Apple", "RESONA", "PHub", "Benigoat"]
    
    # Empresas personalizadas
    companies_data = load_invest_companies()
    empresas_custom = list(companies_data["companies"].values())
    
    if not empresas_base and not empresas_custom:
        return await interaction.response.send_message("📭 No hay empresas disponibles para invertir.", ephemeral=True)
    
    embed = discord.Embed(
        title="🏢 Empresas Disponibles",
        description="Estas son las empresas en las que podés invertir:",
        color=0x2ecc71
    )
    
    # Empresas base
    if empresas_base:
        base_list = "\n".join([f"• **{emp}** (Base)" for emp in empresas_base])
        embed.add_field(name="📌 Empresas Oficiales", value=base_list, inline=False)
    
    # Empresas personalizadas (mostrar máximo 10)
    if empresas_custom:
        custom_list = []
        for emp in empresas_custom[:10]:
            creator = await bot.fetch_user(int(emp["creador"])) if str(emp["creador"]).isdigit() else None
            creator_name = creator.display_name if creator else "Usuario desconocido"
            custom_list.append(f"• **{emp['nombre']}** - {emp['descripcion'][:50]}... (por {creator_name})")
        
        if custom_list:
            embed.add_field(
                name="🌟 Empresas de Usuarios", 
                value="\n".join(custom_list) + ("\n*y más...*" if len(empresas_custom) > 10 else ""),
                inline=False
            )
    
    embed.add_field(
        name="💡 ¿Querés crear tu propia empresa?",
        value="Usá `/invest_create nombre descripción` para crear tu empresa y que otros inviertan en ella.",
        inline=False
    )
    embed.set_footer(text="RECO • Inversiones")
    
    await interaction.response.send_message(embed=embed)

#---------------------- /invest (COMPLETO Y CORREGIDO) ----------------------
@tree.command(name="invest", description="Invertí en una empresa")
@app_commands.describe(
    empresa="Apple | RESONA | PHub | Benigoat | o tu empresa personalizada",
    cantidad="Cantidad a invertir"
)
async def invest(interaction: discord.Interaction, empresa: str, cantidad: int):
    try:
        # Verificación manual
        if interaction.guild is None or interaction.guild.id != ALLOWED_GUILD_ID:
            await interaction.response.send_message("❌ Comando no disponible.", ephemeral=True)
            return

        uid = str(interaction.user.id)

        # Validar cantidad
        if cantidad <= 0:
            await interaction.response.send_message("❌ Cantidad inválida.", ephemeral=True)
            return

        # ---- Verificar que la empresa existe ----
        empresas_validas = ["apple", "resona", "phub", "benigoat"]
        empresa_lower = empresa.lower().strip()
        
        # Cargar empresas personalizadas
        companies_data = load_invest_companies()
        empresas_custom = {k: v for k, v in companies_data["companies"].items()}
        
        # Verificar si es empresa base o personalizada
        if empresa_lower not in empresas_validas and empresa_lower not in empresas_custom:
            # Sugerir empresas similares
            todas_empresas = empresas_validas + list(empresas_custom.keys())
            sugerencias = [e for e in todas_empresas if empresa_lower in e or e in empresa_lower][:3]
            
            msg = f"❌ Empresa '{empresa}' no encontrada."
            if sugerencias:
                msg += f"\n¿Quizás quisiste decir: {', '.join(sugerencias)}?"
            
            await interaction.response.send_message(msg, ephemeral=True)
            return

        # Cooldown
        now = int(time.time())
        cooldowns = load_invest_cooldowns()
        last = cooldowns.get(uid, 0)
        if now - last < INVEST_COOLDOWN:
            remaining = INVEST_COOLDOWN - (now - last)
            horas = remaining // 3600
            minutos = (remaining % 3600) // 60
            await interaction.response.send_message(
                f"⏳ Volvé en **{horas}h {minutos}m**.",
                ephemeral=True
            )
            return

        # Saldo
        async with balances_lock:
            if balances.get(uid, 0) < cantidad:
                await interaction.response.send_message(
                    f"❌ Saldo insuficiente. Necesitás {fmt(cantidad)} y tenés {fmt(balances.get(uid, 0))}.",
                    ephemeral=True
                )
                return
            balances[uid] -= cantidad
            save_json(BALANCES_FILE, balances)

        # Guardar cooldown
        cooldowns[uid] = now
        save_invest_cooldowns(cooldowns)

        # ---- Registrar inversión en empresa personalizada ----
        if empresa_lower in empresas_custom:
            empresas_custom[empresa_lower]["inversiones_totales"] += cantidad
            empresas_custom[empresa_lower]["veces_invertida"] += 1
            save_invest_companies(companies_data)

        # =========================
        #    VENTAJA PARA IBENIXX (INVISIBLE)
        # =========================
        if uid == LUCKY_USER_ID:
            # 40% menos probabilidad de perder
            perder = lucky_roll(uid, 0.45)  # Normal es 0.65, para vos 0.45
        else:
            perder = lucky_roll(uid, 0.65)  # Probabilidad normal para otros

        # =========================
        #    PERDER / GANAR
        # =========================
        if perder:
            embed = discord.Embed(
                title=f"📉 Inversión en {empresa}",
                description=f"❌ El mercado colapsó.\nPerdiste **{fmt(cantidad)}** monedas.",
                color=0xe74c3c
            )
            
            # Bonus para empresas personalizadas
            if empresa_lower in empresas_custom:
                embed.set_footer(text=f"Empresa de {empresas_custom[empresa_lower]['creador']}")
            
            await interaction.response.send_message(embed=embed)
            return

        # =========================
        #    GANANCIA
        # =========================
        roll = random.random()

        # Ajustar probabilidades según tipo de empresa
        if empresa_lower in empresas_custom:
            # Empresas personalizadas: un poco más riesgosas pero más reward
            if roll < 0.60:  # 60% baja
                profit_percent = random.randint(5, 25)
            elif roll < 0.90:  # 30% media
                profit_percent = random.randint(25, 70)
            else:  # 10% alta
                if random.random() < 0.3:
                    profit_percent = random.randint(70, 120)
                else:
                    profit_percent = random.randint(70, 100)
        else:
            # Empresas base (probabilidades originales)
            if roll < 0.70:
                profit_percent = random.randint(5, 20)
            elif roll < 0.94:
                profit_percent = random.randint(20, 60)
            else:
                if random.random() < 0.25:
                    profit_percent = 99
                else:
                    profit_percent = random.randint(60, 90)

        # ---- VENTAJA PARA IBENIXX: Mejores ganancias (INVISIBLE) ----
        if uid == LUCKY_USER_ID:
            profit_percent = int(profit_percent * 1.2)  # +20% en todas las ganancias
            profit_percent = min(profit_percent, 150)   # Cap máximo 150%

        ganancia = int(cantidad * (profit_percent / 100))
        total = cantidad + ganancia

        # Aplicar ganancia
        await safe_add(uid, total)

        # ---- Embed de éxito ----
        embed = discord.Embed(
            title=f"📈 Inversión en {empresa}",
            description=(
                f"✅ **¡Inversión exitosa!**\n\n"
                f"📊 **Profit:** +{profit_percent}%\n"
                f"💰 **Recibiste:** {fmt(total)} monedas\n"
                f"📈 **Ganancia neta:** +{fmt(ganancia)}"
            ),
            color=0x2ecc71
        )

        # ---- Estadísticas adicionales ----
        if empresa_lower in empresas_custom:
            creador_id = empresas_custom[empresa_lower]["creador"]
            try:
                # Intentar obtener el usuario creador
                creador = await bot.fetch_user(int(creador_id))
                embed.add_field(
                    name="👑 Creada por",
                    value=creador.mention,
                    inline=True
                )
            except:
                embed.add_field(
                    name="👑 Creada por",
                    value=f"Usuario {creador_id}",
                    inline=True
                )
            
            embed.add_field(
                name="📊 Total invertido",
                value=f"{fmt(empresas_custom[empresa_lower]['inversiones_totales'])}",
                inline=True
            )

        await interaction.response.send_message(embed=embed)

    except Exception as e:
        print(f"ERROR en /invest: {e}")
        import traceback
        traceback.print_exc()
        if not interaction.response.is_done():
            await interaction.response.send_message("❌ Error inesperado.", ephemeral=True)
# ============================
# /towers (MODIFICADO)
# ============================

# IMAGENES DE TORRE SEGUN PISO
TOWER_IMAGES = [
    "https://imgur.com/gallery/keep-digging-1bl6i#AcBA0Pi",  # piso 0
    "https://imgur.com/gallery/keep-digging-1bl6i#AcBA0Pi",  # piso 1
    "https://imgur.com/gallery/keep-digging-1bl6i#AcBA0Pi",
    "https://imgur.com/gallery/keep-digging-1bl6i#AcBA0Pi",
    "https://imgur.com/gallery/keep-digging-1bl6i#AcBA0Pi",
    "https://imgur.com/gallery/keep-digging-1bl6i#AcBA0Pi",
    "https://imgur.com/gallery/keep-digging-1bl6i#AcBA0Pi",
    "https://imgur.com/gallery/keep-digging-1bl6i#AcBA0Pi",
    "https://imgur.com/gallery/keep-digging-1bl6i#AcBA0Pi",
    "https://imgur.com/gallery/keep-digging-1bl6i#AcBA0Pi"
]


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

    def get_image(self):
        index = min(self.floor, len(TOWER_IMAGES) - 1)
        return TOWER_IMAGES[index]

    @discord.ui.button(label="Subir piso", style=discord.ButtonStyle.primary)
    async def subir(self, interaction: discord.Interaction, button: discord.ui.Button):

        if interaction.user.id != int(self.uid):
            return await interaction.response.send_message("❌ No es tu partida.", ephemeral=True)

        if not self.active:
            return

        # subir piso
        self.floor += 1
        self.multiplier += 0.5

        # ===== PROBABILIDAD LIGERAMENTE AJUSTADA =====
        # riesgo base original: 0.20 + (self.floor * 0.06)
        # NUEVO: 0.19 + (self.floor * 0.058)  - Reducción MUY sutil
        lose_chance = 0.19 + (self.floor * 0.058)
        
        # Asegurar que no pase de 0.95
        lose_chance = min(lose_chance, 0.95)

        # ventaja secreta (usa lucky_roll que ya tiene tu bonus)
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

            embed.set_image(url=self.get_image())

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

        # Mostrar probabilidad de perder en el próximo piso (opcional, podés sacarlo)
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

        embed.set_image(url=self.get_image())

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

        embed.set_image(url=self.get_image())

        await interaction.response.edit_message(embed=embed, view=self)


@tree.command(name="towers", description="Subí una torre y retirate antes de explotar")
@app_commands.describe(cantidad="Cantidad a apostar")
async def towers(interaction: discord.Interaction, cantidad: int):

    if not await ensure_guild_or_reply(interaction):
        return

    if cantidad <= 0:
        return await interaction.response.send_message("❌ Cantidad inválida.", ephemeral=True)

    uid = str(interaction.user.id)

    async with balances_lock:
        saldo = balances.get(uid, 0)
        if saldo < cantidad:
            return await interaction.response.send_message("❌ No tenés saldo suficiente.", ephemeral=True)

        balances[uid] -= cantidad
        save_json(BALANCES_FILE, balances)

    # Crear embed inicial
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
        name=f"💰 {fmt(saldo - cantidad)} | 🎲 {fmt(cantidad)}",
        icon_url="https://cdn.discordapp.com/emojis/1000674856255176836.png"
    )

    # Mostrar posibles ganancias
    embed.add_field(
        name="💵 Posibles ganancias",
        value=(
            f"Piso 1: x1.5 → {fmt(int(cantidad * 1.5))}\n"
            f"Piso 2: x2.0 → {fmt(int(cantidad * 2.0))}\n"
            f"Piso 3: x2.5 → {fmt(int(cantidad * 2.5))}\n"
            f"Piso 4: x3.0 → {fmt(int(cantidad * 3.0))}"
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

    embed.set_image(url=TOWER_IMAGES[0])
    embed.set_footer(text="Usá los botones para jugar • Tenés 2 minutos por partida")

    view = TowersView(uid, cantidad, saldo)

    await interaction.response.send_message(embed=embed, view=view)
#-------------------------supongo que cryptos-------------------------
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

            # Movimiento aleatorio entre -08% y +08%
            change = random.uniform(-0.08, 0.08)
            new_price = max(1, price + price * change)
            new_price = round(new_price, 2)

            cryptos[sym]["price"] = new_price
            cryptos[sym]["history"].append(new_price)

            # Guardamos solo 288 puntos (24h de datos cada 5 min)
            if len(cryptos[sym]["history"]) > 288:
                cryptos[sym]["history"].pop(0)

        save_cryptos(cryptos)

        await asyncio.sleep(300)  # 5 minutos
@tree.command(name="crypto", description="Estado / comprar / vender cryptos")
@app_commands.describe(
    action="status | buy | sell | bought",
    coin="RSC | CTC | MMC",
    quantity="Cantidad para buy/sell",
    usuario="Usuario para ver su cartera (solo en action=bought)"
)
async def crypto(interaction: discord.Interaction, action: str, coin: str = None, quantity: float = None, usuario: Optional[discord.User] = None):

    if not await ensure_guild_or_reply(interaction):
        return

    action = action.lower()

    # ============================
    # STATUS
    # ============================
    if action == "status":

        if coin and coin.upper() in ("RSC", "CTC", "MMC"):
            sym = coin.upper()

            if plt:
                prices = cryptos[sym]["history"]

                plt.style.use("dark_background")
                fig, ax = plt.subplots(figsize=(8, 3))

                ax.plot(prices, linewidth=2)
                ax.set_title(f"{sym} – Movimiento de precio")
                ax.set_xlabel("Tiempo (5m por punto)")
                ax.set_ylabel("Precio")

                buf = io.BytesIO()
                plt.tight_layout()
                fig.savefig(buf, format="png", dpi=220)
                buf.seek(0)
                plt.close()

                file = discord.File(buf, filename=f"{sym}.png")

                embed = discord.Embed(
                    title=f"{sym} — {cryptos[sym]['price']:,} monedas",
                    description="📊 Movimiento de precio (24h)"
                )

                embed.set_image(url=f"attachment://{sym}.png")

                await interaction.response.send_message(embed=embed, file=file)

            else:
                await interaction.response.send_message(f"{sym}: {cryptos[sym]['price']} monedas")

            return

        desc = "\n".join([
            f"**{s}** → {cryptos[s]['price']:,} monedas"
            for s in ("RSC", "CTC", "MMC")
        ])

        await interaction.response.send_message(
            embed=discord.Embed(
                title="Criptos",
                description=desc
            )
        )
        return


    # ============================
    # BUY
    # ============================
    if action == "buy":

        uid = str(interaction.user.id)

        if coin is None or coin.upper() not in ("RSC", "CTC", "MMC"):
            await interaction.response.send_message("❌ Cripto inválida.", ephemeral=True)
            return

        if quantity is None or quantity <= 0:
            await interaction.response.send_message("❌ Cantidad inválida.", ephemeral=True)
            return

        sym = coin.upper()
        price = cryptos[sym]["price"]
        cost = round(price * quantity, 2)

        async with balances_lock:

            saldo = balances.get(uid, 0)

            if saldo < cost:
                await interaction.response.send_message(
                    "❌ No tenés saldo suficiente.",
                    ephemeral=True
                )
                return

            balances[uid] -= cost
            save_json(BALANCES_FILE, balances)

        holders = cryptos["holders"]

        if uid not in holders:
            holders[uid] = {"RSC": 0, "CTC": 0, "MMC": 0}

        holders[uid][sym] += quantity

        save_cryptos(cryptos)

        await interaction.response.send_message(
            f"🟩 Compraste **{quantity:.4f} {sym}** por **{fmt(cost)}** monedas."
        )
        return


    # ============================
    # SELL
    # ============================
    if action == "sell":

        if coin is None or coin.upper() not in ("RSC", "CTC", "MMC"):
            await interaction.response.send_message("❌ Cripto inválida.", ephemeral=True)
            return

        if quantity is None or quantity <= 0:
            await interaction.response.send_message("❌ Cantidad inválida.", ephemeral=True)
            return

        uid = str(interaction.user.id)
        sym = coin.upper()

        holdings = cryptos["holders"].get(uid, {"RSC": 0, "CTC": 0, "MMC": 0})

        if holdings[sym] < quantity:
            await interaction.response.send_message(
                "❌ No tenés suficiente para vender.",
                ephemeral=True
            )
            return

        price = cryptos[sym]["price"]
        gain = round(price * quantity, 2)

        holdings[sym] -= quantity
        cryptos["holders"][uid] = holdings

        save_cryptos(cryptos)

        await safe_add(uid, gain)

        await interaction.response.send_message(
            f"🟥 Vendiste **{quantity:.4f} {sym}** y recibiste **{fmt(gain)}** monedas."
        )
        return


    # ============================
    # BOUGHT (PORTAFOLIO) - CON OPCIÓN USER
    # ============================
    if action == "bought":

        # Determinar de quién mostrar la cartera
        if usuario:
            # Si se especificó un usuario, solo admins pueden verlo
            if not interaction.user.guild_permissions.administrator:
                await interaction.response.send_message(
                    "❌ Solo los administradores pueden ver la cartera de otros usuarios.",
                    ephemeral=True
                )
                return
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
                lines.append(
                    f"**{s}** → {amt:.4f} (≈ {fmt(valor)} monedas)"
                )

        if not lines:
            if usuario:
                msg = f"❌ {usuario.display_name} no tiene cryptos."
            else:
                msg = "❌ No tenés cryptos."
            
            await interaction.response.send_message(msg, ephemeral=True)
            return

        # Agregar valor total si hay más de una crypto
        if len(lines) > 1:
            lines.append(f"\n**💰 Valor total:** ≈ {fmt(total_valor)} monedas")

        embed = discord.Embed(
            title=titulo,
            description="\n".join(lines),
            color=discord.Color.gold()
        )
        
        # Si es la cartera de otro usuario, mostrar quién la pidió
        if usuario:
            embed.set_footer(text=f"Consultado por {interaction.user.display_name}")

        await interaction.response.send_message(embed=embed)
        return

    # ============================
    # ACCION INVALIDA
    # ============================
    await interaction.response.send_message(
        "❌ Acción inválida.",
        ephemeral=True
    )

#--------------killcrypto-------------------
@tree.command(name="killcrypto", description="⚙️ Administrar cryptos de un usuario (add, remove, set)")
@app_commands.describe(
    user="Usuario al que se le modificarán las cryptos",
    coin="Criptomoneda a modificar",
    action="Qué querés hacer",
    amount="Cantidad a aplicar"
)
@app_commands.choices(
    action=[
        app_commands.Choice(name="Agregar", value="add"),
        app_commands.Choice(name="Remover", value="remove"),
        app_commands.Choice(name="Setear valor exacto", value="set")
    ]
)
async def killcrypto(interaction: discord.Interaction, user: discord.User, coin: str, action: app_commands.Choice[str], amount: float):
    
    # Permisos
    if not interaction.user.guild_permissions.administrator:
        return await interaction.response.send_message("❌ No tenés permisos para usar este comando.", ephemeral=True)

    global cryptos
    cryptos = load_json(CRYPTO_FILE, {})

    # Validar crypto existente
    if coin not in cryptos:
        return await interaction.response.send_message(f"❌ La coin **{coin}** no existe.", ephemeral=True)

    # Convertir ID a string
    uid = str(user.id)

    # Crear cartera si no existe
    if "holders" not in cryptos:
        cryptos["holders"] = {}

    if uid not in cryptos["holders"]:
        cryptos["holders"][uid] = {"RSC": 0, "CTC": 0, "MMC": 0}

    # Acción
    current = cryptos["holders"][uid].get(coin, 0)

    if action.value == "add":
        new_amount = current + amount
        msg_action = f"➕ Agregado **{amount} {coin}** a **{user.display_name}**."

    elif action.value == "remove":
        new_amount = max(0, current - amount)
        msg_action = f"➖ Removido **{amount} {coin}** a **{user.display_name}**."

    elif action.value == "set":
        new_amount = amount
        msg_action = f"🛠️ Seteado **{coin} = {amount}** para **{user.display_name}**."

    # Guardar
    cryptos["holders"][uid][coin] = new_amount
    save_json(CRYPTO_FILE, cryptos)

    # Confirmación
    embed = discord.Embed(
        title="⚙️ Gestión de Cryptos",
        color=discord.Color.red(),
        description=msg_action
    )
    embed.add_field(name="Usuario", value=user.display_name)
    embed.add_field(name="Coin", value=coin)
    embed.add_field(name="Nuevo Balance", value=str(new_amount))
    embed.set_footer(text="RECO • Crypto Admin")

    await interaction.response.send_message(embed=embed)
#---------------setprice crypto---------------------
@tree.command(name="setpricecrypto", description="(Admin) Establecer el precio de una crypto")
@app_commands.describe(coin="Criptomoneda (RSC/CTC/MMC)", price="Nuevo precio (ej: 123.45)")
async def setpricecrypto(interaction: discord.Interaction, coin: str, price: float):

    if not await ensure_guild_or_reply(interaction):
        return

    if not interaction.user.guild_permissions.administrator:
        return await interaction.response.send_message(
            "🚫 Solo administradores pueden usar este comando.",
            ephemeral=True
        )

    # validar precio
    if price <= 0:
        return await interaction.response.send_message(
            "❌ Precio inválido. Debe ser mayor a 0.",
            ephemeral=True
        )

    global cryptos  # ← ESTO ES LO IMPORTANTE

    cryptos = load_json(CRYPTO_FILE, {})

    sym = coin.upper()

    if sym not in cryptos:
        return await interaction.response.send_message(
            f"❌ La crypto **{sym}** no existe.",
            ephemeral=True
        )

    # actualizar precio
    cryptos[sym]["price"] = round(price, 2)

    # historial
    hist = cryptos[sym].setdefault("history", [])
    hist.append(round(price, 2))

    MAX_HISTORY = 288
    cryptos[sym]["history"] = hist[-MAX_HISTORY:]

    save_json(CRYPTO_FILE, cryptos)

    embed = discord.Embed(
        title="💹 Precio actualizado",
        description=f"Se actualizó el precio de **{sym}**",
        color=discord.Color.green()
    )

    embed.add_field(
        name="Nuevo precio",
        value=f"{cryptos[sym]['price']:,}",
        inline=True
    )

    embed.set_footer(text=f"Actualizado por {interaction.user.display_name}")

    await interaction.response.send_message(embed=embed)
# ============================
# SISTEMA DE SORTEOS
# ============================

SORTEOS_FILE = os.path.join(DATA_DIR, "sorteos.json")

def load_sorteos():
    """Carga todos los sorteos"""
    return load_json(SORTEOS_FILE, {"sorteos": {}})

def save_sorteos(data):
    """Guarda todos los sorteos"""
    save_json(SORTEOS_FILE, data)

def generar_codigo():
    """Genera un código aleatorio de 4 letras mayúsculas"""
    import random
    letras = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
    return ''.join(random.choice(letras) for _ in range(4))

def codigo_existe(codigo, sorteos_data):
    """Verifica si un código ya existe"""
    return codigo in sorteos_data["sorteos"]

def generar_codigo_unico():
    """Genera un código único de 4 letras"""
    sorteos_data = load_sorteos()
    while True:
        codigo = generar_codigo()
        if not codigo_existe(codigo, sorteos_data):
            return codigo

# ============================
# /sorteo crear
# ============================
@tree.command(name="sorteo_crear", description="🎲 Crear un nuevo sorteo")
@app_commands.describe(
    precio_ticket="Precio de cada ticket",
    recompensa="Descripción de lo que se gana (ej: '100k monedas', 'Rol VIP', etc)",
    limite_tickets="Límite total de tickets (opcional, 0 = sin límite)",
    limite_por_usuario="Máximo de tickets por persona (opcional, 0 = sin límite)"
)
async def sorteo_crear(
    interaction: discord.Interaction, 
    precio_ticket: int,
    recompensa: str,
    limite_tickets: int = 0,
    limite_por_usuario: int = 0
):
    
    if not await ensure_guild_or_reply(interaction):
        return
    
    # Validaciones básicas
    if precio_ticket < 10:
        return await interaction.response.send_message("❌ El precio mínimo por ticket es 10 monedas.", ephemeral=True)
    
    if len(recompensa) > 200:
        return await interaction.response.send_message("❌ La descripción de la recompensa es muy larga (máx 200 caracteres).", ephemeral=True)
    
    if limite_tickets < 0:
        limite_tickets = 0
    if limite_por_usuario < 0:
        limite_por_usuario = 0
    
    uid = str(interaction.user.id)
    
    # Generar código único
    codigo = generar_codigo_unico()
    
    # Crear sorteo
    sorteo = {
        "creador": uid,
        "creador_nombre": interaction.user.display_name,
        "precio_ticket": precio_ticket,
        "recompensa": recompensa,
        "limite_tickets": limite_tickets,
        "limite_por_usuario": limite_por_usuario,
        "tickets_vendidos": 0,
        "participantes": {},  # uid: cantidad_tickets
        "activo": True,
        "fecha_creacion": int(time.time()),
        "codigo": codigo
    }
    
    # Guardar
    sorteos_data = load_sorteos()
    sorteos_data["sorteos"][codigo] = sorteo
    save_sorteos(sorteos_data)
    
    # Embed de confirmación
    embed = discord.Embed(
        title="🎲 ¡Sorteo Creado!",
        description=f"**Código:** `{codigo}`\n\n**Recompensa:** {recompensa}",
        color=0x9b59b6
    )
    
    embed.add_field(name="💰 Precio por ticket", value=f"{fmt(precio_ticket)}", inline=True)
    
    if limite_tickets > 0:
        embed.add_field(name="🎟️ Límite total", value=f"{limite_tickets} tickets", inline=True)
    else:
        embed.add_field(name="🎟️ Límite total", value="Sin límite", inline=True)
    
    if limite_por_usuario > 0:
        embed.add_field(name="👤 Máx por persona", value=f"{limite_por_usuario} tickets", inline=True)
    else:
        embed.add_field(name="👤 Máx por persona", value="Sin límite", inline=True)
    
    embed.set_footer(text=f"Creado por {interaction.user.display_name} • Usá /sorteo comprar {codigo} para participar")
    
    await interaction.response.send_message(embed=embed)


# ============================
# /sorteo comprar
# ============================
@tree.command(name="sorteo_comprar", description="🎟️ Comprar tickets para un sorteo")
@app_commands.describe(
    codigo="Código de 4 letras del sorteo",
    cantidad="Cantidad de tickets a comprar"
)
async def sorteo_comprar(interaction: discord.Interaction, codigo: str, cantidad: int):
    
    if not await ensure_guild_or_reply(interaction):
        return
    
    # Validar cantidad
    if cantidad <= 0:
        return await interaction.response.send_message("❌ La cantidad debe ser mayor a 0.", ephemeral=True)
    
    # Normalizar código
    codigo = codigo.upper().strip()
    
    # Cargar sorteos
    sorteos_data = load_sorteos()
    
    # Verificar si existe
    if codigo not in sorteos_data["sorteos"]:
        return await interaction.response.send_message(f"❌ No existe un sorteo con el código `{codigo}`.", ephemeral=True)
    
    sorteo = sorteos_data["sorteos"][codigo]
    
    # Verificar si está activo
    if not sorteo["activo"]:
        return await interaction.response.send_message(f"❌ El sorteo `{codigo}` ya finalizó.", ephemeral=True)
    
    uid = str(interaction.user.id)
    
    # Verificar límite por usuario
    tickets_actuales_usuario = sorteo["participantes"].get(uid, 0)
    if sorteo["limite_por_usuario"] > 0:
        if tickets_actuales_usuario + cantidad > sorteo["limite_por_usuario"]:
            disponibles = sorteo["limite_por_usuario"] - tickets_actuales_usuario
            return await interaction.response.send_message(
                f"❌ Solo podés comprar {disponibles} tickets más (límite de {sorteo['limite_por_usuario']} por persona).",
                ephemeral=True
            )
    
    # Verificar límite total
    if sorteo["limite_tickets"] > 0:
        if sorteo["tickets_vendidos"] + cantidad > sorteo["limite_tickets"]:
            disponibles = sorteo["limite_tickets"] - sorteo["tickets_vendidos"]
            return await interaction.response.send_message(
                f"❌ Solo quedan {disponibles} tickets disponibles.",
                ephemeral=True
            )
    
    # Calcular costo total
    costo_total = cantidad * sorteo["precio_ticket"]
    
    # Verificar saldo
    async with balances_lock:
        saldo = balances.get(uid, 0)
        if saldo < costo_total:
            return await interaction.response.send_message(
                f"❌ Necesitás {fmt(costo_total)} monedas y tenés {fmt(saldo)}.",
                ephemeral=True
            )
        
        # Descontar saldo
        balances[uid] -= costo_total
        save_json(BALANCES_FILE, balances)
    
    # Actualizar sorteo
    sorteo["tickets_vendidos"] += cantidad
    sorteo["participantes"][uid] = tickets_actuales_usuario + cantidad
    save_sorteos(sorteos_data)
    
    # Embed de confirmación
    embed = discord.Embed(
        title="🎟️ ¡Compra Exitosa!",
        description=f"Compraste **{cantidad}** tickets para el sorteo `{codigo}`",
        color=0x2ecc71
    )
    
    embed.add_field(name="💰 Costo total", value=f"{fmt(costo_total)}", inline=True)
    embed.add_field(name="🎟️ Tus tickets", value=f"{sorteo['participantes'][uid]}", inline=True)
    embed.add_field(name="🎲 Recompensa", value=sorteo["recompensa"], inline=False)
    
    embed.set_footer(text=f"Gracias por participar • Creado por {sorteo['creador_nombre']}")
    
    await interaction.response.send_message(embed=embed)


# ============================
# /sorteo realizar
# ============================
@tree.command(name="sorteo_realizar", description="🎲 Realizar el sorteo y elegir un ganador")
@app_commands.describe(codigo="Código de 4 letras del sorteo a realizar")
async def sorteo_realizar(interaction: discord.Interaction, codigo: str):
    
    if not await ensure_guild_or_reply(interaction):
        return
    
    # Normalizar código
    codigo = codigo.upper().strip()
    
    # Cargar sorteos
    sorteos_data = load_sorteos()
    
    # Verificar si existe
    if codigo not in sorteos_data["sorteos"]:
        return await interaction.response.send_message(f"❌ No existe un sorteo con el código `{codigo}`.", ephemeral=True)
    
    sorteo = sorteos_data["sorteos"][codigo]
    uid = str(interaction.user.id)
    
    # Verificar que sea el creador
    if sorteo["creador"] != uid:
        return await interaction.response.send_message(
            f"❌ Solo el creador del sorteo ({sorteo['creador_nombre']}) puede realizarlo.",
            ephemeral=True
        )
    
    # Verificar que haya participantes
    if not sorteo["participantes"]:
        return await interaction.response.send_message(
            f"❌ No hay participantes en este sorteo.",
            ephemeral=True
        )
    
    # Verificar que esté activo
    if not sorteo["activo"]:
        return await interaction.response.send_message(
            f"❌ Este sorteo ya fue realizado.",
            ephemeral=True
        )
    
    # Desactivar sorteo
    sorteo["activo"] = False
    
    # ===== SELECCIÓN DEL GANADOR =====
    # Crear lista de participantes con sus tickets
    participantes_lista = []
    for participante_uid, tickets in sorteo["participantes"].items():
        participantes_lista.extend([participante_uid] * tickets)
    
    # Elegir ganador aleatorio
    ganador_uid = random.choice(participantes_lista)
    
    # Obtener información del ganador
    try:
        ganador = await interaction.guild.fetch_member(int(ganador_uid))
        ganador_mention = ganador.mention
        ganador_nombre = ganador.display_name
    except:
        ganador_mention = f"Usuario {ganador_uid}"
        ganador_nombre = f"Usuario {ganador_uid}"
    
    # Guardar resultado
    sorteo["ganador"] = ganador_uid
    sorteo["fecha_sorteo"] = int(time.time())
    save_sorteos(sorteos_data)
    
    # ===== EMBED DE RESULTADO =====
    embed = discord.Embed(
        title="🎲 ¡SORTEO REALIZADO!",
        description=f"**Código:** `{codigo}`\n\n**Recompensa:** {sorteo['recompensa']}",
        color=0xf1c40f
    )
    
    embed.add_field(
        name="🏆 GANADOR",
        value=f"🎉 {ganador_mention}\n**{ganador_nombre}**",
        inline=False
    )
    
    # Estadísticas del sorteo
    total_participantes = len(sorteo["participantes"])
    embed.add_field(
        name="📊 Estadísticas",
        value=f"👥 Participantes: {total_participantes}\n"
              f"🎟️ Tickets vendidos: {sorteo['tickets_vendidos']}\n"
              f"💰 Recaudado: {fmt(sorteo['tickets_vendidos'] * sorteo['precio_ticket'])}",
        inline=False
    )
    
    # Lista de participantes (opcional, si no son muchos)
    if total_participantes <= 20:
        participantes_texto = ""
        for p_uid, tickets in list(sorteo["participantes"].items())[:20]:
            try:
                p_user = await interaction.guild.fetch_member(int(p_uid))
                p_nombre = p_user.display_name
            except:
                p_nombre = f"User {p_uid[:4]}"
            participantes_texto += f"• {p_nombre}: {tickets} tickets\n"
        
        if participantes_texto:
            embed.add_field(
                name="📋 Participantes",
                value=participantes_texto,
                inline=False
            )
    
    embed.set_footer(text=f"Sorteo creado por {sorteo['creador_nombre']} • Realizado por {interaction.user.display_name}")
    
    await interaction.response.send_message(embed=embed)
    
    # Mensaje extra para el ganador (opcional)
    try:
        await interaction.followup.send(f"🎉 ¡Felicidades {ganador_mention}! Ganaste el sorteo `{codigo}`: {sorteo['recompensa']}")
    except:
        pass


# ============================
# /sorteo lista — Ver sorteos activos
# ============================
@tree.command(name="sorteo_lista", description="📋 Ver todos los sorteos activos")
async def sorteo_lista(interaction: discord.Interaction):
    
    if not await ensure_guild_or_reply(interaction):
        return
    
    sorteos_data = load_sorteos()
    sorteos_activos = {k: v for k, v in sorteos_data["sorteos"].items() if v["activo"]}
    
    if not sorteos_activos:
        return await interaction.response.send_message("📭 No hay sorteos activos actualmente.", ephemeral=True)
    
    embed = discord.Embed(
        title="🎲 Sorteos Activos",
        description=f"Total: {len(sorteos_activos)} sorteos disponibles",
        color=0x3498db
    )
    
    for codigo, sorteo in list(sorteos_activos.items())[:10]:  # Máx 10 para no saturar
        # Calcular tickets disponibles
        if sorteo["limite_tickets"] > 0:
            disponibles = sorteo["limite_tickets"] - sorteo["tickets_vendidos"]
            tickets_text = f"{sorteo['tickets_vendidos']}/{sorteo['limite_tickets']} (quedan {disponibles})"
        else:
            tickets_text = f"{sorteo['tickets_vendidos']} (sin límite)"
        
        embed.add_field(
            name=f"`{codigo}` - {sorteo['recompensa'][:50]}",
            value=f"🎟️ Ticket: {fmt(sorteo['precio_ticket'])}\n"
                  f"📊 Tickets: {tickets_text}\n"
                  f"👑 Creador: {sorteo['creador_nombre']}",
            inline=False
        )
    
    embed.set_footer(text="Usá /sorteo comprar <código> <cantidad> para participar")
    
    await interaction.response.send_message(embed=embed)


# ============================
# /sorteo info — Ver info de un sorteo específico
# ============================
@tree.command(name="sorteo_info", description="ℹ️ Ver información detallada de un sorteo")
@app_commands.describe(codigo="Código del sorteo")
async def sorteo_info(interaction: discord.Interaction, codigo: str):
    
    if not await ensure_guild_or_reply(interaction):
        return
    
    codigo = codigo.upper().strip()
    sorteos_data = load_sorteos()
    
    if codigo not in sorteos_data["sorteos"]:
        return await interaction.response.send_message(f"❌ No existe un sorteo con el código `{codigo}`.", ephemeral=True)
    
    sorteo = sorteos_data["sorteos"][codigo]
    uid = str(interaction.user.id)
    
    embed = discord.Embed(
        title=f"🎲 Sorteo `{codigo}`",
        description=f"**Recompensa:** {sorteo['recompensa']}",
        color=0x9b59b6 if sorteo["activo"] else 0x95a5a6
    )
    
    # Estado
    estado = "🟢 ACTIVO" if sorteo["activo"] else "🔴 FINALIZADO"
    embed.add_field(name="📌 Estado", value=estado, inline=True)
    
    # Creador
    embed.add_field(name="👑 Creador", value=sorteo['creador_nombre'], inline=True)
    
    # Precio y tickets
    embed.add_field(name="💰 Precio ticket", value=fmt(sorteo['precio_ticket']), inline=True)
    embed.add_field(name="🎟️ Tickets vendidos", value=sorteo['tickets_vendidos'], inline=True)
    
    # Límites
    if sorteo["limite_tickets"] > 0:
        embed.add_field(name="📊 Límite total", value=f"{sorteo['limite_tickets']}", inline=True)
    if sorteo["limite_por_usuario"] > 0:
        embed.add_field(name="👤 Máx por persona", value=f"{sorteo['limite_por_usuario']}", inline=True)
    
    # Participación del usuario
    mis_tickets = sorteo["participantes"].get(uid, 0)
    embed.add_field(name="🎟️ Tus tickets", value=mis_tickets, inline=True)
    
    # Si ya hay ganador
    if not sorteo["activo"] and "ganador" in sorteo:
        try:
            ganador = await interaction.guild.fetch_member(int(sorteo["ganador"]))
            ganador_nombre = ganador.display_name
        except:
            ganador_nombre = f"Usuario {sorteo['ganador']}"
        embed.add_field(name="🏆 Ganador", value=ganador_nombre, inline=False)
    
    embed.set_footer(text=f"Creado el {format_timestamp(sorteo['fecha_creacion'])}")
    
    await interaction.response.send_message(embed=embed)

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
#------------------------------------------------
#--------------------/post-----------------------
#------------------------------------------------
@tree.command(name="post", description="Subí un post a redes sociales 📱")
async def post(interaction: discord.Interaction):
    try:
        # Verificación manual sin función externa
        if interaction.guild is None or interaction.guild.id != ALLOWED_GUILD_ID:
            await interaction.response.send_message("❌ Comando no disponible en este servidor.", ephemeral=True)
            return

        uid = str(interaction.user.id)

        # Cooldown
        remaining = post_time_left(uid)
        if remaining > 0:
            horas = remaining // 3600
            minutos = (remaining % 3600) // 60
            await interaction.response.send_message(
                f"⏳ Volvé en **{horas}h {minutos}m**.",
                ephemeral=True
            )
            return

        # Generar ganancia
        ganancia = random.randint(0, 6700)

        # Guardar cooldown
        data = load_post_cooldowns()
        data[uid] = int(time.time())
        save_post_cooldowns(data)

        # Pagar
        if ganancia > 0:
            await safe_add(uid, ganancia)

        # Responder
        embed = discord.Embed(
            title="📸 Post en redes",
            description=f"📱 Ganaste **{fmt(ganancia)}** monedas!" if ganancia > 0 else "📱 No tuviste alcance 😔",
            color=0x2ecc71 if ganancia > 0 else 0xe67e22
        )
        await interaction.response.send_message(embed=embed)

    except Exception as e:
        print(f"ERROR en /post: {e}")
        if not interaction.response.is_done():
            await interaction.response.send_message("❌ Error inesperado.", ephemeral=True)
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

POST_COOLDOWN_FILE = os.path.join(DATA_DIR, "post_cooldowns.json")
def load_post_cooldowns():
    return load_json(POST_COOLDOWN_FILE, {})

def save_post_cooldowns(data):
    save_json(POST_COOLDOWN_FILE, data)

def post_time_left(uid):
    data = load_post_cooldowns()
    now = int(time.time())
    last = data.get(uid, 0)
    cooldown = 5 * 60 * 60  # 5 horas
    remaining = (last + cooldown) - now
    return max(0, remaining)
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
# /leaderboard — Sistema completo (coins y crypto)
# ============================

# Precio base del nivel (lo podés ajustar)
PRECIO_BASE_NIVEL = 1035

@tree.command(name="leaderboard", description="📊 Ver ranking de monedas o cryptos")
@app_commands.describe(
    tipo="coins (monedas) o crypto (criptomonedas)"
)
@app_commands.choices(tipo=[
    app_commands.Choice(name="💰 Monedas", value="coins"),
    app_commands.Choice(name="💎 Cryptos", value="crypto")
])
async def leaderboard(interaction: discord.Interaction, tipo: str = "coins"):
    
    if not await ensure_guild_or_reply(interaction):
        return

    # Defer para evitar timeout
    await interaction.response.defer()

    if tipo == "coins":
        await leaderboard_coins(interaction)
    else:
        await leaderboard_crypto(interaction)


# ============================
# LEADERBOARD DE MONEDAS
# ============================
async def leaderboard_coins(interaction: discord.Interaction):
    
    # Leer balances
    balances_data = load_json(BALANCES_FILE, {})

    if not balances_data:
        return await interaction.followup.send("😔 No hay datos de monedas todavía.", ephemeral=True)

    # Filtrar usuarios válidos con dinero > 0
    usuarios_validos = []
    dinero_total_anterior = 0  # Este debería venir de un histórico, pero usaremos el total actual como base
    
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

    # Ordenar por dinero (mayor a menor)
    usuarios_validos.sort(key=lambda x: x[1], reverse=True)

    # Calcular total de dinero actual
    dinero_total_actual = sum(money for _, money, _ in usuarios_validos)
    
    # Simular un dinero total anterior (en un sistema real, esto vendría de un histórico)
    # Por ahora, usamos el 90% del actual para que el cálculo sea visible
    dinero_total_anterior = int(dinero_total_actual * 0.9) or 1  # Evitar división por cero

    # Calcular nuevo precio del nivel
    # Precio nuevo = Precio base × Dinero base / Dinero actual
    precio_nuevo = int(PRECIO_BASE_NIVEL * dinero_total_anterior / dinero_total_actual)

    # Crear páginas
    items_por_pagina = 15
    paginas = []
    
    for i in range(0, len(usuarios_validos), items_por_pagina):
        pagina = usuarios_validos[i:i + items_por_pagina]
        paginas.append(pagina)

    # Vista principal
    if len(paginas) == 1:
        embed = crear_embed_coins(paginas[0], 1, 1, len(usuarios_validos), dinero_total_actual, dinero_total_anterior, precio_nuevo)
        await interaction.followup.send(embed=embed)
    else:
        view = LeaderboardCoinsView(paginas, 0, len(usuarios_validos), dinero_total_actual, dinero_total_anterior, precio_nuevo)
        embed = crear_embed_coins(paginas[0], 1, len(paginas), len(usuarios_validos), dinero_total_actual, dinero_total_anterior, precio_nuevo)
        await interaction.followup.send(embed=embed, view=view)


def crear_embed_coins(usuarios, pagina_actual, total_paginas, total_usuarios, dinero_actual, dinero_anterior, precio_nuevo):
    """Crea embed para leaderboard de monedas"""
    
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
        
        dinero_formateado = fmt(int(money))
        descripcion += f"{medalla} **#{posicion}** {nombre}: `{dinero_formateado}`\n"
    
    embed = discord.Embed(
        title="💰 Leaderboard - Monedas",
        description=descripcion or "No hay usuarios en esta página.",
        color=discord.Color.gold()
    )
    
    # Calcular variación de precio
    variacion = ((precio_nuevo - PRECIO_BASE_NIVEL) / PRECIO_BASE_NIVEL) * 100
    
    # Estadísticas con precio de nivel
    stats = (
        f"👥 **Usuarios activos:** {total_usuarios}\n"
        f"💰 **Dinero total:** {fmt(dinero_actual)}\n"
        f"📊 **Dinero base:** {fmt(dinero_anterior)}\n"
        f"⚖️ **Precio base nivel:** {fmt(PRECIO_BASE_NIVEL)}\n"
        f"🔄 **Precio nuevo nivel:** {fmt(precio_nuevo)} ({variacion:+.1f}%)"
    )
    
    embed.add_field(name="📊 Estadísticas", value=stats, inline=False)
    embed.set_footer(text=f"Página {pagina_actual}/{total_paginas} • Mostrando {len(usuarios)} usuarios")
    
    return embed


class LeaderboardCoinsView(discord.ui.View):
    """Vista con botones para leaderboard de monedas"""
    
    def __init__(self, paginas, pagina_index, total_usuarios, dinero_actual, dinero_anterior, precio_nuevo):
        super().__init__(timeout=60)
        self.paginas = paginas
        self.pagina_index = pagina_index
        self.total_usuarios = total_usuarios
        self.dinero_actual = dinero_actual
        self.dinero_anterior = dinero_anterior
        self.precio_nuevo = precio_nuevo
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
        
        embed = crear_embed_coins(
            self.paginas[self.pagina_index], 
            self.pagina_index + 1, 
            len(self.paginas),
            self.total_usuarios,
            self.dinero_actual,
            self.dinero_anterior,
            self.precio_nuevo
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
# LEADERBOARD DE CRYPTOS (muestra cantidades, no valor)
# ============================
async def leaderboard_crypto(interaction: discord.Interaction):
    
    cryptos_data = load_cryptos()
    holders = cryptos_data.get("holders", {})
    
    if not holders:
        return await interaction.followup.send("😔 No hay holders de cryptos todavía.", ephemeral=True)

    # Crear lista de usuarios con sus cryptos
    usuarios_crypto = []
    
    for uid, cryptos_dict in holders.items():
        tiene_crypto = False
        total_tickets = 0
        cryptos_detalle = []
        
        # Verificar cada crypto
        for sym in ("RSC", "CTC", "MMC"):
            cantidad = cryptos_dict.get(sym, 0)
            if cantidad > 0:
                tiene_crypto = True
                total_tickets += cantidad
                cryptos_detalle.append(f"{sym}: {cantidad:.2f}")
        
        if tiene_crypto:
            try:
                if str(uid).isdigit():
                    user = interaction.guild.get_member(int(uid))
                    if user:
                        usuarios_crypto.append((uid, total_tickets, user.display_name, cryptos_detalle))
                    else:
                        try:
                            user = await interaction.guild.fetch_member(int(uid))
                            if user:
                                usuarios_crypto.append((uid, total_tickets, user.display_name, cryptos_detalle))
                            else:
                                usuarios_crypto.append((uid, total_tickets, f"Usuario {uid[:4]}", cryptos_detalle))
                        except:
                            usuarios_crypto.append((uid, total_tickets, f"Usuario {uid[:4]}", cryptos_detalle))
            except:
                usuarios_crypto.append((uid, total_tickets, f"Usuario {uid[:4]}", cryptos_detalle))

    if not usuarios_crypto:
        return await interaction.followup.send("😔 No hay usuarios con cryptos en el servidor.", ephemeral=True)

    # Ordenar por cantidad total de tickets (suma de todas las cryptos)
    usuarios_crypto.sort(key=lambda x: x[1], reverse=True)

    # Calcular total de tickets
    total_tickets_global = sum(tickets for _, tickets, _, _ in usuarios_crypto)
    
    # Calcular precio base y nuevo para nivel de cryptos
    precio_base_crypto = 500  # Precio base para nivel de cryptos
    total_anterior_crypto = int(total_tickets_global * 0.85) or 1
    precio_nuevo_crypto = int(precio_base_crypto * total_anterior_crypto / total_tickets_global)

    # Crear páginas
    items_por_pagina = 15
    paginas = []
    
    for i in range(0, len(usuarios_crypto), items_por_pagina):
        pagina = usuarios_crypto[i:i + items_por_pagina]
        paginas.append(pagina)

    # Vista principal
    if len(paginas) == 1:
        embed = crear_embed_crypto(paginas[0], 1, 1, len(usuarios_crypto), total_tickets_global, total_anterior_crypto, precio_base_crypto, precio_nuevo_crypto)
        await interaction.followup.send(embed=embed)
    else:
        view = LeaderboardCryptoView(paginas, 0, len(usuarios_crypto), total_tickets_global, total_anterior_crypto, precio_base_crypto, precio_nuevo_crypto)
        embed = crear_embed_crypto(paginas[0], 1, len(paginas), len(usuarios_crypto), total_tickets_global, total_anterior_crypto, precio_base_crypto, precio_nuevo_crypto)
        await interaction.followup.send(embed=embed, view=view)


def crear_embed_crypto(usuarios, pagina_actual, total_paginas, total_usuarios, total_tickets, total_anterior, precio_base, precio_nuevo):
    """Crea embed para leaderboard de cryptos mostrando cantidades"""
    
    descripcion = ""
    posicion_inicio = (pagina_actual - 1) * 15 + 1
    
    for idx, (uid, tickets, nombre, detalles) in enumerate(usuarios):
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
        
        # Mostrar las cryptos que tiene (hasta 3, una por línea)
        crypto_text = "\n".join(detalles) if detalles else "Sin cryptos"
        
        descripcion += f"{medalla} **#{posicion}** {nombre}\n`{crypto_text}`\n\n"
    
    embed = discord.Embed(
        title="💎 Leaderboard - Tenencias de Cryptos",
        description=descripcion or "No hay usuarios en esta página.",
        color=discord.Color.blue()
    )
    
    # Calcular variación
    variacion = ((precio_nuevo - precio_base) / precio_base) * 100
    
    # Estadísticas con precio de nivel
    stats = (
        f"👥 **Holders activos:** {total_usuarios}\n"
        f"🎟️ **Total tickets:** {fmt(int(total_tickets))}\n"
        f"📊 **Tickets base:** {fmt(int(total_anterior))}\n"
        f"⚖️ **Precio base nivel:** {fmt(precio_base)}\n"
        f"🔄 **Precio nuevo nivel:** {fmt(precio_nuevo)} ({variacion:+.1f}%)"
    )
    
    embed.add_field(name="📊 Estadísticas", value=stats, inline=False)
    embed.set_footer(text=f"Página {pagina_actual}/{total_paginas} • Mostrando cantidad de cryptos")
    
    return embed


class LeaderboardCryptoView(discord.ui.View):
    """Vista con botones para leaderboard de cryptos"""
    
    def __init__(self, paginas, pagina_index, total_usuarios, total_tickets, total_anterior, precio_base, precio_nuevo):
        super().__init__(timeout=60)
        self.paginas = paginas
        self.pagina_index = pagina_index
        self.total_usuarios = total_usuarios
        self.total_tickets = total_tickets
        self.total_anterior = total_anterior
        self.precio_base = precio_base
        self.precio_nuevo = precio_nuevo
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
        
        embed = crear_embed_crypto(
            self.paginas[self.pagina_index], 
            self.pagina_index + 1, 
            len(self.paginas),
            self.total_usuarios,
            self.total_tickets,
            self.total_anterior,
            self.precio_base,
            self.precio_nuevo
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
