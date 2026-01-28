import os
import time
import logging
import threading
import requests
import asyncio
from datetime import datetime
from flask import Flask, request
from waitress import serve

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, ContextTypes, filters
from pathlib import Path

# =================== CONFIGURACIÓN DE LOGGING ===================
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# =================== CONFIGURACIÓN ===================
DOCS_DIR = Path(__file__).parent / "docs"
DOCS_DIR.mkdir(exist_ok=True)
F001_PDF = DOCS_DIR / "Formulario_001.pdf"
F001_EJEMPLO_PDF = DOCS_DIR / "Ejemplo_Formulario_001.pdf"

TOKEN = os.getenv("BOT_TOKEN")
if not TOKEN:
    raise ValueError("❌ BOT_TOKEN no encontrado en variables de entorno")

WEBHOOK_MODE = os.getenv("WEBHOOK_MODE", "False").lower() == "true"

# =================== KEEP ALIVE SERVICE ===================
class KeepAliveService:
    def __init__(self, app_url):
        self.app_url = app_url
        self.running = False
        
    def ping(self):
        try:
            resp = requests.get(f"{self.app_url}/health", timeout=5)
            logger.info(f"Keep-alive ping: {resp.status_code}")
            return True
        except Exception as e:
            logger.warning(f"Keep-alive ping failed: {e}")
            return False
    
    def start(self, interval_minutes=8):
        self.running = True
        interval = interval_minutes * 60
        
        def worker():
            while self.running:
                self.ping()
                time.sleep(interval)
        
        thread = threading.Thread(target=worker, daemon=True)
        thread.start()
        logger.info(f"✅ Keep-alive service started (every {interval_minutes} min)")

# =================== FLASK APP ===================
flask_app = Flask(__name__)
telegram_app = None
keep_alive = None

@flask_app.route('/')
def home():
    return '''
    <!DOCTYPE html>
    <html>
    <head>
        <title>🤖 Bot PPS UTN FRC</title>
        <meta name="viewport" content="width=device-width, initial-scale=1">
        <style>
            body { 
                font-family: 'Arial', sans-serif; 
                text-align: center; 
                padding: 50px; 
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                color: white;
                min-height: 100vh;
                display: flex;
                flex-direction: column;
                justify-content: center;
                align-items: center;
            }
            .container {
                background: rgba(255, 255, 255, 0.1);
                backdrop-filter: blur(10px);
                border-radius: 20px;
                padding: 40px;
                max-width: 600px;
                box-shadow: 0 8px 32px rgba(0, 0, 0, 0.2);
            }
            .status { 
                color: #4ade80; 
                font-weight: bold;
                font-size: 24px;
                margin: 20px 0;
            }
            .bot-name {
                font-size: 32px;
                margin-bottom: 10px;
                color: #fbbf24;
            }
            .links a {
                display: inline-block;
                margin: 10px;
                padding: 12px 24px;
                background: rgba(255, 255, 255, 0.2);
                color: white;
                text-decoration: none;
                border-radius: 10px;
                transition: all 0.3s;
            }
            .links a:hover {
                background: rgba(255, 255, 255, 0.3);
                transform: translateY(-2px);
            }
            .emoji {
                font-size: 48px;
                margin-bottom: 20px;
            }
        </style>
    </head>
    <body>
        <div class="container">
            <div class="emoji">🤖</div>
            <h1 class="bot-name">Bot PPS - Ingeniería Electrónica UTN FRC</h1>
            <p class="status">✅ Servicio activo y funcionando</p>
            <p>Bot de Telegram para Práctica Profesional Supervisada</p>
            <p>Usa /start en Telegram para comenzar</p>
            <div class="links">
                <a href="/health">🔍 Verificar estado</a>
                <a href="https://t.me/PPS_Electronica_UTN_Bot">💬 Ir al bot</a>
            </div>
            <p style="margin-top: 30px; font-size: 12px; opacity: 0.8;">
                Última actualización: ''' + datetime.now().strftime("%Y-%m-%d %H:%M:%S") + '''
            </p>
        </div>
    </body>
    </html>
    '''

@flask_app.route('/health')
def health():
    return {
        "status": "ok", 
        "service": "telegram-bot-pps", 
        "timestamp": datetime.now().isoformat(),
        "version": "2.0",
        "environment": "production"
    }, 200

