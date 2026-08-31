import discord
from discord.ext import commands
import json
import os


class ReactionRoles(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        base_dir = os.path.dirname(os.path.abspath(__file__))
        self.json_path = os.path.join(base_dir, "reactions.json")
        self.state_path = os.path.join(base_dir, "state.json")
        self.roles_data = self.load_roles()
        state = self.load_state()
        self.channel_id = state.get("channel_id")
        self.message_id = state.get("message_id")

    def load_roles(self):
        with open(self.json_path, "r", encoding="utf-8") as f:
            return json.load(f)

    def load_state(self):
        if not os.path.exists(self.state_path):
            return {"channel_id": None, "message_id": None}
        with open(self.state_path, "r", encoding="utf-8") as f:
            return json.load(f)

    def save_state(self):
        data = {"channel_id": self.channel_id, "message_id": self.message_id}
        with open(self.state_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)

    @commands.command(name="setup_roles")
    @commands.has_permissions(administrator=True)
    async def setup_roles(self, ctx):
        self.roles_data = self.load_roles()
        lines = ["**Réagis pour obtenir un rôle :**\n"]
        for emoji, info in self.roles_data.items():
            lines.append(f"{emoji} → {info['name']}")
        message_text = "\n".join(lines)

        if self.message_id is not None and self.channel_id is not None:
            try:
                channel = self.bot.get_channel(self.channel_id) or await self.bot.fetch_channel(self.channel_id)
                message = await channel.fetch_message(self.message_id)
                await message.edit(content=message_text)
                await message.clear_reactions()
                for emoji in self.roles_data.keys():
                    await message.add_reaction(emoji)
                await ctx.send("✅ Message mis à jour.", delete_after=3)
                await ctx.message.delete()
                return
            except (discord.NotFound, discord.Forbidden):
                pass

        message = await ctx.send(message_text)
        for emoji in self.roles_data.keys():
            await message.add_reaction(emoji)
        self.message_id = message.id
        self.channel_id = ctx.channel.id
        self.save_state()
        await ctx.message.delete()  # Supprime la commande !setup_roles pour faire propre

    async def get_role_and_member(self, payload):
        if payload.message_id != self.message_id or payload.user_id == self.bot.user.id:
            return None, None

        emoji = str(payload.emoji)
        if emoji not in self.roles_data:
            return None, None
        role_id = self.roles_data[emoji]["role_id"]
        guild = self.bot.get_guild(payload.guild_id)
        role = guild.get_role(role_id)

        member = guild.get_member(payload.user_id) or await guild.fetch_member(payload.user_id)
        return role, member

    @commands.Cog.listener()
    async def on_raw_reaction_add(self, payload: discord.RawReactionActionEvent):
        role, member = await self.get_role_and_member(payload)
        if not (role and member):
            return
        channel = self.bot.get_channel(payload.channel_id) or await self.bot.fetch_channel(payload.channel_id)
        message = await channel.fetch_message(payload.message_id)
        # Bascule du rôle et message temporaire
        if role in member.roles:
            await member.remove_roles(role)
            await channel.send(f"❌ Le rôle **{role.name}** t'a été retiré {member.mention}.", delete_after=3)
        else:
            await member.add_roles(role)
            await channel.send(f"✅ Le rôle **{role.name}** t'a été ajouté {member.mention}.", delete_after=3)
        # Retrait de la réaction de l'utilisateur
        await message.remove_reaction(payload.emoji, member)


async def setup(bot):
    await bot.add_cog(ReactionRoles(bot))