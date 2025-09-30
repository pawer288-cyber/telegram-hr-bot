# متطلبات: pip install pyTelegramBotAPI pandas openpyxl
import telebot
import pandas as pd
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
from datetime import datetime
from flask import Flask
import threading
import os

# ============= كود البوت الأصلي كامل هنا =============
API_TOKEN = "8374179218:AAH3g6ZBafbp-RVosoWEvkFMbxOqj5yFcng"
bot = telebot.TeleBot(API_TOKEN)

EXCEL_FILE = "نموذج_الموارد_البشرية.xlsx"
MANAGER_PASSWORD = "5832425"

user_sessions = {}
blocked_users = {}  # لتخزين المستخدمين الذين أنهوا المحادثة مؤقتًا

# ============= تحميل البيانات ===================
try:
    df_salaries = pd.read_excel(EXCEL_FILE, sheet_name="المرتبات")
    df_salaries["كود الموظف"] = df_salaries["كود الموظف"].astype(str).str.strip()
    df_salaries["الاسم"] = df_salaries["الاسم"].astype(str).str.strip()
    print("✅ تم تحميل بيانات المرتبات بنجاح")
except Exception as e:
    print("❌ خطأ في تحميل المرتبات:", e)
    df_salaries = pd.DataFrame()

try:
    df_leaves = pd.read_excel(EXCEL_FILE, sheet_name="رصيد الإجازات")
    df_leaves["كود الموظف"] = df_leaves["كود الموظف"].astype(str).str.strip()
    print("✅ تم تحميل بيانات الإجازات بنجاح")
except:
    print("❌ خطأ في تحميل بيانات الإجازات")
    df_leaves = pd.DataFrame()

try:
    df_taken = pd.read_excel(EXCEL_FILE, sheet_name="الإجازات المأخوذة")
    df_taken["كود الموظف"] = df_taken["كود الموظف"].astype(str).str.strip()
    print("✅ تم تحميل بيانات الإجازات المأخوذة بنجاح")
except:
    print("❌ خطأ في تحميل بيانات الإجازات المأخوذة")
    df_taken = pd.DataFrame()

try:
    df_loans = pd.read_excel(EXCEL_FILE, sheet_name="السلف")
    df_loans["كود الموظف"] = df_loans["كود الموظف"].astype(str).str.strip()
    print("✅ تم تحميل بيانات السلف بنجاح")
except:
    print("❌ خطأ في تحميل بيانات السلف")
    df_loans = pd.DataFrame()

# ============= dict سريع ===================
employees_dict = {str(row['كود الموظف']).strip(): row for _, row in df_salaries.iterrows()}
print(f"✅ تم تحميل {len(employees_dict)} موظف في القاموس")

# ============= البحث المحسن ===================
def search_employee(search_term):
    try:
        search_term = str(search_term).strip().lower()
        # تطبيع النص للبحث المرن (إزالة الهمزات والتشكيل)
        search_term = search_term.replace('أ', 'ا').replace('إ', 'ا').replace('آ', 'ا')
        print(f"🔍 بحث عن: {search_term}")
        
        if search_term.isdigit():
            if search_term in employees_dict:
                row = employees_dict[search_term]
                print(f"✅ تم العثور على الموظف بالكود: {search_term} - {row['الاسم']}")
                return [{"code": row["كود الموظف"], "name": row["الاسم"]}]
            print(f"❌ لم يتم العثور على موظف بالكود: {search_term}")
            return []

        if df_salaries.empty:
            print("❌ قاعدة بيانات المرتبات فارغة")
            return []

        # البحث المرن
        mask = df_salaries['الاسم'].str.replace('أ','ا').str.replace('إ','ا').str.replace('آ','ا').str.lower().str.contains(search_term)
        results_df = df_salaries[mask]
        results = [{"code": row["كود الموظف"], "name": row["الاسم"]} for _, row in results_df.iterrows()]
        
        print(f"✅ نتائج البحث: {len(results)} موظف")
        return results[:8]
    except Exception as e:
        print("❌ خطأ في البحث:", e)
        return []

