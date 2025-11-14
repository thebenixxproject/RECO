# bot.py — Versión corregida y funcional
import os
import json
import random
import asyncio
import io
from datetime import datetime, timedelta
from threading import Thread
from typing import Optional

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
    await interaction.followup.send("🏓 Pong! BETA 5 21:35")


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

# -------------------------
# CRYPTOS: simple market + gráfico (24h history sampling every 5m)
# -------------------------
# Import matplotlib lazily (Render may need it installed)
try:
    import matplotlib.pyplot as plt
except Exception as e:
    plt = None
    print("⚠️ matplotlib no disponible:", e)

def load_cryptos():
    data = load_json(CRYPTO_FILE, None)
    if data:
        return data
    return {
        "RSC": {"price": 900, "history": [900]},
        "CTC": {"price": 500, "history": [500]},
        "MMC": {"price": 250, "history": [250]},
        "holders": {}
    }

def save_cryptos(data):
    save_json(CRYPTO_FILE, data)

cryptos = load_cryptos()

async def update_crypto_prices():
    # loop seguro (corre en setup_hook)
    while True:
        now = datetime.utcnow()
        weekday = now.weekday()  # 0=Mon ... 6=Sun
        weekend = weekday >= 4  # Fri-Sat-Sun stronger move
        for symbol in ("RSC", "CTC", "MMC"):
            c = cryptos[symbol]
            base = c["price"]
            if weekend:
                factor = random.uniform(-0.05, 0.08)
            else:
                factor = random.uniform(-0.01, 0.03)
            new_price = max(10, round(base * (1 + factor), 2))
            c["price"] = new_price
            c["history"].append(new_price)
            if len(c["history"]) > 288:
                c["history"].pop(0)
        save_cryptos(cryptos)
        await asyncio.sleep(300)  # 5 minutos

@tree.command(name="crypto", description="Estado / comprar / ver cryptos: status|buy|bought")
@app_commands.describe(action="status|buy|bought", coin="RSC|CTC|MMC", quantity="Cantidad (para buy)")
async def crypto(interaction: discord.Interaction, action: str, coin: Optional[str] = None, quantity: Optional[float] = None):
    if not await ensure_guild_or_reply(interaction):
        return
    action = action.lower()
    if action == "status":
        if coin and coin.upper() in ("RSC","CTC","MMC"):
            sym = coin.upper()
            # show graph if matplotlib available
            if plt:
                prices = cryptos[sym]["history"]
                plt.figure(figsize=(8,3))
                plt.plot(prices)
                plt.title(f"{sym} - Últimas {len(prices)} lecturas")
                plt.xlabel("ticks (5m)")
                plt.ylabel("precio")
                buf = io.BytesIO()
                plt.tight_layout()
                plt.savefig(buf, format="png")
                buf.seek(0)
                plt.close()
                file = discord.File(buf, filename=f"{sym}.png")
                embed = discord.Embed(title=f"{sym} — {cryptos[sym]['price']:,} monedas")
                embed.set_image(url=f"attachment://{sym}.png")
                await interaction.response.send_message(embed=embed, file=file)
            else:
                await interaction.response.send_message(f"{sym}: {fmt(cryptos[sym]['price'])} (hist len {len(cryptos[sym]['history'])})")
        else:
            desc = "\n".join([f"**{s}** → {fmt(cryptos[s]['price'])} monedas" for s in ("RSC","CTC","MMC")])
            await interaction.response.send_message(embed=discord.Embed(title="Criptos", description=desc))
    elif action == "buy":
        if not coin or coin.upper() not in ("RSC","CTC","MMC"):
            await interaction.response.send_message("❌ Cripto inválida (RSC/CTC/MMC).", ephemeral=True)
            return
        if not quantity or quantity <= 0:
            await interaction.response.send_message("❌ Cantidad inválida.", ephemeral=True)
            return
        symbol = coin.upper()
        price = cryptos[symbol]["price"]
        cost = price * quantity
        async with balances_lock:
            if balances.get(str(interaction.user.id), 0) < cost:
                await interaction.response.send_message(f"❌ No tenés {fmt(cost)} monedas.", ephemeral=True)
                return
            balances[str(interaction.user.id)] -= cost
            save_json(BALANCES_FILE, balances)
        holders = cryptos.setdefault("holders", {})
        holders.setdefault(str(interaction.user.id), {"RSC": 0.0, "CTC": 0.0, "MMC": 0.0})
        holders[str(interaction.user.id)][symbol] += quantity
        save_cryptos(cryptos)
        await interaction.response.send_message(f"✅ Compraste {quantity:.4f} {symbol} por {fmt(cost)} monedas.")
    elif action == "bought":
        holders = cryptos.get("holders", {})
        u = holders.get(str(interaction.user.id), {"RSC":0,"CTC":0,"MMC":0})
        lines = []
        for s in ("RSC","CTC","MMC"):
            amt = u.get(s, 0)
            if amt:
                lines.append(f"**{s}** → {amt:.4f} (≈ {amt * cryptos[s]['price']:.2f} monedas)")
        if not lines:
            await interaction.response.send_message("❌ No tenés cryptos.", ephemeral=True)
            return
        await interaction.response.send_message(embed=discord.Embed(title="Tu cartera", description="\n".join(lines)))
    else:
        await interaction.response.send_message("❌ Acción inválida. Usa status|buy|bought", ephemeral=True)

