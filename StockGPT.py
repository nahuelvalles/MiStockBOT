import os
import re
from datetime import datetime, timedelta
import telebot
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from dotenv import load_dotenv
import firebase_admin
from firebase_admin import credentials as firebase_cred, firestore


load_dotenv()

# Configuración de Firebase
firebase_creds = firebase_cred.Certificate({
    "type": "service_account",
    "project_id": os.getenv("FIREBASE_PROJECT_ID"),
    "private_key_id": os.getenv("FIREBASE_PRIVATE_KEY_ID"),
    "private_key": os.getenv("FIREBASE_PRIVATE_KEY").replace('\\n', '\n'),
    "client_email": os.getenv("FIREBASE_CLIENT_EMAIL"),
    "token_uri": "https://oauth2.googleapis.com/token",
})

firebase_admin.initialize_app(firebase_creds)
db = firestore.client()


# ========== Configuraciones ==========
TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')

# ========== Configuración de Service Account ==========
SERVICE_ACCOUNT_INFO = {
    "type": "service_account",
    "project_id": os.getenv("GOOGLE_PROJECT_ID"),
    "private_key_id": os.getenv("GOOGLE_PRIVATE_KEY_ID"),
    "private_key": os.getenv("GOOGLE_PRIVATE_KEY").replace('\\n', '\n'),
    "client_email": os.getenv("GOOGLE_CLIENT_EMAIL"),
    "client_id": os.getenv("GOOGLE_CLIENT_ID"),
    "auth_uri": "https://accounts.google.com/o/oauth2/auth",
    "token_uri": "https://oauth2.googleapis.com/token",
    "auth_provider_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs",
    "client_x509_cert_url": f"https://www.googleapis.com/robot/v1/metadata/x509/{os.getenv('GOOGLE_CLIENT_EMAIL').replace('@', '%40')}"
}

# ========== Configuración de OAuth ==========
OAUTH_CLIENT_CONFIG = {
    "installed": {
        "client_id": os.getenv("GOOGLE_OAUTH_CLIENT_ID"),
        "client_secret": os.getenv("GOOGLE_OAUTH_CLIENT_SECRET"),
        "redirect_uris": [os.getenv("GOOGLE_REDIRECT_URI", "http://localhost")],
        "auth_uri": "https://accounts.google.com/o/oauth2/auth",
        "token_uri": "https://oauth2.googleapis.com/token"
    }
}

SCOPES = [
    'https://www.googleapis.com/auth/spreadsheets',
    'https://www.googleapis.com/auth/drive.file'
]

bot = telebot.TeleBot(TELEGRAM_BOT_TOKEN)
user_states = {}

# ========== Helpers de OAuth y Sheets ==========

def get_credentials(chat_id, message):
    """Obtiene credenciales desde Firestore."""
    doc_ref = db.collection("users").document(str(chat_id))
    doc = doc_ref.get()
    
    creds = None
    if doc.exists:
        data = doc.to_dict()
        # Construye las credenciales desde Firestore
        creds = Credentials(
            token=data.get("token"),
            refresh_token=data.get("refresh_token"),
            token_uri="https://oauth2.googleapis.com/token",
            client_id=OAUTH_CLIENT_CONFIG["installed"]["client_id"],
            client_secret=OAUTH_CLIENT_CONFIG["installed"]["client_secret"],
            scopes=SCOPES
        )
    
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            try:
                creds.refresh(Request())
                # Actualiza el token en Firestore
                doc_ref.set({
                    "token": creds.token,
                    "refresh_token": creds.refresh_token,
                    "expiry": creds.expiry.isoformat()
                })
            except Exception as e:
                print(f"Error al refrescar token: {e}")
                return None
        else:
            # Inicia flujo OAuth
            flow = InstalledAppFlow.from_client_config(
                OAUTH_CLIENT_CONFIG, SCOPES, redirect_uri='urn:ietf:wg:oauth:2.0:oob'
            )
            auth_url, _ = flow.authorization_url(
                access_type='offline', include_granted_scopes='true'
            )
            user_states[chat_id] = {'awaiting_oauth_code': True, 'flow': flow}
            bot.send_message(
                chat_id,
                "🤖 ¡Bienvenid@ a MiStockBOT! \nNecesito autorización para crear una hoja de Google Sheets, visita el siguiente enlace:\n\n"
                f"{auth_url}\n\n"
                "Copia el código que Google te brinde y enviámelo."
            )
            return None
    return creds

