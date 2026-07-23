import asyncio
import os
import random
import string
import re
from PIL import Image, ImageDraw, ImageFont
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
recorded_steps = []

class BotStates(StatesGroup):
    waiting_for_login_credentials = State()
    waiting_for_proxies = State()

CAPCUT_LOGIN_URL = "https://www.capcut.com/login?redirect_url=https%3A%2F%2Fwww.capcut.com%2Fmy-edit"

def draw_numbered_grid(image_path, output_path, cols=25, rows=40):
    img = Image.open(image_path).convert("RGB")
    width, height = img.size
    cell_width = width / cols
    cell_height = height / rows
    draw = ImageDraw.Draw(img)
    
    counter = 1
    for r in range(rows):
        for c in range(cols):
            x1 = c * cell_width
            y1 = r * cell_height
            x2 = x1 + cell_width
            y2 = y1 + cell_height
            
            draw.rectangle([x1, y1, x2, y2], outline="red", width=1)
            text_x = x1 + (cell_width / 2)
            text_y = y1 + (cell_height / 2)
            draw.text((text_x - 8, text_y - 6), str(counter), fill="blue")
            counter += 1
            
    img.save(output_path)
    return cell_width, cell_height, cols, rows

async def automate_capcut_login(chat_id, email, password):
    await bot.send_message(
        chat_id, 
        f"🚀 **بدء جلسة تسجيل الدخول التلقائي لـ CapCut...**\n"
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
        await bot.send_message(chat_id, "⌨️ جاري إدخال البريد الإلكتروني...")
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
        await bot.send_message(chat_id, "🔑 جاري تعبئة كلمة المرور...")
        password_input = page.locator('input[type="password"]')
        try:
            await password_input.wait_for(state="visible", timeout=10000)
            await password_input.first.fill("")
            await password_input.first.type(password, delay=random.randint(50, 150))
        except:
            all_inputs = page.locator('input')
            if await all_inputs.count() > 0:
                await all_inputs.last.fill(password)

        await page.wait_for_timeout(1500)

        # 5. النقر على Sign in
        await bot.send_message(chat_id, "✅ جاري النقر على زر Sign in...")
        try:
            sign_in_btn = page.locator('button:has-text("Sign in")').first
            await sign_in_btn.click(force=True, timeout=5000)
        except:
            await page.keyboard.press("Enter")

        # 6. الانتظار حتى يتم تحميل لوحة التحكم الرئيسية
        await bot.send_message(chat_id, "🔄 جاري الانتقال إلى لوحة التحكم...")
        try:
            await page.wait_for_url("**/my-edit**", timeout=20000)
        except:
            await page.wait_for_timeout(6000)

        # 7. النقر على زر Upgrade تلقائياً
        await bot.send_message(chat_id, "✨ جاري النقر على زر Upgrade...")
        await page.evaluate("""
            () => {
                const els = Array.from(document.querySelectorAll('a, button, div, span'));
                const target = els.find(el => {
                    const t = el.textContent ? el.textContent.trim().toLowerCase() : '';
                    return t === 'upgrade' || t === 'upgrade space';
                });
                if (target) { target.click(); return true; }
                return false;
            }
        """)

        await page.wait_for_timeout(4000)

        # التقاط الشاشة النظيفة وإرسالها مع الأزرار
        await page.screenshot(path=screenshot_path)
        photo = FSInputFile(screenshot_path)
        
        control_kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔄 تحديث الشاشة", callback_data="refresh_screen"),
             InlineKeyboardButton(text="📊 عرض شبكة الماوس", callback_data="show_grid")],
            [InlineKeyboardButton(text="🏁 إنهاء العملية", callback_data="finish_session")]
        ])
        
        await bot.send_photo(
            chat_id, 
            photo, 
            caption=f"📌 **حالة الجلسة لـ CapCut:**\nالإيميل: `{email}`\n\nاختر من الأزرار أدناه للمتابعة:",
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

# استقبال أرقام المربعات عند تففعيل شبكة الماوس يدويًا
@dp.message(F.text.regexp(r'^\d+(\s+\d+)*$'))
async def handle_grid_click(message: Message, state: FSMContext):
    chat_id = message.chat.id
    if chat_id not in active_sessions:
        return
        
    session = active_sessions[chat_id]
    page = session["page"]
    
    numbers = message.text.strip().split()
    viewport_width, viewport_height = 1440, 900
    cols, rows = 25, 40
    cell_w = viewport_width / cols
    cell_h = viewport_height / rows
    
    for num_str in numbers:
        box_num = int(num_str)
        if box_num < 1 or box_num > (cols * rows):
            continue
            
        box_index = box_num - 1
        r = box_index // cols
        c = box_index % cols
        
        click_x = (c * cell_w) + (cell_w / 2)
        click_y = (r * cell_h) + (cell_h / 2)
        
        await page.mouse.click(click_x, click_y)
        await page.wait_for_timeout(1000)
        
        step_note = f"- Clicked grid cell {box_num} at coordinates: ({click_x}, {click_y})"
        recorded_steps.append(step_note)
        await message.answer(f"🖱️ تم النقر على المربع رقم **{box_num}** (الإحداثيات: X={click_x}, Y={click_y})")

    screenshot_path = f"capcut_result_{chat_id}.png"
    await page.screenshot(path=screenshot_path)
    photo = FSInputFile(screenshot_path)
    
    control_kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔄 تحديث الشاشة", callback_data="refresh_screen"),
         InlineKeyboardButton(text="📊 عرض شبكة الماوس", callback_data="show_grid")],
        [InlineKeyboardButton(text="🏁 إنهاء العملية", callback_data="finish_session")]
    ])
    
    await message.answer_photo(
        photo=photo,
        caption="🔄 **تم تحديث الشاشة النظيفة بعد النقرات:**",
        parse_mode="Markdown",
        reply_markup=control_kb
    )

