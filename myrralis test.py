import os
import logging
import sqlite3
import asyncio
from datetime import datetime
from telethon import TelegramClient, events, Button
from telethon.errors import SessionPasswordNeededError
from instagrapi import Client as InstagramClient
import uuid
import random
import time

# إعدادات التسجيل
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ⚠️ غير هذه البيانات بمعلوماتك الخاصة!
API_ID = 38614956  # ضع API ID الحقيقي هنا
API_HASH = 'e7d64535a8ad4af4cc45df1ce1db1ed3'  # ضع API Hash الحقيقي هنا
BOT_TOKEN = '8553643929:AAESfuEtZNCRuo2R9wzZE5f-ZdiR7fU-_hE'  # ضع توكن البوت الحقيقي هنا

# قاعدة البيانات
class Database:
    def __init__(self):
        self.conn = sqlite3.connect('instagram_swap.db')
        self.cursor = self.conn.cursor()
        self.init_db()
    
    def init_db(self):
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                username TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS accounts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                account_type TEXT,
                insta_username TEXT,
                session_data TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users (user_id)
            )
        ''')
        
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS swaps (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                main_account TEXT,
                target_account TEXT,
                status TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users (user_id)
            )
        ''')
        self.conn.commit()
    
    def save_user(self, user_id, username):
        self.cursor.execute('INSERT OR IGNORE INTO users (user_id, username) VALUES (?, ?)', (user_id, username))
        self.conn.commit()
    
    def save_account(self, user_id, account_type, insta_username, session_data):
        self.cursor.execute('''
            INSERT INTO accounts (user_id, account_type, insta_username, session_data) 
            VALUES (?, ?, ?, ?)
        ''', (user_id, account_type, insta_username, session_data))
        self.conn.commit()
    
    def get_accounts(self, user_id):
        self.cursor.execute('SELECT account_type, insta_username, session_data FROM accounts WHERE user_id = ?', (user_id,))
        return {row[0]: {'username': row[1], 'session_data': row[2]} for row in self.cursor.fetchall()}
    
    def save_swap(self, user_id, main_acc, target_acc, status):
        self.cursor.execute('''
            INSERT INTO swaps (user_id, main_account, target_account, status) 
            VALUES (?, ?, ?, ?)
        ''', (user_id, main_acc, target_acc, status))
        self.conn.commit()

# مدير إنستغرام
class InstagramManager:
    def __init__(self):
        self.db = Database()
    
    def create_instagram_client(self):
        """إنشاء عميل إنستغرام"""
        cl = InstagramClient()
        settings = {
            "user_agent": "Mozilla/5.0 (Linux; Android 13; SM-G991B) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/112.0.0.0 Mobile Safari/537.36",
            "device_settings": {
                "app_version": "309.0.0.0.0",
                "android_version": 33,
                "android_release": "13.0.0",
                "dpi": "480dpi",
                "resolution": "1080x2400",
                "manufacturer": "samsung",
                "device": "SM-G991B",
                "model": "Galaxy S21",
                "cpu": "arm64-v8a"
            },
            "uuid": str(uuid.uuid4()),
            "device_id": f"android-{str(uuid.uuid4())[:16]}",
        }
        cl.set_settings(settings)
        return cl
    
    async def login_with_credentials(self, username, password):
        """تسجيل الدخول ببيانات إنستغرام"""
        try:
            cl = self.create_instagram_client()
            cl.login(username, password)
            
            # الحصول على بيانات الجلسة
            session_data = cl.get_settings()
            account_info = cl.account_info()
            
            return True, session_data, account_info.username
            
        except Exception as e:
            return False, None, str(e)
    
    async def login_with_session(self, session_data):
        """تسجيل الدخول بجلسة محفوظة"""
        try:
            cl = self.create_instagram_client()
            cl.set_settings(session_data)
            cl.login_by_sessionid(session_data.get('cookies', {}).get('sessionid'))
            
            account_info = cl.account_info()
            return True, account_info.username
            
        except Exception as e:
            return False, str(e)
    
    async def swap_usernames(self, main_session, target_session):
        """تبديل أسماء المستخدمين"""
        try:
            # إنشاء عملاء
            cl_main = self.create_instagram_client()
            cl_target = self.create_instagram_client()
            
            # تعيين الجلسات
            cl_main.set_settings(main_session)
            cl_target.set_settings(target_session)
            
            # تسجيل الدخول بالجلسات
            cl_main.login_by_sessionid(main_session.get('cookies', {}).get('sessionid'))
            cl_target.login_by_sessionid(target_session.get('cookies', {}).get('sessionid'))
            
            # الحصول على معلومات الحسابات
            main_info = cl_main.account_info()
            target_info = cl_target.account_info()
            
            # إنشاء اسم مؤقت
            temp_username = f"temp_{int(time.time())}_{random.randint(1000, 9999)}"
            
            # بدء عملية التبديل
            # الخطوة 1: تحريك الحساب الرئيسي إلى اسم مؤقت
            cl_main.account_edit(username=temp_username)
            await asyncio.sleep(2)
            
            # الخطوة 2: تحريك الحساب الهدف إلى اسم الحساب الرئيسي
            cl_target.account_edit(username=main_info.username)
            await asyncio.sleep(2)
            
            # الخطوة 3: تحريك الحساب الرئيسي إلى اسم الحساب الهدف
            cl_main.account_edit(username=target_info.username)
            await asyncio.sleep(1)
            
            return True, main_info.username, target_info.username
            
        except Exception as e:
            return False, None, None, str(e)