def ensure_user_sheet(chat_id):

    # Obtener credenciales desde Firestore
    creds = get_credentials(chat_id, None)
    
    if not creds:
        raise Exception("No se encontraron credenciales para el usuario.")
    
    client = gspread.authorize(creds)
    
    try:
        ss = client.open('StockGPT')
    except gspread.SpreadsheetNotFound:
        ss = client.create('StockGPT')
        # Crear hojas y encabezados
        prod = ss.add_worksheet(title="Productos", rows="100", cols="3")
        vent = ss.add_worksheet(title="Ventas", rows="100", cols="3")
        prod.update('A1:C1', [['Producto','Precio','Stock']])
        vent.update('A1:C1', [['Fecha','Detalle','Total']])
        prod.format("B", {"numberFormat":{"type":"NUMBER","pattern":"#,##0.00"}})
        prod.format("C", {"numberFormat":{"type":"NUMBER","pattern":"#,##0.0"}})
        vent.format("C", {"numberFormat":{"type":"NUMBER","pattern":"#,##0.00"}})
    
    prod_sheet = ss.worksheet("Productos")
    vent_sheet = ss.worksheet("Ventas")
    return prod_sheet, vent_sheet

# ========== OAuth: recibir código ==========
@bot.message_handler(func=lambda m: user_states.get(m.chat.id, {}).get('awaiting_oauth_code'))
def receive_oauth_code(message):
    chat_id = message.chat.id
    state = user_states.get(chat_id)
    code = message.text.strip()
    flow = state.get('flow')
    try:
        flow.fetch_token(code=code)
        creds = flow.credentials
        # Guardar en Firestore
        doc_ref = db.collection("users").document(str(chat_id))
        doc_ref.set({
            "token": creds.token,
            "refresh_token": creds.refresh_token,
            "expiry": creds.expiry.isoformat()
        })
        
        bot.send_message(chat_id, "✅ Autorización exitosa. Para ver los comandos disponibles escribe /menu")
        ensure_user_sheet(chat_id)
        
    except Exception as e: 
        bot.send_message(chat_id, f"❌ Error en autorización: {e}\nIntenta de nuevo.")
    finally: 
        user_states.pop(chat_id, None)

# ========== Funciones Base ==========
def agregar_actualizar_producto(nombre, stock, precio=None, chat_id=None):
    stock = float(str(stock).replace(',', '.'))
    if precio is not None:
        precio = float(str(precio).replace(',', '.'))
    prod_sheet, _ = ensure_user_sheet(chat_id)
    registros = prod_sheet.get_all_records(value_render_option='UNFORMATTED_VALUE')
    for idx, reg in enumerate(registros):
        if reg['Producto'].lower() == nombre.lower():
            nuevo_stock = reg['Stock'] + stock
            if nuevo_stock < 0:
                raise ValueError("Stock no puede ser negativo")
            prod_sheet.update_cell(idx+2, 3, round(nuevo_stock,1))
            if precio is not None:
                prod_sheet.update_cell(idx+2, 2, round(precio,2))
            return "actualizado"
    # Nuevo producto
    nuevos = [nombre.strip().title(),
              round(precio,2) if precio is not None else "",
              round(stock,1)]
    prod_sheet.append_row(nuevos)
    return "nuevo"

