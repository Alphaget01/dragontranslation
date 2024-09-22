import os
import discord
from utils import process_with_nlp
from discord.ext import commands
from discord import ButtonStyle, File
from discord.ui import Button, View
from google.cloud import firestore
from utils import extract_text_from_images, translate_text, register_folder, get_folder_names, preprocess_text

# Configuración de los Intents
intents = discord.Intents.default()
intents.message_content = True

bot = commands.Bot(command_prefix='/', intents=intents)

# Inicialización de Firestore
db = firestore.Client()

@bot.event
async def on_ready():
    print(f'Logged in as {bot.user}')

# Comando: /registrodecarpetas
@bot.command()
async def registrodecarpetas(ctx, unidadcompartida: str, folder_name: str, folder_id: str):
    """
    Comando para registrar una carpeta en Firestore, diferenciando entre
    unidades compartidas y carpetas normales.
    
    Parámetros:
    - unidadcompartida: 'si' o 'no' para especificar si es una unidad compartida.
    - folder_name: Nombre de la carpeta.
    - folder_id: ID de la carpeta en Google Drive.
    """

    # Validar el parámetro unidadcompartida
    if unidadcompartida.lower() not in ["si", "no"]:
        await ctx.send(f'Por favor, selecciona una opción válida para "unidad compartida": "sí" o "no".')
        return

    # Caso 1: Unidad compartida "sí"
    if unidadcompartida.lower() == "si":
        collection_name = "unidadescompartidas"
        
        # Guardar en Firestore el nombre de la unidad compartida y su ID
        db.collection(collection_name).document(folder_id).set({
            "folder_name": folder_name,
            "folder_id": folder_id,
            "username": str(ctx.author)  # Nombre del usuario que registra la carpeta
        })
        
        await ctx.send(f'Unidad compartida "{folder_name}" registrada con éxito en la colección "{collection_name}".')
    
    # Caso 2: Carpeta normal "no"
    elif unidadcompartida.lower() == "no":
        collection_name = "registrodeseries"
        
        # Guardar en Firestore el nombre de la carpeta y su ID
        db.collection(collection_name).document(folder_id).set({
            "folder_name": folder_name,
            "folder_id": folder_id,
            "username": str(ctx.author)  # Nombre del usuario que registra la carpeta
        })
        
        await ctx.send(f'Carpeta normal "{folder_name}" registrada con éxito en la colección "{collection_name}".')


# Comando: /ocr con botones interactivos y flujo de traducción
@bot.command()
async def ocr(ctx, unidadcompartida: str, folder_name: str):
    """
    Comando para realizar OCR sobre las imágenes de una carpeta registrada.
    Distingue entre unidad compartida y no compartida, extrae texto
    usando Google Cloud Vision, lo procesa con Google Cloud Natural Language,
    y presenta opciones para copiar o descargar el texto extraído.
    """

    # Autocompletar nombres de carpetas desde Firestore
    collection_name = "unidadescompartidas" if unidadcompartida.lower() == "si" else "registrodeseries"
    doc_ref = db.collection(collection_name).where("folder_name", "==", folder_name).stream()

    folder_data = None
    for doc in doc_ref:
        folder_data = doc.to_dict()

    if not folder_data:
        await ctx.send(f'No se encontró la carpeta {folder_name} en Firestore.')
        return

    folder_id = folder_data['folder_id']

    # Extraer texto usando Google Cloud Vision
    text_extracted = extract_text_from_images(folder_id)  # Implementación en utils.py

    if not text_extracted:
        await ctx.send(f'No se encontró texto en las imágenes de la carpeta {folder_name}.')
        return

    # Procesar el texto extraído con Google Cloud Natural Language (pseudo globos de texto)
    processed_text = process_with_nlp(text_extracted)  # Implementación en utils.py

    # Formato de texto con nombre de carpeta e imágenes
    formatted_text = f"# Carpeta: {folder_name}\n"
    for idx, (image_name, image_text) in enumerate(processed_text.items()):
        formatted_text += f"# Imagen {idx + 1}: {image_name}\n{image_text}\n\n"

    # Guardar el texto extraído temporalmente en un archivo
    with open(f"{folder_name}_extracted_text.txt", "w", encoding="utf-8") as f:
        f.write(formatted_text)

    # Crear los botones "Copiar" y "Descargar"
    copy_button = Button(label="Copiar texto", style=ButtonStyle.primary)
    download_button = Button(label="Descargar", style=ButtonStyle.secondary)

    # Crear funciones para las interacciones de los botones
    async def copy_callback(interaction):
        await interaction.response.send_message(f'Texto extraído:\n{formatted_text}')

    async def download_callback(interaction):
        file = File(f"{folder_name}_extracted_text.txt")
        await interaction.response.send_message("Aquí tienes tu archivo:", file=file)

    copy_button.callback = copy_callback
    download_button.callback = download_callback

    # Crear una vista para los botones
    view = View()
    view.add_item(copy_button)
    view.add_item(download_button)

    # Enviar los botones al usuario
    await ctx.send("Elige una opción:", view=view)

    # Preguntar si desea traducir el texto extraído
    await ctx.send("¿Deseas usar el texto extraído OCR para traducción? Responde 'sí' o 'no'.")

    def check(m):
        return m.author == ctx.author and m.channel == ctx.channel and m.content.lower() in ['sí', 'no']

    msg = await bot.wait_for('message', check=check)

    if msg.content.lower() == 'sí':
        # Guardar en Firestore el texto extraído
        db.collection("textoextraidocr").document(folder_name).set({
            "text": formatted_text,
            "username": str(ctx.author)
        })
        await ctx.send(f'Texto guardado para traducción de la carpeta {folder_name}.')
    else:
        await ctx.send(f'Texto de {folder_name} descartado.')

    # Manejo de respuestas incorrectas
    if msg.content.lower() not in ['sí', 'no']:
        await ctx.send("Escribe bien care pene, solo 'sí' o 'no'.")
        msg = await bot.wait_for('message', check=check)
        if msg.content.lower() not in ['sí', 'no']:
            await ctx.send("Care chimba no juegues conmigo, te jodiste, voy a eliminar esta monda.")
            return  # Termina el comando si el usuario sigue respondiendo incorrectamente
        

