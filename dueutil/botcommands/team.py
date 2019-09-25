import json
import os
import re
import subprocess
import math
import time
from io import StringIO

import discord
import objgraph

import generalconfig as gconf
import dueutil.permissions
from ..game.helpers import imagehelper
from ..permissions import Permission
from .. import commands, util, events
from ..game import customizations, awards, leaderboards, game, players, emojis, teams

@commands.command(args_pattern="SB?C?")
async def createteam(ctx, name, isOpen=True, lower_level=1, **details):
    """
    ;createteam (name) (recruiting) (Minimum Level)

    Name: Team's name
    recruiting: Accepts people?
    Min level: Lowest level for someone to join the team

    Very basic.. isn't it?
    """
    teams.Team(details["author"], name, "Team Description", lower_level, isOpen, ctx)

    await util.say(ctx.channel, "Successfully created **%s**!" % (name))


@commands.command(args_pattern=None)
async def deleteteam(ctx, **details):
    """
    [CMD_KEY]deleteteam

    Deletes your team
    """

    team = details["author"].team
    name = team.name
    team.Delete()

    await util.say(ctx.channel, "%s successfully deleted!" % (name))


@commands.command(args_pattern="P", aliases=["ti"])
async def teaminvite(ctx, member, **details):
    """
    [CMD_KEY]teaminvite (player)

    NOTE: You cannot invite a player that is already in a team!
    """

    inviter = details["author"]

    team = inviter.team
    if member.team != None:
        raise util.DueUtilException(ctx.channel, "This player is already in a team!")
    if inviter.team is None:
        raise util.DueUtilException(ctx.channel, "You are not a part of a team!")
    if inviter == member:
        raise util.DueUtilException(ctx.channel, "You cannot invite yourself!")
    if not (inviter.id in team.admins:
        raise util.DueUtilException(ctx.channel, "You do not have permissions to send invites!!")

    if inviter.team not in member.team_invites:
        member.team_invites.append(inviter.team)
    else:
        raise util.DueUtilException(ctx.channel, "This player has already been invited to join your team!")
    member.save()

    await util.say(ctx.channel, ":thumbsup: Invite has been sent to **%s**!" % member.get_name_possession_clean())


@commands.command(args_pattern=None, aliases=["si"])
async def showinvites(ctx, **details):
    """
    [CMD_KEY]showinvites

    Display any team invites that you have received!
    """

    member = details["author"]

    Embed = discord.Embed(title="Displaying your team invites!", description="You were invited to join these teams!", type="rich", colour=gconf.DUE_COLOUR)
    if member.team_invites is None:
        member.team_invites = []
    if len(member.team_invites) == 0:
        Embed.add_field(name="No invites!", value="You do not have invites!")
    else:
        for team in member.team_invites:
            if team:
                Embed.add_field(name=team.name, 
                                value="Owner: **%s** (%s)\nMembers: **%s**\nRequired Level: **%s**\nRecruiting: **%s**" 
                                % (team.owner.name_clean, team.owner.id, len(team.members), team.level, ("Yes" if team.open else "No")), 
                                inline=False))
    
    member.save()
    await util.say(ctx.channel, embed=Embed)


@commands.command(args_pattern="C", aliases=["ai"])
async def acceptinvite(ctx, team_index, **details):
    """
    [CMD_KEY]acceptinvite (team index)

    Accept a team invite.
    """

    member = details["author"]
    team_index -= 1
    if member.team != None:
        raise util.DueUtilException(ctx.channel, "You are already in a team.")
    if team_index >= len(member.team_invites):
        raise util.DueUtilException(ctx.channel, "Invite not found!")

    teams = customizations.teams
    team_name = member.team_invites[team_index]
    member.team = team_name
    with open('dueutil/game/configs/teams.json', 'r+') as team_file:
        teams = json.load(team_file)
        if not (team_name in teams):
            del member.team_invites[team_index]
            member.save()
            raise util.DueUtilException(ctx.channel, "This team does not exist anymore!")

        team_target = teams[team_name]
        team_target["members"].append(member.id)

        team_file.seek(0)
        team_file.truncate()
        json.dump(teams, team_file, indent=4)
    del member.team_invites[team_index]
    member.save()
            
    await util.say(ctx.channel, "Successfully joined **%s**!" % team_name)


