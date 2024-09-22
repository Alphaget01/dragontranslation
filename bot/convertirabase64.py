import base64

def convertir_a_base64(file_path: str):
    with open(file_path, "rb") as f:
        encoded = base64.b64encode(f.read())
        return encoded.decode('utf-8')

if __name__ == "__main__":
    ruta_archivo = "D:\\ZApng ENEDEA\\DADA\\angular-glyph-435500-j6-c6e87973f7ad.json"  # Ruta del archivo de credenciales
    resultado_base64 = convertir_a_base64(ruta_archivo)
    
    with open("credentials/creds_base64.txt", "w") as f:
        f.write(resultado_base64)
    
    print("Credenciales codificadas guardadas en 'credentials/creds_base64.txt'")
