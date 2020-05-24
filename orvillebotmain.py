import csv
import os
import discord
from dotenv import load_dotenv
from discord.ext import commands
from datetime import datetime
import glob
import json
import pytz
import asyncio

# import time module, Observer, FileSystemEventHandler
import time
from watchdog.observers import Observer
from watchdog.events import FileSystemEvent, FileSystemEventHandler
from hachiko.hachiko import AIOWatchdog, AIOEventHandler


load_dotenv()
TOKEN = os.getenv('DISCORD_TOKEN')
COMMAND = os.getenv('DISCORD_CMD')
BOTPREFIX = "!" + COMMAND

DAYZERO = int(os.getenv('DAY_ZERO'))
ZFILL_LEN = 4
default_timezone:str = "America/New_York"
current_date_no: int = -1

WATCH_DIRECTORY = os.getenv('WATCH_DIRECTORY')
NOTIFY_OFF = -1

client = None

####################### CLASSES #######################

class OnMyWatch:



    def __init__(self):
        self.observer = Observer()

    async def run(self):
        print("run()")
        evh = Handler()
        watch = AIOWatchdog(WATCH_DIRECTORY, event_handler=evh)
        watch.start()

        #self.observer.schedule(event_handler, WATCH_DIRECTORY, recursive=True)
        #self.observer.start()

        print ("Observer started")

        try:
            while True:
                await asyncio.sleep(1)
        except:
            watch.stop()
            print("Observer Stopped")

        #self.observer.join()


class Handler(AIOEventHandler):
    """Subclass of asyncio-compatible event handler."""

    paths_changed:list = []

    async def on_created(self, event):
        print('Created:', event.src_path)  # add your functionality here

    async def on_deleted(self, event):
        print('Deleted:', event.src_path)  # add your functionality here

    async def on_moved(self, event):
        print('Moved:', event.src_path)  # add your functionality here

    async def on_modified(self, event):
        global client

        print('Modified:', event.src_path)  # add your functionality here
        #TODO Have a more robust way of addressing multiple FileOps within a short time and only calling the appropriate methods once

        if not event.is_directory:

            if event.src_path in self.paths_changed:
                self.paths_changed.remove(event.src_path)
            else:
                self.paths_changed.append(event.src_path)
                await client.on_json_update(event.src_path)

                await asyncio.sleep(1)
                if event.src_path in self.paths_changed:
                    self.paths_changed.remove(event.src_path)




class OrvilleClient(discord.Client):

    async def on_json_update(self, src_path:str):
        if ".json~" not in src_path and "orville" not in src_path:


            #server_id_str: str = src_path[-42:-24]  # Hacky way to get the server id
            orville_path: str = "../TurnipPriceBot/Users/orville.json"
            orville_info: dict = []
            try:
                with open(orville_path, 'r') as jsonfile:
                    orville_info = dict(json.load(jsonfile))
                    jsonfile.close()
            except Exception as e:
                print("on_any_event error occurred loading json " + str(e))

            if "servers" in orville_info:

                for server in orville_info["servers"]:

                    server_id_str:str = server["server_id"]
                    cached_count: int = 0 if "open_count" not in server else server["open_count"]
                    open_island_tally: tuple = get_open_island_tally(server_id_str)

                    if open_island_tally[1] != cached_count:
                        # There's been a change! Broadcast island status change and update count

                        if "broadcast_channel_id" in server:
                            channel_id:int = int(server["broadcast_channel_id"])
                            await self.send_message_to_broadcast_channel(open_island_tally[0], channel_id)

                        server["open_count"] = open_island_tally[1]  # update cached value

                        try:
                            with open(orville_path, 'w+') as wf:
                                json.dump(orville_info, wf, indent=4, sort_keys=True)
                                wf.close()
                        except Exception as e:
                            print("on_any_event error occurred loading json " + str(e))

                    await asyncio.sleep(1)


    async def on_ready(self):
        print('OrvilleClient ready!')


    async def send_message_to_broadcast_channel(self, message:str, channel_id:int):
        channel:discord.TextChannel = self.get_channel(channel_id)
        if channel is not None:
            await channel.send(message)


    async def on_message(self, message:discord.Message):

        ack_emoji:str = "\U0001F197"
        print("on_message " + message.content)

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

            #elif message_content.find(BOTPREFIX + "visit") != -1:
            #    await self.tally_open_islands(message, use_broadcast_channel=False)


    #async def tally_open_islands(self, message: discord.Message, use_broadcast_channel:bool):

     #   if use_broadcast_channel:
     #       channel = self.get_channel(BROADCAST_CHANNEL)
     #       await channel.send(get_open_island_tally(str(message.guild.id))[0])
     #   else:
      #      await message.channel.send(get_open_island_tally(str(message.guild.id))[0])

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
        user_data["user_info"]["open_reason"] = ""

        update_user_data(user_data)

        await message.channel.send(
            "Okay I've registered this channel {} as your island channel!".format(message.channel.name))


    async def set_island_open(self, message: discord.Message, arg: str = ""):
        # Update user data flags
        user_data: dict = get_user_data_object(message)

        update_island_flag(user_data["user_info"], "O", True)
        user_data["user_info"]["open_reason"] = arg

        update_user_data(user_data)

        # Update Island Chatter Channel Name
        if "ic_channel_id" in user_data["user_info"]:
            channel = self.get_channel(user_data["user_info"]["ic_channel_id"])
            if channel is not None \
                    and "username" in user_data["user_info"] \
                    and "ic_channel_name" in user_data["user_info"]:
                channel_postfix_name: str = "_open_" + arg.replace(' ', '_')
                await channel.edit(name=user_data["user_info"]["ic_channel_name"] + channel_postfix_name)
                await channel.send("Gates are open for " + user_data["user_info"]["username"] + "!!")




