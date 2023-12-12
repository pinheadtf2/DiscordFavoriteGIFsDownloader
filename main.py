import asyncio
import aiofiles
from json import loads, dumps
from collections import deque
from zipfile import ZipFile
from os import path, mkdir
from datetime import datetime
from rich import print as rprint
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TimeElapsedColumn, BarColumn, TaskProgressColumn, \
    MofNCompleteColumn
from aiohttp import ClientSession, TCPConnector

# set up progress bar
progress = Progress(
    SpinnerColumn(),
    TimeElapsedColumn(),
    BarColumn(),
    MofNCompleteColumn(),
    TaskProgressColumn()
)

# set up console
console = Console()


def current_time():
    # prints out the colored current time with ms for console-like output
    return f"[aquamarine3][{datetime.now().strftime('%T.%f')[:-3]}][/aquamarine3] "


async def dequeue(semaphore: asyncio.Semaphore, sleep: int):
    """Wait for a duration, then increase the Semaphore"""
    try:
        await asyncio.sleep(sleep)
    finally:
        semaphore.release()


async def download_gif(semaphore: asyncio.Semaphore, session: ClientSession, progress_task, sleep: int, url: str):
    """Decrement the semaphore, schedule an increment, and download a URL"""
    await semaphore.acquire()
    asyncio.create_task(dequeue(semaphore, sleep))

    # get filename from url for saving
    filename = url.rsplit('/', 1)[-1].rsplit('.', 1)[0]

    async with session.get(url) as response:
        # ensure response is good
        if response.status == 200:
            # verify that content is valid gif
            if response.headers['Content-Type'] == 'image/gif':
                # if a duplicate file is found, start adding a counter in the name
                if path.isfile(f'gifs/{filename}.gif'):
                    i = 0
                    while path.exists(f"gifs/{filename}{i}.gif"):
                        i += 1
                    filename = filename + str(i)

                # save gif
                async with aiofiles.open(f"gifs/{filename}.gif", 'wb') as file:
                    await file.write(await response.read())
                progress.update(progress_task, advance=1)
        else:
            # return url to re-save if something went wrong
            progress.console.print(
                f"{current_time()}[bold red1]Download failed on file [/bold red1][purple]{filename}[/purple] "
                f"[orange1]({response.status})[/orange1]")
            return [url, response.status]


async def main():
    rprint(f"{current_time()}pinhead's Favorite GIF Downloader v1.0\n"
           f"Saves your Discord-hosted GIFs to your files. Only works pre-media link change! "
           f"Ensure you have downloaded and placed your zipped data package in this folder!")

    if path.isdir('gifs'):
        rprint(
            f"{current_time()}[bold red1]Error:[/bold red1] The [purple]gifs[/purple] folder has been found, "
            f"and your GIFs may already be downloaded. Continuing will create duplicates. "
            f"Please change the name of the [purple]gifs[/purple] folder, or delete it.")
        exit(0)
    else:
        mkdir('gifs')

    # check to see if the package even exists
    if not path.isfile('package.zip'):
        rprint(f"{current_time()}[bold red1]Error:[/bold red1] [italic purple]package.zip[/italic purple] not found! "
               "Did you place it in the same folder as me?")
        exit(0)

    # access the package zip
    data_package = ZipFile('package.zip', 'r')
    rprint(f"{current_time()}[green]Found package.zip![/green]")

    # see if the user file exists in the package
    if 'account/user.json' not in data_package.namelist():
        rprint(
            f"{current_time()}[bold red1]Error:[/bold red1] [italic blue1]account/user.json[/italic blue1] not found in "
            "[italic purple]package.zip[/italic purple]! Is your package corrupted?")
        exit(0)

    # read the file and convert the bytes to a string
    user_file_string = data_package.read('account/user.json').decode("utf-8")
    # convert the string to a json dict
    user_json = loads(user_file_string)
    favorite_gifs = user_json['settings']['frecency']['favoriteGifs']['gifs']
    rprint(f"{current_time()}[green]Loaded GIF list, and found "
           f"[bold purple]{len(favorite_gifs)}[/bold purple] GIFs![/green]")

    # deque has faster read/write times than dict and list
    discord_media_links = deque()
    for key in favorite_gifs.keys():
        if 'media.discordapp.net' in favorite_gifs[key]['src']:
            discord_media_links.append(favorite_gifs[key]['src'])
    rprint(f"{current_time()}[green]Added [bold purple]{len(discord_media_links)}[/bold purple] "
           f"[red]Discord-Hosted[/red] GIFs to the download list!")

    rprint(f"{current_time()}[green]Downloads starting![/green]")
    failed_download_urls = None
    with progress:
        progress_task = progress.add_task("[cyan]Downloading...[/cyan]", total=len(discord_media_links))

        # limit connections as failsafe
        with TCPConnector(limit=5) as connector:
            async with ClientSession(connector=connector) as session:
                # create async limit and sleep
                sleep_duration = 3
                semaphore = asyncio.Semaphore(5)
                # run task loop
                tasks = [asyncio.create_task(download_gif(semaphore, session, progress_task, sleep_duration, url))
                         for url in discord_media_links]
                failed_download_urls = await asyncio.gather(*tasks)

        # clear out successful results
        failed_download_urls = list(filter(None, failed_download_urls))
        # attempt to update progress to be correct
        progress.update(progress_task, advance=len(failed_download_urls))

    # save failed downloads to file and attach http code
    async with aiofiles.open('failed_downloads.json', 'w') as file:
        await file.write(dumps(failed_download_urls, indent=4))
    rprint(f"{current_time()}[green]Completed! Failed to download [red1]{len(failed_download_urls)}[/red1] GIFs. "
           f"Failed list has been saved to file as [purple]failed_downloads.json[/purple].")
    rprint(f"{current_time()}Thank you for using my script! "
           f"Be sure to move your GIFs elsewhere, and then you can delete this folder.\n"
           f"https://pinhead.dev")


asyncio.run(main())