def registrar_venta(productos, total, chat_id=None):
    total = float(str(total).replace(',', '.'))
    prod_sheet, vent_sheet = ensure_user_sheet(chat_id)
    registros = prod_sheet.get_all_records(value_render_option='UNFORMATTED_VALUE')
    # Verificar stock
    for p in productos:
        p['producto'] = p['producto'].lower()
        p['cantidad'] = round(float(str(p['cantidad']).replace(',', '.')),1)
        for reg in registros:
            if reg['Producto'].lower()==p['producto']:
                if reg['Stock'] < p['cantidad']:
                    raise ValueError(f"Stock insuficiente de {p['producto']}")
                break
        else:
            raise ValueError(f"Producto {p['producto']} no encontrado")
    # Registrar
    fecha  = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    det    = " | ".join([f"{p['cantidad']}KG {p['producto']}" for p in productos])
    vent_sheet.append_row([fecha, det, round(total,2)])
    # Actualizar stock
    for p in productos:
        registros = prod_sheet.get_all_records(value_render_option='UNFORMATTED_VALUE')
        for idx, reg in enumerate(registros):
            if reg['Producto'].lower()==p['producto']:
                nuevo = reg['Stock'] - p['cantidad']
                prod_sheet.update_cell(idx+2,3,round(nuevo,1))
                break

def obtener_ventas(rango_dias=None, chat_id=None):
    _, vent_sheet = ensure_user_sheet(chat_id)
    regs = vent_sheet.get_all_records(value_render_option='UNFORMATTED_VALUE')
    hoy = datetime.now()
    
    if not rango_dias:
        return regs
    
    out = []
    for v in regs:
        fv = datetime.strptime(v['Fecha'], "%Y-%m-%d %H:%M:%S")
        
        if rango_dias == 1:  # Fecha de hoy
            if fv.date() == hoy.date():
                out.append(v)
                
        elif rango_dias == 30:  # Este mes y año
            if fv.month == hoy.month and fv.year == hoy.year:
                out.append(v)
                
    return out

# ========== Handlers de Comandos ==========
@bot.message_handler(commands=['reset'])
def cmd_reset(message):
    chat_id = message.chat.id
    # Eliminar de Firestore
    doc_ref = db.collection("users").document(str(chat_id))
    if doc_ref.get().exists:
        doc_ref.delete()
        bot.send_message(chat_id, "♻️ Historial reiniciado. Usa /authorize para vincular Google de nuevo.")
    else:
        bot.send_message(chat_id, "ℹ️ No hay historial previo para eliminar.")

@bot.message_handler(commands=['start','authorize'])
def cmd_start(message):
    creds = get_credentials(message.chat.id, message)
    if creds:
        bot.send_message(message.chat.id, "✅ Listo! Usa /ayuda para ver comandos.")

@bot.message_handler(commands=['menu','ayuda'])
def mostrar_ayuda(message):
    if not get_credentials(message.chat.id, message):
        return
    text = (
        "🏪 *MiStockBOT* 🛒\n\n"
        "*/venta* - Registra una venta\n"
        "*/consultar* - Consulta Stock o Ventas\n"
        "*/agregarstock* - Añadir/Actualizar Producto\n"
        "*/actualizar* - Cambiar precio de producto\n"
        "*/authorize* - Reautorizar Google\n"
        "*/ayuda* - Este mensaje"
    )
    bot.send_message(message.chat.id, text, parse_mode='Markdown')

@bot.message_handler(commands=['venta'])
def iniciar_venta(message):
    if not get_credentials(message.chat.id, message):
        return
    cid = message.chat.id
    user_states[cid] = {'paso':'productos','productos':[]}
    bot.send_message(cid,
        "📝 *Registro de Venta*:\n"
        "Puedes ingresar tu producto de la siguiente manera:"
        "\n KG Producto"
        "\n Ej. 2.5 Manzana Roja o 2 Pera"
        "\n También puedes utilizarlo como unidades:"
        "\n Ej. 4 Pepsi o 12 Huevo",
        parse_mode='Markdown'
    )