# -------------------------
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

# ---------- Russian roulette ----------
@tree.command(name="russianroulette", description="1/6 de perder, si ganas cobrás x5. Min 10")
@app_commands.describe(bet="Monto o 'a' para todo")
async def russianroulette(interaction: discord.Interaction, bet: str):
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
    chamber = random.randint(1,6)
    if chamber == 1:
        await interaction.response.send_message(f"💀 Perdiste **{fmt(bet_val)}**")
    else:
        payout = bet_val * 5
        await safe_add(uid, payout)
        await interaction.response.send_message(f"🔫 Ganaste: cobraste **{fmt(int(payout))}**")

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

# ---------- Blackjack (interactivo) ----------
blackjack_sessions: dict[str, dict] = {}

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
        # Inactividad -> cancelar y devolver nothing (apuesta perdida)
        blackjack_sessions.pop(self.uid, None)
        try:
            await self.message.edit(content="⏰ Tiempo agotado. Mano finalizada.", view=None)
        except:
            pass

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
    # iniciar mano
    deck = DECK.copy()
    random.shuffle(deck)
    player = draw_from(deck, 2)
    dealer = draw_from(deck, 2)
    session = {"uid": uid, "player": player, "dealer": dealer, "deck": deck, "bet": bet_val}
    blackjack_sessions[uid] = session
    view = BlackjackView(uid, session, timeout=60)
    embed = embed_for_session(session)
    await interaction.response.send_message(embed=embed, view=view)
    # obtener referencia al mensaje para on_timeout
    try:
        view.message = await interaction.original_response()
    except:
        view.message = None

# ---------- Crash (interactivo) ----------
@tree.command(name="crash", description="Apostá y tratá de no crashear 💥")
@app_commands.describe(bet="Monto o 'a' para todo", target="Multiplicador (ej: 2.5)")
async def crash(interaction: discord.Interaction, bet: str, target: float):
    if not await ensure_guild_or_reply(interaction):
        return
    parsed = await parse_bet(interaction, bet, min_bet=100)
    if parsed is None:
        await interaction.response.send_message("❌ Apuesta inválida (min 100 o 'a')", ephemeral=True)
        return
    bet_val = float(parsed)
    uid = str(interaction.user.id)
    if bet_val < 100:
        await interaction.response.send_message("❌ Apuesta mínima 100", ephemeral=True)
        return
    async with balances_lock:
        if balances.get(uid, 0) < bet_val:
            await interaction.response.send_message("❌ Saldo insuficiente.", ephemeral=True)
            return
        balances[uid] -= bet_val
        save_json(BALANCES_FILE, balances)
    # crash simulation
    crash_point = round(random.uniform(1.0, random.uniform(2.0, 10.0)), 2)
    await interaction.response.send_message("🚀 Crash en progreso...")
    msg = await interaction.original_response()
    multiplier = 1.0
    while multiplier < crash_point:
        await asyncio.sleep(0.6)
        multiplier = round(multiplier + random.uniform(0.1, 0.3), 2)
        try:
            await msg.edit(content=f"🚀 x{multiplier}")
        except:
            pass
    if crash_point >= target:
        payout = bet_val * target
        await safe_add(uid, payout)
        await msg.edit(content=f"💎 Ganaste! Crash x{crash_point} — Cobraste {fmt(int(payout))}")
    else:
        await msg.edit(content=f"💥 Perdiste. Crash x{crash_point} antes de x{target} — Perdiste {fmt(int(bet_val))}")

# ---------- Battles, leaderboard etc (mantener tal como tenías) ----------
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