@flask_app.route('/webhook', methods=['POST'])
def webhook():
    if request.is_json:
        try:
            update = Update.de_json(request.get_json(), telegram_app.bot)
            asyncio.run_coroutine_threadsafe(
                telegram_app.process_update(update),
                telegram_app._get_running_loop() or asyncio.new_event_loop()
            )
            logger.info(f"Webhook recibido: {update.update_id}")
            return 'OK', 200
        except Exception as e:
            logger.error(f"Error procesando webhook: {e}")
            return 'ERROR', 500
    return 'NO JSON', 400

# =================== INFORMACIÓN DEL BOT ===================
INFO = {
    "welcome": (
        "👋 ¡Hola! Soy el bot de <b>Prácticas Profesionales Supervisadas</b>\n"
        "de la carrera <b>Ingeniería Electrónica - UTN FRC</b>\n\n"
        "⬇️ Seleccioná una opción:"
    ),
    "menu_principal": (
        "<b>Menú Principal</b>\n\n"
        "⬇️ Selecciona una opción:"
    ),
    "inicio_pps": (
        "🏭 <b>INICIO DE PPS</b>\n\n"
        "<b>¿Qué es la Práctica Profesional Supervisada?</b>\n\n"
        "🔸 Es una <b>materia obligatoria</b> de la carrera\n"
        "🔸 Se evalúa con condición <b>aprobado</b>\n"
        "🔸 <b>200 horas</b> de duración\n"
        "🔸 Proyecto innovador en empresa o centro de investigación\n\n"
        "❗ <b>Importante:</b> Debe realizarse en un ámbito profesional\n\n"
        "<b>Pasos para iniciar:</b>\n"
        "1\\. Verificar requisitos académicos ✅\n"
        "2\\. Buscar empresa/institución 🏢\n"
        "3\\. Completar documentación inicial 📄\n"
        "4\\. Dejar documentación en Departamento de Electrónica 📄\n"
        "5\\. Esperar aprobación ⌛\n"
        "6\\. Iniciar prácticas 🚀\n\n"
        "👇 <b>Selecciona una opción:</b>"
    ),
    "finalizacion": (
        "🔵 *Finalización de la Práctica*\n\n"
        "1\\) Verificá que cumpliste la carga horaria requerida\\.\n"
        "2\\) Prepará el informe final \\(estructura y formato según cátedra\\)\\.\n"
        "3\\) Pedí certificado/constancia a la empresa \\(si aplica\\)\\.\n"
        "4\\) Entregá informe \\+ documentación final antes de la fecha límite\\.\n\n"
        "📌 Tip: Si te falta el certificado, escribí *'certificado'*\\.\n"
        "Escribí *'informe'* para más detalles sobre el informe final\\."
    ),
    "faq": (
        "❓ *Preguntas frecuentes*\n\n"
        "• *¿Qué pasa si no consigo empresa?* → escribí: no tengo empresa\n"
        "• *¿Qué documentos necesito al inicio?* → escribí: documentos inicio\n"
        "• *¿Cómo es el informe final?* → escribí: informe\n"
        "• *¿Necesito certificado?* → escribí: certificado\n"
    ),
    "contacto": (
        "📩 *Contacto / Cátedra*\n\n"
        "Mail: pps@frce\\.utn\\.edu\\.ar\n"
        "Horarios de consulta: Lunes a Viernes 9:00\\-12:00\n"
        "Aula virtual: Campus Virtual UTN FRC\n"
    ),
    "inicio": (
        "*Inicio de la PPS*\n\n"
        "❗*¿Qué es la Práctica Profesional Supervisada \\(PPS\\)?*\n\n"
        "La PPS es una *materia obligatoria* de la carrera de Ingeniería Electrónica\\.\n"
        "Todos los estudiantes deben realizarla y se evalúa con condición *aprobado*\\.\n\n"
        "Su objetivo es que el/la estudiante pueda *aplicar los conocimientos adquiridos* "
        "en la carrera en un *entorno profesional real*, adquirir experiencia, "
        "vincularse con el ámbito laboral y desarrollar un *proyecto técnico*\\.\n\n"
        "La PPS puede realizarse en una *empresa como en un centro de investigación*\\.\n"
        "Puede desarrollarse en un lugar donde el/la estudiante ya se encuentre trabajando, "
        "ya sea en relación de dependencia, como pasante o investigador\\.\n\n"
        "En todos los casos, debe presentarse un *proyecto innovador* vinculado a la Ingeniería Electrónica, "
        "con una carga horaria total de *200 horas*\\.\n\n"
        "Para comenzar, es necesario cumplir con los requisitos académicos y presentar la documentación correspondiente\\.\n\n"
        "✅ *Primero*: verificá requisitos académicos\n"
        "📄 *Después*: juntá la documentación\n"
    ),
    "requisitos": (
        "✅ *Requisitos académicos para iniciar la PPS*\n\n"
        "Para poder comenzar, el/la estudiante debe:\n"
        "• Tener *todas las asignaturas de 4º año regularizadas*\\.\n"
        "• Tener *todas las asignaturas de 3º año aprobadas*\\.\n\n"
        "📌 Si no cumplís alguno de estos puntos, por el momento no podrás realizar PPS\\."
    ),
    "docs_inicio": (
        "📄 *Documentación para INICIO de PPS*\n\n"
        "1\\) *Formulario 001* \\(completar *digital*, no a mano\\)\n"
        "2\\) *Convenio Marco de Prácticas Supervisadas* \\(la empresa lo completa *una sola vez*\\)\n"
        "3\\) *Convenio Específico de Prácticas Supervisadas* \\(*solo* si el/la estudiante *no* es parte de la empresa ni pasante\\)\n"
        "4\\) El/la estudiante debe enviar *copia de ART*\n\n"
        "🔸 Si la empresa es *monotributista*: enviar *constancia de AFIP*\n\n"
        "Escribí: /f001 /convenio\\_marco /convenio\\_especifico /monotributo /art\n"
        "O escribí las palabras clave directamente\\."
    ),
    "convenio_marco": (
        "📑 *Convenio Marco de PPS*\n\n"
        "• Lo completa la *empresa*\\.\n"
        "• Se presenta *una sola vez* \\(para futuras PPS no se vuelve a completar, salvo que la cátedra indique lo contrario\\)\\.\n\n"
        "Si querés, decime si tu empresa ya tiene convenio marco cargado y te digo qué sigue\\."
    ),
    "convenio_especifico": (
        "📘 *Convenio Específico de PPS*\n\n"
        "⚠️ Solo lo completan estudiantes que *NO* sean parte de la empresa ni pasantes\\.\n\n"
        "Si me decís tu situación:\n"
        "1\\) empleado/a\n"
        "2\\) pasante\n"
        "3\\) externo/a\n"
        "te confirmo si lo necesitás\\."
    ),
    "monotributo": (
        "🧾 *Empresa monotributista*\n\n"
        "Si la empresa es monotributista, se debe enviar *constancia de AFIP* junto con la documentación de inicio\\."
    ),
    "art": (
        "🛡️ *ART*\n\n"
        "El/la estudiante debe enviar *copia de ART* como parte de la documentación de inicio\\.\n"
        "Si no sabés cuál es la ART o cómo pedir la constancia, decime cómo es tu vínculo con la empresa y te guío\\."
    ),
}

