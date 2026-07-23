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

BOT_TOKEN = os.getenv("PROXY_SERVER") # سيبقى على التوكن الصحيح من الـ env
if not os.getenv("BOT_TOKEN"):
    raise ValueError("⚠️ التوكن غير موجود!")

BOT_TOKEN = os.getenv("BOT_TOKEN")
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

proxy_list = []
proxy_enabled = True
active_sessions = {}

class BotStates(StatesGroup):
    waiting_for_email = State()
    waiting_for_login_credentials = State()
    waiting_for_proxies = State()

CAPCUT_LOGIN_URL = "https://www.capcut.com/login?redirect_url=https%3A%2F%2Fwww.capcut.com%2Fmy-edit"
DEFAULT_PASSWORD = "00CHAT700z00"

async def automate_capcut_action(chat_id, action_type, email, password=DEFAULT_PASSWORD):
    is_signup = action_type == 'signup'
    
    await bot.send_message(
        chat_id, 
        f"🚀 **بدء جلسة {'إنشاء حساب' if is_signup else 'تسجيل الدخول'} CapCut...**\n"
        f"📧 الإيميل: `{email}`",
        parse_mode="Markdown"
    )
    
    p = await async_playwright().start()
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
    
    active_sessions[chat_id] = {
        "browser": browser,
        "page": page,
        "playwright": p,
        "email": email
    }
    
    screenshot_path = f"capcut_result_{chat_id}.png"
    
    try:
        await bot.send_message(chat_id, "🌐 جاري فتح صفحة كاب كات...")
        await page.goto(CAPCUT_LOGIN_URL, wait_until="domcontentloaded", timeout=60000)
        await page.wait_for_timeout(3000)
        
        # 1. النقر على Continue with email
        email_btn = page.locator('text="Continue with email"')
        if await email_btn.count() > 0:
            await email_btn.first.click()
        else:
            await page.locator('button, div').filter(has_text=re.compile("email", re.IGNORECASE)).first.click()
            
        await page.wait_for_timeout(2000)

        # 2. إدخال الإيميل
        email_input = page.locator('input[type="text"], input[type="email"]')
        await email_input.wait_for(state="visible", timeout=10000)
        await email_input.first.fill("")
        await email_input.first.type(email, delay=random.randint(50, 150))
        
        await page.wait_for_timeout(1000)

        # 3. النقر على Continue
        continue_btn = page.locator('button:has-text("Continue")')
        if await continue_btn.count() > 0:
            await continue_btn.first.click()
        
        await page.wait_for_timeout(3000)

        # 4. إدخال كلمة المرور
        password_input = page.locator('input[type="password"]')
        await password_input.wait_for(state="visible", timeout=10000)
        await password_input.first.fill("")
        await password_input.first.type(password, delay=random.randint(50, 150))

        await page.wait_for_timeout(1000)

        # 5. النقر على Sign in / Register / Continue
        sign_btn = page.locator('button').filter(has_text=re.compile("Sign in|Sign up|Register|Continue", re.IGNORECASE))
        if await sign_btn.count() > 0:
            try:
                await sign_btn.first.click(timeout=3000)
            except:
                await page.keyboard.press("Enter")
        else:
            await page.keyboard.press("Enter")

        await page.wait_for_timeout(5000)

        # ---------------------------------------------------------
        # معالجة شاشة تاريخ الميلاد (لإنشاء الحساب الجديد)
        # ---------------------------------------------------------
        if is_signup and await page.locator('text="When\'s your birthday?"').count() > 0:
            await bot.send_message(chat_id, "🎂 تم رصد شاشة تاريخ الميلاد، جاري الاختيار العشوائي (سنة بين 1990 و 2005)...")
            
            rand_year = str(random.randint(1990, 2005))
            
            try:
                # محاولة التعامل مع حقل السنة المنسدل أو النصي
                year_box = page.locator('input').first
                if await year_box.count() > 0:
                    await year_box.click()
                    await year_box.fill(rand_year)
                    await page.keyboard.press("Enter")
                
                await page.wait_for_timeout(1500)
                
                # النقر على زر Continue الخاص بتاريخ الميلاد
                birth_continue = page.locator('button:has-text("Continue")')
                if await birth_continue.count() > 0:
                    await birth_continue.first.click()
                    await page.wait_for_timeout(4000)
            except Exception as ex:
                print(f"Birthday handler notice: {ex}")

        # ---------------------------------------------------------
        # الانتقال إلى لوحة التحكم والضغط على Upgrade تلقائياً
        # ---------------------------------------------------------
        await bot.send_message(chat_id, "🔍 جاري الانتقال إلى لوحة التحكم والبحث عن زر Upgrade...")
        try:
            # الانتظار حتى يظهر زر Upgrade في لوحة التحكم
            upgrade_btn = page.locator('button:has-text("Upgrade"), a:has-text("Upgrade")')
            if await upgrade_btn.count() > 0:
                await upgrade_btn.first.click(timeout=5000)
                await bot.send_message(chat_id, "✨ تم النقر على زر Upgrade بنجاح!")
            else:
                print("Upgrade button not immediately found.")
        except Exception as ex:
            print(f"Upgrade click error: {ex}")

        await page.wait_for_timeout(4000)

        # التقاط الشاشة وإرسالها مع أزرار التحكم
        await page.screenshot(path=screenshot_path)
        photo = FSInputFile(screenshot_path)
        
        control_kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔄 تحديث الشاشة", callback_data="refresh_screen"),
             InlineKeyboardButton(text="🏁 إنهاء العملية", callback_data="finish_session")]
        ])
        
        await bot.send_photo(
            chat_id, 
            photo, 
            caption=f"📌 **حالة الجلسة الحالية لـ CapCut:**\nالإيميل: `{email}`\n\nاختر من الأزرار أدناه للمتابعة:",
            parse_mode="Markdown",
            reply_markup=control_kb
        )
        
    except Exception as e:
        error_msg = str(e).split('\n')[0]
        await bot.send_message(chat_id, f"❌ حدث خطأ أثناء التنفيذ: `{error_msg}`", parse_mode="Markdown")
        if chat_id in active_sessions:
            await browser.close()
            await p.stop()
            del active_sessions[chat_id]

