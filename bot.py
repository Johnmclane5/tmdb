import logging
import flask
import requests
import telegram
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Updater, CommandHandler, CallbackQueryHandler
import os
from dotenv import load_dotenv
import signal
from keep_alive import keep_alive

# Load environment variables from .env file
load_dotenv()

# Get the bot token and TMDB API key from environment variables
bot_token = os.environ.get("BOT_TOKEN")
tmdb_api_key = os.environ.get("TMDB_API_KEY")

# Enable logging
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)

keep_alive()

# Define the function to handle the /start command
def start(update, context):
    # Send a welcome message to the user
    update.message.reply_text('Welcome to the movie and TV show search bot!')



# Define the Telegram bot command handlers
def search_movie_entry(update, context):
    try:
        query = context.args
        if query:
            search_query = ' '.join(query)
            # Make the API request for movies
            movie_results = search_movies(search_query)

            if movie_results:
                buttons = []
                for result in movie_results[:10]:  # Only consider the top 10 results
                    title = result["title"]
                    overview = result["overview"]
                    vote_average = result["vote_average"]
                    release_date = result.get("release_date", "")
                    entry_id = result["id"]
                    callback_data = f"entry_id={entry_id}&type=movie"
                    button = InlineKeyboardButton(text=title, callback_data=callback_data)
                    buttons.append([button])

                # Create the inline keyboard markup
                reply_markup = InlineKeyboardMarkup(buttons)

                # Send the inline keyboard to the Telegram bot
                chat_id = update.effective_chat.id
                bot = context.bot
                bot.send_message(chat_id=chat_id, text="Please select a movie:", reply_markup=reply_markup)
            else:
                update.message.reply_text('No movie results found.')
        else:
            update.message.reply_text('Please provide a movie search query.')
    except Exception as e:
        logging.error(f"Error in search_movie_entry: {e}")
        update.message.reply_text('An error occurred while processing your request. Please try again later.')

def search_tv_entry(update, context):
    try:
        query = context.args
        if query:
            search_query = ' '.join(query)
            # Make the API request for TV shows
            tv_results = search_tv(search_query)

            if tv_results:
                buttons = []
                for result in tv_results[:10]:  # Only consider the top 10 results
                    title = result["name"]
                    overview = result["overview"]
                    vote_average = result["vote_average"]
                    release_date = result.get("first_air_date", "")
                    entry_id = result["id"]
                    callback_data = f"entry_id={entry_id}&type=tv"
                    button = InlineKeyboardButton(text=title, callback_data=callback_data)
                    buttons.append([button])

                # Create the inline keyboard markup
                reply_markup = InlineKeyboardMarkup(buttons)

                # Send the inline keyboard to the Telegram bot
                chat_id = update.effective_chat.id
                bot = context.bot
                bot.send_message(chat_id=chat_id, text="Please select a TV show:", reply_markup=reply_markup)
            else:
                update.message.reply_text('No TV show results found.')
        else:
            update.message.reply_text('Please provide a TV show search query.')
    except Exception as e:
        logging.error(f"Error in search_tv_entry: {e}")
        update.message.reply_text('An error occurred while processing your request. Please try again later.')