from discord.ui import Button, View
from utils import preprocess_text, translate_text

# Comando: /traducir con preprocesamiento de texto
@bot.command()
async def traducir(ctx, folder_name: str):
    """
    Comando para traducir el texto extraído en la carpeta especificada.
    Utiliza la API de DeepL para la traducción, y da opciones de copiar
    o descargar la traducción.
    """

    # Buscar el texto extraído en Firestore en la colección "textoextraidocr"
    doc_ref = db.collection("textoextraidocr").document(folder_name)
    doc = doc_ref.get()

    if not doc.exists:
        await ctx.send(f'No se encontró texto para la carpeta {folder_name}.')
        return

    extracted_text = doc.to_dict().get('text')

    # Preprocesar el texto antes de la traducción (formas y terminologías especiales)
    preprocessed_text = preprocess_text(extracted_text)

    # Traducir el texto utilizando la API de DeepL
    translation = translate_text(preprocessed_text)

    if not translation:
        await ctx.send(f'Hubo un error al traducir el texto de la carpeta {folder_name}.')
        return

    # Guardar la traducción temporalmente en Firestore en "textotraducido"
    db.collection("textotraducido").document(folder_name).set({
        "translated_text": translation,
        "username": str(ctx.author)
    })

    # Guardar la traducción temporalmente en un archivo
    with open(f"{folder_name}_translated_text.txt", "w", encoding="utf-8") as f:
        f.write(translation)

    # Crear los botones "Copiar traducción" y "Descargar traducción"
    copy_button = Button(label="Copiar traducción", style=ButtonStyle.primary)
    download_button = Button(label="Descargar traducción", style=ButtonStyle.secondary)

    # Crear funciones para las interacciones de los botones
    async def copy_callback(interaction):
        await interaction.response.send_message(f'Traducción:\n{translation}')

    async def download_callback(interaction):
        file = File(f"{folder_name}_translated_text.txt")
        await interaction.response.send_message("Aquí tienes tu traducción:", file=file)

    copy_button.callback = copy_callback
    download_button.callback = download_callback

    # Crear una vista para los botones
    view = View()
    view.add_item(copy_button)
    view.add_item(download_button)

    # Enviar los botones al usuario
    await ctx.send("Elige una opción:", view=view)

    # Después de que el usuario interactúa, eliminar el documento traducido de Firestore
    async def delete_document():
        # Esperar la interacción con los botones antes de eliminar
        await ctx.send("Traducción eliminada de Firestore.")
        db.collection("textotraducido").document(folder_name).delete()

    # Llamar a la función para eliminar la traducción después de la interacción
    await delete_document()