# ============= بيانات الموظف ===================
def get_employee_data(code, password=None, skip_password=False):
    try:
        print(f"📋 جلب بيانات الموظف - الكود: {code}, تخطي كلمة السر: {skip_password}")
        
        if code not in employees_dict:
            print(f"❌ الكود غير مسجل: {code}")
            return {"error": "الكود غير مسجل"}
        row = employees_dict[code]

        if not skip_password and password is not None:
            stored_raw = row.get("الرقم السري", None)
            if pd.isna(stored_raw) or stored_raw is None:
                print(f"❌ الرقم السري غير مسجل للموظف: {code}")
                return {"error": "الرقم السري غير مسجل"}
            stored_password = str(int(stored_raw)) if isinstance(stored_raw, float) else str(stored_raw).strip()
            if str(password).strip() != stored_password:
                print(f"❌ الرقم السري غير صحيح للموظف: {code}")
                return {"error": "الرقم السري غير صحيح"}

        name = row["الاسم"]
        print(f"✅ تم التحقق من بيانات الموظف: {name} ({code})")

        salary_details = []
        for col in df_salaries.columns:
            if col not in ["كود الموظف", "الاسم", "الرقم السري"]:
                value = row[col]
                if pd.isna(value) or value == 0:
                    continue
                if isinstance(value, float):
                    value = round(value, 2)
                    if value == int(value):
                        value = int(value)
                salary_details.append(f"- {col}: {value}")

        leaves_balance = []
        if not df_leaves.empty:
            balance_rows = df_leaves[df_leaves["كود الموظف"] == code]
            if not balance_rows.empty:
                for _, r in balance_rows.iterrows():
                    leave_type = r["نوع الإجازة"]
                    remaining = r["الرصيد المتبقي"]
                    if pd.isna(remaining):
                        remaining = 0
                    if isinstance(remaining, float):
                        remaining = int(remaining)
                    leaves_balance.append(f"- {leave_type}: {remaining} يوم")
            else:
                leaves_balance.append("لا توجد بيانات إجازات")
        else:
            leaves_balance.append("لا توجد بيانات إجازات")

        taken_leaves = []
        if not df_taken.empty:
            taken_rows = df_taken[df_taken["كود الموظف"] == code]
            if not taken_rows.empty:
                for _, r in taken_rows.iterrows():
                    start = pd.to_datetime(r["تاريخ البداية"]).strftime("%d/%m/%Y")
                    end = pd.to_datetime(r["تاريخ النهاية"]).strftime("%d/%m/%Y")
                    leave_type = r["نوع الإجازة"]
                    taken_leaves.append(f"- {leave_type} من {start} إلى {end}")
            else:
                taken_leaves.append("لا توجد بيانات إجازات مأخوذة")
        else:
            taken_leaves.append("لا توجد بيانات إجازات مأخوذة")

        loans = []
        if not df_loans.empty:
            loan_rows = df_loans[df_loans["كود الموظف"] == code]
            if not loan_rows.empty:
                for _, r in loan_rows.iterrows():
                    end_date = pd.to_datetime(r["تاريخ الانتهاء"])
                    month_year = end_date.strftime("%m/%Y")
                    loans.append(f"- السلفة هتنتهي فى {month_year}")
            else:
                loans.append("لا توجد بيانات سلف")
        else:
            loans.append("لا توجد بيانات سلف")

        print(f"✅ تم جلب جميع بيانات الموظف: {name}")
        return {
            "name": name,
            "salary": "\n".join(salary_details) if salary_details else "لا توجد بيانات مرتبات",
            "leaves": "\n".join(leaves_balance),
            "taken_leaves": "\n".join(taken_leaves),
            "loans": "\n".join(loans)
        }

    except Exception as e:
        print("❌ خطأ في جلب البيانات:", e)
        return {"error": "حاول مرة أخرى"}

# ============= القائمة الرئيسية ===================
def show_main_menu(chat_id, code, name):
    print(f"📱 عرض القائمة الرئيسية للموظف: {name} ({code}) - Chat ID: {chat_id}")
    markup = InlineKeyboardMarkup()
    markup.row(
        InlineKeyboardButton("💰 تفاصيل الراتب", callback_data=f"salary_{code}"),
        InlineKeyboardButton("📅 رصيد الإجازات", callback_data=f"vac_{code}")
    )
    markup.row(
        InlineKeyboardButton("🗓️ الإجازات المأخوذة", callback_data=f"taken_{code}"),
        InlineKeyboardButton("💳 السلف", callback_data=f"loan_{code}")
    )
    markup.row(
        InlineKeyboardButton("⬅️ رجوع للخلف", callback_data=f"back_{code}"),
        InlineKeyboardButton("🔍 بحث عن موظف آخر", callback_data="new_search")
    )
    markup.row(
        InlineKeyboardButton("❌ إنهاء المحادثة", callback_data="end_conversation")
    )

    bot.send_message(
        chat_id,
        f"👤 *الموظف: {name}*\n\n"
        f"🌹 السلام عليكم ورحمة الله وبركاته 🌹\n"
        f"أهلاً وسهلاً أ / {name} 👋\n"
        f"معاك/ي مسئول الموارد البشرية أ / إسلام كمال\n"
        f"اختار الخدمة اللي تحب تستعلم عنها:",
        reply_markup=markup,
        parse_mode='Markdown'
    )

