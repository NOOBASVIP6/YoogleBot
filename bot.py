import os
import time
import requests
import json
import asyncio
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from googlesearch import search
import trafilatura

# --- НАСТРОЙКИ ИЗ ПЕРЕМЕННЫХ ОКРУЖЕНИЯ ---
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
# -----------------

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

tools_map = {
    "search_web": search_web,
    "read_website": read_website
}

tools_declaration = [
    {
        "function_declarations": [
            {
                "name": "search_web",
                "description": "Search the web for information.",
                "parameters": {
                    "type": "OBJECT",
                    "properties": {
                        "query": {"type": "STRING", "description": "Search query"}
                    },
                    "required": ["query"]
                }
            },
            {
                "name": "read_website",
                "description": "Read text content from a website URL.",
                "parameters": {
                    "type": "OBJECT",
                    "properties": {
                        "url": {"type": "STRING", "description": "Website URL"}
                    },
                    "required": ["url"]
                }
            }
        ]
    }
]

def call_gemini(contents):
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={GEMINI_API_KEY}"
    headers = {"Content-Type": "application/json"}
    
    payload = {
        "contents": contents,
        "tools": tools_declaration,
        "system_instruction": {
            "parts": [{"text": "Ты — автономный исследовательский ИИ-агент. Используй поиск и чтение сайтов, чтобы отвечать на вопросы."}]
        }
    }
    
    response = requests.post(url, headers=headers, data=json.dumps(payload))
    if response.status_code != 200:
        raise Exception(f"API Error {response.status_code}: {response.text}")
    return response.json()

def run_agent_logic(task: str) -> str:
    contents = [{"role": "user", "parts": [{"text": task}]}]
    
    for step in range(4):
        res_json = call_gemini(contents)
        candidate = res_json.get("candidates", [{}])[0]
        content = candidate.get("content", {})
        parts = content.get("parts", [])
        
        function_call = None
        for p in parts:
            if "functionCall" in p:
                function_call = p["functionCall"]
                break
                
        if function_call:
            fn_name = function_call["name"]
            fn_args = function_call["args"]
            
            contents.append(content)
            
            if fn_name in tools_map:
                tool_result = tools_map[fn_name](**fn_args)
            else:
                tool_result = "Инструмент не найден"
                
            contents.append({
                "role": "function",
                "parts": [{
                    "functionResponse": {
                        "name": fn_name,
                        "response": {"result": tool_result}
                    }
                }]
            })
        else:
            final_text = "".join([p.get("text", "") for p in parts])
            return final_text
    return "Превышен лимит шагов агента."

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