@bot.message_handler(func=lambda m: user_states.get(m.chat.id,{}).get('paso')=='productos')
def procesar_producto(m):
    cid = m.chat.id
    txt = m.text.strip()
    try:
        match = re.match(r'^(\d+\.?\d*)\s*(?:kg|kgs?)?\s*(.+)$', txt, re.IGNORECASE)
        if not match: raise
        cantidad = round(float(match.group(1).replace(',','.')),1)
        producto = match.group(2).strip().title()
        user_states[cid]['productos'].append({'producto':producto,'cantidad':cantidad})
        markup = telebot.types.ReplyKeyboardMarkup(one_time_keyboard=True)
        markup.add('✅ Sí','❌ No')
        msg = bot.send_message(
            cid,
            f"➕ Añadido: {cantidad}KG de {producto}\n¿Vendiste algo más?",
            reply_markup=markup
        )
        bot.register_next_step_handler(msg, procesar_confirmacion)
    except:
        bot.send_message(
            cid,
            "❌ Formato incorrecto. Ej: `3.5 Manzana Verde`",
            parse_mode='Markdown'
        )

def procesar_confirmacion(m):
    cid = m.chat.id
    resp = m.text.lower()
    if resp in ['sí','si','s','✅ sí']:
        bot.send_message(cid, "Ingresa el producto:")
    else:
        user_states[cid]['paso']='total'
        bot.send_message(cid, "💵 *Ingrese el monto total de la venta:*\n Ej. '500' o '450.75'", parse_mode='Markdown')

@bot.message_handler(func=lambda m: user_states.get(m.chat.id,{}).get('paso')=='total')
def finalizar_venta(m):
    cid = m.chat.id
    try:
        total = round(float(m.text.replace(',','.')),2)
        productos = user_states[cid]['productos']
        registrar_venta(productos, total, chat_id=cid)
        resumen = "\n".join([f"- {p['cantidad']}KG {p['producto']}" for p in productos])
        bot.send_message(
            cid,
            f"✅ *Venta registrada!* 🎉\n📝 Detalle:\n{resumen}\n💵 Total: ${total:.2f}",
            parse_mode='Markdown'
        )
    except Exception as e:
        bot.send_message(cid, f"❌ Error: {e}")
    finally:
        user_states.pop(cid,None)

@bot.message_handler(commands=['agregarstock'])
def iniciar_agregar_stock(m):
    if not get_credentials(m.chat.id, m):
        return
    cid = m.chat.id
    user_states[cid] = {'paso':'nombre_producto'}
    bot.send_message(cid, "📦 *Ingrese el nombre del producto:*", parse_mode='Markdown')

@bot.message_handler(func=lambda m: user_states.get(m.chat.id,{}).get('paso')=='nombre_producto')
def procesar_nombre_producto(m):
    cid = m.chat.id
    user_states[cid] = {
        'paso':'cantidad_producto',
        'producto': m.text.strip().title()
    }
    bot.send_message(cid, "🔢 *Ingrese la cantidad a agregar (KG o Unidades):*", parse_mode='Markdown')

@bot.message_handler(func=lambda m: user_states.get(m.chat.id,{}).get('paso')=='cantidad_producto')
def procesar_cantidad(m):
    cid = m.chat.id
    try:
        cantidad = round(float(m.text.replace(',','.')),1)
        user_states[cid].update({'cantidad':cantidad,'paso':'precio_producto'})
        markup = telebot.types.ReplyKeyboardMarkup(one_time_keyboard=True)
        markup.add('💰 Sí','🚫 No')
        bot.send_message(cid, "🔄 ¿Actualizar precio del producto?", reply_markup=markup)
    except:
        bot.send_message(cid, "❌ Valor inválido. Ej: `5` o `5.5`", parse_mode='Markdown')