@dp.callback_query(F.data == "refresh_screen")
async def refresh_screen_callback(callback: types.CallbackQuery):
    chat_id = callback.message.chat.id
    if chat_id not in active_sessions:
        await callback.answer("⚠️ لا توجد جلسة نشطة حالياً.", show_alert=True)
        return
        
    page = active_sessions[chat_id]["page"]
    screenshot_path = f"capcut_refresh_{chat_id}.png"
    
    try:
        await page.screenshot(path=screenshot_path)
        photo = FSInputFile(screenshot_path)
        
        control_kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔄 تحديث الشاشة", callback_data="refresh_screen"),
             InlineKeyboardButton(text="🏁 إنهاء العملية", callback_data="finish_session")]
        ])
        
        await callback.message.answer_photo(
            photo=photo,
            caption="🔄 **تم تحديث الشاشة بنجاح:**",
            parse_mode="Markdown",
            reply_markup=control_kb
        )
        await callback.answer("تم تحديث الشاشة!")
    except Exception as e:
        await callback.answer(f"فشل التحديث: {str(e)}", show_alert=True)

@dp.callback_query(F.data == "finish_session")
async def finish_session_callback(callback: types.CallbackQuery):
    chat_id = callback.message.chat.id
    if chat_id in active_sessions:
        session = active_sessions[chat_id]
        try:
            await session["browser"].close()
            await session["playwright"].stop()
        except:
            pass
        del active_sessions[chat_id]
        
    await callback.message.edit_reply_markup(reply_markup=None)
    await callback.message.answer("🏁 **تم إنهاء وإغلاق جلسة المتصفح بنجاح.**", parse_mode="Markdown")
    await callback.answer()