# ============= قائمة المدير ===================
def show_manager_menu(chat_id):
    print(f"🛠️ دخول المدير - Chat ID: {chat_id}")
    user_sessions[chat_id] = {"is_manager": True, "manager_searching": True}
    bot.send_message(chat_id, "✅ مرحباً بك مدير النظام.\nمن فضلك اكتب اسم الموظف أو الكود للبحث:")

# ============= استقبال الرسائل ===================
@bot.message_handler(func=lambda message: True)
def handle_message(message):
    user_id = message.from_user.id
    chat_id = message.chat.id
    text = message.text.strip()
    
    print(f"📩 رسالة واردة من User ID: {user_id}, Chat ID: {chat_id}, النص: {text}")

    # البداية: اختيار موظف أو مدير
    if text in ["/start", "ابدأ", "start", "بدء"]:
        print(f"🚀 بدء محادثة جديدة - User ID: {user_id}")
        markup = InlineKeyboardMarkup()
        markup.row(
            InlineKeyboardButton("👤 موظف", callback_data="choose_employee"),
            InlineKeyboardButton("🛠 مدير", callback_data="choose_manager")
        )
        bot.send_message(message.chat.id, "🌹 السلام عليكم ورحمة الله وبركاته 🌹\nاختر الدخول كـ:", reply_markup=markup)
        return

    # المدير يدخل الباسورد
    if user_sessions.get(user_id, {}).get("waiting_for_manager_password"):
        print(f"🔐 محاولة دخول مدير - User ID: {user_id}, الباسورد المدخل: {text}")
        if text == MANAGER_PASSWORD:
            print(f"✅ تم التحقق من باسورد المدير بنجاح - User ID: {user_id}")
            show_manager_menu(message.chat.id)
        else:
            print(f"❌ باسورد المدير غير صحيح - User ID: {user_id}")
            bot.reply_to(message, "❌ الباسورد غير صحيح. حاول مرة أخرى:")
        return

    # المدير بيبحث عن موظف (بدون طلب كلمة سر)
    if user_sessions.get(user_id, {}).get("manager_searching"):
        print(f"🔍 المدير يبحث عن موظف - User ID: {user_id}, البحث: {text}")
        results = search_employee(text)
        if not results:
            bot.reply_to(message, "❌ لم يتم العثور على موظف.")
            return
        if len(results) == 1:
            code = results[0]["code"]
            data = get_employee_data(code, skip_password=True)
            print(f"✅ المدير عرض بيانات الموظف: {data['name']} ({code})")
            show_main_menu(message.chat.id, code, data["name"])
        else:
            markup = InlineKeyboardMarkup()
            for r in results:
                markup.row(InlineKeyboardButton(f"{r['name']} ({r['code']})", callback_data=f"mselect_{r['code']}"))
            bot.send_message(message.chat.id, "اختر من القائمة:", reply_markup=markup)
        return

    # الموظف يدخل بياناته
    if user_sessions.get(user_id, {}).get("waiting_for_password"):
        code = user_sessions[user_id]["code"]
        name = user_sessions[user_id]["name"]
        print(f"🔐 محاولة دخول موظف - User ID: {user_id}, الموظف: {name} ({code}), الباسورد المدخل: {text}")
        data = get_employee_data(code, password=text)
        if "error" in data:
            print(f"❌ فشل دخول الموظف - User ID: {user_id}, السبب: {data['error']}")
            bot.reply_to(message, "❌ الرقم السري غير صحيح. ابدأ من جديد بكتابة الكود أو الاسم.")
            user_sessions.pop(user_id, None)
            return
        print(f"✅ تم دخول الموظف بنجاح - User ID: {user_id}, الموظف: {data['name']} ({code})")
        show_main_menu(message.chat.id, code, data["name"])
        user_sessions.pop(user_id, None)
        return

    # البحث للموظف
    results = search_employee(text)
    if results:
        if len(results) == 1:
            user_sessions[user_id] = {"code": results[0]["code"], "name": results[0]["name"], "waiting_for_password": True}
            print(f"✅ تم العثور على موظف واحد - User ID: {user_id}, الموظف: {results[0]['name']} ({results[0]['code']})")
            bot.send_message(message.chat.id, f"تم العثور على: {results[0]['name']}\n🔑 أدخل الرقم السري:")
        else:
            print(f"✅ تم العثور على {len(results)} موظفين - User ID: {user_id}")
            markup = InlineKeyboardMarkup()
            for r in results:
                markup.row(InlineKeyboardButton(f"{r['name']} ({r['code']})", callback_data=f"eselect_{r['code']}"))
            bot.send_message(message.chat.id, "اختر الموظف الصحيح:", reply_markup=markup)
    else:
        print(f"❌ لم يتم العثور على موظف - User ID: {user_id}, البحث: {text}")
        bot.reply_to(message, "❌ لم يتم العثور على موظف بهذا الاسم أو الكود.")

