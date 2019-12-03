import logging

from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Updater, CommandHandler, ConversationHandler, MessageHandler, Filters, CallbackQueryHandler
from telegram.parsemode import ParseMode
import os

# Enable logging
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
                    level=logging.INFO)

logger = logging.getLogger(__name__)


MAIN_MENU, POLL_LIST, HELP, ABOUT = range(4)


def start(update, context):
    user = update.message.from_user
    context.bot.send_message(chat_id=update.effective_chat.id, text="¡Bienvenido " + user.first_name + "! Mediante este bot podrás participar fácilmente en las distintas votaciones de la plataforma Decide")
    menu(update, context)


def echo(update, context):
    context.bot.send_message(chat_id=update.effective_chat.id, text="¡Lo siento! No entiendo qué significa \"" + update.message.text + "\"")


def menu(update, context):
    keyboard = [[InlineKeyboardButton("🗳️ Votaciones activas", callback_data='1'),
                 InlineKeyboardButton("☑️ Mis votaciones", callback_data='2')],
                [InlineKeyboardButton("❓ Ayuda", callback_data='3'),
                 InlineKeyboardButton("ℹ️ Acerca del bot", callback_data='4')]]

    update.message.reply_text("🔸 *Menú principal* 🔸", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode=ParseMode.MARKDOWN)


def button(update, context):
    query = update.callback_query

    query.edit_message_text(text="Opción seleccionada: {}".format(query.data))


def main():
    updater = Updater(token=os.environ["TG_TOKEN"], use_context=True)
    dispatcher = updater.dispatcher
    
#     conv_handler = ConversationHandler(
#         entry_points = [CommandHandler('start', start)],
#         
#         states = {
#             POLL_LIST: []
#         },
#         
#         fallbacks = [CommandHandler("menu", menu)]
#     )
    
    dispatcher.add_handler(CommandHandler('start', start))
    dispatcher.add_handler(MessageHandler(Filters.text, echo))
    dispatcher.add_handler(CommandHandler('menu', menu))
    dispatcher.add_handler(CallbackQueryHandler(button))
    
    updater.start_polling()

    
if __name__ == '__main__':
    main()
