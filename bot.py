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
task_queue = asyncio.Queue()
proxy_list = []
proxy_enabled = True

# حالات البوت (FSM) لاستقبال بيانات تسجيل الدخول أو البروكسيات
class BotStates(StatesGroup):
    waiting_for_proxies = State()
    waiting_for_login_credentials = State()

CAPCUT_LOGIN_URL = "https://www.capcut.com/login?redirect_url=https%3A%2F%2Fwww.capcut.com%2Fmy-edit"

def generate_random_capcut_data():
    first_names = ["James", "John", "Robert", "Michael", "William", "David", "Richard", "Joseph", "Thomas", "Charles", "Mark", "Daniel", "Paul", "Steven", "Andrew"]
    last_names = ["Smith", "Johnson", "Williams", "Brown", "Jones", "Garcia", "Miller", "Davis", "Rodriguez", "Martinez", "Taylor", "Moore", "Jackson", "Martin", "Lee"]
    
    fname = random.choice(first_names)
    lname = random.choice(last_names)
    
    random_nums = ''.join(random.choices(string.digits, k=4))
    email = f"{fname.lower()}{lname.lower()}{random_nums}@gmail.com"
    
    # كلمة مرور قوية تتوافق مع متطلبات كاب كات
    password = "00CHAT" + ''.join(random.choices(string.ascii_letters + string.digits, k=6)) + "00"
    
    return email, password