@bot.message_handler(func=lambda m: user_states.get(m.chat.id,{}).get('paso')=='precio_producto')
def procesar_opcion_precio(m):
    cid = m.chat.id
    resp = m.text.lower()
    if resp in ['sí','si','s','💰 sí']:
        user_states[cid]['paso']='ingresar_precio'
        bot.send_message(cid, "💵 *Ingrese el nuevo precio (por KG o Unidad):*", parse_mode='Markdown')
    else:
        try:
            res = agregar_actualizar_producto(
                user_states[cid]['producto'],
                user_states[cid]['cantidad'],
                chat_id=cid
            )
            bot.send_message(cid, f"✅ *Stock {res}* ✔️", parse_mode='Markdown')
        except Exception as e:
            bot.send_message(cid, f"❌ Error: {e}")
        finally:
            user_states.pop(cid,None)

@bot.message_handler(func=lambda m: user_states.get(m.chat.id,{}).get('paso')=='ingresar_precio')
def procesar_precio(m):
    cid = m.chat.id
    estado = user_states[cid]
    try:
        precio = round(float(m.text.replace(',','.')),2)
        if precio <= 0:
            raise ValueError("El precio debe ser > 0")
        res = agregar_actualizar_producto(
            estado['producto'], estado['cantidad'], precio, chat_id=cid
        )
        bot.send_message(
            cid,
            f"✅ *Producto {res} exitosamente!* 🏷️{estado['producto']}\n"
            f"📦 {estado['cantidad']}KG\n💵 ${precio:.2f}",
            parse_mode='Markdown'
        )
    except Exception as e:
        bot.send_message(cid, f"❌ {e}\nEj: `150.50`", parse_mode='Markdown')
    finally:
        user_states.pop(cid,None)

@bot.message_handler(commands=['actualizar'])
def iniciar_actualizar_precio(m):
    if not get_credentials(m.chat.id, m):
        return
    cid = m.chat.id
    prod_sheet, _ = ensure_user_sheet(cid)
    regs = prod_sheet.get_all_records()
    if not regs:
        return bot.send_message(cid, "📭 No hay productos en inventario")
    lista = "\n".join([f"• {p['Producto']}" for p in regs])
    msg = bot.send_message(
        cid,
        f"📋 *Productos actuales en Inventario:* \n{lista}\n\n"
        "Escribe el nombre del producto del cual quieres actualizar el precio:",
        parse_mode='Markdown'
    )
    bot.register_next_step_handler(msg, procesar_producto_actualizar)

def procesar_producto_actualizar(m):
    cid = m.chat.id
    nombre = m.text.strip().title()
    prod_sheet, _ = ensure_user_sheet(cid)
    regs = prod_sheet.get_all_records()
    for reg in regs:
        if reg['Producto'].lower()==nombre.lower():
            user_states[cid] = {'paso':'actualizar_precio','producto':nombre}
            return bot.send_message(
                cid,
                f"🏷️ {nombre}\n💵 Ingresa nuevo precio:",
                parse_mode='Markdown'
            )
    bot.send_message(cid, f"❌ '{nombre}' No encontrado. Intenta otra vez.")
    bot.register_next_step_handler(m, procesar_producto_actualizar)

@bot.message_handler(func=lambda m: user_states.get(m.chat.id,{}).get('paso')=='actualizar_precio')
def actualizar_precio_producto(m):
    cid = m.chat.id
    estado = user_states[cid]
    try:
        nuevo = round(float(m.text.replace(',','.')),2)
        if nuevo <= 0:
            raise ValueError("El precio debe ser > 0")
        prod_sheet, _ = ensure_user_sheet(cid)
        regs = prod_sheet.get_all_records()
        for idx, reg in enumerate(regs):
            if reg['Producto'].lower()==estado['producto'].lower():
                prod_sheet.update_cell(idx+2,2,nuevo)
                break
        bot.send_message(
            cid,
            f"✅ Precio actualizado!\n• {estado['producto']}: ${nuevo:.2f}",
            parse_mode='Markdown'
        )
    except Exception as e:
        bot.send_message(cid, f"❌ {e}\nEj: `150.50`")
    finally:
        user_states.pop(cid,None)

