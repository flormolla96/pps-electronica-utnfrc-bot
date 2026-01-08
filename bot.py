import os
from flask import Flask
import threading

from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, ContextTypes, filters
from pathlib import Path

DOCS_DIR = Path(__file__).parent / "docs"
DOCS_DIR.mkdir(exist_ok=True)  # Crear carpeta si no existe
F001_PDF = DOCS_DIR / "Formulario_001.pdf"
F001_EJEMPLO_PDF = DOCS_DIR / "Ejemplo_Formulario_001.pdf"

TOKEN = os.getenv("BOT_TOKEN")

INFO = {
    "finalizacion": (
        "🔵 *Finalización de la Práctica*\n\n"
        "1) Verificá que cumpliste la carga horaria requerida\\.\n"
        "2) Prepará el informe final \\(estructura y formato según cátedra\\)\\.\n"
        "3) Pedí certificado/constancia a la empresa \\(si aplica\\)\\.\n"
        "4) Entregá informe \\+ documentación final antes de la fecha límite\\.\n\n"
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
        "Mail: \\(completá acá\\)\n"
        "Horarios de consulta: \\(completá acá\\)\n"
        "Aula virtual / link: \\(completá acá\\)\n"
    ),
        "inicio": (
        "<b>Inicio de la PPS</b>\n\n"
        "❗<b>¿Qué es la Práctica Profesional Supervisada (PPS)?</b>\n\n"
        "La PPS es una <b>materia obligatoria</b> de la carrera de Ingeniería Electrónica.\n"
        "Todos los estudiantes deben realizarla y se evalúa con condición <b>aprobado</b>.\n\n"
        "Su objetivo es que el/la estudiante pueda <b>aplicar los conocimientos adquiridos</b> "
        "en la carrera en un <b>entorno profesional real</b>, adquirir experiencia, "
        "vincularse con el ámbito laboral y desarrollar un <b>proyecto técnico</b>.\n\n"
        "La PPS puede realizarse en una <b>empresa como en un centro de investigación</b>.\n"
        "Puede desarrollarse en un lugar donde el/la estudiante ya se encuentre trabajando, "
        "ya sea en relación de dependencia, como pasante o investigador.\n\n"
        "En todos los casos, debe presentarse un <b>proyecto innovador</b> vinculado a la Ingeniería Electrónica, "
        "con una carga horaria total de <b>200 horas</b>.\n\n"
        "Para comenzar, es necesario cumplir con los requisitos académicos y presentar la documentación correspondiente.\n\n"
        "✅ <b>Primero</b>: verificá requisitos académicos → /requisitos\n"
        "📄 <b>Después</b>: juntá la documentación → /docs_inicio\n"
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
        "1) empleado/a\n"
        "2) pasante\n"
        "3) externo/a\n"
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

# -----------------------------
# Comandos
# -----------------------------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = (
        "👋 ¡Hola\\! Soy el bot de *Prácticas Profesionales Supervisadas \\(PPS\\)* de la \\(UTN–FRC\\)\\ carrera *Ingenieria Electrónica*\\.\n\n"
        "📌 *Inicio de PPS*\n"
        "/inicio → guía general\n"
        "/requisitos → requisitos académicos\n"
        "/docs\\_inicio → documentación de inicio\n"
        "📌 *Finalización de PPS*\n"
        "/finalizacion\n\n"
        "ℹ️ Otros\n"
        "/faq\n"
        "/contacto\n\n"
        "También podés escribir: *inicio*, *final*, *documentos inicio*, *no tengo empresa*, *certificado*\\.\n\n"
        "¿En qué puedo ayudarte\\?"
    )
    await update.message.reply_text(msg, parse_mode="MarkdownV2")


async def inicio(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(INFO["inicio"], parse_mode="HTML")

async def finalizacion(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(INFO["finalizacion"], parse_mode="MarkdownV2")

async def faq(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(INFO["faq"], parse_mode="MarkdownV2")

async def contacto(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(INFO["contacto"], parse_mode="MarkdownV2")

# -----------------------------
# Respuestas por texto (keywords)
# -----------------------------
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

async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = (update.message.text or "").strip().lower()

    # Buscar palabra clave
    intent = None
    for k, v in KEYWORDS.items():
        if k in text:
            intent = v
            break

    # Manejar intents
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
        # default
        await update.message.reply_text(
            "No estoy seguro qué necesitás 🙃\n"
            "Probá con: /inicio, /finalizacion, /faq o escribí 'inicio' / 'final' / 'informe'\\.",
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
    await update.message.reply_text(texto, parse_mode="MarkdownV2")

    if F001_PDF.exists():
        await update.message.reply_document(document=open(F001_PDF, "rb"), filename=F001_PDF.name)
    else:
        await update.message.reply_text("⚠️ No encuentro el PDF del Formulario 001 en la carpeta /docs\\.")

    if F001_EJEMPLO_PDF.exists():
        await update.message.reply_document(document=open(F001_EJEMPLO_PDF, "rb"), filename=F001_EJEMPLO_PDF.name)
    else:
        await update.message.reply_text("⚠️ No encuentro el PDF de ejemplo del Formulario 001 en la carpeta /docs\\.")

async def requisitos(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(INFO["requisitos"], parse_mode="MarkdownV2")

async def docs_inicio(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(INFO["docs_inicio"], parse_mode="MarkdownV2")

async def convenio_marco(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(INFO["convenio_marco"], parse_mode="MarkdownV2")

async def convenio_especifico(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(INFO["convenio_especifico"], parse_mode="MarkdownV2")

async def monotributo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(INFO["monotributo"], parse_mode="MarkdownV2")

async def art(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(INFO["art"], parse_mode="MarkdownV2")


def run_web():
    app = Flask(__name__)

    @app.route("/")
    def home():
        return "Bot PPS UTN FRC activo"

    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)

# -----------------------------
# Main
# -----------------------------
def main():
    app = ApplicationBuilder().token(TOKEN).build()

    # Agregar todos los handlers de comandos
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("inicio", inicio))
    app.add_handler(CommandHandler("finalizacion", finalizacion))
    app.add_handler(CommandHandler("faq", faq))
    app.add_handler(CommandHandler("contacto", contacto))
    app.add_handler(CommandHandler("f001", f001))
    app.add_handler(CommandHandler("requisitos", requisitos))
    app.add_handler(CommandHandler("docs_inicio", docs_inicio))
    app.add_handler(CommandHandler("convenio_marco", convenio_marco))
    app.add_handler(CommandHandler("convenio_especifico", convenio_especifico))
    app.add_handler(CommandHandler("monotributo", monotributo))
    app.add_handler(CommandHandler("art", art))

    # Handler para mensajes de texto
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))

    threading.Thread(target=run_web, daemon=True).start()
    
    print("🤖 Bot en ejecución...")
    app.run_polling()

if __name__ == "__main__":
    main()