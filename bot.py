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
recorded_steps = [] # لتسجيل خطوات الماوس

class BotStates(StatesGroup):
    waiting_for_login_credentials = State()
    waiting_for_proxies = State()
    waiting_for_grid_click = State()

CAPCUT_LOGIN_URL = "https://www.capcut.com/login?redirect_url=https%3A%2F%2Fwww.capcut.com%2Fmy-edit"

def draw_numbered_grid(image_path, output_path, cols=25, rows=40):
    """
    تقسيم الصورة إلى شبكة (مثلاً 25 عمود × 40 صف = 1000 مربع) وترقيمها
    """
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
            
            # رسم حدود المربع بشفافية خفيفة أو خطوط رفيعة
            draw.rectangle([x1, y1, x2, y2], outline="red", width=1)
            
            # كتابة رقم المربع في منتصفه
            text_x = x1 + (cell_width / 2)
            text_y = y1 + (cell_height / 2)
            
            # رسم رقم صغير داخل المربع
            draw.text((text_x - 8, text_y - 6), str(counter), fill="blue")
            counter += 1
            
    img.save(output_path)
    return cell_width, cell_height, cols, rows

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
    grid_screenshot_path = f"capcut_grid_{chat_id}.png"
    
    try:
        await bot.send_message(chat_id, "🌐 جاري فتح صفحة كاب كات...")
        await page.goto(CAPCUT_LOGIN_URL, wait_until="domcontentloaded", timeout=60000)
        await page.wait_for_timeout(3000)
        
        # التقاط الشاشة الحالية وتطبيق شبكة الـ 1000 مربع
        await page.screenshot(path=screenshot_path)
        draw_numbered_grid(screenshot_path, grid_screenshot_path, cols=25, rows=40)
        
        photo = FSInputFile(grid_screenshot_path)
        control_kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔄 تحديث الشاشة بالشبكة", callback_data="refresh_grid"),
             InlineKeyboardButton(text="🏁 إنهاء العملية", callback_data="finish_session")]
        ])
        
        await bot.send_photo(
            chat_id, 
            photo, 
            caption=(
                "🎯 **تم تفعيل نظام التحكم بالماوس (1000 مربع مرقم):**\n"
                "انظر إلى الصورة المرسلة وأرسل لي **رقم المربع** الذي تريد الضغط عليه.\n"
                "*(سيقوم البوت بالضغط وتسجيل الخطوة لك تلقائياً)*"
            ),
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

# استقبال أرقام المربعات من المستخدم وتطبيق الضغط عليها بالماوس
@dp.message(F.text.regexp(r'^\d+(\s+\d+)*$'))
async def handle_grid_click(message: Message, state: FSMContext):
    chat_id = message.chat.id
    if chat_id not in active_sessions:
        return # إذا لم تكن هناك جلسة نشطة، تجاهل الرسالة لتسمح بباقي الأوامر
        
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
            
        # حساب الإحداثيات (center of the grid cell)
        box_index = box_num - 1
        r = box_index // cols
        c = box_index % cols
        
        click_x = (c * cell_w) + (cell_w / 2)
        click_y = (r * cell_h) + (cell_h / 2)
        
        # تنفيذ النقر بالماوس الفعلي في المتصفح
        await page.mouse.click(click_x, click_y)
        await page.wait_for_timeout(1000)
        
        # تسجيل الخطوة
        step_note = f"- Clicked grid cell {box_num} at coordinates: ({click_x}, {click_y})"
        recorded_steps.append(step_note)
        await message.answer(f"🖱️ تم النقر على المربع رقم **{box_num}** (الإحداثيات: X={click_x}, Y={click_y})")

    # التقاط الشاشة وتحديث الشبكة للمستخدم
    screenshot_path = f"capcut_result_{chat_id}.png"
    grid_screenshot_path = f"capcut_grid_{chat_id}.png"
    
    await page.screenshot(path=screenshot_path)
    draw_numbered_grid(screenshot_path, grid_screenshot_path, cols=25, rows=40)
    
    photo = FSInputFile(grid_screenshot_path)
    control_kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔄 تحديث الشاشة بالشبكة", callback_data="refresh_grid"),
         InlineKeyboardButton(text="🏁 إنهاء العملية", callback_data="finish_session")]
    ])
    
    # عرض سجل الخطوات المسجلة حتى الآن
    steps_text = "\n".join(recorded_steps[-5:]) if recorded_steps else "لا توجد خطوات مسجلة بعد."
    
    await message.answer_photo(
        photo=photo,
        caption=(
            "🔄 **تم تحديث الشاشة بعد النقرات:**\n"
            f"**الخطوات المسجلة حالياً:**\n`{steps_text}`\n\n"
            "أرسل رقم مربع جديد أو اضغط إنهاء العملية."
        ),
        parse_mode="Markdown",
        reply_markup=control_kb
    )

# زر تحديث الشاشة والشبكة
@dp.callback_query(F.data == "refresh_grid")
async def refresh_grid_callback(callback: types.CallbackQuery):
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
            [InlineKeyboardButton(text="🔄 تحديث الشاشة بالشبكة", callback_data="refresh_grid"),
             InlineKeyboardButton(text="🏁 إنهاء العملية", callback_data="finish_session")]
        ])
        
        await callback.message.answer_photo(
            photo=photo,
            caption="🔄 **تم تحديث الشاشة وتوليد الشبكة بنجاح:**",
            parse_mode="Markdown",
            reply_markup=control_kb
        )
        await callback.answer("تم التحديث!")
    except Exception as e:
        await callback.answer(f"فشل التحديث: {str(e)}", show_alert=True)

# زر إنهاء العملية وعرض السجل الكامل للخطوات
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
        
    # طباعة السجل الكامل للخطوات التي قمت بها لتأخذها وتجعلها تلقائية
    full_script_report = "\n".join(recorded_steps)
    
    await callback.message.edit_reply_markup(reply_markup=None)
    await callback.message.answer(
        "🏁 **تم إنهاء الجلسة بنجاح.**\n\n"
        "📜 **إليك السكريبت المسجل للضغطات لتستخدمه لاحقاً:**\n"
        f"```text\n{full_script_report}\n```",
        parse_mode="Markdown"
    )
    await callback.answer()

@dp.message(Command("start"))
async def send_welcome(message: Message):
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔐 بدء جلسة تفاعلية (تسجيل الدخول)", callback_data="capcut_login")],
        [InlineKeyboardButton(text="➕ اضافة بروكسيات", callback_data="add_proxies"),
         InlineKeyboardButton(text="🛑 إيقاف البروكسيات", callback_data="stop_proxies")]
    ])
    
    status_text = "🟢 **البروكسيات:** مفعلة" if proxy_enabled and proxy_list else "🔴 **البروكسيات:** متوقفة (اتصال محلي)"
    
    await message.reply(
        f"مرحباً بك في بوت التحكم اليدوي والشبكي لـ **CapCut**.\n"
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
    recorded_steps = [] # تفريغ السجل لجلسة جديدة
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
    print("CapCut Grid Mouse Bot is starting...")
    await dp.start_polling(bot)

if __name__ == '__main__':
    asyncio.run(main())