async def automate_capcut_action(chat_id, action_type, data: dict):
    """
    action_type: 'signup' أو 'login'
    data: يحتوي على {'email': ..., 'password': ...}
    """
    is_signup = action_type == 'signup'
    email = data['email']
    password = data['password']
    
    title_msg = "🚀 جاري إنشاء حساب جديد في CapCut..." if is_signup else "🔐 جاري تسجيل الدخول إلى CapCut..."
    await bot.send_message(
        chat_id, 
        f"{title_msg}\n"
        f"📧 الإيميل: `{email}`",
        parse_mode="Markdown"
    )
    
    async with async_playwright() as p:
        proxy_settings = None
        selected_proxy = None
        
        if proxy_enabled and proxy_list:
            selected_proxy = random.choice(proxy_list)
            try:
                credentials, server_address = selected_proxy.split('@')
                p_user, p_pass = credentials.split(':')
                proxy_settings = {
                    "server": f"http://{server_address}",
                    "username": p_user,
                    "password": p_pass
                }
            except Exception as e:
                print(f"Error parsing proxy {selected_proxy}: {e}")

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
        
        screenshot_path = f"capcut_result_{chat_id}.png"
        error_img = f"capcut_error_{chat_id}.png"
        
        try:
            await page.goto(CAPCUT_LOGIN_URL, wait_until="domcontentloaded", timeout=60000)
            
            # الخطوة 1: النقر على "Continue with email" بناءً على التقرير الدقيق
            await page.wait_for_timeout(3000)
            
            # البحث عن زر البريد الإلكتروني والنقر عليه
            email_btn = page.locator('text="Continue with email"')
            if await email_btn.count() > 0:
                await email_btn.first.click()
            else:
                # محاولة بديلة بالنقر عبر الإحداثيات الموثوقة أو محددات أخرى
                await page.locator('button, div').filter(has_text=re.compile("email", re.IGNORECASE)).first.click()
                
            await page.wait_for_timeout(2000)

            # الخطوة 2: إدخال الإيميل
            # بناءً على خطوات التقرير، حقل الإيميل يظهر بعد النقر
            email_input = page.locator('input[type="text"], input[type="email"]')
            await email_input.wait_for(state="visible", timeout=10000)
            await email_input.first.fill("")
            await email_input.first.type(email, delay=random.randint(50, 150))
            
            await page.wait_for_timeout(1000)

            # الخطوة 3: النقر على زر Continue
            continue_btn = page.locator('button:has-text("Continue")')
            if await continue_btn.count() > 0:
                await continue_btn.first.click()
            
            await page.wait_for_timeout(3000)

            # الخطوة 4: إدخال كلمة المرور
            password_input = page.locator('input[type="password"]')
            await password_input.wait_for(state="visible", timeout=10000)
            await password_input.first.fill("")
            await password_input.first.type(password, delay=random.randint(50, 150))

            await page.wait_for_timeout(1000)

            # الخطوة 5: النقر على زر Sign in / Register
            sign_in_btn = page.locator('button:has-text("Sign in"), button:has-text("Sign up"), button:has-text("Register")')
            if await sign_in_btn.count() > 0:
                await sign_in_btn.first.click()
            else:
                # ضغط زر الإرسال الافتراضي
                await page.keyboard.press("Enter")

            # انتظار حتى يتم تسجيل الدخول وتحول الرابط إلى لوحة التحكم my-edit
            await bot.send_message(chat_id, "🔄 جاري التحقق وإنهاء الجلسة...")
            
            try:
                await page.wait_for_url("**/my-edit**", timeout=25000)
            except:
                # إذا لم يتغير الرابط بالكامل، ننتظر قليلاً لنلتقط الشاشة ونرى النتيجة
                await page.wait_for_timeout(8000)

            page_url = page.url
            page_text = await page.evaluate("document.body.innerText")

            if "my-edit" in page_url or "invite members" in page_text.lower() or "upgrade space" in page_text.lower():
                status_result = f"✅ **تم بنجاح!** تم {'إنشاء الحساب' if is_signup else 'تسجيل الدخول'} والدخول إلى لوحة التحكم.\n🔑 كلمة المرور المستخدمة: `{password}`"
            else:
                status_result = "⚠️ **انتبه:** قد تتطلب العملية تأكيد رمز تحقق (OTP) أو كابتشا يدوية. يرجى مراجعة الصورة أدناه."

            await page.screenshot(path=screenshot_path)
            photo = FSInputFile(screenshot_path)
            
            await bot.send_photo(
                chat_id, 
                photo, 
                caption=f"🎉 النتيجة النهائية لـ CapCut:\n\n{status_result}",
                parse_mode="Markdown"
            )
            
        except Exception as e:
            error_msg = str(e).split('\n')[0] 
            
            if "ERR_TUNNEL_CONNECTION_FAILED" in error_msg or "ERR_PROXY_CONNECTION_FAILED" in error_msg:
                custom_error = f"❌ **فشل الاتصال:** البروكسي المستخدم ميت أو لا يعمل."
            else:
                custom_error = f"❌ **فشل تقني:** حدث استثناء أثناء التنفيذ (`{error_msg}`)"

            try:
                await page.screenshot(path=error_img)
                photo = FSInputFile(error_img)
                await bot.send_photo(
                    chat_id, 
                    photo, 
                    caption=f"🎉 النتيجة النهائية لـ CapCut:\n\n{custom_error}",
                    parse_mode="Markdown"
                )
            except:
                await bot.send_message(
                    chat_id, 
                    f"🎉 النتيجة النهائية لـ CapCut:\n\n{custom_error}",
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
        chat_id, action_type, data = await task_queue.get()
        try:
            await automate_capcut_action(chat_id, action_type, data)
        except Exception as e:
            print(f"Error processing task: {e}")
        finally:
            task_queue.task_done()
            await asyncio.sleep(3)

@dp.message(Command("start"))
async def send_welcome(message: Message):
    # لوحة تحكم أزرار تفاعلية متقدمة جداً
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="👤 إنشاء حساب CapCut عشوائي", callback_data="capcut_signup")],
        [InlineKeyboardButton(text="🔐 تسجيل دخول (إيميل مخصص)", callback_data="capcut_login")],
        [InlineKeyboardButton(text="➕ اضافة بروكسيات", callback_data="add_proxies"),
         InlineKeyboardButton(text="🛑 إيقاف البروكسيات", callback_data="stop_proxies")]
    ])
    
    status_text = "🟢 **البروكسيات:** مفعلة" if proxy_enabled and proxy_list else "🔴 **البروكسيات:** متوقفة (اتصال محلي)"
    
    await message.reply(
        f"مرحباً بك في بوت أتمتة **CapCut** الذكي.\n"
        f"{status_text}\n\n"
        "اختر أحد الأوامر أدناه من الأزرار التفاعلية:",
        parse_mode="Markdown",
        reply_markup=kb
    )

