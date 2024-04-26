from google.cloud import vision
from google.oauth2 import service_account
from telegram import Update, Message
from telegram.ext import ApplicationBuilder, Updater, CommandHandler, MessageHandler, CallbackContext, ContextTypes, filters
from dotenv import load_dotenv
from collections.abc import Sequence

import os
from openai import OpenAI
import io
import logging


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

openai_client = OpenAI(
    api_key = openai_api_key
)

# Get Service Account file from the variable SERVICE_ACCOUNT_FILE or the environment file .env
service_account_file = os.getenv("SERVICE_ACCOUNT_FILE")
if service_account_file is None:
    raise ValueError("Please set the SERVICE_ACCOUNT_FILE environment variable.")

credentials = service_account.Credentials.from_service_account_file(service_account_file)

def detect_text(path):
    """Detects text in the file."""
    
    client = vision.ImageAnnotatorClient(credentials=credentials)

    with io.open(path, 'rb') as image_file:
        content = image_file.read()

    image = vision.Image(content=content)

    response = client.text_detection(image=image) # type: ignore
    # texts = response.text_annotations
    # print('Texts:')

    # for text in texts:
    #     print('\n"{}"'.format(text.description))

    #     vertices = (['({},{})'.format(vertex.x, vertex.y)
    #                 for vertex in text.bounding_poly.vertices])

    #     print('bounds: {}'.format(','.join(vertices)))

    if response.error.message:
        raise Exception(
            '{}\nFor more info on error messages, check: '
            'https://cloud.google.com/apis/design/errors'.format(
                response.error.message))
    else:
        return response

def pergunta(text):

    chat_completion = openai_client.chat.completions.create(
        model=openai_chat_model, # type: ignore
        messages=[
            {"role": "user", "content": text}
        ]
    )

    return chat_completion.choices[0].message.content

def resposta(image):
    response = detect_text(image)
    res = str(response.text_annotations[0].description).splitlines()
    res = list(map(lambda x: x.strip(),res))
    res.append('Por favor responde apenas com uma letra.')

    res = '\n'.join(res)

    return pergunta(res)

# Enable logging
logging.basicConfig(level=logging.INFO)

# Define a start command handler
async def start(update: Update, _: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text("Send me an image and I'll process it.") # type: ignore


# Define the function to process the image
def process_image(image_file_id):
    print("Image file ID:", image_file_id)
    # Add your image processing logic here
    return "Image processing done."


async def image_handler(update: Update, _: ContextTypes.DEFAULT_TYPE):

    # Check for message is of the type Message
    if not isinstance(update.message, Message):
        raise ValueError("The update object does not have a message.")

    # Check if the message has a photo of the type (Sequence[telegram.PhotoSize], optional)
    if not isinstance(update.message.photo, Sequence):
        raise ValueError("The message does not have a photo.")

    # get the image file
    image = await update.message.photo[-1].get_file()

    # download the image
    await image.download_to_drive('image.jpg')  # replace 'image.jpg' with your preferred file path and name

    # process the image (if needed)
    result = resposta('image.jpg')  # replace 'image.jpg' with your preferred file path and name

    # check if the result is a string
    if not isinstance(result, str):
        raise ValueError("The result is not a string.")

    # send a response message
    await update.message.reply_text(result)


def main():
    app = ApplicationBuilder().token(telegram_bot_api_token).build()

    # Register the handlers
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.PHOTO, image_handler))

    app.run_polling()


if __name__ == "__main__":
    main()