# =================== KEYWORDS ===================
KEYWORDS = {
    "inicio": "inicio",
    "comenzar": "inicio",
    "empezar": "inicio",
    "final": "finalizacion",
    "finalizacion": "finalizacion",
    "terminar": "finalizacion",
    "requisitos": "requisitos",
    "docs": "docs_inicio",
    "documentos": "docs_inicio",
    "documentación": "docs_inicio",
    "convenio marco": "convenio_marco",
    "convenio específico": "convenio_especifico",
    "convenio especifico": "convenio_especifico",
    "art": "art",
    "afip": "monotributo",
    "monotributo": "monotributo",
    "informe": "informe",
    "certificado": "certificado",
    "no tengo empresa": "no_empresa",
    "sin empresa": "no_empresa",
}

# =================== TECLADOS DEL BOT ===================
def teclado_menu_principal():
    keyboard = [
        [InlineKeyboardButton("Inicio de la PPS", callback_data="menu_inicio_pps")],
        [InlineKeyboardButton("Finalización de la PPS", callback_data="menu_finalizacion")],
        [InlineKeyboardButton("Preguntas frecuentes", callback_data="menu_faq")],
        [InlineKeyboardButton("Contacto", callback_data="menu_contacto")],
    ]
    return InlineKeyboardMarkup(keyboard)

def teclado_inicio_pps():
    keyboard = [
        [InlineKeyboardButton("✅ Requisitos Académicos", callback_data="requisitos")],
        [InlineKeyboardButton("📄 Documentación Inicial", callback_data="docs_inicio")],
        [InlineKeyboardButton("🏢 No tengo empresa", callback_data="no_empresa")],
        [InlineKeyboardButton("⬅️ Menú Principal", callback_data="menu_principal")]
    ]
    return InlineKeyboardMarkup(keyboard)