@bot.message_handler(commands=['consultar'])
def consultar_menu(m):
    if not get_credentials(m.chat.id, m):
        return
    cid = m.chat.id
    markup = telebot.types.ReplyKeyboardMarkup(one_time_keyboard=True)
    markup.row('📦 Stock Actual','📊 Ventas')
    bot.send_message(cid, "¿Qué deseas consultar?", reply_markup=markup)

@bot.message_handler(func=lambda m: m.text.lower() in ['📦 stock actual','stock'])
def consultar_stock(m):
    cid = m.chat.id
    prod_sheet, _ = ensure_user_sheet(cid)
    regs = prod_sheet.get_all_records(value_render_option='UNFORMATTED_VALUE')
    if not regs:
        return bot.send_message(cid, "📭 No hay productos")
    lista = "\n".join([f"• {p['Producto']}: {p['Stock']:.1f}KG" for p in regs])
    bot.send_message(
        cid,
        f"📦 *Inventario* 📋\n\n{lista}\nTotal: {len(regs)}",
        parse_mode='Markdown'
    )

@bot.message_handler(func=lambda m: m.text.lower() in ['📊 ventas','ventas'])
def consultar_ventas(m):
    cid = m.chat.id
    markup = telebot.types.ReplyKeyboardMarkup(one_time_keyboard=True)
    markup.row('📅 Hoy','🗓 Este Mes','📂 Historial')
    bot.send_message(cid, "🔍 Selecciona período:", reply_markup=markup)

@bot.message_handler(func=lambda m: m.text.lower() in ['📅 hoy','hoy','🗓 este mes','este mes','📂 historial','historial'])
def procesar_consulta_ventas(m):
    cid = m.chat.id
    txt = m.text.lower()
    
    # Obtener ventas del período solicitado
    if 'hoy' in txt:
        ventas_periodo = obtener_ventas(1, chat_id=cid)
        titulo = 'hoy'
        msg_no_ventas = "📭 No tienes ventas registradas hoy."
    elif 'mes' in txt:
        ventas_periodo = obtener_ventas(30, chat_id=cid)
        titulo = 'este mes'
        msg_no_ventas = "📭 No tienes ventas registradas para este mes."
    else:
        ventas_periodo = obtener_ventas(None, chat_id=cid)
        titulo = 'historial'
        msg_no_ventas = "📭 No hay ventas en el historial."
    
    # Obtener últimas 5 ventas del historial completo
    ventas_historial = obtener_ventas(None, chat_id=cid)
    ultimas = ventas_historial[-5:] if ventas_historial else []
    
    # Construir mensaje principal
    mensaje = ""
    if not ventas_periodo:
        mensaje = f"{msg_no_ventas}\n\n"
    else:
        total = sum(float(v['Total']) for v in ventas_periodo)
        transacciones = len(ventas_periodo)
        mensaje = (
            f"📊 *Ventas ({titulo.title()})*\n\n"
            f"Total Vendido: ${total:.2f}\n"
            f"Transacciones: {transacciones}\n\n"
        )
    
    # Añadir últimas 5 ventas del historial
    if ultimas:
        detalle = "\n".join([f"• {v['Fecha']} - ${float(v['Total']):.2f}" for v in ultimas])
        mensaje += f"Últimas 5 ventas registradas:\n{detalle}"
    else:
        mensaje += "No hay ventas registradas en el historial."
    
    bot.send_message(cid, mensaje, parse_mode='Markdown')

# ========== Ejecutar Bot ==========
if __name__ == '__main__':
    print("🤖 Bot en ejecución...")
    bot.polling()