####################### FUNCTIONS #######################

def get_open_island_tally(server_id:str)->tuple:
    result:str = "\n ---------------------------------------- \n :airplane_small: :beach: ISLANDS OPEN RIGHT NOW :airplane_small: :beach: "

    json_files: list = glob.glob("../TurnipPriceBot/Users/{}/*.json".format(server_id))

    # Find users who are open
    count:int = 0
    for file in json_files:
        user_info: dict = load_user_info(file)

        date_no = datetime.now(pytz.timezone(user_info["timezone"])).timetuple().tm_yday - DAYZERO
        key: str = str(date_no).zfill(ZFILL_LEN)

        if "open_reason" in user_info \
                and "island_flags" in user_info \
                and key in user_info["island_flags"] \
                and "O" in user_info["island_flags"][key]:

            result += "\n **" + user_info["username"] + "**: " + user_info["open_reason"]
            if "ic_channel_id" in user_info and user_info["ic_channel_id"] != "":
                result += " <#" + str(user_info["ic_channel_id"]) + "> "

            count += 1

    if count == 0:
        result += "\n\nNo island is reportedly open at this time ! :no_entry_sign:"

    return result + "\n ---------------------------------------- \n", count


def get_user_data_object(message:discord.Message)->dict:
    server_id: str = str(message.guild.id)

    user_data_path: str = "../TurnipPriceBot/Users/{}".format(server_id)
    if not os.path.exists(user_data_path):
        os.mkdir(user_data_path)

    author_id: str = str(message.author.id)

    author_username: str = str(message.author)

    user_info_path: str = "../TurnipPriceBot/Users/{}/{}.json".format(server_id, author_id)
    user_info: dict = load_user_info(user_info_path)

    return { "author_id": author_id, "server_id": server_id, "author_username": author_username, "user_info_path": user_info_path, "user_info": user_info }

def load_user_info(file_path:str)->dict:
    global NOTIFY_OFF

    user_info: dict = {"username": "None", "username_discord": "None", "timezone": default_timezone, "notify": NOTIFY_OFF, "prices": {}, "ic_channel_id": "", "ic_channel_name": "", "island_flags": {}, "open_reason": "" }
    try:
        with open(file_path, 'r') as jsonfile:
            user_info = json.load(jsonfile)
            jsonfile.close()
    except Exception as e:
        print("load_user_info error occurred loading json " + str(e))

    if "island_flags" not in user_info:
        user_info["island_flags"] = {}
    if "open_reason" not in user_info:
        user_info["open_reason"] = ""

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

async def main():
    global client

    client = OrvilleClient()
    watch = OnMyWatch()

    tasks = [asyncio.ensure_future(watch.run()), asyncio.ensure_future(client.start(TOKEN))]

    await asyncio.gather(*tasks)

if __name__=="__main__":
    loop = asyncio.get_event_loop()
    loop.run_until_complete(main())
