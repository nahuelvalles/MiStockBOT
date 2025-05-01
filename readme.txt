# 🤖 MiStockBOT  
*Un bot de Telegram para gestión de inventarios y ventas*  
 
---

## 🚀 Características  
- 📦 **Gestión de inventario**:  
  - Añadir/actualizar productos con stock y precios.  
  - Consultar stock en tiempo real.  
- 💰 **Registro de ventas**:  
  - Multi-productos con actualización automática de stock.  
  - Historial de ventas diarias/mensuales.  
- 🔐 **Autenticación segura**:  
  - Integración con Google OAuth y Firebase Firestore.  
  - Tokens almacenados de forma cifrada.  

---

## 🛠 Stack Tecnológico  
| **Categoría**       | **Tecnologías**                                                                |  
|---------------------|--------------------------------------------------------------------------------|  
| Lenguaje            | Python 3.11                                                                    |  
| Frameworks          | `python-telegram-bot`, `gspread`, `firebase-admin`                             |  
| APIs                | Google Sheets API, Firebase Firestore API                                      |  
| Despliegue          | Railway.app (Free Tier)                                |  

---

## ⚙️ Configuración Rápida  

### Requisitos Previos  
1. Cuenta de Google Cloud (para Sheets API y OAuth).  
2. Proyecto Firebase con Firestore habilitado.  
3. Token de bot de Telegram ([@BotFather](https://t.me/BotFather)).  

### Pasos:

1. **Clonar repositorio**:  
```bash  
git clone https://github.com/nahuelvalles/MiStockBOT.git  
cd MiStockBOT

2. **Configurar .env**:
TELEGRAM_BOT_TOKEN="tu_token"  
FIREBASE_PROJECT_ID="tu_proyecto"  
FIREBASE_PRIVATE_KEY="-----BEGIN PRIVATE KEY-----\n..."  
FIREBASE_CLIENT_EMAIL="firebase-adminsdk-...@....iam.gserviceaccount.com"  
GOOGLE_OAUTH_CLIENT_ID="tu_client_id"  
GOOGLE_OAUTH_CLIENT_SECRET="tu_client_secret"

3. **Instalar dependencias**:
pip install -r requirements.txt

📋 Comandos Disponibles
Comando	            Descripción	                            Ejemplo
/start	            Inicia el bot y autenticación	        /start
/venta	            Registra una nueva venta	            /venta → Sigue el flujo
/consultar	        Muestra stock o reportes de ventas      /consultar → Elige opción
/agregarstock       Añade/actualiza productos	            /agregarstock Manzanas 50
/actualizar	        Modifica precios de productos	        /actualizar Manzanas 120
/reset	            Borra tus datos de la base de datos	    /reset

---

🚨 Solución de Errores Comunes
Error: google.api_core.exceptions.PermissionDenied
Causa: Permisos insuficientes en Firestore.

Solución:
Ve a Google Cloud IAM.

Dale el rol "Cloud Firestore Owner" al service account de Firebase.

---

🌟 Contribuciones
¡Todas las contribuciones son bienvenidas!

Haz un fork del proyecto.

Crea una rama: git checkout -b feature/nueva-funcionalidad.

Commit: git commit -m 'Añade algo increíble'.

Push: git push origin feature/nueva-funcionalidad.

Abre un Pull Request.

---

**Especial mención a ChatGPT y Deepseek que me ayudaron con muchas dudas** 