# زر تحديث الشاشة (عادية بدون شبكة)
@dp.callback_query(F.data == "refresh_screen")
async def refresh_screen_callback(callback: types.CallbackQuery):
    chat_id = callback.message.chat.id
    if chat_id not in active_sessions:
        await callback.answer("⚠️ لا توجد جلسة نشطة حالياً.", show_alert=True)
        return
        
    page = active_sessions[chat_id]["page"]
    screenshot_path = f"capcut_result_{chat_id}.png"
    
    try:
        await page.screenshot(path=screenshot_path)
        photo = FSInputFile(screenshot_path)
        
        control_kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔄 تحديث الشاشة", callback_data="refresh_screen"),
             InlineKeyboardButton(text="📊 عرض شبكة الماوس", callback_data="show_grid")],
            [InlineKeyboardButton(text="🏁 إنهاء العملية", callback_data="finish_session")]
        ])
        
        await callback.message.answer_photo(
            photo=photo,
            caption="🔄 **تم تحديث الشاشة بنجاح:**",
            parse_mode="Markdown",
            reply_markup=control_kb
        )
        await callback.answer("تم التحديث!")
    except Exception as e:
        await callback.answer(f"فشل التحديث: {str(e)}", show_alert=True)

# زر عرض شبكة الماوس المرقمة (عند الطلب فقط)
@dp.callback_query(F.data == "show_grid")
async def show_grid_callback(callback: types.CallbackQuery):
    chat_id = callback.message.chat.id
    if chat_id not in active_sessions:
        await callback.answer("⚠️ لا توجد جلسة نشطة حالياً.", show_alert=True)
        return
        
    page = active_sessions[chat_id]["page"]
    screenshot_path = f"capcut_result_{chat_id}.png"
    grid_screenshot_path = f"capcut_grid_{chat_id}.png"
    
    try:
        await page.screenshot(path=screenshot_path)
        draw_numbered_grid(screenshot_path, grid_screenshot_path, cols=25, rows=40)
        photo = FSInputFile(grid_screenshot_path)
        
        control_kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔄 إخفاء الشبكة والتحديث", callback_data="refresh_screen"),
             InlineKeyboardButton(text="🏁 إنهاء العملية", callback_data="finish_session")]
        ])
        
        await callback.message.answer_photo(
            photo=photo,
            caption=(
                "🎯 **تم تفعيل شبكة الماوس المرقمة (1000 مربع):**\n"
                "أرسل لي الآن رقم المربع الذي تريد الضغط عليه لتنفيذ النقرة وتسجيلها."
            ),
            parse_mode="Markdown",
            reply_markup=control_kb
        )
        await callback.answer()
    except Exception as e:
        await callback.answer(f"فشل عرض الشبكة: {str(e)}", show_alert=True)

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
        
    full_script_report = "\n".join(recorded_steps) if recorded_steps else "لا توجد نقرات مسجلة."
    
    await callback.message.edit_reply_markup(reply_markup=None)
    await callback.message.answer(
        "🏁 **تم إنهاء الجلسة بنجاح.**\n\n"
        "📜 **سجل الخطوات والنقرات:**\n"
        f"```text\n{full_script_report}\n```",
        parse_mode="Markdown"
    )
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
        f"مرحباً بك في بوت أتمتة كاب كات الذكي.\n"
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
    global recorded_steps
    recorded_steps = []
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
    proxy_enabled, proxy_list = False, []
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
    print("CapCut Clean Bot is starting...")
    await dp.start_polling(bot)

if __name__ == '__main__':
    asyncio.run(main())
