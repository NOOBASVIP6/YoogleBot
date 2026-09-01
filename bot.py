import os
import time
import requests
import json
import asyncio
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from googlesearch import search
import trafilatura
import google.generativeai as genai

# --- НАСТРОЙКИ ---
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

genai.configure(api_key=GEMINI_API_KEY)

bot = Bot(token=TELEGRAM_BOT_TOKEN)
dp = Dispatcher()

def search_web(query: str) -> str:
    print(f"\n🔎 [Поиск в Google]: {query}")
    results = []
    try:
        safe_query = query.encode("ascii", "ignore").decode("ascii")
        if not safe_query.strip():
            safe_query = "AI benchmark coding"
            
        search_results = search(safe_query, num_results=3, advanced=True, lang="ru", sleep_interval=2)
        for r in search_results:
            results.append(f"Title: {r.title}\nURL: {r.url}\nSnippet: {r.description}\n")
            
        time.sleep(1)
        return "\n---\n".join(results) if results else "Ничего не найдено."
    except Exception as e:
        return f"Ошибка поиска: {str(e)}"

def read_website(url: str) -> str:
    print(f"\n🌐 [Чтение сайта]: {url}")
    try:
        downloaded = trafilatura.fetch_url(url)
        if not downloaded:
            return "Не удалось загрузить страницу."
        text = trafilatura.extract(downloaded)
        return text[:2500] if text else "Текст не извлечен."
    except Exception as e:
        return f"Ошибка чтения: {str(e)}"

# Инициализация модели через официальную библиотеку
model = genai.GenerativeModel(
   model_name="gemini-1.5-flash-latest",
    tools=[search_web, read_website],
    system_instruction="Ты — автономный исследовательский ИИ-агент. Используй поиск и чтение сайтов, чтобы отвечать на вопросы."
)

def run_agent_logic(task: str) -> str:
    try:
        chat = model.start_chat(enable_automatic_function_calling=True)
        response = chat.send_message(task)
        return response.text
    except Exception as e:
        return f"Ошибка выполнения агента: {str(e)}"

@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    await message.answer("Привет! Я твой автономный ИИ-агент с доступом к интернету. Напиши мне любую задачу или вопрос.")

@dp.message()
async def handle_message(message: types.Message):
    user_task = message.text
    processing_msg = await message.answer("🔎 Думаю, ищу информацию в сети...")
    
    loop = asyncio.get_running_loop()
    try:
        result = await loop.run_in_executor(None, run_agent_logic, user_task)
        await bot.delete_message(chat_id=message.chat.id, message_id=processing_msg.message_id)
        
        if len(result) > 4000:
            for x in range(0, len(result), 4000):
                await message.answer(result[x:x+4000])
        else:
            await message.answer(result)
            
    except Exception as e:
        await bot.delete_message(chat_id=message.chat.id, message_id=processing_msg.message_id)
        await message.answer(f"Произошла ошибка при выполнении задачи: {str(e)}")

async def main():
    print("🤖 Telegram-бот запущен и ожидает сообщения...")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