# =================== HANDLERS DEL BOT ===================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Comando /start con menú visual"""
    welcome_text = INFO["welcome"]
    await update.message.reply_text(
        welcome_text,
        parse_mode="HTML",
        reply_markup=teclado_menu_principal()
    )

async def menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Comando /menu para mostrar el menú principal"""
    menu_text = INFO["menu_principal"]
    await update.message.reply_text(
        menu_text,
        parse_mode="HTML",
        reply_markup=teclado_menu_principal()
    )

# =================== HANDLERS DEL BOT ===================
async def manejar_botones(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    data = query.data
    logger.info(f"Callback recibido: {data}")

    # MENÚ PRINCIPAL
    if data == "menu_principal":  # CORRECCIÓN: cambié query.data por data
        await query.edit_message_text(
            INFO["menu_principal"],
            parse_mode="HTML",
            reply_markup=teclado_menu_principal()
        )
    
    # INICIO DE PPS
    elif data == "menu_inicio_pps":
        await query.edit_message_text(
            INFO["inicio_pps"],
            parse_mode="HTML",  # CORRECCIÓN: cambié MarkdownV2 por HTML
            reply_markup=teclado_inicio_pps()
        )
    
    # OPCIONES DE INICIO DE PPS
    elif data == "requisitos":
        await query.edit_message_text(
            INFO["requisitos"],
            parse_mode="MarkdownV2"
        )
    
    elif data == "docs_inicio":
        await query.edit_message_text(
            INFO["docs_inicio"],
            parse_mode="MarkdownV2"
        )
    
    elif data == "no_empresa":
        await query.edit_message_text(
            "🏢 *Sin empresa todavía*\n\n"
            "1\\) Contame tu orientación/interés \\(embebidos, potencia, telecom, control, etc\\.\\)\n"
            "2\\) ¿Tenés CV actualizado?\n"
            "3\\) ¿Podés hacer presencial/híbrido?\n\n"
            "Con eso te sugiero un plan para conseguir lugar y armar mails de contacto\\.",
            parse_mode="MarkdownV2"
        )
    
    # OTRAS OPCIONES DEL MENÚ PRINCIPAL
    elif data == "menu_finalizacion":
        await query.edit_message_text(
            INFO["finalizacion"],
            parse_mode="MarkdownV2"
        )
    
    elif data == "menu_faq":
        await query.edit_message_text(
            INFO["faq"],
            parse_mode="MarkdownV2"
        )
    
    elif data == "menu_contacto":
        await query.edit_message_text(
            INFO["contacto"],
            parse_mode="MarkdownV2"
        )
    
    # BOTONES DE DOCUMENTOS (comandos existentes)
    elif data == "f001":
        await f001(query, context)
    elif data == "convenio_marco":
        await query.edit_message_text(INFO["convenio_marco"], parse_mode="MarkdownV2")
    elif data == "convenio_especifico":
        await query.edit_message_text(INFO["convenio_especifico"], parse_mode="MarkdownV2")
    elif data == "art":
        await query.edit_message_text(INFO["art"], parse_mode="MarkdownV2")
    elif data == "monotributo":
        await query.edit_message_text(INFO["monotributo"], parse_mode="MarkdownV2")

async def inicio(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message:
        await update.message.reply_text(
            INFO["inicio_pps"],
            parse_mode="HTML",  # CORRECCIÓN: cambié MarkdownV2 por HTML
            reply_markup=teclado_inicio_pps()
        )
    elif update.callback_query:
        await update.callback_query.edit_message_text(
            INFO["inicio_pps"],
            parse_mode="HTML",  # CORRECCIÓN: cambié MarkdownV2 por HTML
            reply_markup=teclado_inicio_pps()
        )

async def finalizacion(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message:
        await update.message.reply_text(INFO["finalizacion"], parse_mode="MarkdownV2")
    elif update.callback_query:
        await update.callback_query.edit_message_text(INFO["finalizacion"], parse_mode="MarkdownV2")

async def faq(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message:
        await update.message.reply_text(INFO["faq"], parse_mode="MarkdownV2")
    elif update.callback_query:
        await update.callback_query.edit_message_text(INFO["faq"], parse_mode="MarkdownV2")

async def contacto(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message:
        await update.message.reply_text(INFO["contacto"], parse_mode="MarkdownV2")
    elif update.callback_query:
        await update.callback_query.edit_message_text(INFO["contacto"], parse_mode="MarkdownV2")

async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = (update.message.text or "").strip().lower()

    intent = None
    for k, v in KEYWORDS.items():
        if k in text:
            intent = v
            break

    if intent == "inicio":
        return await inicio(update, context)
    elif intent == "finalizacion":
        return await finalizacion(update, context)
    elif intent == "informe":
        return await update.message.reply_text(
            "📝 *Informe final*\n\n"
            "Decime qué te piden en tu cátedra \\(índice / formato / extensión\\) y te armo una plantilla\\.\n"
            "Si ya tenés el enunciado, pegalo acá\\.",
            parse_mode="MarkdownV2",
        )
    elif intent == "certificado":
        return await update.message.reply_text(
            "📄 *Certificado / Constancia*\n\n"
            "En general lo emite la empresa e incluye: nombre, DNI, período, horas y tareas\\.\n"
            "Si querés, te genero un modelo para que lo firmen\\.",
            parse_mode="MarkdownV2",
        )
    elif intent == "no_empresa":
        return await update.message.reply_text(
            "🏢 *Sin empresa todavía*\n\n"
            "1\\) Contame tu orientación/interés \\(embebidos, potencia, telecom, control, etc\\.\\)\n"
            "2\\) ¿Tenés CV actualizado?\n"
            "3\\) ¿Podés hacer presencial/híbrido?\n\n"
            "Con eso te sugiero un plan para conseguir lugar y armar mails de contacto\\.",
            parse_mode="MarkdownV2",
        )
    elif intent == "docs_inicio":
        return await update.message.reply_text(INFO["docs_inicio"], parse_mode="MarkdownV2")
    elif intent == "requisitos":
        return await update.message.reply_text(INFO["requisitos"], parse_mode="MarkdownV2")
    elif intent == "convenio_marco":
        return await update.message.reply_text(INFO["convenio_marco"], parse_mode="MarkdownV2")
    elif intent == "convenio_especifico":
        return await update.message.reply_text(INFO["convenio_especifico"], parse_mode="MarkdownV2")
    elif intent == "art":
        return await update.message.reply_text(INFO["art"], parse_mode="MarkdownV2")
    elif intent == "monotributo":
        return await update.message.reply_text(INFO["monotributo"], parse_mode="MarkdownV2")
    else:
        await update.message.reply_text(
            "No estoy seguro qué necesitás 🙃\n"
            "Usá /start para ver el menú principal o escribí alguna de estas palabras:\n"
            "\\- 'inicio' para comenzar PPS\n"
            "\\- 'documentos' para ver documentación\n"
            "\\- 'requisitos' para ver requisitos académicos\n"
            "\\- 'final' para finalización",
            parse_mode="MarkdownV2"
        )

async def f001(update: Update, context: ContextTypes.DEFAULT_TYPE):
    texto = (
        "🧾 *Formulario 001*\n\n"
        "📌 Debe completarse *en formato digital*\\.\n\n"
        "Te dejo:\n"
        "1\\) el formulario vacío\n"
        "2\\) un ejemplo completo\n\n"
        "Luego escribime *'preguntas f001'* para ver dudas típicas\\."
    )
    
    # Determinar si es mensaje o callback query
    if isinstance(update, Update) and update.message:
        user_message = update.message
        await user_message.reply_text(texto, parse_mode="MarkdownV2")
    elif isinstance(update, Update) and update.callback_query:
        user_message = update.callback_query.message
        await user_message.reply_text(texto, parse_mode="MarkdownV2")
    else:
        # Si es el callback query directamente
        user_message = update.message if hasattr(update, 'message') else None
        if user_message:
            await user_message.reply_text(texto, parse_mode="MarkdownV2")
        else:
            return

    if F001_PDF.exists():
        await user_message.reply_document(document=open(F001_PDF, "rb"), filename=F001_PDF.name)
    else:
        await user_message.reply_text("⚠️ No encuentro el PDF del Formulario 001 en la carpeta /docs\\.")

    if F001_EJEMPLO_PDF.exists():
        await user_message.reply_document(document=open(F001_EJEMPLO_PDF, "rb"), filename=F001_EJEMPLO_PDF.name)
    else:
        await user_message.reply_text("⚠️ No encuentro el PDF de ejemplo del Formulario 001 en la carpeta /docs\\.")

# =================== CONFIGURACIÓN DEL BOT ===================
def setup_telegram_app():
    global telegram_app
    
    telegram_app = Application.builder().token(TOKEN).build()
    
    telegram_app.add_handler(CommandHandler("start", start))
    telegram_app.add_handler(CommandHandler("menu", menu))
    telegram_app.add_handler(CommandHandler("inicio", inicio))
    telegram_app.add_handler(CommandHandler("finalizacion", finalizacion))
    telegram_app.add_handler(CommandHandler("faq", faq))
    telegram_app.add_handler(CommandHandler("contacto", contacto))
    telegram_app.add_handler(CommandHandler("f001", f001))
    
    telegram_app.add_handler(CallbackQueryHandler(manejar_botones))
    telegram_app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    
    logger.info("✅ Aplicación de Telegram configurada correctamente")

async def setup_webhook_async():
    try:
        render_service_name = os.environ.get('RENDER_SERVICE_NAME', 'pps-electronica-utnfrc-bot')
        webhook_url = f"https://{render_service_name}.onrender.com/webhook"
        
        await telegram_app.bot.set_webhook(
            url=webhook_url,
            allowed_updates=Update.ALL_TYPES,
            drop_pending_updates=True
        )
        
        logger.info(f"🌐 Webhook configurado en: {webhook_url}")
        return True
    except Exception as e:
        logger.error(f"❌ Error configurando webhook: {e}")
        return False

def setup_webhook_sync():
    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        success = loop.run_until_complete(setup_webhook_async())
        loop.close()
        return success
    except Exception as e:
        logger.error(f"❌ Error en setup webhook sync: {e}")
        return False

def run_flask_server():
    port = int(os.environ.get('PORT', 10000))
    logger.info(f"🌍 Iniciando servidor Flask en puerto {port}")
    serve(flask_app, host='0.0.0.0', port=port, threads=4)

def run_polling_mode():
    global keep_alive
    
    try:
        render_service_name = os.environ.get('RENDER_SERVICE_NAME', 'pps-electronica-utnfrc-bot')
        app_url = f"https://{render_service_name}.onrender.com"
        
        keep_alive = KeepAliveService(app_url)
        keep_alive.start(interval_minutes=8)
        
        flask_thread = threading.Thread(target=run_flask_server, daemon=True)
        flask_thread.start()
        
        print("✅ Servidor Flask iniciado")
        print("✅ Keep-alive activado")
        print("✅ Iniciando bot en modo polling...")
        print("=" * 60)
        
        time.sleep(2)
        
        telegram_app.run_polling(
            poll_interval=1.0,
            timeout=30,
            drop_pending_updates=True,
            allowed_updates=Update.ALL_TYPES
        )
        
    except Exception as e:
        logger.error(f"❌ Error en modo polling: {e}")
        raise

def run_webhook_mode():
    try:
        if not setup_webhook_sync():
            print("❌ Falló la configuración del webhook, cambiando a polling...")
            return False
        
        port = int(os.environ.get('PORT', 10000))
        logger.info(f"🌍 Servidor web en puerto {port}")
        print(f"✅ Webhook configurado: https://pps-electronica-utnfrc-bot.onrender.com/webhook")
        print("✅ Bot listo para recibir mensajes")
        print("=" * 60)
        
        serve(flask_app, host='0.0.0.0', port=port, threads=4)
        return True
        
    except Exception as e:
        logger.error(f"❌ Error en modo webhook: {e}")
        return False

def main():
    print("=" * 60)
    print("🚀 INICIANDO BOT PPS - INGENIERÍA ELECTRÓNICA UTN FRC")
    print("=" * 60)
    print(f"Modo: {'WEBHOOK' if WEBHOOK_MODE else 'POLLING + KEEP-ALIVE'}")
    print(f"Token: {TOKEN[:10]}...")
    print(f"Directorio docs: {DOCS_DIR}")
    print("=" * 60)
    
    setup_telegram_app()
    
    use_webhook = WEBHOOK_MODE
    
    if use_webhook:
        print("🔄 Intentando modo webhook...")
        success = run_webhook_mode()
        if not success:
            print("🔄 Cambiando a modo polling...")
            use_webhook = False
    
    if not use_webhook:
        print("🔄 Iniciando en modo polling...")
        try:
            run_polling_mode()
            
        except Exception as e:
            logger.error(f"❌ Error en modo polling: {e}")
            print(f"❌ Error: {e}")
            import traceback
            traceback.print_exc()

if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        print("\n🛑 Bot detenido por el usuario")
        if keep_alive:
            keep_alive.running = False
    except Exception as e:
        logger.error(f"❌ Error crítico: {e}")
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()