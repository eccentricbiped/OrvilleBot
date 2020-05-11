import csv
import os
import discord
from dotenv import load_dotenv
from discord.ext import commands
from datetime import datetime
import glob
import json
import pytz

load_dotenv()
TOKEN = os.getenv('DISCORD_TOKEN')
COMMAND = os.getenv('DISCORD_CMD')
BOTPREFIX = "!" + COMMAND

DAYZERO = int(os.getenv('DAY_ZERO'))
ZFILL_LEN = 4
default_timezone:str = "America/New_York"
current_date_no: int = -1

NOTIFY_OFF = -1

####################### CLASSES #######################

class OrvilleClient(discord.Client):

    async def on_ready(self):
        print('OrvilleClient ready!')


    async def on_message(self, message:discord.Message):

        ack_emoji:str = "\U0001F197"

        if message.content.find(BOTPREFIX) != -1:
            message_content: str = message.content.lower()

            open_cmd_idx:int = message_content.find(BOTPREFIX + "open")
            if open_cmd_idx != -1:

                next_space_idx:int = message_content.find(" ", open_cmd_idx) + 1
                postfix_name:str = ""

                if next_space_idx > 0 and next_space_idx + 1 < len(message_content):
                    postfix_name = message_content[next_space_idx:]

                await self.set_island_open(message, postfix_name)
                await message.add_reaction(ack_emoji)

            elif message_content.find(BOTPREFIX + "clos") != -1:
                await self.set_island_closed(message)
                await message.add_reaction(ack_emoji)

            elif message_content.find(BOTPREFIX + "reg") != -1:
                await self.register_ic_channel(message)
                await message.add_reaction(ack_emoji)


    async def set_island_closed(self, message: discord.Message):
        # Update user data flags
        user_data: dict = get_user_data_object(message)
        update_island_flag(user_data["user_info"], "O", False)
        update_user_data(user_data)

        # Update Island Chatter Channel Name
        channel = client.get_channel(user_data["user_info"]["ic_channel_id"])
        if channel is not None \
                and "username" in user_data["user_info"] \
                and "ic_channel_name" in user_data["user_info"]:
            await channel.edit(name=user_data["user_info"]["ic_channel_name"])
            await channel.send("Gates have closed for " + user_data["user_info"]["username"] + "!!")


    async def register_ic_channel(self, message: discord.Message):
        user_data: dict = get_user_data_object(message)

        user_data["user_info"]["ic_channel_id"] = message.channel.id
        user_data["user_info"]["ic_channel_name"] = message.channel.name
        user_data["user_info"]["island_flags"] = {}

        update_user_data(user_data)

        await message.channel.send(
            "Okay I've registered this channel {} as your island channel!".format(message.channel.name))


    async def set_island_open(self, message: discord.Message, arg: str = ""):
        # Update user data flags
        user_data: dict = get_user_data_object(message)
        update_island_flag(user_data["user_info"], "O", True)
        update_user_data(user_data)

        # Update Island Chatter Channel Name
        channel = self.get_channel(user_data["user_info"]["ic_channel_id"])
        if channel is not None \
                and "username" in user_data["user_info"] \
                and "ic_channel_name" in user_data["user_info"]:
            channel_postfix_name: str = "_open_" + arg.replace(' ', '_')
            await channel.edit(name=user_data["user_info"]["ic_channel_name"] + channel_postfix_name)
            await channel.send("Gates are open for " + user_data["user_info"]["username"] + "!!")


client: OrvilleClient = OrvilleClient()

####################### FUNCTIONS #######################

def get_user_data_object(message:discord.Message)->dict:
    server_id: str = str(message.guild.id)

    user_data_path: str = "./Users/{}".format(server_id)
    if not os.path.exists(user_data_path):
        os.mkdir(user_data_path)

    author_id: str = str(message.author.id)

    author_username: str = str(message.author)

    user_info_path: str = "./Users/{}/{}.json".format(server_id, author_id)
    user_info: dict = load_user_info(user_info_path)

    return { "author_id": author_id, "server_id": server_id, "author_username": author_username, "user_info_path": user_info_path, "user_info": user_info }

def load_user_info(file_path:str)->dict:
    global NOTIFY_OFF

    user_info: dict = {"username": "None", "username_discord": "None", "timezone": default_timezone, "notify": NOTIFY_OFF, "prices": {}, "ic_channel_id": "", "ic_channel_name": "", "island_flags": {} }
    try:
        with open(file_path, 'r') as jsonfile:
            user_info = json.load(jsonfile)
            jsonfile.close()
    except Exception as e:
        print("load_user_info error occurred loading json " + str(e))

    return user_info


def update_user_json(user_info:dict, user_info_path:str):
    with open(user_info_path, 'w+') as wf:
        json.dump(user_info, wf, indent=4, sort_keys=True)
        wf.close()


def update_user_data(user_data:dict):
    if "user_info" in user_data and "user_info_path" in user_data:
        update_user_json(user_data["user_info"], user_data["user_info_path"])

def update_island_flag(user_info:dict, flag_str:str, switch:bool):
    global current_date_no

    current_date_no = datetime.now(pytz.timezone(user_info["timezone"])).timetuple().tm_yday - DAYZERO
    key:str = str(current_date_no).zfill(ZFILL_LEN)
    user_flags:str = "" if key not in user_info["island_flags"] else user_info["island_flags"][key]

    if switch:
        if flag_str not in user_flags:
            user_flags += flag_str
    else:
        if flag_str in user_flags:
            user_flags = user_flags.replace(flag_str, '')

    user_info["island_flags"][key] = user_flags


client.run(TOKEN)