import asyncio
import os
import random
import string
from aiogram import Bot, Dispatcher
from aiogram.filters import Command
from aiogram.types import Message, FSInputFile
from playwright.async_api import async_playwright

BOT_TOKEN = os.getenv("BOT_TOKEN")

if not BOT_TOKEN:
    raise ValueError("⚠️ التوكن غير موجود! تأكد من إضافته في إعدادات Variables في Railway.")

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

ADOBE_URL = "https://commerce.adobe.com/store/checkout?items%5B0%5D%5Bid%5D=D0440AB0F2F7F2F2CB39657F45BC5D56&items%5B0%5D%5Bq%5D=1&cli=creative&co=US&lang=en"

# دالة لتوليد بيانات أمريكية وإيميلات عشوائية
def generate_random_data():
    first_names = ["James", "John", "Robert", "Michael", "William", "David", "Richard", "Joseph", "Thomas", "Charles", "Mary", "Patricia", "Jennifer", "Linda", "Elizabeth", "Barbara", "Susan", "Jessica", "Sarah", "Karen"]
    last_names = ["Smith", "Johnson", "Williams", "Brown", "Jones", "Garcia", "Miller", "Davis", "Rodriguez", "Martinez", "Hernandez", "Lopez", "Gonzalez", "Wilson", "Anderson", "Thomas", "Taylor", "Moore", "Jackson", "Martin"]
    # رموز بريدية أمريكية صالحة
    zip_codes = ["10001", "90210", "60601", "73301", "33101", "94105", "98101", "02108", "30301", "75201"]
    
    fname = random.choice(first_names)
    lname = random.choice(last_names)
    zip_code = random.choice(zip_codes)
    
    # توليد إيميل عشوائي بناءً على طلبك
    random_chars = ''.join(random.choices(string.ascii_lowercase + string.digits, k=4))
    email = f"nabeel886ADOBEVV44{random_chars}@gmail.com"
    
    return email, fname, lname, zip_code

async def automate_adobe_checkout(chat_id, data: dict):
    await bot.send_message(
        chat_id, 
        f"⏳ بدء الجلسة ببيانات عشوائية:\n"
        f"📧 الإيميل: `{data['email']}`\n"
        f"👤 الاسم: {data['fname']} {data['lname']}\n"
        f"📍 الرمز البريدي: {data['zip']}",
        parse_mode="Markdown"
    )
    
    async with async_playwright() as p:
        proxy_server = os.getenv("PROXY_SERVER")
        proxy_username = os.getenv("PROXY_USERNAME")
        proxy_password = os.getenv("PROXY_PASSWORD")
        
        proxy_settings = None
        if proxy_server:
            proxy_settings = {"server": proxy_server}
            if proxy_username and proxy_password:
                proxy_settings["username"] = proxy_username
                proxy_settings["password"] = proxy_password

        browser = await p.chromium.launch(
            headless=True,
            args=['--no-sandbox', '--disable-setuid-sandbox', '--disable-dev-shm-usage']
        )
        
        context = await browser.new_context(
            viewport={'width': 1440, 'height': 900},
            proxy=proxy_settings
        )
        page = await context.new_page()
        
        screenshot_path = f"result_{chat_id}.png"
        error_img = f"error_{chat_id}.png"
        
        try:
            await bot.send_message(chat_id, "🌐 جاري الاتصال ببوابة أدوبي...")
            await page.goto(ADOBE_URL, wait_until="networkidle")

            # الخطوة 1: الإيميل
            await page.locator('input[type="email"]').type(data['email'], delay=100)
            await page.locator('button:has-text("Continue")').click()
            await page.wait_for_timeout(4000)

            # دالة لاقتحام الإطارات الأمنية (iframes)
            async def type_in_field(placeholder_text, name_attr, value):
                direct_loc = page.locator(f'input[name="{name_attr}"], input[placeholder="{placeholder_text}" i]')
                if await direct_loc.count() > 0:
                    await direct_loc.first.type(value, delay=100)
                    return

                frames_count = await page.locator('iframe').count()
                for i in range(frames_count):
                    frame_loc = page.frame_locator('iframe').nth(i).locator(f'input[name="{name_attr}"], input[placeholder="{placeholder_text}" i]')
                    if await frame_loc.count() > 0:
                        await frame_loc.first.type(value, delay=100)
                        return
                
                raise Exception(f"لم يتم العثور على الحقل: {placeholder_text}")

            # الخطوة 2: بيانات الدفع 
            await bot.send_message(chat_id, "💳 إدخال بيانات البطاقة...")
            await type_in_field("Card number", "cardNumber", data['card'])
            await type_in_field("MM/YY", "expirationDate", data['expiry'])

            # الخطوة 3: البيانات الشخصية
            await bot.send_message(chat_id, "👤 إدخال البيانات الشخصية العشوائية...")
            await type_in_field("First name", "firstName", data['fname'])
            await type_in_field("Last name", "lastName", data['lname'])
            await type_in_field("Zip code", "zip", data['zip'])

            await page.mouse.wheel(0, 500)
            await page.wait_for_timeout(1000)
            
            # الخطوة 4: تأكيد الاشتراك
            await bot.send_message(chat_id, "✅ جاري النقر على زر الاشتراك...")
            await page.locator('button:has-text("Agree and subscribe")').click()
            
            await page.wait_for_timeout(6000)
            
            await page.screenshot(path=screenshot_path)
            photo = FSInputFile(screenshot_path)
            await bot.send_photo(chat_id, photo, caption="🎉 انتهت العملية. هذه لقطة للشاشة الحالية:")
            
        except Exception as e:
            await page.screenshot(path=error_img)
            photo = FSInputFile(error_img)
            error_msg = str(e).split('\n')[0] 
            
            await bot.send_photo(
                chat_id, 
                photo, 
                caption=f"❌ توقف البوت هنا!\n\nتفاصيل الخطأ:\n`{error_msg}`",
                parse_mode="Markdown"
            )
            
        finally:
            await browser.close()
            if os.path.exists(screenshot_path):
                os.remove(screenshot_path)
            if os.path.exists(error_img):
                os.remove(error_img)

@dp.message(Command("start"))
async def send_welcome(message: Message):
    await message.reply(
        "مرحباً بك.\n"
        "أرسل لي فقط بيانات الدفع بهذا التنسيق:\n\n"
        "`رقم_البطاقة|تاريخ_الانتهاء`\n\n"
        "مثال:\n"
        "`4938 7506 7122 3872|0731`",
        parse_mode="Markdown"
    )

@dp.message()
async def process_data(message: Message):
    parts = message.text.split('|')
    if len(parts) != 2:
        await message.reply("⚠️ التنسيق خاطئ. الرجاء إرسال البطاقة والتاريخ فقط، يفصل بينهما علامة |")
        return
        
    card_clean = parts[0].strip().replace(" ", "")
    expiry_clean = parts[1].strip().replace("/", "")
    
    # جلب البيانات العشوائية من الدالة
    rand_email, rand_fname, rand_lname, rand_zip = generate_random_data()
    
    user_data = {
        'email': rand_email,
        'card': card_clean,
        'expiry': expiry_clean,
        'fname': rand_fname,
        'lname': rand_lname,
        'zip': rand_zip
    }
    
    asyncio.create_task(automate_adobe_checkout(message.chat.id, user_data))

async def main():
    print("Bot is starting...")
    await dp.start_polling(bot)

if __name__ == '__main__':
    asyncio.run(main())
