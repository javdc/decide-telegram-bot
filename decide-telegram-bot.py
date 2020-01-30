import logging
import os
import json
import requests
import random

from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Updater, CommandHandler, ConversationHandler, MessageHandler, Filters, CallbackQueryHandler
from telegram.parsemode import ParseMode


logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
                    level=logging.INFO)

logger = logging.getLogger(__name__)

MENU, POLL_LIST, ENTER_URL, ASK_USERNAME, ASK_PASSWORD, SHOW_OPTIONS, VOTE, HELP, ABOUT = range(9)

PORT = int(os.environ.get("PORT", "8443"))

TOKEN = os.environ.get("TG_TOKEN")

APP_URL = os.environ.get("TG_HEROKU_APP_URL", "https://decide-telegram-bot.herokuapp.com/")

GATEWAY_URL = os.environ.get("TG_GATEWAY_URL")

KEYBITS = int(os.environ.get("TG_KEYBITS", "256"))


# Thanks to https://github.com/RyanRiddle/elgamal ===========
class PublicKey(object):
    def __init__(self, p=None, g=None, h=None, iNumBits=KEYBITS):
        self.p = p
        self.g = g
        self.h = h
        self.iNumBits = iNumBits

def modexp( base, exp, modulus ):
        return pow(base, exp, modulus)