# البوت الرئيسي
class TelegramSwapBot:
    def __init__(self):
        self.db = Database()
        self.instagram_manager = InstagramManager()
        self.user_states = {}
    
    async def start_bot(self):
        """بدء تشغيل البوت"""
        client = TelegramClient('swap_bot', API_ID, API_HASH).start(bot_token=BOT_TOKEN)
        
        @client.on(events.NewMessage(pattern='/start'))
        async def start_handler(event):
            """معالج أمر البدء"""
            user_id = event.sender_id
            username = event.sender.username or "Unknown"
            
            self.db.save_user(user_id, username)
            
            # زر البداية
            buttons = [
                [Button.inline("➕ إضافة حساب", b"add_account")],
                [Button.inline("🔄 تبديل أسماء", b"swap_accounts")],
                [Button.inline("👤 حساباتي", b"my_accounts")],
                [Button.inline("ℹ️ المساعدة", b"help")]
            ]
            
            await event.reply(
                "**🚀 أهلاً بك في بوت تبديل أسماء إنستغرام!**\n\n"
                "**المميزات:**\n"
                "• تبديل أسماء المستخدمين بين حسابين\n"
                "• دعم الجلسات لحفظ الحسابات\n"
                "• واجهة سهلة الاستخدام\n\n"
                "**اختر من الأزرار أدناه:**",
                buttons=buttons
            )
        
        @client.on(events.CallbackQuery)
        async def callback_handler(event):
            """معالج الأزرار"""
            user_id = event.sender_id
            data = event.data.decode()
            
            if data == "add_account":
                await self.handle_add_account(event)
            elif data == "swap_accounts":
                await self.handle_swap_accounts(event)
            elif data == "my_accounts":
                await self.handle_my_accounts(event)
            elif data == "help":
                await self.handle_help(event)
            elif data.startswith("account_type_"):
                account_type = data.split("_")[2]
                self.user_states[user_id] = {'action': 'add_account', 'type': account_type}
                await event.edit("**📝 أرسل يوزرنيم إنستغرام:**")
        
        @client.on(events.NewMessage)
        async def message_handler(event):
            """معالج الرسائل العادية"""
            user_id = event.sender_id
            message_text = event.text
            
            if user_id in self.user_states:
                state = self.user_states[user_id]
                
                if state['action'] == 'add_account' and 'type' in state:
                    if 'username' not in state:
                        # حفظ اليوزرنيم
                        state['username'] = message_text
                        self.user_states[user_id] = state
                        await event.reply("**🔐 أرسل كلمة المرور أو الجلسة (Session):**")
                    
                    elif 'username' in state and 'password' not in state:
                        # معالجة كلمة المرور أو الجلسة
                        if len(message_text) > 100:  # إذا كانت جلسة
                            try:
                                session_data = eval(message_text)  # تحويل النص إلى dictionary
                                success, username = await self.instagram_manager.login_with_session(session_data)
                                
                                if success:
                                    self.db.save_account(user_id, state['type'], state['username'], str(session_data))
                                    await event.reply(f"**✅ تم إضافة الحساب {state['type']} بنجاح!**\n👤 @{username}")
                                    del self.user_states[user_id]
                                else:
                                    await event.reply(f"**❌ فشل في تسجيل الدخول بالجلسة:** {username}")
                                
                            except Exception as e:
                                await event.reply(f"**❌ جلسة غير صالحة:** {str(e)}")
                        
                        else:  # إذا كانت كلمة مرور
                            success, session_data, result = await self.instagram_manager.login_with_credentials(state['username'], message_text)
                            
                            if success:
                                self.db.save_account(user_id, state['type'], state['username'], str(session_data))
                                await event.reply(f"**✅ تم إضافة الحساب {state['type']} بنجاح!**\n👤 @{result}")
                                del self.user_states[user_id]
                            else:
                                await event.reply(f"**❌ فشل في تسجيل الدخول:** {result}")
        
        await client.run_until_disconnected()
    
    async def handle_add_account(self, event):
        """معالج إضافة حساب"""
        buttons = [
            [Button.inline("🎯 حساب رئيسي", b"account_type_main")],
            [Button.inline("🎯 حساب هدف", b"account_type_target")],
            [Button.inline("🔙 رجوع", b"start")]
        ]
        
        await event.edit(
            "**➕ إضافة حساب إنستغرام**\n\n"
            "**اختر نوع الحساب:**\n"
            "• 🎯 **حساب رئيسي:** الحساب الذي تريد الاحتفاظ باسمه\n"
            "• 🎯 **حساب هدف:** الحساب الذي تريد التبديل معه\n\n"
            "**ستحتاج إما:**\n"
            "• يوزرنيم + باسورد\n"
            "• أو جلسة (Session) جاهزة",
            buttons=buttons
        )
    
    async def handle_swap_accounts(self, event):
        """معالج تبديل الحسابات"""
        user_id = event.sender_id
        accounts = self.db.get_accounts(user_id)
        
        if 'main' not in accounts or 'target' not in accounts:
            buttons = [[Button.inline("➕ إضافة حساب", b"add_account")]]
            await event.edit(
                "**❌ تحتاج إلى إضافة الحساب الرئيسي والهدف أولاً!**",
                buttons=buttons
            )
            return
        
        # بدء عملية التبديل
        await event.edit("**⚡ جاري تبديل أسماء المستخدمين...**")
        
        try:
            main_session = eval(accounts['main']['session_data'])
            target_session = eval(accounts['target']['session_data'])
            
            success, old_main, old_target = await self.instagram_manager.swap_usernames(main_session, target_session)
            
            if success:
                self.db.save_swap(user_id, old_main, old_target, 'success')
                
                result_text = (
                    f"**✅ تم التبديل بنجاح!**\n\n"
                    f"**🔄 النتائج:**\n"
                    f"• الحساب الرئيسي: `{old_main}` → `{old_target}`\n"
                    f"• الحساب الهدف: `{old_target}` → `{old_main}`\n\n"
                    f"**⏰ الوقت:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
                )
                
                buttons = [
                    [Button.inline("🔄 تبديل مرة أخرى", b"swap_accounts")],
                    [Button.inline("🔙 القائمة الرئيسية", b"start")]
                ]
                
                await event.edit(result_text, buttons=buttons)
            else:
                await event.edit(f"**❌ فشل في التبديل:** {old_target}")
                
        except Exception as e:
            await event.edit(f"**❌ حدث خطأ:** {str(e)}")
    
    async def handle_my_accounts(self, event):
        """معالج عرض الحسابات"""
        user_id = event.sender_id
        accounts = self.db.get_accounts(user_id)
        
        if not accounts:
            buttons = [[Button.inline("➕ إضافة حساب", b"add_account")]]
            await event.edit("**❌ لا توجد حسابات مضافة!**", buttons=buttons)
            return
        
        accounts_text = "**👤 حساباتك:**\n\n"
        
        for acc_type, acc_data in accounts.items():
            emoji = "🎯" if acc_type == "main" else "🎯"
            accounts_text += f"{emoji} **{acc_type.upper()}:** @{acc_data['username']}\n"
        
        buttons = [
            [Button.inline("🔄 تبديل أسماء", b"swap_accounts")],
            [Button.inline("➕ إضافة حساب", b"add_account")],
            [Button.inline("🔙 رجوع", b"start")]
        ]
        
        await event.edit(accounts_text, buttons=buttons)
    
    async def handle_help(self, event):
        """معالج المساعدة"""
        help_text = (
            "**ℹ️ دليل الاستخدام**\n\n"
            "**📋 الخطوات:**\n"
            "1. أضف الحساب الرئيسي (الذي تريد الاحتفاظ باسمه)\n"
            "2. أضف الحساب الهدف (الذي تريد التبديل معه)\n"
            "3. شغل عملية التبديل\n\n"
            "**🔐 طرق الإضافة:**\n"
            "• **الباسورد:** يوزرنيم + باسورد\n"
            "• **الجلسة:** يوزرنيم + جلسة جاهزة\n\n"
            "**💡 نصائح:**\n"
            "• تأكد من صحة البيانات\n"
            "• استخدم جلسات جديدة\n"
            "• لا تستخدم الحسابات حديثة الإنشاء\n\n"
            "**🛠 الأوامر:**\n"
            "• /start - بدء البوت\n"
            "• الأزرار - للتنقل بين الخيارات"
        )
        
        buttons = [[Button.inline("🔙 رجوع", b"start")]]
        await event.edit(help_text, buttons=buttons)

# تشغيل البوت
if __name__ == "__main__":
    bot = TelegramSwapBot()
    
    print("🚀 جاري تشغيل بوت تبديل أسماء إنستغرام...")
    asyncio.run(bot.start_bot())