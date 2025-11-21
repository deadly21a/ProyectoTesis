# prepare_data.py (VERSIÓN FINAL PARA ESTRUCTURA SIMÉTRICA)

import os
import shutil
from sklearn.model_selection import train_test_split
import pandas as pd
import numpy as np

# ==============================================================================
# CONFIGURACIÓN DE RUTAS Y PARÁMETROS
# ==============================================================================

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
# Fuente de Imágenes: Tienen subcarpetas de clase (COVID/, Normal/, etc.)
SOURCE_IMAGE_BASE_DIR = os.path.join(BASE_DIR, "radiografias", "images") 
# Fuente de Máscaras: Tienen subcarpetas de clase (COVID/, Normal/, etc.)
SOURCE_MASK_BASE_DIR = os.path.join(BASE_DIR, "radiografias", "masks") 

# Ruta de destino (donde se creará la estructura train/validation)
DEST_BASE_DIR = os.path.join(BASE_DIR, "datos_entrenamiento")

# Parámetros de división
TEST_SIZE_SPLIT = 0.20 # 20% de los datos para validación
RANDOM_SEED = 42      

# Nombres de las subcarpetas de clase
CLASS_LABELS = ["COVID", "Normal", "Lung_Opacity", "Viral Pneumonia"] 

# ==============================================================================
# 1. FUNCIÓN PRINCIPAL DE PROCESAMIENTO
# ==============================================================================

def prepare_data_structure():
    print("--- 1. Recopilando archivos y extrayendo etiquetas ---")
    
    file_records = []
    
    # Recorrer las subcarpetas de clase
    for label in CLASS_LABELS:
        image_subdir = os.path.join(SOURCE_IMAGE_BASE_DIR, label)
        
        if not os.path.exists(image_subdir):
            print(f"Advertencia: Subcarpeta de imágenes no encontrada: {image_subdir}. Ignorando clase.")
            continue
            
        # 1.1. Recopilar archivos dentro de cada subcarpeta de clase
        for filename in os.listdir(image_subdir):
            if not filename.lower().endswith(('.png', '.jpg', '.jpeg')):
                continue
                
            # 🚨 CORRECCIÓN CLAVE: Buscar la máscara en su SUB-CARPETA correspondiente.
            mask_path = os.path.join(SOURCE_MASK_BASE_DIR, label, filename) 
            
            if not os.path.exists(mask_path):
                print(f"Advertencia: Máscara para {filename} (Clase {label}) no encontrada en la subcarpeta de masks. Ignorando archivo.")
                continue
                
            file_records.append({'filename': filename, 'class': label})

    if not file_records:
        print("ERROR: No se encontraron archivos. Verifique que las subcarpetas de imágenes contengan archivos y que exista la estructura simétrica en 'radiografias/masks'.")
        return

    df = pd.DataFrame(file_records)
    print(f"Total de imágenes etiquetadas y con máscara: {len(df)}")
    
    # 2. Dividir el dataset
    print("--- 2. Dividiendo datos en Entrenamiento (80%) y Validación (20%) ---")
    
    train_files, validation_files = train_test_split(
        df, test_size=TEST_SIZE_SPLIT, stratify=df['class'], random_state=RANDOM_SEED
    )
    
    # 3. Crear y poblar la nueva estructura de carpetas (destino)
    print("--- 3. Creando directorios y copiando archivos ---")
    
    # Limpiar el directorio de destino antes de empezar
    if os.path.exists(DEST_BASE_DIR):
        shutil.rmtree(DEST_BASE_DIR)
        print(f"Directorio '{DEST_BASE_DIR}' limpiado.")
        
    os.makedirs(DEST_BASE_DIR, exist_ok=True)
    
    datasets = {'train': train_files, 'validation': validation_files}
    
    for split_name, subset_df in datasets.items():
        for index, row in subset_df.iterrows():
            filename = row['filename']
            label = row['class']
            
            # Rutas de destino (Estructura: datos_entrenamiento/train/COVID/images/)
            dest_image_dir = os.path.join(DEST_BASE_DIR, split_name, label, "images")
            dest_mask_dir = os.path.join(DEST_BASE_DIR, split_name, label, "masks")
            
            os.makedirs(dest_image_dir, exist_ok=True)
            os.makedirs(dest_mask_dir, exist_ok=True)
            
            # Copiar imagen: Fuente es /images/{Clase}/{nombre_archivo}
            src_image_path = os.path.join(SOURCE_IMAGE_BASE_DIR, label, filename) 
            shutil.copy(src_image_path, dest_image_dir)
            
            # Copiar máscara: Fuente es /masks/{Clase}/{nombre_archivo}
            src_mask_path = os.path.join(SOURCE_MASK_BASE_DIR, label, filename)
            shutil.copy(src_mask_path, dest_mask_dir)
            
    print("\n✅ Estructura de datos creada exitosamente en:", DEST_BASE_DIR)

# Ejecución
if __name__ == "__main__":
    prepare_data_structure()