# Define the callback handler for inline button presses
def button_callback(update, context):
    try:
        query = update.callback_query
        query_data = query.data.split("&")
        entry_id = query_data[0].split("=")[1]
        if len(query_data) > 1:  # Check if page number is present in callback data
            entry_type = query_data[1].split("=")[1]
        else:
            entry_type = None

        if entry_type:
            # Retrieve entry details using the entry ID and type (movie or tv)
            if entry_type == "movie":
                entry = get_movie_details(entry_id)
            else:
                entry = get_tv_details(entry_id)

            if entry:
                title = entry["title"] if "title" in entry else entry["name"]
                overview = entry["overview"]
                poster_path = entry["poster_path"]
                vote_average = entry["vote_average"]
                release_date = entry.get("release_date", "")
                genre_ids = entry.get("genre_ids", [])

                # Get the genre names
                genres = get_genre_names(genre_ids)

                # Prepare the entry details message
                message = f"<i><b>🏷️Title:{title}</b></i>\n"
                message += f"<i><b>📝Overview:</b>\n{overview}</i>\n"
                message += f"<i><b>🎬Genre: {', '.join(genres)}</b></i>\n"
                message += f"<i><b>⭐️Rating: {vote_average}</b></i>\n"
                message += f"<i><b>📅Release Date: {release_date}</b></i>"

                # Download the image and send it as a photo along with the title and overview
                photo_url= f"https://image.tmdb.org/t/p/w780/{poster_path}"
                try:
                    response = requests.get(photo_url)
                    response.raise_for_status()  # Raise an exception if there's an error
                    photo_path = f"{entry_id}.jpg"
                    with open(photo_path, 'wb') as photo_file:
                        photo_file.write(response.content)

                    query.answer()
                    query.bot.send_photo(chat_id=query.message.chat_id, photo=open(photo_path, 'rb'), caption=message, parse_mode=telegram.ParseMode.HTML)

                    # Delete the temporary image file
                    os.remove(photo_path)
                except requests.exceptions.RequestException as e:
                    logging.error(f"Error while fetching the image: {e}")
                    query.answer("Error occurred while fetching the image.")
            else:
                query.answer("Entry details not found.")
        else:
            # Handle page navigation logic
            page = int(entry_id)  # The entry ID now represents the page number
            search_query = context.user_data.get("search_query")
            if search_query:
                # Make the API request for movies
                movie_results = search_movies(search_query, page)
                # Make the API request for TV shows
                tv_results = search_tv(search_query, page)

                # Combine the results
                results = movie_results + tv_results

                if results:
                    buttons = []
                    for result in results[:10]:  # Only consider the top 10 results
                        if "title" in result:
                            entry_type = "movie"
                            title = result["title"]
                        else:
                            entry_type = "tv"
                            title = result["name"]
                        overview = result["overview"]
                        vote_average = result["vote_average"]
                        release_date = result.get("release_date", "")
                        entry_id = result["id"]
                        callback_data = f"entry_id={entry_id}&type={entry_type}"
                        button = InlineKeyboardButton(text=title, callback_data=callback_data)
                        buttons.append([button])

                    # Add pagination buttons
                    page_buttons = []
                    if len(results) > 10:
                        next_page = page + 1
                        page_button = InlineKeyboardButton(text=f"Page {next_page}", callback_data=f"entry_id={next_page}")
                        page_buttons.append(page_button)
                    buttons.append(page_buttons)

                    # Create the inline keyboard markup and send to the user
                    reply_markup = InlineKeyboardMarkup(buttons)
                    query.edit_message_text(text="Please select an entry:", reply_markup=reply_markup)
                else:
                    query.answer("No more results.")
            else:
                query.answer("Search query not found.")
    except Exception as e:
        logging.error(f"Error in button_callback: {e}")
        query.answer("An error occurred while processing your request. Please try again later.")

def get_genre_names(genre_ids):
    url = f"https://api.themoviedb.org/3/genre/movie/list"
    params = {
        "api_key": tmdb_api_key
    }
    response = requests.get(url, params=params)
    data = response.json()
    genre_names = []
    for genre in data["genres"]:
        if genre["id"] in genre_ids:
            genre_names.append(genre["name"])
    return genre_names

# Make the API request to search for movies
def search_movies(query):
    url = "https://api.themoviedb.org/3/search/movie"
    params = {
        "query": query,
        "api_key": tmdb_api_key
    }
    response = requests.get(url, params=params)
    data = response.json()
    return data.get("results", [])

# Make the API request to search for TV shows
def search_tv(query):
    url = "https://api.themoviedb.org/3/search/tv"
    params = {
        "query": query,
        "api_key": tmdb_api_key
    }
    response = requests.get(url, params=params)
    data = response.json()
    return data.get("results", [])

# Retrieve movie details using the movie ID
def get_movie_details(movie_id):
    url = f"https://api.themoviedb.org/3/movie/{movie_id}"
    params = {
        "api_key": tmdb_api_key
    }
    response = requests.get(url, params=params)
    data = response.json()
    return data

# Retrieve TV show details using the TV show ID
def get_tv_details(tv_id):
    url = f"https://api.themoviedb.org/3/tv/{tv_id}"
    params = {
        "api_key": tmdb_api_key
    }
    response = requests.get(url, params=params)
    data = response.json()
    return data

# Set up the Telegram bot
updater = Updater(token=bot_token, use_context=True)
dispatcher = updater.dispatcher

# Register the command handlers
dispatcher.add_handler(CommandHandler("start", start))
dispatcher.add_handler(CommandHandler("searchmovie", search_movie_entry))
dispatcher.add_handler(CommandHandler("searchtv", search_tv_entry))
dispatcher.add_handler(CallbackQueryHandler(button_callback))

# Start the bot
updater.start_polling()
updater.idle()