@commands.command(args_pattern="C", aliases=["di"])
async def declineinvite(ctx, team_index, **details):
    """
    [CMD_KEY]declineinvite (team index)

    Decline a team invite cuz you're too good for it.
    """

    member = details["author"]
    team_index -= 1

    if member.team_invites is None:
        member.team_invites = []
    if team_index >= len(member.team_invites):
        raise util.DueUtilException(ctx.channel, "Invite not found!")
        
    team_name = member.team_invites[team_index]
    del member.team_invites[team_index]
    member.save()
            
    await util.say(ctx.channel, "Successfully deleted **%s** invite!" % team_name)


@commands.command(args_pattern=None, aliases=["mt"])
async def myteam(ctx, **details):
    """
    [CMD_KEY]myteam

    Display your team!

    Couldn't find 
    a longer description 
    for this than 
    that :shrug:
    So now it is longer
    """

    member = details["author"]
    teams = customizations.teams

    if member.team != None:
        if member.team in teams:
            await util.say(ctx.channel, "You are a part of **%s**!" % member.team)
        else:
            member.team = None
            await util.say(ctx.channel, "You are **not** a part of a team!")
    else:
        await util.say(ctx.channel, "You are **not** a part of a team!")

    member.save()

@commands.command(args_pattern="P", aliases=["pu"])
async def promoteuser(ctx, user, **details):
    """
    [CMD_KEY]promoteuser (player)

    Promote a member of your team to admin.
    Being an admin allows you to manage the team: Invite players, kick players, etc.

    NOTE: Only the owner can promote members!
    """

    member = details["author"]
    team = customizations.teams[member.team]

    if member == user:
        raise util.DueUtilException(ctx.channel, "You are not allowed to promote yourself!")
    if member.team is None:
        raise util.DueUtilException(ctx.channel, "You are not in a team!")
    if user.team is None:
        raise util.DueUtilException(ctx.channel, "This player is not in a team!")
    if member.id != team["owner"]:
        raise util.DueUtilException(ctx.channel, "You are not allowed to promote users! (You must be owner!)")
    if member.team != user.team:
        raise util.DueUtilException(ctx.channel, "This player is not in your team!")
    
    with open('dueutil/game/configs/teams.json', 'r+') as team_file:
        teams = json.load(team_file)
        team = teams[member.team]
        if user.id in team["admins"]:
            raise util.DueUtilException(ctx.channel, "This user is already an admin!")

        team["admins"].append(user.id)

        team_file.seek(0)
        team_file.truncate()
        json.dump(teams, team_file, indent=4)
    
    await util.say(ctx.channel, "Successfully **promoted %s** as an **admin** in **%s**!" % (user.get_name_possession_clean(), team["name"]))


@commands.command(args_pattern="P", aliases=["du"])
async def demoteuser(ctx, user, **details):
    """
    [CMD_KEY]demoteuser (player)

    Demote an admin of your team to a normal member.

    NOTE: Only the owner can demote members!
    """

    member = details["author"]
    team = customizations.teams[member.team]

    if member.team is None:
        raise util.DueUtilException(ctx.channel, "You are not in a team!")
    if user.team is None:
        raise util.DueUtilException(ctx.channel, "This player is not in your team!")
    if member.team != user.team:
        raise util.DueUtilException(ctx.channel, "This player is not in your team!")
    if member.id != team["owner"]:
        raise util.DueUtilException(ctx.channel, "You are not allowed to demote users! (You must be the owner!)")
    if member == user:
        raise util.DueUtilException(ctx.channel, "There is no reason to demote yourself!")
    
    with open('dueutil/game/configs/teams.json', 'r+') as team_file:
        teams = json.load(team_file)
        team = teams[user.team]

        if user.id in team["admins"]:
            team["admins"].remove(user.id)
            user.save()
        else:
            raise util.DueUtilException(ctx.channel, "This player is already a member. If you meant to kick him, please use %steamkick (user)" % (details["cmd_key"]))

    await util.say(ctx.channel, "**%s** has been demoted to **Member**" % (user.get_name_possession_clean()))
        

