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

proxy_list = []
proxy_enabled = True
active_sessions = {}

class BotStates(StatesGroup):
    waiting_for_login_credentials = State()
    waiting_for_proxies = State()

CAPCUT_LOGIN_URL = "https://www.capcut.com/login?redirect_url=https%3A%2F%2Fwww.capcut.com%2Fmy-edit"

async def automate_capcut_login(chat_id, email, password):
    await bot.send_message(
        chat_id, 
        f"🚀 **بدء جلسة تسجيل الدخول لـ CapCut...**\n"
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
        
        await page.wait_for_timeout(3500)

        # 4. تعبئة كلمة المرور في شاشة Welcome back
        password_input = page.locator('input[type="password"]')
        try:
            await password_input.wait_for(state="visible", timeout=10000)
            await password_input.first.fill("")
            await password_input.first.type(password, delay=random.randint(50, 150))
        except:
            all_inputs = page.locator('input')
            if await all_inputs.count() > 0:
                await all_inputs.last.fill(password)

        await page.wait_for_timeout(1000)

        # 5. النقر على Sign in
        sign_in_btn = page.locator('button:has-text("Sign in")')
        if await sign_in_btn.count() > 0:
            try:
                await sign_in_btn.first.click(timeout=3000)
            except:
                await page.keyboard.press("Enter")
        else:
            await page.keyboard.press("Enter")

        # انتظار تحميل لوحة التحكم الرئيسية بالكامل
        await bot.send_message(chat_id, "🔄 جاري الدخول إلى لوحة التحكم والبحث عن زر Upgrade...")
        await page.wait_for_timeout(7000)

        # 6. دالة ذكية للبحث والضغط على زر Upgrade حتى لو تأخر ظهوره
        clicked_upgrade = False
        for _ in range(10): # محاولة لمدة 10 ثوانٍ
            try:
                upgrade_btn = page.locator('button:has-text("Upgrade"), a:has-text("Upgrade")').first
                if await upgrade_btn.is_visible():
                    await upgrade_btn.click()
                    clicked_upgrade = True
                    await bot.send_message(chat_id, "✨ تم النقر على زر Upgrade بنجاح!")
                    break
            except:
                pass
            await page.wait_for_timeout(1000)

        if not clicked_upgrade:
            await bot.send_message(chat_id, "⚠️ ملاحظة: لم يتم العثور على زر Upgrade تلقائياً، يمكنك الضغط عليه يدوياً أو تحديث الشاشة.")

        await page.wait_for_timeout(3000)

        # التقاط الشاشة النهائية وإرسالها مع أزرار التحكم
        await page.screenshot(path=screenshot_path)
        photo = FSInputFile(screenshot_path)
        
        control_kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔄 تحديث الشاشة", callback_data="refresh_screen"),
             InlineKeyboardButton(text="🏁 إنهاء العملية", callback_data="finish_session")]
        ])
        
        await bot.send_photo(
            chat_id, 
            photo, 
            caption=f"📌 **حالة جلسة تسجيل الدخول لـ CapCut:**\nالإيميل: `{email}`\n\nاختر من الأزرار أدناه للمتابعة:",
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

# زر تحديث الشاشة
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

# زر إنهاء العملية
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
        [InlineKeyboardButton(text="🔐 تسجيل دخول (إيميل مخصص)", callback_data="capcut_login")],
        [InlineKeyboardButton(text="➕ اضافة بروكسيات", callback_data="add_proxies"),
         InlineKeyboardButton(text="🛑 إيقاف البروكسيات", callback_data="stop_proxies")]
    ])
    
    status_text = "🟢 **البروكسيات:** مفعلة" if proxy_enabled and proxy_list else "🔴 **البروكسيات:** متوقفة (اتصال محلي)"
    
    await message.reply(
        f"مرحباً بك في بوت أتمتة تسجيل الدخول لـ **CapCut**.\n"
        f"{status_text}\n\n"
        "اختر أحد الخيارات أدناه:",
        parse_mode="Markdown",
        reply_markup=kb
    )

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
    asyncio.create_task(automate_capcut_login(message.chat.id, email, password))

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
    print("CapCut Login Bot is starting...")
    await dp.start_polling(bot)

if __name__ == '__main__':
    asyncio.run(main())
