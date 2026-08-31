import discord
from discord.ext import commands
from discord.ui import Button, View, Modal, TextInput
import os
from dotenv import load_dotenv

load_dotenv()

#################################
# CREATION/DELETE VOICE CHANNEL #
#################################
class VoiceChannel(commands.Cog):

    def __init__(self, bot):
        self.bot = bot

        #######
        # ENV #
        #######
        self.voice_channel_creator = int(os.getenv("VOICE_CHANNEL_CREATOR"))

        ############
        # VARIABLE #
        ############
        self.temp_channels = []

    @commands.Cog.listener(name="on_voice_state_update")
    async def voice_creation_delete(self, member, before, after):

        ##########################
        # CREATION VOICE CHANNEL #
        ##########################
        if after.channel and after.channel.id == self.voice_channel_creator:

            discord_server = member.guild
            voice_channel_category = after.channel.category

            new_voice_channel = await discord_server.create_voice_channel(
                name=f"🎙️ {member.display_name}",
                category=voice_channel_category
            )

            self.temp_channels.append(new_voice_channel.id)

            await member.move_to(new_voice_channel)

            await new_voice_channel.send(
                f"Salut {member.mention}, gère ton salon ici :",
                view=ControlView(owner_id=member.id)
            )

        ########################
        # DELETE VOICE CHANNEL #
        ########################
        if before.channel and before.channel.id in self.temp_channels:
            if len(before.channel.members) == 0:
                await before.channel.delete()
                self.temp_channels.remove(before.channel.id)


#########################
# CONTROL VOICE CHANNEL #
#########################
class ControlView(View):

    def __init__(self, owner_id):
        super().__init__(timeout=None)
        self.owner_id = owner_id
        self.shared = False

    # Fonction qui vérifie qui peut utiliser les boutons
    def can_interact(self, interaction: discord.Interaction):
        if interaction.user.id == self.owner_id:
            return True
        
        if self.shared and interaction.user in interaction.channel.members:
            return True

        return False

    ###########
    # BUTTONS #
    ###########
    # Rename Button
    @discord.ui.button(label="✏️ Renommer", style=discord.ButtonStyle.primary)
    async def rename_button(self, interaction: discord.Interaction, button: Button):
        if not self.can_interact(interaction):
            return await interaction.response.send_message("❌ Tu n'as pas les droits.", ephemeral=True)
        
        await interaction.response.send_modal(RenameModal())

    # Limit Button
    @discord.ui.button(label="👥 Limiter de places", style=discord.ButtonStyle.primary)
    async def limit_button(self, interaction: discord.Interaction, button: Button):
        if not self.can_interact(interaction):
            return await interaction.response.send_message("❌ Tu n'as pas les droits.", ephemeral=True)

        await interaction.response.send_modal(LimitModal())

    # Permission Restriction Button
    @discord.ui.button(label="🔒 Restreindre les droits", style=discord.ButtonStyle.danger)
    async def toggle_rights(self, interaction: discord.Interaction, button: Button):
        if interaction.user.id != self.owner_id:
            return await interaction.response.send_message("❌ Seul le créateur peut modifier ce paramètre.", ephemeral=True)
        
        # Inversion des textes et couleurs
        self.shared = not self.shared

        if self.shared:
            button.label = "🔓 Partager les droits"
            button.style = discord.ButtonStyle.success
        else:
            button.label = "🔒 Restreindre les droits"
            button.style = discord.ButtonStyle.danger
        
        await interaction.response.edit_message(view=self)

    # Hide Button
    @discord.ui.button(label="👻 Cacher le salon", style=discord.ButtonStyle.primary)
    async def hide_button(self, interaction: discord.Interaction, button: Button):
        if not self.can_interact(interaction):
            return await interaction.response.send_message("❌ Tu n'as pas les droits.", ephemeral=True)
        
        # On vérifie si le rôle @everyone a la permission de voir le salon
        everyone_role = interaction.guild.default_role
        is_hidden = interaction.channel.permissions_for(everyone_role).view_channel == False
        
        # On inverse : si caché on montre, si visible on cache
        await interaction.channel.set_permissions(everyone_role, view_channel=is_hidden)
        
        if not is_hidden:
            button.label = "👁️ Rendre visible"
        else:
            button.label = "👻 Cacher le salon"
        
        await interaction.response.edit_message(view=self)

    # Trust Button
    @discord.ui.button(label="🤝 Autoriser la/les personne(s)", style=discord.ButtonStyle.success)
    async def trust_button(self, interaction: discord.Interaction, button: Button):
        if not self.can_interact(interaction):
            return await interaction.response.send_message("❌ Vous n'avez pas les droits.", ephemeral=True)
        
        await interaction.response.send_message("Sélectionnez les membres :", view=TrustView(), ephemeral=True)
   
    # Claim Button
    @discord.ui.button(label="🙋‍♂️ Revendiquer", style=discord.ButtonStyle.success)
    async def claim_button(self, interaction: discord.Interaction, button: Button):

        # On vérifie si le créateur actuel est encore dans le salon vocal
        owner_present = any(m.id == self.owner_id for m in interaction.channel.members)
        
        if owner_present:
            return await interaction.response.send_message("❌ Le propriétaire actuel est toujours dans le vocal.", ephemeral=True)
            
        # On transfère la propriété
        self.owner_id = interaction.user.id
        await interaction.response.send_message(f"👑 {interaction.user.mention} est le nouveau propriétaire du vocal !")


#########
# MODAL #
#########
# Rename Modal
class RenameModal(Modal, title="Renommer le salon"):
    name_input = TextInput(label="Nouveau nom", max_length=50)

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.channel.edit(name=self.name_input.value)
        await interaction.response.send_message(f"✅ Salon renommé en : **{self.name_input.value}**", ephemeral=True)

# Limit Modal
class LimitModal(Modal, title="Limite de places"):
    limit_input = TextInput(label="Nombre maximum (0 = illimité)", max_length=2)

    async def on_submit(self, interaction: discord.Interaction):
        try:
            limit = int(self.limit_input.value)
            await interaction.channel.edit(user_limit=limit)

            if limit > 0:
                msg = f"✅ Limite fixée à : **{limit}** places"
            else:
                msg = f"✅ Limite retirée (illimité)."
            
            await interaction.response.send_message(msg, ephemeral=True)

        except ValueError:
            await interaction.response.send_message("❌ Erreur : Tu dois entrer un chiffre.", ephemeral=True)

class TrustSelect(discord.ui.UserSelect):
    def __init__(self):
        super().__init__(placeholder="Choisissez les membres à autoriser...", min_values=1, max_values=10)

    async def callback(self, interaction: discord.Interaction):
        # On accorde la permission de voir le salon pour chaque membre sélectionné
        for member in self.values:
            await interaction.channel.set_permissions(member, view_channel=True)
        await interaction.response.send_message(f"✅ Accès visible accordé à {len(self.values)} membre(s).", ephemeral=True)

class TrustView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=120)
        self.add_item(TrustSelect())


#################
# START SERVICE #
#################
async def setup(bot):
    await bot.add_cog(VoiceChannel(bot))