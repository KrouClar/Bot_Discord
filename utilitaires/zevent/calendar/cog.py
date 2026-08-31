import discord
from discord.ext import commands, tasks
import json
import os
import asyncio
import logging
import aiohttp
from datetime import datetime, time
from zoneinfo import ZoneInfo

logger = logging.getLogger(__name__)

BRUSSELS_TZ = ZoneInfo("Europe/Brussels")

# ID de l'événement ZEvent 2026 sur l'API evenmorestats.fr (trouvé via les
# outils de dev du navigateur, onglet Réseau -> XHR sur zevent.gdoc.fr).
# Cette API est celle d'un site tiers non officiel : elle peut changer de
# format ou disparaître sans préavis.
EVENT_ID = "019f5bd1-fe07-7d78-a326-a02198a9d50f"
API_BASE = f"https://api.ppr.evenmorestats.fr/events/{EVENT_ID}/shows"

# Jours couverts par le ZEvent 2026, vus sur les onglets du site (Jeudi -> Lundi)
EVENT_DAYS = ["2026-09-03", "2026-09-04", "2026-09-05", "2026-09-06"]

DAY_LABELS = {
    "2026-09-03": "🎤 Jeudi 3 septembre — Concert",
    "2026-09-04": "📅 Vendredi 4 septembre",
    "2026-09-05": "📅 Samedi 5 septembre",
    "2026-09-06": "📅 Dimanche 6 septembre",
}


class ZEventCalendar(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        # Remplacer par l'ID (clic droit sur le salon -> Copier l'identifiant)
        self.channel_id = 1543917677628629093

        base_dir = os.path.dirname(os.path.abspath(__file__))
        self.state_path = os.path.join(base_dir, "state.json")

        state = self.load_state()
        self.message_id = state.get("message_id")

        self.update_calendar.start()

    def cog_unload(self):
        # Arrête proprement la boucle si le cog est déchargé/rechargé,
        # sinon l'ancienne tâche continue de tourner en parallèle de la nouvelle.
        self.update_calendar.cancel()

    def load_state(self):
        if not os.path.exists(self.state_path):
            return {"message_id": None}
        with open(self.state_path, "r", encoding="utf-8") as f:
            return json.load(f)

    def save_state(self):
        with open(self.state_path, "w", encoding="utf-8") as f:
            json.dump({"message_id": self.message_id}, f)

    async def fetch_day(self, session, day):
        """Récupère les shows d'une journée. Renvoie [] en cas d'erreur,
        pour qu'une seule journée en échec ne fasse pas planter tout l'embed."""
        try:
            async with session.get(API_BASE, params={"day": day}) as resp:
                if resp.status == 200:
                    return await resp.json()
                logger.warning("ZEventCalendar : l'API a répondu %s pour %s", resp.status, day)
                return []
        except (aiohttp.ClientError, asyncio.TimeoutError) as e:
            logger.warning("ZEventCalendar : erreur d'appel API pour %s : %s", day, e)
            return []

    def format_day_field(self, shows, current_day):
        """Construit le texte d'un champ d'embed en filtrant sur le jour de début."""
        if not shows:
            return "_Rien de prévu pour l'instant._"

        shows_sorted = sorted(shows, key=lambda s: s["schedule"]["start"])
        lines = []
        seen_ids = set()

        for show in shows_sorted:
            # Récupère l'heure de début
            start = datetime.fromisoformat(show["schedule"]["start"].replace("Z", "+00:00")).astimezone(BRUSSELS_TZ)
            
            # On ignore l'événement s'il ne commence pas aujourd'hui
            if start.strftime("%Y-%m-%d") != current_day:
                continue
                
            # Évite les doublons accidentels de l'API
            if show["id"] in seen_ids:
                continue
            seen_ids.add(show["id"])

            if show.get("all_day"):
                time_label = "Toute la journée"
            else:
                time_label = f"{start:%H:%M}"
            
            # Tentative de récupération du nom de l'orga
            organisateur = show.get("streamer", "") # À adapter si l'API utilise un autre nom comme "channel"
            orga_text = f" *(par {organisateur})*" if organisateur else ""
                
            lines.append(f"**{time_label}** — {show['name']}{orga_text}")

        if not lines:
            return "_Rien de prévu pour l'instant._"

        text = "\n".join(lines)
        return text[:1024]

    # Exécution une fois par jour à 1h du matin, heure de Bruxelles
    # (ZoneInfo gère automatiquement le passage heure d'été / heure d'hiver)
    @tasks.loop(hours=8)
    async def update_calendar(self):
        channel = self.bot.get_channel(self.channel_id) or await self.bot.fetch_channel(self.channel_id)
        if not channel:
            logger.warning("ZEventCalendar : salon %s introuvable", self.channel_id)
            return

        embed = discord.Embed(title="📅 Planning ZEvent 2026", color=0x2ecc71)

        async with aiohttp.ClientSession() as session:
            for index, day in enumerate(EVENT_DAYS):
                shows = await self.fetch_day(session, day)
                label = DAY_LABELS.get(day, day)
                embed.add_field(name=label, value=self.format_day_field(shows, day), inline=True)
                
                # Ajoute une colonne invisible après le Vendredi (index 1) pour forcer le 2x2
                if index == 1:
                    embed.add_field(name="\u200b", value="\u200b", inline=True)

        embed.set_footer(text=f"Dernière maj à {datetime.now(BRUSSELS_TZ):%H:%M}")

        if self.message_id:
            try:
                msg = await channel.fetch_message(self.message_id)
                await msg.edit(embed=embed)
                return
            except discord.NotFound:
                pass

        # Création du message si inexistant
        msg = await channel.send(embed=embed)
        self.message_id = msg.id
        self.save_state()

    @update_calendar.before_loop
    async def before_update(self):
        await self.bot.wait_until_ready()

    @commands.command(name="force_update_calendar")
    @commands.has_permissions(administrator=True)
    async def force_update_calendar(self, ctx):
        # Appeler self.update_calendar() directement (et non .start()) exécute
        # le corps de la tâche une seule fois, sans toucher au planning de la boucle.
        await self.update_calendar()
        await ctx.send("✅ Calendrier mis à jour manuellement.", delete_after=3)


async def setup(bot):
    await bot.add_cog(ZEventCalendar(bot))
