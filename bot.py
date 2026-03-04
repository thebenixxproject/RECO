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

# -------------------------
# Archivos / datos
# -------------------------
DATA_DIR = "data"
os.makedirs(DATA_DIR, exist_ok=True)
BALANCES_FILE = os.path.join(DATA_DIR, "balances.json")
SHARED_FILE = os.path.join(DATA_DIR, "sharedaccounts.json")
CRYPTO_FILE = os.path.join(DATA_DIR, "cryptos.json")

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
    await interaction.followup.send("reco 1.2 jajajajaja decime cuantos puntos hay aca y te doy 67 trillones de monedas........................................................................................................................................................................................................................................................................................................................................................................................................................................................................................................................................." \
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
#---------------------HELPERS EN GENERAL----------------------
INVEST_COOLDOWN_FILE = os.path.join(DATA_DIR, "invest_cooldowns.json")
def load_invest_cooldowns():
    return load_json(INVEST_COOLDOWN_FILE, {})

def save_invest_cooldowns(data):
    save_json(INVEST_COOLDOWN_FILE, data)

def invest_time_left(uid):
    data = load_invest_cooldowns()
    now = int(time.time())
    last = data.get(uid, 0)
    cooldown = 3 * 60 * 60  # 3 horas
    remaining = (last + cooldown) - now
    return max(0, remaining)
# ============================
# /invest — Invertir en empresas
# ============================
INVEST_COOLDOWN = 60 * 60 * 3  # 3 horas

@tree.command(name="invest", description="Invertí en una empresa (cada 3 horas)")
@app_commands.describe(
    empresa="Apple | RESONA | PHub | Reservas X",
    cantidad="Cantidad a invertir"
)
async def invest(interaction: discord.Interaction, empresa: str, cantidad: int):

    if not await ensure_guild_or_reply(interaction):
        return

    uid = str(interaction.user.id)

    empresas_validas = ["apple", "resona", "phub", "reservas x"]
    if empresa.lower() not in empresas_validas:
        return await interaction.response.send_message(
            "❌ Empresa inválida.",
            ephemeral=True
        )

    if cantidad <= 0:
        return await interaction.response.send_message(
            "❌ Cantidad inválida.",
            ephemeral=True
        )

    # --- cooldown ---
    now = int(time.time())
    cooldowns = load_json("invest_cd.json", {})
    last = cooldowns.get(uid, 0)

    if now - last < INVEST_COOLDOWN:
        remaining = INVEST_COOLDOWN - (now - last)
        horas = remaining // 3600
        minutos = (remaining % 3600) // 60
        return await interaction.response.send_message(
            f"⏳ Ya invertiste recientemente.\nVolvé en **{horas}h {minutos}m**.",
            ephemeral=True
        )

    async with balances_lock:
        saldo = balances.get(uid, 0)
        if saldo < cantidad:
            return await interaction.response.send_message(
                "❌ No tenés saldo suficiente.",
                ephemeral=True
            )
        balances[uid] -= cantidad
        save_json(BALANCES_FILE, balances)

    cooldowns[uid] = now
    save_json("invest_cd.json", cooldowns)

    # ============================
    # RESULTADO
    # ============================

    win = random.random() < 0.45  # 45% win

    if not win:
        embed = discord.Embed(
            title=f"📉 Inversión en {empresa}",
            description=f"❌ La inversión salió mal.\nPerdiste **{fmt(cantidad)}** monedas.",
            color=0xe74c3c
        )
        return await interaction.response.send_message(embed=embed)

    # Distribución de profits (más alto = menos probabilidad)
    # 8% chance de 99%
    # resto distribuido decreciente

    roll = random.random()

    if roll < 0.08:
        profit_percent = 99
    else:
        # entre 10% y 80% pero con peso hacia valores bajos
        profit_percent = int(random.triangular(10, 80, 15))

    ganancia = int(cantidad * (profit_percent / 100))
    total = cantidad + ganancia

    await safe_add(uid, total)

    embed = discord.Embed(
        title=f"📈 Inversión en {empresa}",
        description=(
            f"✅ La empresa explotó en bolsa!\n\n"
            f"📊 Profit: **+{profit_percent}%**\n"
            f"💰 Recibiste: **{fmt(total)}** monedas"
        ),
        color=0x2ecc71
    )

    await interaction.response.send_message(embed=embed)
# ============================
# /towers
# ============================

class TowersView(discord.ui.View):
    def __init__(self, uid, bet):
        super().__init__(timeout=120)
        self.uid = uid
        self.bet = bet
        self.multiplier = 1.0
        self.active = True

    @discord.ui.button(label="Subir piso", style=discord.ButtonStyle.primary)
    async def subir(self, interaction: discord.Interaction, button: discord.ui.Button):

        if interaction.user.id != int(self.uid):
            return await interaction.response.send_message("❌ No es tu partida.", ephemeral=True)

        if not self.active:
            return

        if random.random() < 0.30:  # 30% perder
            self.active = False
            self.clear_items()
            embed = discord.Embed(
                title="💥 Torre explotó",
                description="Perdiste todo.",
                color=0xe74c3c
            )
            return await interaction.response.edit_message(embed=embed, view=self)

        # gana piso
        self.multiplier += 0.5

        embed = discord.Embed(
            title="🏰 Towers",
            description=(
                f"Subiste un piso!\n\n"
                f"Multiplicador actual: **x{self.multiplier:.2f}**"
            ),
            color=0x3498db
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

        embed = discord.Embed(
            title="💰 Cash Out",
            description=f"Cobraste **{fmt(reward)}** monedas (x{self.multiplier:.2f})",
            color=0x2ecc71
        )

        await interaction.response.edit_message(embed=embed, view=self)


@tree.command(name="towers", description="Juego tipo Towers")
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

    embed = discord.Embed(
        title="🏰 Towers",
        description="Subí pisos y retirate antes de explotar.",
        color=0x3498db
    )

    view = TowersView(uid, cantidad)
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

            # Movimiento aleatorio entre -8% y +8%
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
    quantity="Cantidad para buy/sell"
)
async def crypto(interaction: discord.Interaction, action: str, coin: str = None, quantity: float = None):
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
        await interaction.response.send_message(embed=discord.Embed(title="Criptos", description=desc))
        return

        # ============================
    # BUY
    # ============================
    if action == "buy":
        uid = str(interaction.user.id)

        if coin is None or coin.upper() not in ("RSC", "CTC", "MMC"):
            return await interaction.response.send_message("❌ Cripto inválida.", ephemeral=True)

        if quantity is None or quantity <= 0:
            return await interaction.response.send_message("❌ Cantidad inválida.", ephemeral=True)

        sym = coin.upper()
        price = cryptos[sym]["price"]
        cost = round(price * quantity, 2)

        async with balances_lock:
            saldo = balances.get(uid, 0)

            if saldo < cost:
                return await interaction.response.send_message(
                    "❌ No tenés saldo suficiente.",
                    ephemeral=True
                )

            balances[uid] -= cost
            save_json(BALANCES_FILE, balances)

        holders = cryptos["holders"]
        holders.setdefault(uid, {"RSC": 0, "CTC": 0, "MMC": 0})
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

        sym = coin.upper()
        uid = str(interaction.user.id)
        holdings = cryptos["holders"].get(uid, {"RSC": 0, "CTC": 0, "MMC": 0})

        if holdings[sym] < quantity:
            await interaction.response.send_message("❌ No tenés suficiente para vender.", ephemeral=True)
            return

        price = cryptos[sym]["price"]
        gain = round(price * quantity, 2)

        holdings[sym] -= quantity
        save_cryptos(cryptos)
        await safe_add(uid, gain)

        await interaction.response.send_message(f"🟥 Vendiste **{quantity:.4f} {sym}** y recibiste **{fmt(gain)}** monedas.")
        return

    # ============================
    # BOUGHT (portafolio)
    # ============================
    if action == "bought":
        uid = str(interaction.user.id)
        holders = cryptos["holders"]
        u = holders.get(uid, {"RSC": 0, "CTC": 0, "MMC": 0})

        lines = []
        for s in ("RSC", "CTC", "MMC"):
            amt = u.get(s, 0)
            if amt > 0:
                value = round(amt * cryptos[s]['price'], 2)
                lines.append(f"**{s}** → {amt:.4f} (≈ {fmt(value)} monedas)")

        if not lines:
            await interaction.response.send_message("❌ No tenés cryptos.", ephemeral=True)
            return

        await interaction.response.send_message(embed=discord.Embed(
            title="💼 Tu cartera",
            description="\n".join(lines)
        ))
        return

    await interaction.response.send_message("❌ Acción inválida.", ephemeral=True)
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
    # Validar guild y permisos
    if not await ensure_guild_or_reply(interaction):
        return
    if not interaction.user.guild_permissions.administrator:
        return await interaction.response.send_message("🚫 Solo administradores pueden usar este comando.", ephemeral=True)

    # Validar precio
    try:
        price = float(price)
        if price <= 0:
            raise ValueError()
    except:
        return await interaction.response.send_message("❌ Precio inválido. Debe ser un número mayor a 0.", ephemeral=True)

    # Cargar cryptos desde archivo (no confiar en variable global sola)
    cryptos = load_json(CRYPTO_FILE, {})
    if not cryptos:
        return await interaction.response.send_message("❌ Archivo de cryptos vacío o inexistente.", ephemeral=True)

    sym = coin.upper()
    if sym not in cryptos or not isinstance(cryptos[sym], dict) or "price" not in cryptos[sym]:
        return await interaction.response.send_message(f"❌ La crypto **{coin}** no existe.", ephemeral=True)

    # Actualizar precio e historial
    cryptos[sym]["price"] = round(price, 2)
    hist = cryptos[sym].setdefault("history", [])
    hist.append(round(price, 2))

    # Limitar history a 288 puntos (24h @ 5min)
    MAX_HISTORY = 288
    if len(hist) > MAX_HISTORY:
        cryptos[sym]["history"] = hist[-MAX_HISTORY:]

    # Guardar
    try:
        save_json(CRYPTO_FILE, cryptos)
    except Exception as e:
        return await interaction.response.send_message(f"⚠️ Error al guardar: `{e}`", ephemeral=True)

    # Respuesta con embed
    embed = discord.Embed(
        title="💹 Precio actualizado",
        description=f"Se actualizó el precio de **{sym}**",
        color=discord.Color.green()
    )
    embed.add_field(name="Nuevo precio", value=f"{cryptos[sym]['price']:,}", inline=True)
    embed.add_field(name="Puntos en historial", value=str(len(cryptos[sym].get("history", []))), inline=True)
    embed.set_footer(text=f"Actualizado por {interaction.user.display_name}")

    await interaction.response.send_message(embed=embed)
# =========================
#        SYSTEM: BOXES
# =========================

#─── Config Boxes ───────────────────────────────────────────────
BOXES = {
    "normal": {
        "price": 30000,
        "rewards": [
            ("Gallina", 50),
            ("Piedra – 30 CTC", 25),
            ("León – 40.000 monedas", 15),
            ("Tortuga – 40% OFF (compra +40 niveles)", 10),
        ]
    },
    "rara": {
        "price": 60000,
        "rewards": [
            ("Toilet – 3 tickets + 15 MMC", 40),
            ("Bombero – Cupón Rol + 20.000", 30),
            ("Mujer – x2 suerte Blackjack (70% ganancia)", 20),
            ("Limón – Crear Crypto + 40.000", 10),
        ]
    },
    "crazy": {
        "price": 100000,
        "rewards": [
            ("Mango – 80 niveles + 90.000", 30),
            ("Foca – Romper 2 reglas + 50.000 + 30 CTC", 30),
            ("Círculo Violeta – HoF + 60.000", 35),
            ("Barra de Oro – 150.000 + x4 Crypto + Rol + Timeout 1h + 100 niveles", 5),
        ]
    }
}

# =========================
#     GIFTS SYSTEM
# =========================

GIFTS_FILE = os.path.join(DATA_DIR, "gifts.json")

def load_gifts():
    return load_json(GIFTS_FILE, {})

def save_gifts(data):
    save_json(GIFTS_FILE, data)

def add_gift(uid, gift_name):
    data = load_gifts()
    if uid not in data:
        data[uid] = []
    data[uid].append(gift_name)
    save_gifts(data)

def remove_gift(uid, gift_name):
    data = load_gifts()
    if uid not in data:
        return False
    if gift_name not in data[uid]:
        return False
    data[uid].remove(gift_name)
    save_gifts(data)
    return True

def has_gift(uid, gift_name):
    data = load_gifts()
    user = data.get(uid, [])
    return any(gift_name.lower() in g.lower() for g in user)


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


# =========================
#          /boxes
# =========================

@tree.command(name="boxes", description="Comprar y abrir cajas misteriosas 🎁")
@app_commands.describe(tipo="normal, rara o crazy")
async def boxes(interaction: discord.Interaction, tipo: str):

    tipo = tipo.lower()

    if tipo not in BOXES:
        return await interaction.response.send_message(
            "❌ Tipo inválido: normal / rara / crazy",
            ephemeral=True
        )

    uid = str(interaction.user.id)
    caja = BOXES[tipo]
    precio = caja["price"]

    # Descontar monedas
    async with balances_lock:
        saldo = balances.get(uid, 0)
        if saldo < precio:
            return await interaction.response.send_message(
                f"❌ Necesitás {precio:,} monedas.",
                ephemeral=True
            )
        balances[uid] -= precio
        save_json(BALANCES_FILE, balances)

    # Selección probabilística
    items = [r[0] for r in caja["rewards"]]
    probs = [r[1] for r in caja["rewards"]]

    premio = random.choices(items, probs)[0]

    # -------------------------
    #   CASO ESPECIAL: GALLINA
    # -------------------------
    if premio == "Gallina":
        apply_buff(uid, "Gallina", 600)  # 10 minutos
        return await interaction.response.send_message(
            "🐔 **Gallina conseguida!**\n"
            "Durante **10 minutos** obtenés **+1.25x** en TODAS tus ganancias.",
        )

    # Guardar premio en inventario
    add_gift(uid, premio)

    embed = discord.Embed(
        title="🎁 Caja Misteriosa Abierta!",
        description=f"Tipo: **{tipo.upper()}**",
        color=discord.Color.gold()
    )

    embed.add_field(name="🎉 Ganaste:", value=f"**{premio}**", inline=False)
    embed.set_footer(text=f"Costó {precio:,} monedas")

    await interaction.response.send_message(embed=embed)


# =========================
#       /seegifts
# =========================

@tree.command(name="seegifts", description="Ver tus cupones y regalos 🎁")
async def seegifts(interaction: discord.Interaction):
    uid = str(interaction.user.id)
    inv = load_gifts().get(uid, [])

    if not inv:
        return await interaction.response.send_message(
            "📭 No tenés regalos todavía.",
            ephemeral=True
        )

    embed = discord.Embed(
        title="🎁 Tu inventario de regalos",
        color=discord.Color.purple()
    )

    embed.add_field(name="Regalos:", value="\n".join([f"• {g}" for g in inv]), inline=False)
    await interaction.response.send_message(embed=embed)


# =========================
#       /addbox
# =========================

@tree.command(name="addbox", description="(Admin) Agregar un regalo manualmente a un usuario")
@app_commands.describe(user="Usuario", regalo="Texto exacto del regalo")
async def addbox(interaction: discord.Interaction, user: discord.User, regalo: str):

    if not interaction.user.guild_permissions.administrator:
        return await interaction.response.send_message("❌ Solo admins.", ephemeral=True)

    uid = str(user.id)
    add_gift(uid, regalo)

    await interaction.response.send_message(
        f"✅ Regalo agregado a **{user.display_name}**: `{regalo}`"
    )

# ============================
import unicodedata

# -------------------------
# Helpers para gifts
# -------------------------
def normalize(text: str) -> str:
    """
    Normaliza texto: quita tildes, pasa a minúsculas y limpia espacios.
    Esto ayuda a hacer matches flexibles (ej: 'LEÓN' -> 'leon').
    """
    if not isinstance(text, str):
        return ""
    text = text.strip().lower()
    # quitar acentos
    text = unicodedata.normalize("NFKD", text)
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    return text

def get_gifts(uid: str) -> list:
    """
    Devuelve la lista de regalos del usuario (copiada).
    Siempre devuelve lista (vacía si no tiene).
    """
    data = load_gifts()  # usa tu función existente
    lst = data.get(str(uid), [])
    # asegurarse de devolver una copia y strings
    return [str(x) for x in lst]

# -------------------------
# /transfergiftbox (actualizado)
# -------------------------
@tree.command(name="transfergiftbox", description="Transferir un regalo a otro jugador")
@app_commands.describe(user="Usuario destino", regalo="Nombre del regalo (puede ser aproximado)")
async def transfergiftbox(interaction: discord.Interaction, user: discord.User, regalo: str):

    sender = str(interaction.user.id)
    receiver = str(user.id)

    if sender == receiver:
        return await interaction.response.send_message("❌ No podés transferirte regalos a vos mismo.", ephemeral=True)

    # Obtener lista de regalos del remitente
    gifts_sender = get_gifts(sender)
    if not gifts_sender:
        return await interaction.response.send_message("❌ No tenés regalos para transferir.", ephemeral=True)

    # Normalizar entrada
    entrada_norm = normalize(regalo)

    # Construir lookup normalizado -> original (prioriza coincidencia exacta)
    lookup = {}
    for g in gifts_sender:
        lookup[normalize(g)] = g

    elegido = None

    # 1) buscar coincidencia exacta normalizada
    if entrada_norm in lookup:
        elegido = lookup[entrada_norm]
    else:
        # 2) buscar coincidencia por substring (primero en originales normalizados)
        for k_norm, original in lookup.items():
            if entrada_norm in k_norm or k_norm in entrada_norm:
                elegido = original
                break

    if elegido is None:
        # 3) intentar coincidencia parcial más laxa (palabras)
        entrada_tokens = entrada_norm.split()
        for k_norm, original in lookup.items():
            for t in entrada_tokens:
                if t and t in k_norm:
                    elegido = original
                    break
            if elegido:
                break

    if elegido is None:
        # Construir lista corta de los primeros 8 regalos para ayudar al usuario
        sample = gifts_sender[:8]
        sample_txt = ", ".join(sample)
        return await interaction.response.send_message(
            f"❌ No encontré ningún regalo parecido a **{regalo}** en tu inventario.\n"
            f"Ejemplos de lo que tenés: {sample_txt}",
            ephemeral=True
        )

    # Remover del que envía
    ok = remove_gift(sender, elegido)
    if not ok:
        return await interaction.response.send_message("❌ Error al quitar el regalo de tu inventario.", ephemeral=True)

    # Agregar al receptor
    add_gift(receiver, elegido)

    await interaction.response.send_message(
        f"📦 **Transferencia completa!**\n\n"
        f"Regalo enviado: **{elegido}**\n"
        f"Para: **{user.display_name}**"
    )
# ============================
# Juego: Encontrá la Piedra (/find)
# ============================

@tree.command(name="find", description="Encontrá la piedra bajo 1 de los 5 vasos 🎲")
@app_commands.describe(bet="Cantidad a apostar o 'a' para todo")
async def find(interaction: discord.Interaction, bet: str):

    if not await ensure_guild_or_reply(interaction):
        return

    uid = str(interaction.user.id)

    # ---------------- APUESTA ----------------
    parsed = await parse_bet(interaction, bet)
    if parsed is None:
        return await interaction.response.send_message(
            f"❌ Apuesta inválida. Mínimo {MIN_BET}.",
            ephemeral=True
        )

    bet_val = int(parsed)

    async with balances_lock:
        if balances.get(uid, 0) < bet_val:
            return await interaction.response.send_message("❌ Saldo insuficiente.", ephemeral=True)

        balances[uid] -= bet_val
        save_json(BALANCES_FILE, balances)

    # ---------------- JUEGO ----------------

    # Vaso correcto (1-5)
    correct = random.randint(1, 5)

    # Vasos iniciales
    vasos = ["🔵", "🔵", "🔵", "🔵", "🔵"]

    embed = discord.Embed(
        title="🥤 Encuentra la Piedra",
        description="Una piedra fue escondida bajo **1 de 5 vasos**.\nElegí con cuidado...",
        color=0x3498db
    )
    embed.add_field(name="Vasos", value="🔵 🔵 🔵 🔵 🔵", inline=False)
    embed.add_field(name="Apuesta", value=fmt(bet_val), inline=False)

    view = FindView(uid, bet_val, correct)
    await interaction.response.send_message(embed=embed, view=view)
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

    # 5 BOTONES
    @discord.ui.button(label="1", style=discord.ButtonStyle.primary)
    async def b1(self, i, b):
        await self.reveal(i, 1)

    @discord.ui.button(label="2", style=discord.ButtonStyle.primary)
    async def b2(self, i, b):
        await self.reveal(i, 2)

    @discord.ui.button(label="3", style=discord.ButtonStyle.primary)
    async def b3(self, i, b):
        await self.reveal(i, 3)

    @discord.ui.button(label="4", style=discord.ButtonStyle.primary)
    async def b4(self, i, b):
        await self.reveal(i, 4)

    @discord.ui.button(label="5", style=discord.ButtonStyle.primary)
    async def b5(self, i, b):
        await self.reveal(i, 5)

    # ---------------- RESULTADO ----------------

    async def reveal(self, interaction, chosen):
        self.stop()

        vasos = ["🔵", "🔵", "🔵", "🔵", "🔵"]

        # piedra aparece donde realmente estaba
        vasos[self.correct - 1] = "🪨"

        acierto = (chosen == self.correct)

        if acierto:
            ganancia = self.bet * 2
            await safe_add(self.uid, ganancia)  # devolver al usuario

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
# ============================
# /post — Redes sociales
# ============================
print("POST CARGADO")
@tree.command(name="post", description="Subí un post a redes sociales 📱 (cada 5 horas)")
async def post(interaction: discord.Interaction):

    if not await ensure_guild_or_reply(interaction):
        return

    uid = str(interaction.user.id)

    # ---- cooldown ----
    remaining = post_time_left(uid)
    if remaining > 0:
        horas = remaining // 3600
        minutos = (remaining % 3600) // 60
        return await interaction.response.send_message(
            f"⏳ Ya subiste un post recientemente.\n"
            f"Volvé a intentarlo en **{horas}h {minutos}m**.",
            ephemeral=True
        )

    # ---- generar ganancia ----
    ganancia = random.randint(0, 6700)

    # ---- guardar cooldown ----
    data = load_post_cooldowns()
    data[uid] = int(time.time())
    save_post_cooldowns(data)

    # ---- pagar ----
    if ganancia > 0:
        await safe_add(uid, ganancia)
        msg = f"📱 Subiste un post y ganaste **{fmt(ganancia)}** monedas!"
        color = 0x2ecc71
    else:
        msg = "📱 Subiste un post… pero no tuvo alcance 😔 (0 monedas)"
        color = 0xe67e22

    embed = discord.Embed(
        title="📸 Post en redes",
        description=msg,
        color=color
    )
    embed.set_footer(text="RECO • Redes Sociales")

    await interaction.response.send_message(embed=embed)
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
        await interaction.response.send_message(f"🎰 {' | '.join(res)} — Ganaste **{fmt(int(win))}**")
    else:
        await interaction.response.send_message(f"🎰 {' | '.join(res)} — Perdiste **{fmt(int(bet_val))}**")

# ==========================
#    BLACKJACK COMPLETO
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

        # detectar buff Mujer → funciona con contains
        tiene_mujer = has_gift(uid, "Mujer")

        # --- Si el jugador se pasó ---
        if busted:
            payout = 0
            note = "Te pasaste (bust). Perdiste."
            pval = hand_value(session["player"])
            dval = hand_value(session["dealer"])
        else:
            # ----------------------------------
            #     JUEGA EL DEALER (reglas reales)
            # ----------------------------------
            pval = hand_value(session["player"])
            dval = hand_value(session["dealer"])

            # Si el jugador tiene blackjack natural, dealer no juega
            if not (pval == 21 and len(session["player"]) == 2):
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

            # ------------------------------------------------------------
            #                    BUFF MUJER APLICADO
            # ------------------------------------------------------------
            if tiene_mujer and not busted and not empate:
                # ➤ Caso ganar naturalmente
                if gana:
                    payout = int(payout * 0.70)
                    note += " **(Buff Mujer: pago reducido al 70%)**"

                # ➤ Caso perder → chance de convertir derrota
                else:
                    # 35% de chance de salvarte
                    if random.random() < 0.35:
                        gana = True
                        payout = int(bet * 2 * 0.70)
                        note = "🔥 Buff Mujer activado! La suerte te salvó (pago 70%)."

        # ------------------------------------
        #       Aplicar pago al jugador
        # ------------------------------------
        if payout > 0:
            await safe_add(uid, payout)

        blackjack_sessions.pop(uid, None)

        # ---------------------------
        #   Embed final del resultado
        # ---------------------------
        embed = discord.Embed(
            title="🃏 Blackjack — Resultado",
            color=0x2F3136
        )

        # Mostrar manos completas
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

        # respuesta segura
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

    # Descontar apuesta
    async with balances_lock:
        if balances.get(uid, 0) < bet_val:
            await interaction.response.send_message("❌ Saldo insuficiente.", ephemeral=True)
            return
        balances[uid] -= bet_val
        save_json(BALANCES_FILE, balances)

    # Preparar mano
    deck = DECK.copy()
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

    # Guardar el mensaje para manejar timeout
    try:
        view.message = await interaction.original_response()
    except:
        view.message = None
# ---------- Battles, leaderboard etc (mantener tal como tenías) ----------
#leaderboard
#leaderboard
@tree.command(name="leaderboard", description="Mirá el top de los jugadores con más dinero 💰")
async def leaderboard(interaction: discord.Interaction):
    if not await ensure_guild_or_reply(interaction):
        return

    # leer balances
    balances = load_json(BALANCES_FILE, {})

    if not balances:
        await interaction.response.send_message("😔 No hay datos todavía.", ephemeral=True)
        return

    # ordenar TOP 10
    top = sorted(balances.items(), key=lambda x: x[1], reverse=True)[:10]

    msg = "🏆 **Leaderboard - Top 10** 🏆\n\n"
    pos = 1
    for uid, money in top:
        user = await interaction.guild.fetch_member(int(uid)) if str(uid).isdigit() else None
        name = user.display_name if user else f"User {uid}"
        msg += f"**#{pos}** — {name}: `{fmt(int(money))}`\n"
        pos += 1

    await interaction.response.send_message(msg)

# (Mantén tus comandos battle_start, battle_join, leaderboard, etc.)
# ... (si quieres que los revise/limpie los agrego también)

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