@commands.command(args_pattern="P", aliases=["tk"])
async def teamkick(ctx, user, **details):
    """
    [CMD_KEY]teamkick (player)

    Allows you to kick a member from your team.
    You don't like him? Get rid of him!

    NOTE: Team owner & admin are able to kick users from their team!
        Admins cannot kick other admins or the owner.
        Only the owner can kick an admin.
    """

    member = details["author"]
    team = customizations.teams[member.team]

    if member == user:
        raise util.DueUtilException(ctx.channel, "There is no reason to kick yourself!")
    if member.team is None:
        raise util.DueUtilException(ctx.channel, "You are not in a team!")
    if user.team is None:
        raise util.DueUtilException(ctx.channel, "This player is not in a team!")
    if member.team != user.team:
        raise util.DueUtilException(ctx.channel, "This player is not in your team!")

    if user.id in team["admins"] and member.id != team["owner"]:
        raise util.DueUtilException(ctx.channel, "You must be the owner to kick this player from the team!")
    if member.id not in team["admins"]:
        raise util.DueUtilException(ctx.channel, "You must be an admin to use this command!")
    
    with open('dueutil/game/configs/teams.json', 'r+') as team_file:
        teams = json.load(team_file)
        team = teams[member.team]

        user.team = None
        if user.id in team["members"]:
            team["members"].remove(user.id)
        if user.id in team["admins"]:
            team["admins"].remove(user.id)

        team_file.seek(0)
        team_file.truncate()
        json.dump(teams, team_file, indent=4)

    await util.say(ctx.channel, "Successfully kicked **%s** from your team, adios amigos!" % user.get_name_possession())


@commands.command(args_pattern=None, aliases=["lt"])
async def leaveteam(ctx, **details):
    """
    [CMD_KEY]leaveteam

    You don't want to be in your team anymore?

    Congrats you found the right command to leave! 

    :D
    """

    user = details["author"]

    if not user.team:
        raise util.DueUtilException(ctx.channel, "You are not in any team.. You can't leave the void.. My void! :smiling_imp:")

    with open('dueutil/game/configs/teams.json', 'r+') as team_file:
        teams = json.load(team_file)
        team = teams[user.team]

        if user.id == team["owner"]:
            raise util.DueUtilException(ctx.channel, "You cannot leave this team! If you want to disband it, use `%sdeleteteam`" % (details["cmd_key"]))
        if user.id in team["admins"]:
            team["admins"].remove(user.id)
        team["members"].remove(user.id)
        user.team = None
        user.save()

        team_file.seek(0)
        team_file.truncate()
        json.dump(teams, team_file, indent=4)

    await util.say(ctx.channel, "You successfully left your team!")


@commands.command(args_pattern="C?", aliases=["st"])
async def showteams(ctx, page=1, **details):
    """
    [CMD_KEY]showteams (page)

    Show all existant teams
    
    Obviously they are existant...
    how would it even display something not existant?
    """
    
    page = page - 1
    if page != 0 and page * 5 >= len(customizations.teams):
        raise util.DueUtilException(ctx.channel, "Page not found")

    teamsEmbed = discord.Embed(title="There is the teams lists", description="Display all existant teams", type="rich", colour=gconf.DUE_COLOUR)
    with open('dueutil/game/configs/teams.json', 'r+') as team_file:
        teamsdict = json.load(team_file)
        teams = list(teamsdict)
        top = (page * 5 + 5)
        limit = top if top < len(teams) else len(teams) - 1
        for index in range(page * 5, limit, 1):
            team_name = teams[index]
            team = teamsdict[team_name]
            teamsEmbed.add_field(name=team["name"], value="Owner: **%s** (%s)\nMembers: **%s**\nRequired Level: **%s**\nRecruiting: **%s**" % (players.find_player(team["owner"]).name_clean, str(team["owner"]), len(team["members"]), team.level, ("Yes" if team.open else "No")), inline=False)
        limit = (5 * page) + 5 < len(teams)
        teamsEmbed.set_footer(text="%s" % (("Do %sshowteams %d for the next page!" % (details["cmd_key"], page + 2)) if limit else "That's all the teams!"))
    await util.say(ctx.channel, embed=teamsEmbed)


