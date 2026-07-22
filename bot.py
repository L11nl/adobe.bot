import asyncio
import os
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.types import Message, FSInputFile
from playwright.async_api import async_playwright

# سحب التوكن من إعدادات Railway
BOT_TOKEN = os.getenv("BOT_TOKEN")

if not BOT_TOKEN:
    raise ValueError("⚠️ التوكن غير موجود! تأكد من إضافته في إعدادات Variables في Railway.")

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

# رابط أدوبي
ADOBE_URL = "https://commerce.adobe.com/store/checkout?items%5B0%5D%5Bid%5D=D0440AB0F2F7F2F2CB39657F45BC5D56&items%5B0%5D%5Bq%5D=1&cli=creative&co=US&lang=en"

async def automate_adobe_checkout(chat_id, data: dict):
    await bot.send_message(chat_id, "⏳ جاري فتح المتصفح على الخادم السحابي...")
    
    async with async_playwright() as p:
        # سحب بيانات البروكسي من متغيرات Railway
        proxy_server = os.getenv("PROXY_SERVER")
        proxy_username = os.getenv("PROXY_USERNAME")
        proxy_password = os.getenv("PROXY_PASSWORD")
        
        proxy_settings = None
        if proxy_server:
            proxy_settings = {
                "server": proxy_server
            }
            if proxy_username and proxy_password:
                proxy_settings["username"] = proxy_username
                proxy_settings["password"] = proxy_password

        # تشغيل المتصفح مع تعطيل الحماية المعزولة ليتوافق مع Railway
        browser = await p.chromium.launch(
            headless=True,
            args=['--no-sandbox', '--disable-setuid-sandbox', '--disable-dev-shm-usage']
        )
        
        # إعداد بيئة المتصفح وربط البروكسي (إن وجد)
        context = await browser.new_context(
            viewport={'width': 1440, 'height': 900},
            proxy=proxy_settings
        )
        page = await context.new_page()
        
        screenshot_path = f"result_{chat_id}.png"
        
        try:
            await bot.send_message(chat_id, "🌐 جاري الاتصال ببوابة أدوبي...")
            await page.goto(ADOBE_URL, wait_until="networkidle")

            # الخطوة 1: الإيميل
            await bot.send_message(chat_id, f"⌨️ إدخال الإيميل: {data['email']}")
            await page.locator('input[type="email"]').type(data['email'], delay=100)
            await page.locator('button:has-text("Continue")').click()
            await page.wait_for_timeout(2000)

            # الخطوة 2: الدفع
            await bot.send_message(chat_id, "💳 إدخال بيانات الدفع...")
            await page.locator('input[name="cardNumber"]').type(data['card'], delay=100)
            await page.locator('input[name="expirationDate"]').type(data['expiry'], delay=100)

            # الخطوة 3: البيانات الشخصية
            await bot.send_message(chat_id, "👤 إدخال الاسم والرمز البريدي...")
            await page.locator('input[name="firstName"]').type(data['fname'], delay=100)
            await page.locator('input[name="lastName"]').type(data['lname'], delay=100)
            await page.locator('input[name="zip"]').type(data['zip'], delay=100)

            # التمرير (Scrolling) لكي يبدو كبشر
            await page.mouse.wheel(0, 500)
            await page.wait_for_timeout(500)
            
            # الخطوة 4: الاشتراك
            await bot.send_message(chat_id, "✅ جاري تأكيد الاشتراك...")
            await page.locator('button:has-text("Agree and subscribe")').click()
            
            # انتظار 5 ثواني لمعرفة النتيجة
            await page.wait_for_timeout(5000)
            
            # أخذ لقطة شاشة للنتيجة وإرسالها
            await page.screenshot(path=screenshot_path)
            photo = FSInputFile(screenshot_path)
            await bot.send_photo(chat_id, photo, caption="🎉 انتهت العملية. هذه لقطة للشاشة الحالية:")
            
        except Exception as e:
            await bot.send_message(chat_id, f"❌ حدث خطأ أثناء التنفيذ: {str(e)}")
            
        finally:
            await browser.close()
            # تنظيف ملف الصورة من الخادم بعد الإرسال
            if os.path.exists(screenshot_path):
                os.remove(screenshot_path)

@dp.message(Command("start"))
async def send_welcome(message: Message):
    await message.reply(
        "مرحباً بك.\n"
        "أرسل لي البيانات بهذا التنسيق لملء النموذج تلقائياً:\n\n"
        "`الايميل|رقم_البطاقة|تاريخ_الانتهاء|الاسم|اللقب|الرمز_البريدي`",
        parse_mode="Markdown"
    )

@dp.message()
async def process_data(message: Message):
    parts = message.text.split('|')
    if len(parts) != 6:
        await message.reply("⚠️ التنسيق خاطئ. الرجاء التأكد من إرسال 6 قيم تفصل بينها علامة |")
        return
        
    user_data = {
        'email': parts[0].strip(),
        'card': parts[1].strip(),
        'expiry': parts[2].strip(),
        'fname': parts[3].strip(),
        'lname': parts[4].strip(),
        'zip': parts[5].strip()
    }
    
    # تشغيل المهمة في الخلفية حتى يستمر البوت في استقبال رسائل أخرى
    asyncio.create_task(automate_adobe_checkout(message.chat.id, user_data))

async def main():
    print("Bot is starting...")
    await dp.start_polling(bot)

if __name__ == '__main__':
    asyncio.run(main())
