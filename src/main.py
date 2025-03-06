import re
import asyncio
import aiohttp
from dotenv import load_dotenv
import io
import logging
import os
import openai

from telegram import Update
from telegram.ext.dispatcher import run_async
from telegram.ext import (
    Updater,
    CommandHandler,
    MessageHandler,
    Filters,
    CallbackContext,
    MessageFilter,
)
from telegram import Message

from google.oauth2 import service_account
from google.cloud import vision

load_dotenv()

# Get telegram bot API token from the variable BOT_API_TOKEN or the environment file .env
telegram_bot_api_token = os.getenv("BOT_API_TOKEN")
if telegram_bot_api_token is None:
    raise ValueError("Please set the BOT_API_TOKEN environment variable.")

# Get your OpenAI API key from the variable OPENAI_API_KEY or the environment file .env
openai_api_key = os.getenv("OPENAI_API_KEY")
if openai_api_key is None:
    raise ValueError("Please set the OPENAI_API_KEY environment variable.")

# Get open ai chat model from the variable OPENAI_CHAT_MODEL or the environment file .env
openai_chat_model = os.getenv("OPENAI_CHAT_MODEL")
if openai_chat_model is None:
    raise ValueError("Please set the OPENAI_CHAT_MODEL environment variable.")

rapid_api_key = os.getenv("RAPID_API_KEY")
if rapid_api_key is None:
    raise ValueError("Please set the RAPID_API_KEY environment variable.")

RapidApi_Key = rapid_api_key
openai.api_key = openai_api_key
API_TOKEN = telegram_bot_api_token
# Get Service Account file from the variable SERVICE_ACCOUNT_FILE or the environment file .env
service_account_file = os.getenv("SERVICE_ACCOUNT_FILE")
if service_account_file is None:
    raise ValueError("Please set the SERVICE_ACCOUNT_FILE environment variable.")

# Check if the file exists
if not os.path.exists(service_account_file):
    raise FileNotFoundError("The service account file does not exist.")

credentials = service_account.Credentials.from_service_account_file(service_account_file)

fim = None

# Set up logging configuration
logging.basicConfig(
    level=logging.INFO,
    filename="app.log",
    filemode="w",
    format="%(asctime)s - %(levelname)s - %(message)s",
)

async def make_request(url):
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as response:
            response_text = await response.text()
            return response_text

async def description(query):

    if not re.search(r"(?:QUAL +D(?:O|A)S +SEGUINTES)|(?:QUAL +DESTES)", query):

        url = "https://duckduckgo8.p.rapidapi.com/"

        querystring = {"q": query}

        headers = {
            "X-RapidAPI-Key": RapidApi_Key,
            "X-RapidAPI-Host": "duckduckgo8.p.rapidapi.com",
        }

        async with aiohttp.ClientSession() as session:
            async with session.get(
                url, headers=headers, params=querystring
            ) as response:
                res = await response.json()
                return "\n\n".join(
                    [
                        res["results"][0]["description"],
                        res["results"][1]["description"],
                        res["results"][2]["description"],
                    ]
                )
    else:
        return None

def detect_text(path):
    """Detects text in the file."""
    client = vision.ImageAnnotatorClient(credentials=credentials)

    with io.open(path, "rb") as image_file:
        content = image_file.read()

    image = vision.Image(content=content)

    response = client.text_detection(image=image)

    if response.error.message:
        logging.info("Google Text Failed")
        raise Exception(
            f"{response.error.message}\nFor more info on error messages, check: "
            "https://cloud.google.com/apis/design/errors"
        )

    return response

async def pergunta(text):

    completion = await openai.ChatCompletion.acreate(
        model=openai_chat_model,
        temperature=1,
        messages=[{"role": "user", "content": text}],
        timeout=4,
    )

    return completion.choices[0].message.content


def number_to_letter(number):
    if 1 <= number <= 26:
        letter = chr(number + 64)
        return letter

    return "Invalid number"