@commands.command(args_pattern="T", aliases=["sti"])
async def showteaminfo(ctx, team, **details):
    """
    [CMD_KEY]showteaminfo (team)

    Display information about selected team - Owner, Admins, Members, team name, number of members, etc
    """

    team_embed = discord.Embed(title="Team Information", description="Displaying team information", type="rich", colour=gconf.DUE_COLOUR)
    pendings = ""
    members = ""
    admins = ""
    for id in team["admins"]:
        if id != team["owner"]:
            admins += "%s (%s)\n" % (players.find_player(id).name_clean, str(id))
    for id in team["members"]:
        if id not in team["admins"]:
            members += "%s (%s)\n" % (players.find_player(id).name_clean, str(id))
    for id in team["pendings"]:
        if id in team["members"]:
            team["pendings"].remove(id)
        else:
            pendings += "%s (%s)\n" % (players.find_player(id).name_clean, str(id))
        

    team_embed.add_field(name="Global Information:", 
                         value="Team Name: **%s**\nMember count: **%s**\nRequired level: **%s**\nRecruiting: **%s**" % (team["name"], len(team["members"]), team.level, ("Yes" if team.open else "No")),
                         inline=False)
    if len(pendings) == 0:
        pendings = "Nobody is pending!"
    if len(members) == 0:
        members = "There is no member to display!"
    if len(admins) == 0:
        admins = "There is no admin to display!"
    team_embed.add_field(name="Owner:", value="%s (%s)" % (players.find_player(team["owner"]).name_clean, str(team["owner"])))
    team_embed.add_field(name="Admins:", value=admins)
    team_embed.add_field(name="Members:", value=members)
    team_embed.add_field(name="Pendings:", value=pendings)

    await util.say(ctx.channel, embed=team_embed)


@commands.command(args_pattern="T", aliases=["jt"])
async def jointeam(ctx, team, **details):
    """
    [CMD_KEY]jointeam (team)
    
    Join a team or puts you on pending list
    """

    user = details["author"]

    if user.team != None:
        raise util.DueUtilException(ctx.channel, "You are already in a team.")
    
    with open('dueutil/game/configs/teams.json', 'r+') as team_file:
        teams = json.load(team_file)
        team = teams[team["name"]]

        if user.level < team.level:
            raise util.DueUtilException(ctx.channel, "You must be level %s or higher to join this team!" % (str(team.level)))
        if team.open:
            team["members"].append(user.id)
            user.team = team["name"]
            if user.id in team["pendings"]:
                team["pendings"].remove(user.id)
        else:
            if user.id in team["pendings"]:
                raise util.DueUtilException(ctx.channel, "You are already pending for that team!")
            team["pendings"].append(user.id)

        team_file.seek(0)
        team_file.truncate()
        json.dump(teams, team_file, indent=4)

    user.save()
    message = "You successfully joined **%s**!" % (team["name"])
    await util.say(ctx.channel, message if team.open else "You have been added to the team's pending list!")


@commands.command(args_pattern='S*', aliases=["ts"])
@commands.extras.dict_command(optional={"min level/minimum level/level": "I", "open/recruiting": "B"})
async def teamsettings(ctx, updates, **details):
    """
    [CMD_KEY]teamsettings param (value)+

    You can change both properties at the same time.

    Properties:
        __level__, __recruiting__

    Example usage:

        [CMD_KEY]teamsettings "minimum level" 10

        [CMD_KEY]teamsettings recruiting true
    """

    user = details["author"]

    if user.team is None:
        raise util.DueUtilException(ctx.channel, "You are not in a team!")

    with open('dueutil/game/configs/teams.json', 'r+') as team_file:
        teams = json.load(team_file)
        team = teams[user.team]
        if user.id not in team["admins"]:
            raise util.DueUtilException(ctx.channel, "You must be an admin in order to change settings!")
        
        for prop, value in updates.items():
            if prop in ("minimum level", "level", "min level"):
                if value >= 1:
                    team.level = value
                else:
                    updates[prop] = "Must be at least 1!"
                continue
            elif prop in ("open", "recruiting"):
                team.open = value
            else:
                continue

        team_file.seek(0)
        team_file.truncate()
        json.dump(teams, team_file, indent=4)

    if len(updates) == 0:
        await util.say(ctx.channel, "You need to provide a valid property for the team!")
    else:
        result = "**Settings changed:**\n"
        for prop, value in updates.items():
            result += ("``%s`` → %s\n" % (prop, value))
        await util.say(ctx.channel, result)