@dp.message(Command("start"))
async def send_welcome(message: Message):
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="👤 إنشاء حساب CapCut", callback_data="ask_email_signup")],
        [InlineKeyboardButton(text="🔐 تسجيل دخول (إيميل مخصص)", callback_data="capcut_login")],
        [InlineKeyboardButton(text="➕ اضافة بروكسيات", callback_data="add_proxies"),
         InlineKeyboardButton(text="🛑 إيقاف البروكسيات", callback_data="stop_proxies")]
    ])
    
    status_text = "🟢 **البروكسيات:** مفعلة" if proxy_enabled and proxy_list else "🔴 **البروكسيات:** متوقفة (اتصال محلي)"
    
    await message.reply(
        f"مرحباً بك في بوت أتمتة **CapCut**.\n"
        f"{status_text}\n\n"
        "اختر أحد الخيارات أدناه:",
        parse_mode="Markdown",
        reply_markup=kb
    )

@dp.callback_query(F.data == "ask_email_signup")
async def ask_email_signup(callback: types.CallbackQuery, state: FSMContext):
    await callback.message.answer(
        "أرسل البريد الإلكتروني الذي تريد إنشاء الحساب به:\n"
        f"*(ملاحظة: سيتم استخدام كلمة المرور التلقائية `{DEFAULT_PASSWORD}`)*",
        parse_mode="Markdown"
    )
    await state.set_state(BotStates.waiting_for_email)
    await callback.answer()

@dp.message(BotStates.waiting_for_email)
async def receive_email_for_signup(message: Message, state: FSMContext):
    email = message.text.strip()
    if "@" not in email or "." not in email:
        await message.reply("⚠️ الإيميل غير صحيح. يرجى إرسال إيميل صالح:")
        return
        
    await state.clear()
    asyncio.create_task(automate_capcut_action(message.chat.id, 'signup', email, DEFAULT_PASSWORD))

@dp.callback_query(F.data == "capcut_login")
async def capcut_login_callback(callback: types.CallbackQuery, state: FSMContext):
    await callback.message.answer(
        "أرسل بيانات تسجيل الدخول بهذا التنسيق (في سطر واحد):\n\n"
        "`email@gmail.com|password`",
        parse_mode="Markdown"
    )
    await state.set_state(BotStates.waiting_for_login_credentials)
    await callback.answer()

@dp.message(BotStates.waiting_for_login_credentials)
async def receive_login_credentials(message: Message, state: FSMContext):
    text = message.text.strip()
    parts = text.split('|')
    
    if len(parts) != 2:
        await message.reply("⚠️ التنسيق خاطئ. الرجاء الإرسال بهذا الشكل: `email@gmail.com|password`", parse_mode="Markdown")
        return
        
    email = parts[0].strip()
    password = parts[1].strip()
    
    await state.clear()
    asyncio.create_task(automate_capcut_action(message.chat.id, 'login', email, password))

@dp.callback_query(F.data == "add_proxies")
async def add_proxies_callback(callback: types.CallbackQuery, state: FSMContext):
    global proxy_enabled
    proxy_enabled = True
    await callback.message.answer(
        "أرسل البروكسيات الآن بالتنسيق:\n`username:password@ip:port`", 
        parse_mode="Markdown"
    )
    await state.set_state(BotStates.waiting_for_proxies)
    await callback.answer()

@dp.callback_query(F.data == "stop_proxies")
async def stop_proxies_callback(callback: types.CallbackQuery, state: FSMContext):
    global proxy_enabled
    proxy_enabled = False
    await callback.message.answer("🛑 **تم إيقاف البروكسيات بنجاح.**", parse_mode="Markdown")
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
        await message.reply(f"✅ تم إضافة **{added_count}** بروكسيات بنجاح!", parse_mode="Markdown")
    else:
        await message.reply("⚠️ لم يتم العثور على بروكسيات بالتنسيق الصحيح.")
        
    await state.clear()

async def main():
    print("CapCut Bot is starting...")
    await dp.start_polling(bot)

if __name__ == '__main__':
    asyncio.run(main())