def resposta(image):
    global fim
    response = detect_text(image)
    res = str(response.text_annotations[0].description).splitlines()
    res = list(map(lambda x: x.strip(), res))

    for line in res[:5]:
        if len(line) <= 6:
            res.pop(0)
        else:
            break

    j = 0

    for i, line in enumerate(res[:3]):
        if "?" in line:
            j = i
            break

    for _ in range(j):
        line = res.pop(1)
        res[0] = res[0] + " " + line

    for i, line in enumerate(res[1:]):
        if re.search(r".*D(?:r|e)(?:\.|:)Why.*", line):
            res = res[: i + 1]
            break

    j = 5

    for i, line in enumerate(res[1:]):
        if j > i:
            res[i + 1] = number_to_letter(i + 1) + ") " + line
        else:
            break

    res.append(
        "Por favor responde apenas com a letra correspondente à resposta (se não tiver letra considere a primeira opcão a letra A, segunda a B ...) e a resposta.\nSe não tiver opções simplesmente responda sucitamente."
    )

    if fim:
        res.append(fim)

    first = res[0]

    res = "\n".join(res)

    return res, first


async def resposta_final(image, loop):
    res, first = resposta(image)

    logging.info("Google Texto: " + res)

    task1 = loop.create_task(description(first), name="description")

    task2 = loop.create_task(pergunta(res), name="pergunta")

    task3 = loop.create_task(
        pergunta(first + "\nResponda de forma sucinta"), name="pergunta1"
    )

    l = [task1, task2, task3]

    while True:
        done, pending = await asyncio.wait(l, return_when=asyncio.FIRST_COMPLETED)

        # Process completed tasks
        for task in done:
            l.remove(task)

            if task.get_name() == "description":
                logging.info("Descricao: " + task.result())
            elif task.get_name() == "pergunta":
                logging.info("Resposta: " + task.result())
            elif task.get_name() == "pergunta":
                logging.info("Resposta: " + task.result())

        if not pending:
            break

# Define a start command handler
def start(update: Update, context: CallbackContext):
    update.message.reply_text("Send me an image and I'll process it.")

# Define the function to process the image
def process_image(image_file_id):
    print("Image file ID:", image_file_id)
    # Add your image processing logic here
    return "Image processing done."

async def sleep(t):
    await asyncio.sleep(t)
    return

async def image_handler_async(update: Update, context: CallbackContext):

    logging.info("Entering image_handler")

    loop = asyncio.get_event_loop()

    # get the image file
    image = update.message.photo[-1].get_file()

    # download the image
    image.download(
        "image.jpg"
    )  # replace 'image.jpg' with your preferred file path and name

    # send a response message

    res, first = resposta("image.jpg")

    logging.info("Pergunta: " + res)

    task1 = loop.create_task(description(first), name="description")

    task2 = loop.create_task(pergunta(res), name="pergunta")

    task3 = loop.create_task(sleep(5), name="time")

    task4 = loop.create_task(
        pergunta(first + "\nResponda de forma sucinta"), name="pergunta"
    )

    l = [task1, task2, task3, task4]

    check = False

    while True:
        done, pending = await asyncio.wait(l, return_when=asyncio.FIRST_COMPLETED)

        # Process completed tasks
        for task in done:
            if task.get_name() == "time":
                l.remove(task)
                check = True
                break
            if task.get_name() == "description":
                logging.info("Descricao: " + task.result())
            elif task.get_name() == "pergunta":
                logging.info("Resposta: " + task.result())
            l.remove(task)
            update.message.reply_text(task.result())

        if not pending or check:
            break

    if len(l) != 0:
        update.message.reply_text("Timeout!")

    for t in l:
        t.cancel()

    try:
        await asyncio.wait(l)
    except:
        pass


def image_handler(update: Update, context: CallbackContext):
    asyncio.run(image_handler_async(update, context))


def add_handler(update: Update, context: CallbackContext):
    global fim
    logging.info("Texto a adicionar: " + update.message.text[5:])
    fim = update.message.text[5:]
    update.message.reply_text("Adicionado.")


def rem_handler(update: Update, context: CallbackContext):
    global fim
    logging.info("Texto removido")
    fim = None
    update.message.reply_text("Removido.")


def main():
    updater = Updater(API_TOKEN)
    user = 1702993292

    # Get the dispatcher to register handlers
    dp = updater.dispatcher

    # Register the handlers
    dp.add_handler(CommandHandler("start", start, filters=Filters.user(user)))
    dp.add_handler(
        MessageHandler(Filters.photo & Filters.user(user), image_handler)
    )
    dp.add_handler(
        CommandHandler(
            "add", add_handler, pass_args=True, filters=Filters.user(user)
        )
    )
    dp.add_handler(CommandHandler("rem", rem_handler, filters=Filters.user(user)))

    # Start the bot
    updater.start_polling()

    # Run the bot until Ctrl-C is pressed or the process receives SIGINT, SIGTERM or SIGABRT
    updater.idle()


if __name__ == "__main__":
    main()