@commands.command(args_pattern="I?", aliases=["pendings", "stp"])
async def showteampendings(ctx, page=1, **details):
    """
    [CMD_KEY]showteampendings (page)

    Display a list of pending users for your team!
    """

    user = details["author"]
    page = page -1
    if user.team is None:
        raise util.DueUtilException(ctx.channel, "You're not part of any team!")
    
    pendings = ""
    with open('dueutil/game/configs/teams.json', 'r+') as team_file:
        teams = json.load(team_file)
        team = teams[user.team]
        if page != 0 and page * 5 >= len(team["pendings"]):
            raise util.DueUtilException(ctx.channel, "Page not found")
            
        top = ((5 * page) + 5) if ((5 * page) + 5 < len(team["pendings"])) else len(team["pendings"])
        for index in range((5 * page), top, 1):
            id = team["pendings"][index]
            pendings += "%i - %s (%s)\n" % (index + 1, players.find_player(id).name_clean, str(id))
            
        if len(pendings) == 0:
            pendings = "Nobody is pending!"
        pendings_embed = discord.Embed(title="**%s** pendings list" % (team["name"]), description="Displaying user pending to your team", type="rich", colour=gconf.DUE_COLOUR)
        pendings_embed.add_field(name="Pendings:", value=pendings)
        limit = (5 * page) + 5 < len(team["pendings"])
        pendings_embed.set_footer(text="%s" % (("Do %sshowpendings %d for the next page!" % (details["cmd_key"], page + 2)) if limit else "That's all the pendings!"))
    
    await util.say(ctx.channel, embed=pendings_embed)


@commands.command(args_pattern="I", aliases=["ap"])
async def acceptpending(ctx, index, **details):
    """
    [CMD_KEY]acceptpending (index)

    Accept a user pending to your team.
    """

    user = details["author"]
    index -= 1
    if user.team is None:
        raise util.DueUtilException(ctx.channel, "You're not in a team!")

    with open('dueutil/game/configs/teams.json', 'r+') as team_file:
        teams = json.load(team_file)
        team = teams[user.team]
        if user.id not in team["admins"]:
            raise util.DueUtilException(ctx.channel, "Hold on! You're not allowed to accept people in your team!")
        if index >= len(team["pendings"]):
            raise util.DueUtilException(ctx.channel, "Pending user not found!")
        pending_user = players.find_player(team["pendings"][index])
        if pending_user.team != None:
            del team["pendings"][index]
            raise util.DueUtilException(ctx.channel, "This player found his favorite team already!")
        team["members"].append(pending_user.id)
        team["pendings"].remove(pending_user.id)
        pending_user.team = user.team
        pending_user.save()

        team_file.seek(0)
        team_file.truncate()
        json.dump(teams, team_file, indent=4)
    await util.say(ctx.channel, "Accepted **%s** in your team!" % (pending_user.name_clean))


@commands.command(args_pattern="I", aliases=["dp"])
async def declinepending(ctx, index, **details):
    """
    [CMD_KEY]declinepending (index)

    Decline a user pending to your team.
    """

    user = details["author"]
    index -= 1
    if user.team is None:
        raise util.DueUtilException(ctx.channel, "You're not in a team!")

    with open('dueutil/game/configs/teams.json', 'r+') as team_file:
        teams = json.load(team_file)
        team = teams[user.team]
        if user.id not in team["admins"]:
            raise util.DueUtilException(ctx.channel, "Hold on! You're not allowed to refuse people!")
        if index >= len(team["pendings"]):
            raise util.DueUtilException(ctx.channel, "Pending user not found!")
        pending_user = players.find_player(team["pendings"][index])
        team["pendings"].remove(pending_user.id)
        pending_user.save()

        team_file.seek(0)
        team_file.truncate()
        json.dump(teams, team_file, indent=4)
    await util.say(ctx.channel, "Refused **%s**!" % (pending_user.name_clean))