import os
from google.cloud import vision
from googleapiclient.discovery import build
from deepl import Translator

# Extraer texto de imágenes desde Google Drive usando Google Vision API
def extract_text_from_images(folder_id: str):
    vision_client = vision.ImageAnnotatorClient()

    # Obtener imágenes desde Google Drive
    drive_service = build('drive', 'v3')
    results = drive_service.files().list(q=f"'{folder_id}' in parents and mimeType contains 'image/'").execute()
    images = results.get('files', [])

    if not images:
        return None

    extracted_text = ""
    
    for image in images:
        file_id = image['id']
        file_name = image['name']
        image_data = drive_service.files().get_media(fileId=file_id).execute()
        
        image_vision = vision.Image(content=image_data)
        response = vision_client.text_detection(image=image_vision)
        texts = response.text_annotations

        extracted_text += f"# Imagen: {file_name}\n"
        extracted_text += texts[0].description if texts else "No se encontró texto\n"
    
    return extracted_text

# Traducir texto usando DeepL API
def translate_text(text: str):
    """
    Traduce el texto dado utilizando la API de DeepL.
    Maneja errores si la API no responde correctamente.
    """
    try:
        translator = Translator(os.getenv('DEEPL_API_KEY'))
        translated_text = translator.translate_text(text, target_lang="ES")
        return translated_text.text if translated_text else None
    except Exception as e:
        print(f"Error al traducir el texto: {e}")
        return None

# Preprocesar el texto antes de la traducción para manejar formas y terminologías especiales
def preprocess_text(text: str) -> str:
    """
    Preprocesa el texto antes de la traducción, teniendo en cuenta formas,
    terminologías y definiciones específicas.
    """
    # Formas de poner: detectar ciertas combinaciones y patrones
    formas = {
        "괘": "괜찮아요",
        "뭐...뭐야?": "¡¿Q...Qué?!",
        "싸-싼다": "M-me corro",
        "ㄲ…꽂히고 있어": "R-realmente se la estoy metiendo."
    }
    
    # Terminologías especiales
    terminologias = {
        "형님": "Hyung",
        "누나": "Nuna",
        "오빠": "Oppa",
        "언니": "Unni",
        "아줌마": "Ajumma"
    }

    # Reemplazar las formas en el texto
    for key, value in formas.items():
        text = text.replace(key, value)
    
    # Reemplazar las terminologías especiales en el texto
    for key, value in terminologias.items():
        text = text.replace(key, value)
    
    return text

# Registrar carpeta en Firestore
def register_folder(db, unidadcompartida: str, folder_name: str, folder_id: str):
    collection_name = "unidadescompartidas" if unidadcompartida == "si" else "registrodeseries"
    db.collection(collection_name).document(folder_id).set({
        "folder_name": folder_name,
        "folder_id": folder_id
    })

# Obtener los nombres de carpetas registradas
def get_folder_names(db, unidadcompartida: str):
    collection_name = "unidadescompartidas" if unidadcompartida == "si" else "registrodeseries"
    docs = db.collection(collection_name).stream()
    return [doc.to_dict()['folder_name'] for doc in docs]