# ============= الأزرار ===================
@bot.callback_query_handler(func=lambda call: True)
def callback_query(call):
    user_id = call.from_user.id
    chat_id = call.message.chat.id
    data = call.data
    
    print(f"🔘 ضغط على زر - User ID: {user_id}, الزر: {data}")

    if data == "choose_employee":
        print(f"👤 اختيار الدخول كموظف - User ID: {user_id}")
        bot.send_message(call.message.chat.id, "من فضلك اكتب اسمك أو كود الموظف:")
        return

    if data == "choose_manager":
        print(f"🛠️ اختيار الدخول كمدير - User ID: {user_id}")
        user_sessions[user_id] = {"waiting_for_manager_password": True}
        bot.send_message(call.message.chat.id, "🔑 من فضلك أدخل باسورد المدير:")
        return

    if data.startswith("eselect_"):
        code = data.split("_")[1]
        name = employees_dict.get(code, {}).get("الاسم", "الموظف")
        print(f"✅ اختيار موظف من القائمة - User ID: {user_id}, الموظف: {name} ({code})")
        user_sessions[user_id] = {"code": code, "name": name, "waiting_for_password": True}
        bot.send_message(call.message.chat.id, f"تم اختيار: {name}\n🔑 أدخل الرقم السري:")

    if data.startswith("mselect_"):
        code = data.split("_")[1]
        emp_data = get_employee_data(code, skip_password=True)
        print(f"✅ المدير اختار موظف من القائمة - User ID: {user_id}, الموظف: {emp_data['name']} ({code})")
        show_main_menu(call.message.chat.id, code, emp_data["name"])

    elif data.startswith("salary_"):
        code = data.split("_")[1]
        data_emp = get_employee_data(code, skip_password=True)
        print(f"💰 عرض تفاصيل الراتب - User ID: {user_id}, الموظف: {data_emp['name']} ({code})")
        markup = InlineKeyboardMarkup()
        markup.row(
            InlineKeyboardButton("⬅️ رجوع للخلف", callback_data=f"back_{code}"),
            InlineKeyboardButton("🔍 بحث عن موظف آخر", callback_data="new_search")
        )
        markup.row(
            InlineKeyboardButton("❌ إنهاء المحادثة", callback_data="end_conversation")
        )
        bot.send_message(call.message.chat.id, f"👤 *الموظف: {data_emp['name']}*\n\n💰 تفاصيل الراتب:\n{data_emp['salary']}", 
                        reply_markup=markup, parse_mode='Markdown')

    elif data.startswith("vac_"):
        code = data.split("_")[1]
        data_emp = get_employee_data(code, skip_password=True)
        print(f"📅 عرض رصيد الإجازات - User ID: {user_id}, الموظف: {data_emp['name']} ({code})")
        markup = InlineKeyboardMarkup()
        markup.row(
            InlineKeyboardButton("⬅️ رجوع للخلف", callback_data=f"back_{code}"),
            InlineKeyboardButton("🔍 بحث عن موظف آخر", callback_data="new_search")
        )
        markup.row(
            InlineKeyboardButton("❌ إنهاء المحادثة", callback_data="end_conversation")
        )
        bot.send_message(call.message.chat.id, f"👤 *الموظف: {data_emp['name']}*\n\n📅 رصيد الإجازات حتى يوم 15/9:\n{data_emp['leaves']}", 
                        reply_markup=markup, parse_mode='Markdown')

    elif data.startswith("taken_"):
        code = data.split("_")[1]
        data_emp = get_employee_data(code, skip_password=True)
        print(f"🗓️ عرض الإجازات المأخوذة - User ID: {user_id}, الموظف: {data_emp['name']} ({code})")
        markup = InlineKeyboardMarkup()
        markup.row(
            InlineKeyboardButton("⬅️ رجوع للخلف", callback_data=f"back_{code}"),
            InlineKeyboardButton("🔍 بحث عن موظف آخر", callback_data="new_search")
        )
        markup.row(
            InlineKeyboardButton("❌ إنهاء المحادثة", callback_data="end_conversation")
        )
        bot.send_message(call.message.chat.id, f"👤 *الموظف: {data_emp['name']}*\n\n🗓️ الإجازات المأخوذة:\n{data_emp['taken_leaves']}", 
                        reply_markup=markup, parse_mode='Markdown')

    elif data.startswith("loan_"):
        code = data.split("_")[1]
        data_emp = get_employee_data(code, skip_password=True)
        print(f"💳 عرض السلف - User ID: {user_id}, الموظف: {data_emp['name']} ({code})")
        markup = InlineKeyboardMarkup()
        markup.row(
            InlineKeyboardButton("⬅️ رجوع للخلف", callback_data=f"back_{code}"),
            InlineKeyboardButton("🔍 بحث عن موظف آخر", callback_data="new_search")
        )
        markup.row(
            InlineKeyboardButton("❌ إنهاء المحادثة", callback_data="end_conversation")
        )
        bot.send_message(call.message.chat.id, f"👤 *الموظف: {data_emp['name']}*\n\n💳 السلف:\n{data_emp['loans']}", 
                        reply_markup=markup, parse_mode='Markdown')

    elif data.startswith("back_"):
        code = data.split("_")[1]
        data_emp = get_employee_data(code, skip_password=True)
        print(f"⬅️ رجوع للقائمة الرئيسية - User ID: {user_id}, الموظف: {data_emp['name']} ({code})")
        show_main_menu(call.message.chat.id, code, data_emp["name"])

    elif data == "new_search":
        print(f"🔍 بحث عن موظف آخر - User ID: {user_id}")
        # إذا كان مدير، ابقى في وضع المدير
        if user_sessions.get(user_id, {}).get("is_manager"):
            user_sessions[user_id] = {"is_manager": True, "manager_searching": True}
            bot.send_message(call.message.chat.id, "🔍 اكتب اسم الموظف أو الكود للبحث:")
        else:
            user_sessions.pop(user_id, None)
            bot.send_message(call.message.chat.id, "من فضلك اكتب اسم الموظف أو الكود:")

    elif data == "end_conversation":
        print(f"❌ إنهاء المحادثة - User ID: {user_id}")
        user_sessions.pop(user_id, None)
        markup = InlineKeyboardMarkup()
        markup.row(
            InlineKeyboardButton("👤 موظف", callback_data="choose_employee"),
            InlineKeyboardButton("🛠 مدير", callback_data="choose_manager")
        )
        bot.send_message(call.message.chat.id, "✅ تم إنهاء المحادثة.\nاختر الدخول من جديد كـ:", reply_markup=markup)

# ============= كود Flask للعمل على Render =============
app = Flask(__name__)

@app.route('/')
def home():
    return "✅ البوت شغال على Render!"

@app.route('/health')
def health():
    return "OK", 200

def run_flask():
    port = int(os.environ.get('PORT', 8080))
    app.run(host='0.0.0.0', port=port)

def run_bot():
    print("✅ البوت شغال...")
    try:
        bot.infinity_polling()
    except Exception as e:
        print(f"❌ حدث خطأ: {e}")

if __name__ == "__main__":
    # تشغيل السيرفر في thread منفصل
    flask_thread = threading.Thread(target=run_flask)
    flask_thread.daemon = True
    flask_thread.start()
    
    # تشغيل البوت
    run_bot()