def encode(sPlaintext, iNumBits):
        byte_array = bytearray(sPlaintext, 'utf-16')
        
        z = []
        
        k = iNumBits//8
        j = -1 * k
        for i in range( len(byte_array) ):
                if i % k == 0:
                        j += k
                        z.append(0)
                z[j//k] += byte_array[i]*(2**(8*(i%k)))
        
        return z

def encrypt(key, sPlaintext):
        z = encode(sPlaintext, key.iNumBits)
        cipher_pairs = []
        for i in z:
                y = random.randint( 0, key.p )
                c = modexp( key.g, y, key.p )
                d = (i*modexp( key.h, y, key.p)) % key.p
                cipher_pairs.append( [c, d] )

        encryptedStr = ""
        for pair in cipher_pairs:
                encryptedStr += str(pair[0]) + ' ' + str(pair[1]) + ' '
    
        return encryptedStr
# ==============================================================================

def search_voting_by_id(votings, voting_id):
    for voting in votings:
        if voting.get("id") == voting_id:
            return voting


def dont_understand(update, context):
    context.bot.send_message(chat_id=update.effective_chat.id, text=f"¡Lo siento! No entiendo qué significa {update.message.text}")


def start(update, context):
    user = update.message.from_user
    context.bot.send_message(chat_id=update.effective_chat.id, text="¡Bienvenido " + user.first_name + "! Mediante este bot podrás participar fácilmente en las distintas votaciones de la plataforma Decide")
    menu(update, context)
    return MENU


def menu(update, context):
    keyboard = [[InlineKeyboardButton("🗳️ Votaciones activas", callback_data=str(POLL_LIST))],
                [InlineKeyboardButton("🔗 Introducir URL de votación", callback_data=str(ENTER_URL))],
                [InlineKeyboardButton("❓ Ayuda", url="https://github.com/javdc/decide-telegram-bot/blob/master/README.md"),
                 InlineKeyboardButton("ℹ️ Acerca del bot", url="https://github.com/javdc/decide-telegram-bot/blob/master/README.md")]]
    context.bot.send_message(chat_id=update.effective_chat.id, text="🔸 *Menú principal* 🔸", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode=ParseMode.MARKDOWN)
    return MENU


def poll_list(update, context):
    query = update.callback_query
    bot = context.bot
    
    votings = json.loads(requests.get(GATEWAY_URL + "voting/?format=json").text)
    
    keyboard = [[InlineKeyboardButton(voting.get("name"), callback_data=voting.get("id"))] for voting in votings if voting.get("pub_key") != None and voting.get("end_date") == None]
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    bot.edit_message_text(
        chat_id=query.message.chat_id,
        message_id=query.message.message_id,
        text="Selecciona una votación",
        reply_markup=reply_markup
    )
    
    context.user_data["votings"] = votings
    
    return POLL_LIST


def save_voting_id_by_btn_and_ask_username(update, context):
    query_data = update.callback_query.data
    context.user_data["voting_id"] = query_data
    ask_username(update, context)
    return ASK_USERNAME


def enter_url(update, context):
    query = update.callback_query
    query.edit_message_text(text="🔗 Envíame la URL de una votación")
    return ENTER_URL


def save_voting_id_by_url_and_ask_username(update, context):
    context.user_data["voting_id"] = update.message.text.rstrip('/').split("/")[-1]
    ask_username(update, context)
    return ASK_USERNAME


def ask_username(update, context):
    context.bot.send_message(chat_id=update.effective_chat.id, text="Necesitas iniciar sesión para poder votar.")
    context.bot.send_message(chat_id=update.effective_chat.id, text="Introduce tu usuario")
    return ASK_USERNAME


def ask_password(update, context):
    context.user_data["user"] = update.message.text
    context.bot.send_message(chat_id=update.effective_chat.id, text="Ahora introduce tu contraseña")
    return ASK_PASSWORD


def show_options(update, context):
    context.user_data["pass"] = update.message.text
    
    login_json = requests.post(GATEWAY_URL + "authentication/login/", data={"username": context.user_data['user'], "password": context.user_data['pass']}).json()
    token = login_json.get("token")
    
    if token == None:
        context.bot.send_message(chat_id=update.effective_chat.id, text="Error al iniciar sesión. Inténtalo de nuevo más tarde.")
        menu(update, context)
        return MENU
    else:
        context.bot.send_message(chat_id=update.effective_chat.id, text="Sesión iniciada correctamente.")
    
    context.user_data["token"] = token
    
    getuser_json = requests.post(GATEWAY_URL + "authentication/getuser/", data={"token": token}).json()
    
    context.user_data["user_id"] = getuser_json.get("id")
    
    voting = search_voting_by_id(context.user_data["votings"], int(context.user_data["voting_id"]))
    
    if voting.get("pub_key") == None:
        context.bot.send_message(chat_id=update.effective_chat.id, text="Esta votación está cerrada.")
        menu(update, context)
        return MENU
    
    for party in voting.get("parties"):
        party_string = ""
        party_string += f"*{party.get('name')}*\nCandidatos a la presidencia:\n"
        for candidate in party.get("president_candidates"):
            party_string += f"{candidate.get('number')}. {candidate.get('president_candidate')}\n"
        party_string += f"\nCandidatos al congreso:\n"
        for candidate in party.get("congress_candidates"):
            party_string += f"{candidate.get('number')}. {candidate.get('congress_candidate')}\n"
        context.bot.send_message(chat_id=update.effective_chat.id, text=party_string, parse_mode=ParseMode.MARKDOWN)
    
    context.bot.send_message(chat_id=update.effective_chat.id, text="Envía los números de los candidatos separados por comas")

    context.user_data["pub_key"] = voting.get("pub_key")
    
    return SHOW_OPTIONS


def vote(update, context):
    selected_options = update.message.text.split(", ")
    
    key = PublicKey(context.user_data["pub_key"].get("p"), context.user_data["pub_key"].get("g"), context.user_data["pub_key"].get("y"))
    
    vote_options = [encrypt(key, option).split() for option in selected_options]

    votes = [{"a":option[0], "b":option[1]} for option in vote_options]
    
    data_json = json.dumps({"votes":votes,
                            "voting":context.user_data["voting_id"],
                            "voter":context.user_data["user_id"],
                            "token":context.user_data["token"]})
        
    vote_response = requests.post(GATEWAY_URL + "store/", data=data_json, headers={"Authorization":f"Token {context.user_data['token']}", "content-type": "application/json"})
    
    if vote_response.status_code == 200:
        context.bot.send_message(chat_id=update.effective_chat.id, text="¡Tu voto se ha enviado satisfactoriamente!")
    else:
        context.bot.send_message(chat_id=update.effective_chat.id, text=f"Error {vote_response.status_code} al enviar el voto. Inténtalo de nuevo más tarde.")
    
    menu(update, context)
    return MENU


def main():
    updater = Updater(token=TOKEN, use_context=True)
    dispatcher = updater.dispatcher
    
    conv_handler = ConversationHandler(
        entry_points = [CommandHandler('menu', menu),
                        CommandHandler('start', start)],
         
        states = {
            MENU: [CallbackQueryHandler(poll_list, pattern=f"^{str(POLL_LIST)}$"),
                   CallbackQueryHandler(enter_url, pattern=f"^{str(ENTER_URL)}$")],
            POLL_LIST: [CallbackQueryHandler(save_voting_id_by_btn_and_ask_username, pattern="^\d+$")],
            ENTER_URL: [MessageHandler(Filters.regex(r'^(http[s]?:\/\/)?[A-Za-z0-9\-]+([.][A-Za-z0-9\-]+)*([:][\d]+)?\/booth\/\d+[/]?$'), save_voting_id_by_url_and_ask_username)],
            ASK_USERNAME: [MessageHandler(Filters.text, ask_password)],
            ASK_PASSWORD: [MessageHandler(Filters.text, show_options)],
            SHOW_OPTIONS: [MessageHandler(Filters.regex(r'^\d+(, \d+)*$'), vote)]
        },
        
        fallbacks = [CommandHandler('menu', menu),
                     CommandHandler('start', start),
                     MessageHandler(Filters.text, dont_understand)]
    )
    
    dispatcher.add_handler(conv_handler)
    
    updater.start_webhook(listen="0.0.0.0", port=PORT, url_path=TOKEN)

    updater.bot.set_webhook(APP_URL + TOKEN)
    
    updater.idle()

    
if __name__ == '__main__':
    main()