# تفاعل زر إنشاء حساب عشوائي
@dp.callback_query(F.data == "capcut_signup")
async def capcut_signup_callback(callback: types.CallbackQuery):
    email, password = generate_random_capcut_data()
    data = {'email': email, 'password': password}
    
    await task_queue.put((callback.message.chat.id, 'signup', data))
    await callback.message.answer("✅ تمت إضافة مهمة **إنشاء حساب كاب كات** إلى الطابور بنجاح!", parse_mode="Markdown")
    await callback.answer()

# تفاعل زر تسجيل الدخول
@dp.callback_query(F.data == "capcut_login")
async def capcut_login_callback(callback: types.CallbackQuery, state: FSMContext):
    await callback.message.answer(
        "أرسل بيانات تسجيل الدخول بهذا التنسيق (في سطر واحد):\n\n"
        "`email@gmail.com|password`",
        parse_mode="Markdown"
    )
    await state.set_state(BotStates.waiting_for_login_credentials)
    await callback.answer()

# استقبال بيانات تسجيل الدخول المخصصة
@dp.message(BotStates.waiting_for_login_credentials)
async def receive_login_credentials(message: Message, state: FSMContext):
    text = message.text.strip()
    parts = text.split('|')
    
    if len(parts) != 2:
        await message.reply("⚠️ التنسيق خاطئ. الرجاء الإرسال بهذا الشكل: `email@gmail.com|password`", parse_mode="Markdown")
        return
        
    email = parts[0].strip()
    password = parts[1].strip()
    
    data = {'email': email, 'password': password}
    await task_queue.put((message.chat.id, 'login', data))
    
    await message.reply("✅ تم استلام بيانات تسجيل الدخول وإضافتها للطابور بنجاح!", parse_mode="Markdown")
    await state.clear()

@dp.callback_query(F.data == "add_proxies")
async def add_proxies_callback(callback: types.CallbackQuery, state: FSMContext):
    global proxy_enabled
    proxy_enabled = True
    await callback.message.answer(
        "أرسل البروكسيات الآن.\n"
        "التنسيق المطلوب:\n"
        "`username:password@ip:port`", 
        parse_mode="Markdown"
    )
    await state.set_state(BotStates.waiting_for_proxies)
    await callback.answer()

@dp.callback_query(F.data == "stop_proxies")
async def stop_proxies_callback(callback: types.CallbackQuery, state: FSMContext):
    global proxy_enabled
    proxy_enabled = False
    await callback.message.answer("🛑 **تم إيقاف البروكسيات بنجاح.**\nسيعمل البوت محلياً.", parse_mode="Markdown")
    await callback.answer()

@dp.message(BotStates.waiting_for_proxies)
async def receive_proxies(message: Message, state: FSMContext):
    text = message.text.strip()
    raw_proxies = re.split(r'\s+', text)
    
    added_count = 0
    for rp in raw_proxies:
        if '@' in rp and ':' in rp:
            proxy_list.append(rp)
            added_count += 1
            
    if added_count > 0:
        await message.reply(f"✅ تم إضافة **{added_count}** بروكسيات بنجاح وتم تفعيلها!\nإجمالي البروكسيات: **{len(proxy_list)}**", parse_mode="Markdown")
    else:
        await message.reply("⚠️ لم يتم العثور على بروكسيات بالتنسيق الصحيح.")
        
    await state.clear()

async def main():
    print("CapCut Bot is starting...")
    asyncio.create_task(queue_worker())
    await dp.start_polling(bot)

if __name__ == '__main__':
    asyncio.run(main())
