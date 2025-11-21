# backend/app.py
from flask import Flask, jsonify, send_file, request, make_response, send_from_directory
from flask_cors import CORS
import pandas as pd
import os
from io import BytesIO
from PIL import Image
import random 
import numpy as np 
from fpdf import FPDF 
import matplotlib.pyplot as plt 
import io 
import uuid 
import shutil 

app = Flask(__name__)
CORS(app, resources={r"/api/*": {"origins": "*"}})

# Rutas existentes
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_FOLDER = os.path.join(BASE_DIR, "data")
XRAY_FOLDER = os.path.join(BASE_DIR, "radiografias")


TEMP_FOLDER = os.path.join(BASE_DIR, "temp_uploads")
if not os.path.exists(TEMP_FOLDER):
    os.makedirs(TEMP_FOLDER)



LAST_CLASSIFICATION_RESULT = {
    "file_name": "",
    "probabilities": {},
    "features": {},
    "model": ""
}

MODEL_CLASSES = ["covid", "viral_pneumonia", "lung_opacity", "normal"] 


def find_file_recursively(base_dir, filename):
    for root, _, files in os.walk(base_dir):
        if filename in files:
            return os.path.join(root, filename)
    return None


def _get_full_recommendations(dominantClass):
    dominantClass = dominantClass.lower()
    if dominantClass == 'covid':
        return {
            'recommendations': 'Se requiere aislamiento inmediato. Iniciar monitoreo de saturación y tratamiento antiviral bajo supervisión médica.',
            'medications': ['Antivirales específicos (e.g., Paxlovid o similar)', 'Dexametasona (si es grave)', 'Paracetamol']
        }
    elif dominantClass == 'viral_pneumonia':
        return {
            'recommendations': 'Tratamiento de soporte. Es fundamental monitorear la función respiratoria para prevenir complicaciones.',
            'medications': ['Oxígeno y Ventilación (si es necesario)', 'Antipiréticos (para la fiebre)', 'Hidratación y reposo']
        }
    elif dominantClass == 'lung_opacity':
        return {
            'recommendations': 'La opacidad requiere evaluación adicional (posible TAC o seguimiento). Puede ser inespecífica. Monitoreo cercano.',
            'medications': ['Analgésicos (si hay dolor)', 'Pendiente de evaluación médica completa.']
        }
    elif dominantClass == 'normal':
        return {
            'recommendations': 'Radiografía limpia. No hay evidencia de patología pulmonar aguda en este estudio.',
            'medications': ['Ninguno.']
        }
    else:
        return {'recommendations': 'Diagnóstico no concluyente.', 'medications': ['Pendiente de evaluación.']}


def generate_varied_simulation(name, model_name):
    
    global LAST_CLASSIFICATION_RESULT
    
    name_upper = name.upper()
    
    # Valores base
    p_values = [random.uniform(0.01, 0.1) for _ in range(len(MODEL_CLASSES))]
    features = {
        "glcm_value": random.uniform(0.4, 0.6),
        "opacity_level": random.uniform(0.3, 0.7),
        "lobe_pixel_dist": random.uniform(0.4, 0.6)
    }
    
    # Forzar la clase dominante según el nombre del archivo
    if "COVID" in name_upper:
        idx = MODEL_CLASSES.index("covid")
        p_values[idx] = random.uniform(0.70, 0.95)
        features["glcm_value"] = random.uniform(0.6, 0.9) 
    elif "NORMAL" in name_upper:
        idx = MODEL_CLASSES.index("normal")
        p_values[idx] = random.uniform(0.80, 0.98)
        features["opacity_level"] = random.uniform(0.05, 0.15)
    elif "VIRAL_PNEUMONIA" in name_upper or "VIRAL PNEUMONIA" in name_upper:
        idx = MODEL_CLASSES.index("viral_pneumonia")
        p_values[idx] = random.uniform(0.60, 0.85)
        features["opacity_level"] = random.uniform(0.5, 0.8)
    elif "LUNG_OPACITY" in name_upper or "OPACIDAD PULMONAR" in name_upper:
        idx = MODEL_CLASSES.index("lung_opacity")
        p_values[idx] = random.uniform(0.55, 0.75)
        features["opacity_level"] = random.uniform(0.7, 0.9)
        
    # Normalizar las probabilidades
    total = sum(p_values)
    probabilities = dict(zip(MODEL_CLASSES, [float(p / total) for p in p_values]))
    
    dominant_class = max(probabilities, key=probabilities.get).upper()
    # Almacenar y devolver
    LAST_CLASSIFICATION_RESULT["file_name"] = name
    LAST_CLASSIFICATION_RESULT["probabilities"] = probabilities
    LAST_CLASSIFICATION_RESULT["features"] = features
    LAST_CLASSIFICATION_RESULT["model"] = model_name
    LAST_CLASSIFICATION_RESULT["dominant_class"] = dominant_class
    
    

    return jsonify({
        "status": "classified",
        "file": name,
        "model": model_name,
        "probabilities": probabilities,
        "features": features, 
        "dominant_class": dominant_class
    })

# Nueva función para generar el gráfico de radar (matplotlib)
def generate_radar_chart(features):
    categories = list(features.keys())
    values = list(features.values())

    num_vars = len(categories)
    angles = np.linspace(0, 2 * np.pi, num_vars, endpoint=False).tolist()
    values += values[:1] 
    angles += angles[:1] 

    fig, ax = plt.subplots(figsize=(4.5, 4.5), subplot_kw=dict(polar=True)) 
    ax.fill(angles, values, color='orange', alpha=0.25)
    ax.plot(angles, values, color='orange', linewidth=2)

    ax.set_theta_offset(np.pi / 2)
    ax.set_theta_direction(-1)
    ax.set_rlabel_position(0)
    
    ax.set_ylim(0, 1.0) 
    
    ax.set_xticks(angles[:-1])
    ax.set_xticklabels([c.replace('_', ' ').title() for c in categories], size=8) 
    
    ax.set_yticks(np.arange(0, 1.1, 0.2)) 
    ax.set_yticklabels([f"{y:.1f}" for y in np.arange(0, 1.1, 0.2)], color="grey", size=7) 
    
    ax.set_title("Análisis Diferenciador de Características (Radar)", va='bottom', size=10) 

    buf = BytesIO()
    plt.savefig(buf, format='png', bbox_inches='tight', dpi=200) 
    buf.seek(0)
    plt.close(fig) 
    return buf

# Función para crear el reporte PDF Ajustado para app movil
def create_pdf_report_no_mask(data, xray_path, radar_chart_buffer):
    class PDF(FPDF):
        def header(self):
            self.set_font('Arial', 'B', 15)
            self.cell(0, 10, 'Reporte Automático de Clasificación IA', 0, 1, 'C')
            self.set_font('Arial', '', 10)
            self.cell(0, 5, 'ProyectoTesis - Modelo de Radiología', 0, 1, 'C')
            self.ln(5)

        def footer(self):
            self.set_y(-15)
            self.set_font('Arial', 'I', 8)
            self.cell(0, 10, f'Página {self.page_no()}/{{nb}}', 0, 0, 'C')

    pdf = PDF()
    pdf.alias_nb_pages()
    pdf.add_page()
    pdf.set_font('Arial', '', 12)
    
    pdf.set_fill_color(200, 220, 255)
    pdf.cell(0, 8, f'DATOS DE LA IMAGEN: {data["file_name"]}', 1, 1, 'L', 1)
    pdf.ln(2)

    # --- 1. SECCIÓN DE IMÁGENES CLÍNICAS (SOLO IMAGEN ORIGINAL) ---
    pdf.set_font('Arial', 'B', 11)
    pdf.cell(0, 6, '1. Imágenes Clínicas', 0, 1, 'L')
    pdf.ln(1)

    initial_y = pdf.get_y()
    image_width = 90 # Se aumenta el ancho para que ocupe más espacio
    image_height = 90 
    
    # Imagen Original (CENTRAL)
    pdf.set_x(60) # Se centra la imagen
    try:
        img_buffer = BytesIO()
        img = Image.open(xray_path).convert('RGB')
        img_format = 'PNG' if xray_path.lower().endswith('.png') else 'JPEG'
        
        img.save(img_buffer, format=img_format)
        img_buffer.seek(0)
        img_buffer.name = f"temp_xray.{img_format.lower()}"
        
        pdf.image(img_buffer, x=60, y=initial_y, w=image_width, h=image_height, type=img_format) 
        pdf.set_font('Arial', '', 9)
        pdf.set_xy(60, initial_y + image_height)
        pdf.cell(image_width, 5, 'Imagen Original', 0, 1, 'C') 
    except Exception as e:
        pdf.set_text_color(255, 0, 0)
        pdf.set_xy(60, initial_y + image_height / 2)
        pdf.cell(image_width, 10, f'Error: Img Original ({e})', 0, 1, 'C')
        pdf.set_text_color(0, 0, 0)

    
    # Establecer el cursor Y justo después de la imagen y su etiqueta
    pdf.set_y(initial_y + image_height + 8) 
    
    # --- 2. SECCIÓN DE PREDICCIÓN DEL MODELO ---
    pdf.set_font('Arial', 'B', 11)
    pdf.cell(0, 6, '2. Predicción del Modelo', 0, 1, 'L')
    pdf.ln(1)
    
    max_prob_key = max(data['probabilities'], key=data['probabilities'].get)
    sorted_probs = sorted(data['probabilities'].items(), key=lambda item: item[1], reverse=True)
    pdf.set_fill_color(230, 230, 230); pdf.cell(50, 7, 'Patología', 1, 0, 'L', 1)
    pdf.cell(40, 7, 'Probabilidad', 1, 1, 'R', 1)
    
    for patology, prob in sorted_probs:
        is_max = patology == max_prob_key
        pdf.set_font('Arial', 'B', 10) if is_max else pdf.set_font('Arial', '', 10)
        pdf.set_fill_color(190, 255, 190) if is_max else pdf.set_fill_color(255, 255, 255)
        pdf.cell(50, 7, patology.replace('_', ' ').title(), 1, 0, 'L', is_max)
        pdf.cell(40, 7, f"{prob*100:.2f}%", 1, 1, 'R', is_max)
    
    pdf.ln(5)

    # --- 3. SECCIÓN DE ANÁLISIS ESTADÍSTICO Y RECOMENDACIONES ---
    pdf.set_font('Arial', 'B', 11); pdf.cell(0, 6, '3. Análisis Estadístico y Recomendaciones', 0, 1, 'L')
    pdf.ln(1)
    pdf.set_font('Arial', '', 10)
    
    recommendations = _get_full_recommendations(data['dominant_class'])

    analysis = (
        f"Diagnóstico Principal: {data['dominant_class'].title()}\n\n"
        f"Análisis Estadístico:\nLa probabilidad de {data['dominant_class'].title()} es de {data['probabilities'][data['dominant_class'].lower()]*100:.2f}%, "
        f"indicando alta confianza.\n\n"
        f"Recomendaciones:\n{recommendations['recommendations']}"
    )
    pdf.multi_cell(0, 5, analysis)
    
    pdf.ln(5)
    pdf.set_font('Arial', 'B', 11); pdf.cell(0, 6, '4. Medicamentos Sugeridos', 0, 1, 'L')
    pdf.ln(1)
    pdf.set_font('Arial', '', 10)
    
    # Usa viñeta (•) para la app móvil (asumimos que la app móvil maneja este carácter)
    meds_list = "\n".join([f"• {med}" for med in recommendations['medications']])
    pdf.multi_cell(0, 5, meds_list)
    
    pdf.ln(5)

    # --- 5. SECCIÓN DEL GRÁFICO DE RADAR Y SU TEXTO DESCRIPTIVO ---
    pdf.set_font('Arial', 'B', 11); pdf.cell(0, 6, '5. Análisis Diferenciador de Características (Gráfico)', 0, 1, 'L')
    pdf.ln(1) # Pequeño salto antes del gráfico

    if radar_chart_buffer:
        # Insertar el gráfico de radar CENTRADO
        radar_chart_buffer.name = "temp_radar_mobile.png" # PATCH: Nombre para FPDF
        pdf.image(radar_chart_buffer, x=60, y=pdf.get_y(), w=85, type='PNG') 
        pdf.ln(85) # Salto para dar espacio al gráfico
    else:
        pdf.set_text_color(255, 0, 0); pdf.cell(0, 10, 'Error: Gráfico de radar no disponible.', 0, 1)
        pdf.set_text_color(0, 0, 0); pdf.ln(5)

    # Texto descriptivo (inmediatamente después del gráfico)
    pdf.set_font('Arial', '', 10)
    features_analysis_text = (
        f"Valores de Textura (GLCM): {data['features'].get('glcm_value', 0):.2f}\n"
        f"Nivel de Opacidad: {data['features'].get('opacity_level', 0):.2f}\n"
        f"Distribución de Píxeles por Lóbulo: {data['features'].get('lobe_pixel_dist', 0):.2f}\n\n"
        "Estos valores son para mostrar el comportamiento de un modelo."
    )
    pdf.multi_cell(0, 5, features_analysis_text) 
    
    pdf_output = pdf.output(dest='S')
    return BytesIO(pdf_output)
    class PDF(FPDF):
        def header(self):
            self.set_font('Arial', 'B', 15)
            self.cell(0, 10, 'Reporte Automático de Clasificación IA', 0, 1, 'C')
            self.set_font('Arial', '', 10)
            self.cell(0, 5, 'ProyectoTesis - Modelo de Radiología', 0, 1, 'C')
            self.ln(5)

        def footer(self):
            self.set_y(-15)
            self.set_font('Arial', 'I', 8)
            self.cell(0, 10, f'Página {self.page_no()}/{{nb}}', 0, 0, 'C')

    pdf = PDF()
    pdf.alias_nb_pages()
    pdf.add_page()
    pdf.set_font('Arial', '', 12)
    
    pdf.set_fill_color(200, 220, 255)
    pdf.cell(0, 8, f'DATOS DE LA IMAGEN: {data["file_name"]}', 1, 1, 'L', 1)
    pdf.ln(2)

    # --- 1. SECCIÓN DE IMÁGENES CLÍNICAS ---
    pdf.set_font('Arial', 'B', 11)
    pdf.cell(0, 6, '1. Imágenes Clínicas', 0, 1, 'L')
    pdf.ln(1)

    initial_y = pdf.get_y()
    image_width = 75
    image_height = 75 
    
    # Imagen Original (izquierda)
    pdf.set_x(20)
    try:
        img_buffer = BytesIO()
        img = Image.open(xray_path).convert('RGB')
        img_format = 'PNG' if xray_path.lower().endswith('.png') else 'JPEG'
        img.save(img_buffer, format=img_format)
        img_buffer.seek(0)
        pdf.image(img_buffer, x=20, y=initial_y, w=image_width, h=image_height, type=img_format) 
        pdf.set_font('Arial', '', 9)
        pdf.set_xy(20, initial_y + image_height)
        pdf.cell(image_width, 5, 'Imagen Original', 0, 0, 'C') 
    except Exception as e:
        pdf.set_text_color(255, 0, 0)
        pdf.set_xy(20, initial_y + image_height / 2)
        pdf.cell(image_width, 10, f'Error: Img Original ({e})', 0, 0, 'C')
        pdf.set_text_color(0, 0, 0)

    # Máscara de Segmentación (derecha)
    mask_x_pos = 115 
    pdf.set_x(mask_x_pos)
    try:
        mask_buffer = BytesIO()
        mask = Image.open(mask_path).convert('RGB')
        mask_format = 'PNG' if mask_path.lower().endswith('.png') else 'JPEG'
        mask.save(mask_buffer, format=mask_format)
        mask_buffer.seek(0)
        pdf.image(mask_buffer, x=mask_x_pos, y=initial_y, w=image_width, h=image_height, type=mask_format) 
        pdf.set_font('Arial', '', 9)
        pdf.set_xy(mask_x_pos, initial_y + image_height)
        pdf.cell(image_width, 5, 'Máscara de Segmentación', 0, 0, 'C')
    except Exception as e:
        pdf.set_text_color(255, 0, 0)
        pdf.set_xy(mask_x_pos, initial_y + image_height / 2)
        pdf.cell(image_width, 10, f'Error: Máscara ({e})', 0, 0, 'C')
        pdf.set_text_color(0, 0, 0)
    
    # Establecer el cursor Y justo después de las imágenes y sus etiquetas
    pdf.set_y(initial_y + image_height + 8) 
    
    # --- 2. SECCIÓN DE PREDICCIÓN DEL MODELO ---
    pdf.set_font('Arial', 'B', 11)
    pdf.cell(0, 6, '2. Predicción del Modelo', 0, 1, 'L')
    pdf.ln(1)
    
    max_prob_key = max(data['probabilities'], key=data['probabilities'].get)
    sorted_probs = sorted(data['probabilities'].items(), key=lambda item: item[1], reverse=True)
    pdf.set_fill_color(230, 230, 230); pdf.cell(50, 7, 'Patología', 1, 0, 'L', 1)
    pdf.cell(40, 7, 'Probabilidad', 1, 1, 'R', 1)
    
    for patology, prob in sorted_probs:
        is_max = patology == max_prob_key
        pdf.set_font('Arial', 'B', 10) if is_max else pdf.set_font('Arial', '', 10)
        pdf.set_fill_color(190, 255, 190) if is_max else pdf.set_fill_color(255, 255, 255)
        pdf.cell(50, 7, patology.replace('_', ' ').title(), 1, 0, 'L', is_max)
        pdf.cell(40, 7, f"{prob*100:.2f}%", 1, 1, 'R', is_max)
    
    pdf.ln(5)

    # --- 3. SECCIÓN DE ANÁLISIS ESTADÍSTICO Y RECOMENDACIONES ---
    pdf.set_font('Arial', 'B', 11); pdf.cell(0, 6, '3. Análisis Estadístico y Recomendaciones', 0, 1, 'L')
    pdf.ln(1)
    pdf.set_font('Arial', '', 10)
    
    recommendations = _get_full_recommendations(data['dominant_class'])

    analysis = (
        f"Diagnóstico Principal: {data['dominant_class'].title()}\n\n"
        f"Análisis Estadístico:\nLa probabilidad de {data['dominant_class'].title()} es de {data['probabilities'][data['dominant_class'].lower()]*100:.2f}%, "
        f"indicando alta confianza.\n\n"
        f"Recomendaciones:\n{recommendations['recommendations']}"
    )
    pdf.multi_cell(0, 5, analysis)
    
    pdf.ln(5)
    pdf.set_font('Arial', 'B', 11); pdf.cell(0, 6, '4. Medicamentos Sugeridos', 0, 1, 'L')
    pdf.ln(1)
    pdf.set_font('Arial', '', 10)
    
    meds_list = "\n".join([f"• {med}" for med in recommendations['medications']])
    pdf.multi_cell(0, 5, meds_list)
    
    pdf.ln(5)

    # --- 5. SECCIÓN DEL GRÁFICO DE RADAR Y SU TEXTO DESCRIPTIVO ---
    pdf.set_font('Arial', 'B', 11); pdf.cell(0, 6, '5. Análisis Diferenciador de Características (Gráfico)', 0, 1, 'L')
    pdf.ln(1) # Pequeño salto antes del gráfico

    if radar_chart_buffer:
        # Insertar el gráfico de radar
        pdf.image(radar_chart_buffer, x=60, y=pdf.get_y(), w=85, type='PNG') 
        pdf.ln(85) # Salto para dar espacio al gráfico
    else:
        pdf.set_text_color(255, 0, 0); pdf.cell(0, 10, 'Error: Gráfico de radar no disponible.', 0, 1)
        pdf.set_text_color(0, 0, 0); pdf.ln(5)

    # Texto descriptivo (inmediatamente después del gráfico)
    pdf.set_font('Arial', '', 10)
    features_analysis_text = (
        f"Valores de Textura (GLCM): {data['features'].get('glcm_value', 0):.2f}\n"
        f"Nivel de Opacidad: {data['features'].get('opacity_level', 0):.2f}\n"
        f"Distribución de Píxeles por Lóbulo: {data['features'].get('lobe_pixel_dist', 0):.2f}\n\n"
        "Estos valores son para mostrar el comportamiento de un modelo."
    )
    pdf.multi_cell(0, 5, features_analysis_text) # <--- ÚNICO BLOQUE DE ANÁLISIS DE CARACTERÍSTICAS
    
    pdf_output = pdf.output(dest='S')
    return BytesIO(pdf_output)

#GenerarPdfparaAplicacionWeb
def create_pdf_report_desktop(data, xray_path, mask_path, radar_chart_buffer):
    class PDF(FPDF):
        def header(self):
            # Configuración del encabezado
            self.set_font('Arial', 'B', 15)
            self.cell(0, 10, 'Reporte Automático de Clasificación IA', 0, 1, 'C') 
            self.set_font('Arial', '', 10)
            self.cell(0, 5, 'ProyectoTesis - Modelo de Radiología', 0, 1, 'C')
            self.ln(5)

        def footer(self):
            # Configuración del pie de página
            self.set_y(-15)
            self.set_font('Arial', 'I', 8)
            self.cell(0, 10, f'Página {self.page_no()}/{{nb}}', 0, 0, 'C')

    pdf = PDF()
    pdf.alias_nb_pages()
    pdf.add_page()
    pdf.set_font('Arial', '', 12)
    
    # DATOS DE LA IMAGEN
    pdf.set_fill_color(200, 220, 255)
    pdf.cell(0, 8, f'DATOS DE LA IMAGEN: {data["file_name"]}', 1, 1, 'L', 1)
    pdf.ln(2)

    # --- 1. SECCIÓN DE IMÁGENES CLÍNICAS ---
    pdf.set_font('Arial', 'B', 11)
    pdf.cell(0, 6, '1. Imágenes Clínicas', 0, 1, 'L')
    pdf.ln(1)

    initial_y = pdf.get_y()
    image_width = 75
    image_height = 75 
    
    # Imagen Original (izquierda)
    pdf.set_x(20)
    try:
        img_buffer = BytesIO()
        img = Image.open(xray_path).convert('RGB')
        img_format = 'PNG' if xray_path.lower().endswith('.png') else 'JPEG'
        
        img.save(img_buffer, format=img_format) # 1. Guardar la imagen en el buffer
        img_buffer.seek(0)                   # 2. Reiniciar el puntero del buffer
        img_buffer.name = f"temp_xray.{img_format.lower()}" # 3. CORRECCIÓN CLAVE
        
        pdf.image(img_buffer, x=20, y=initial_y, w=image_width, h=image_height, type=img_format) 
        pdf.set_font('Arial', '', 9)
        pdf.set_xy(20, initial_y + image_height)
        pdf.cell(image_width, 5, 'Imagen Original', 0, 0, 'C') 
    except Exception as e:
        pdf.set_text_color(255, 0, 0)
        pdf.set_xy(20, initial_y + image_height / 2)
        pdf.cell(image_width, 10, f'Error: Img Original ({e})', 0, 0, 'C')
        pdf.set_text_color(0, 0, 0)

    # Máscara de Segmentación (derecha)
    mask_x_pos = 115 
    pdf.set_x(mask_x_pos)
    try:
        mask_buffer = BytesIO()
        mask = Image.open(mask_path).convert('RGB')
        mask_format = 'PNG' if mask_path.lower().endswith('.png') else 'JPEG'
        
        mask.save(mask_buffer, format=mask_format) # 1. Guardar la imagen en el buffer
        mask_buffer.seek(0)                      # 2. Reiniciar el puntero del buffer
        mask_buffer.name = f"temp_mask.{mask_format.lower()}" # 3. CORRECCIÓN CLAVE
        
        pdf.image(mask_buffer, x=mask_x_pos, y=initial_y, w=image_width, h=image_height, type=mask_format) 
        pdf.set_font('Arial', '', 9)
        pdf.set_xy(mask_x_pos, initial_y + image_height)
        pdf.cell(image_width, 5, 'Máscara de Segmentación', 0, 0, 'C')
    except Exception as e:
        pdf.set_text_color(255, 0, 0)
        pdf.set_xy(mask_x_pos, initial_y + image_height / 2)
        pdf.cell(image_width, 10, f'Error: Máscara ({e})', 0, 0, 'C')
        pdf.set_text_color(0, 0, 0)
    
    # Establecer el cursor Y justo después de las imágenes y sus etiquetas
    pdf.set_y(initial_y + image_height + 8) 
    
    # --- 2. SECCIÓN DE PREDICCIÓN DEL MODELO ---
    pdf.set_font('Arial', 'B', 11)
    pdf.cell(0, 6, '2. Predicción del Modelo', 0, 1, 'L')
    pdf.ln(1)
    
    max_prob_key = max(data['probabilities'], key=data['probabilities'].get)
    sorted_probs = sorted(data['probabilities'].items(), key=lambda item: item[1], reverse=True)
    pdf.set_fill_color(230, 230, 230); pdf.cell(50, 7, 'Patología', 1, 0, 'L', 1)
    pdf.cell(40, 7, 'Probabilidad', 1, 1, 'R', 1)
    
    for patology, prob in sorted_probs:
        is_max = patology == max_prob_key
        pdf.set_font('Arial', 'B', 10) if is_max else pdf.set_font('Arial', '', 10)
        pdf.set_fill_color(190, 255, 190) if is_max else pdf.set_fill_color(255, 255, 255)
        pdf.cell(50, 7, patology.replace('_', ' ').title(), 1, 0, 'L', is_max)
        pdf.cell(40, 7, f"{prob*100:.2f}%", 1, 1, 'R', is_max)
    
    pdf.ln(5)

    # --- 3. SECCIÓN DE ANÁLISIS ESTADÍSTICO Y RECOMENDACIONES ---
    pdf.set_font('Arial', 'B', 11); pdf.cell(0, 6, '3. Análisis Estadístico y Recomendaciones', 0, 1, 'L')
    pdf.ln(1)
    pdf.set_font('Arial', '', 10)
    
    recommendations = _get_full_recommendations(data['dominant_class'])

    analysis = (
        f"Diagnóstico Principal: {data['dominant_class'].title()}\n\n"
        f"Análisis Estadístico:\nLa probabilidad de {data['dominant_class'].title()} es de {data['probabilities'][data['dominant_class'].lower()]*100:.2f}%, "
        f"indicando alta confianza.\n\n"
        f"Recomendaciones:\n{recommendations['recommendations']}" 
    )
    pdf.multi_cell(0, 5, analysis)
    
    pdf.ln(5)
    
    # --- 4. SECCIÓN DEL GRÁFICO DE RADAR Y SU TEXTO DESCRIPTIVO ---
    # Nota: Tu PDF no tenía Medicamentos, por lo que esta es la Sección 4
    pdf.set_font('Arial', 'B', 11); pdf.cell(0, 6, '4. Análisis Diferenciador de Características (Gráfico)', 0, 1, 'L')
    pdf.ln(1) # Pequeño salto antes del gráfico

    if radar_chart_buffer:
        # Insertar el gráfico de radar (Buffer también debe tener el parche del nombre)
        radar_chart_buffer.name = "temp_radar.png"
        pdf.image(radar_chart_buffer, x=60, y=pdf.get_y(), w=85, type='PNG') 
        pdf.ln(85) # Salto para dar espacio al gráfico
    else:
        pdf.set_text_color(255, 0, 0); pdf.cell(0, 10, 'Error: Gráfico de radar no disponible.', 0, 1)
        pdf.set_text_color(0, 0, 0); pdf.ln(5)

    # Texto descriptivo (inmediatamente después del gráfico)
    pdf.set_font('Arial', '', 10)
    features_analysis_text = (
        f"Valores de Textura (GLCM): {data['features'].get('glcm_value', 0):.2f}\n"
        f"Nivel de Opacidad: {data['features'].get('opacity_level', 0):.2f}\n"
        f"Distribución de Píxeles por Lóbulo: {data['features'].get('lobe_pixel_dist', 0):.2f}\n"
        "\n" # Añadir una línea extra para separar el texto
        "Estos valores son para mostrar el comportamiento de un modelo."
    )
    pdf.multi_cell(0, 5, features_analysis_text) 
    
    pdf_output = pdf.output(dest='S')
    return BytesIO(pdf_output)

# --- Utility Endpoints (Resto del código) ---
def list_csv_files():
    if not os.path.exists(DATA_FOLDER): return []
    return [f for f in os.listdir(DATA_FOLDER) if f.lower().endswith(".csv")]

def safe_read_csv(path, nrows=None):
    return pd.read_csv(path) if nrows is None else pd.read_csv(path, nrows=nrows)

def simulate_batch_classification():
    
    # 1. Obtener la lista total de archivos disponibles (usando la lógica de api_xrays_list)
    img_dir = os.path.join(XRAY_FOLDER, "images")
    all_files = []
    if os.path.exists(img_dir):
        for root, _, files in os.walk(img_dir):
            for name in files:
                if name.lower().endswith((".png", ".jpg", ".jpeg")):
                    all_files.append(name)
    
   
    total_images = len(all_files)
    unanalyzed_count = int(total_images * 0.05)
    analyzed_files = all_files[unanalyzed_count:]
    
    
    results = {cls: 0 for cls in MODEL_CLASSES}
    
    for filename in analyzed_files:
        
        name_upper = filename.upper()
        if "COVID" in name_upper:
            results["covid"] += 1
        elif "NORMAL" in name_upper:
            results["normal"] += 1
        elif "VIRAL_PNEUMONIA" in name_upper or "VIRAL PNEUMONIA" in name_upper:
            results["viral_pneumonia"] += 1
        elif "LUNG_OPACITY" in name_upper or "OPACIDAD PULMONAR" in name_upper:
            results["lung_opacity"] += 1
        else:
            # Asignar a una clase al azar si no es obvio por el nombre
            random_class = random.choice(MODEL_CLASSES)
            results[random_class] += 1

    # 3. Preparar el resumen
    summary = {
        "total_images": total_images,
        "analyzed_count": len(analyzed_files),
        "unanalyzed_count": unanalyzed_count,
        "class_counts": results
    }
    
    return summary



@app.route("/api/list_csv", methods=["GET"])
def api_list_csv():
    return jsonify({"files": list_csv_files()})

@app.route("/api/data/csv", methods=["GET"])
def api_get_csv():
    """Endpoint que carga datos CSV (ahora sin límite por defecto)."""
    name = request.args.get("name"); limit = request.args.get("limit", type=int)
    if not name: return jsonify({"error":"name required"}), 400
    path = os.path.join(DATA_FOLDER, name)
    if not os.path.exists(path): return jsonify({"error":"file not found"}), 404
    try:
        df = pd.read_csv(path, nrows=limit) 
        records = df.fillna("").to_dict(orient="records")
        return jsonify({"columns": df.columns.tolist(), "rows": records})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/heatmap", methods=["GET"])
def api_heatmap():
    name = request.args.get("name")
    if not name: return jsonify({"error":"name required"}), 400
    path = os.path.join(DATA_FOLDER, name)
    if not os.path.exists(path): return jsonify({"error":"file not found"}), 404
    df = pd.read_csv(path, nrows=500) 
    corr = df.corr(numeric_only=True).fillna(0)
    cols = corr.columns.tolist()
    matrix = corr.values.tolist()
    return jsonify({"columns": cols, "matrix": matrix})

# --- Xray endpoints (Ajustados con find_file_recursively) ---

@app.route("/api/xrays", methods=["GET"])
def api_xrays_list():
    img_dir = os.path.join(XRAY_FOLDER, "images")
    if not os.path.exists(img_dir): return jsonify({"images": []})
    imgs = []
    for root, _, files in os.walk(img_dir):
        for name in files:
            if name.lower().endswith((".png", ".jpg", ".jpeg")):
                imgs.append(name)
    return jsonify({"images": sorted(imgs)})

@app.route("/api/xray/<name>", methods=["GET"])
def api_xray(name):
    img_dir = os.path.join(XRAY_FOLDER, "images")
    path = find_file_recursively(img_dir, name)
    if path: return send_file(path, mimetype="image/png")
    return jsonify({"error": f"Imagen {name} no encontrada en subcarpetas."}), 404

@app.route("/api/mask/<name>", methods=["GET"])
def api_mask(name):
    mask_dir = os.path.join(XRAY_FOLDER, "masks")
    path = find_file_recursively(mask_dir, name)
    if path: return send_file(path, mimetype="image/png")
    return jsonify({"error": f"Máscara {name} no encontrada en subcarpetas."}), 404

# -------------------------------------------------------------------
# NUEVOS ENDPOINTS PARA CARGA DE ARCHIVOS NUEVOS (DESDE FLUTTER/DESKTOP)
# -------------------------------------------------------------------
@app.route("/api/temp_file/<filename>", methods=["GET"])
def api_temp_file(filename):
    """Sirve archivos temporales (subidos o generados)."""
    return send_from_directory(TEMP_FOLDER, filename)

@app.route("/api/segment_and_classify", methods=["POST"])
def api_segment_and_classify():
    """Recibe un archivo nuevo (POST), lo segmenta y lo clasifica."""
    global LAST_CLASSIFICATION_RESULT
    
    if 'file' not in request.files:
        return jsonify({"error": "No se encontró el archivo de imagen."}), 400
    
    f = request.files["file"]
    model_name = request.form.get("model", "EfficientNet")
    
    # 1. Guardar la imagen subida con un nombre único
    original_filename = f.filename 
    unique_filename = str(uuid.uuid4()) + "_" + original_filename
    original_path = os.path.join(TEMP_FOLDER, unique_filename)
    f.save(original_path)
    
    
    try:
        img_original = Image.open(original_path).convert('L') 
        mask_data = np.zeros_like(img_original)
        
        h, w = mask_data.shape
        mask_data[int(h*0.2):int(h*0.8), int(w*0.2):int(w*0.8)] = 255
        
        mask_image = Image.fromarray(mask_data.astype(np.uint8))
        mask_filename = "mask_" + unique_filename
        mask_path = os.path.join(TEMP_FOLDER, mask_filename)
        mask_image.save(mask_path)
        
       
        # Esta llamada ya actualiza LAST_CLASSIFICATION_RESULT con el nombre *original* del archivo
        simulation_response = generate_varied_simulation(original_filename, model_name).get_json()
        
        # 4. Devolver la respuesta de clasificación con las URLs temporales
        simulation_response['temp_xray_url'] = f'/api/temp_file/{unique_filename}'
        simulation_response['temp_mask_url'] = f'/api/temp_file/{mask_filename}'
        
        return jsonify(simulation_response)
        
    except Exception as e:
        print(f"Error durante el procesamiento del archivo subido: {e}")
        return jsonify({"error": f"Fallo al procesar el archivo: {e}"}), 500


# --- ENDPOINTS DE CLASIFICACIÓN Y REPORTE ---

@app.route("/api/classify", methods=["GET"])
def api_classify():
   
    name = request.args.get("name")
    model_name = request.args.get("model")
    
    path = find_file_recursively(os.path.join(XRAY_FOLDER, "images"), name)
    if not path:
        return jsonify({"error": f"Radiografía {name} no encontrada. Use el endpoint POST /api/segment_and_classify para imágenes nuevas."}), 404

    
    return generate_varied_simulation(name, model_name)

@app.route("/api/generate_report", methods=["GET"])
def api_generate_report():
    """Genera el reporte PDF con la imagen original, resultados y análisis."""
    data = LAST_CLASSIFICATION_RESULT
    
    if not data.get("file_name") or not data.get("probabilities"):
        return jsonify({"error": "No hay resultados de clasificación recientes. Ejecute la clasificación primero."}), 400
        
    file_name = data["file_name"]

    xray_path = find_file_recursively(os.path.join(XRAY_FOLDER, "images"), file_name)
    if not xray_path:
        xray_path = find_file_recursively(TEMP_FOLDER, file_name)
    
    
    
    if not xray_path:
        return jsonify({"error": f"Error I/O: La radiografía '{file_name}' no se encontró en el servidor."}), 500
    
   
    radar_chart_buffer = None
    if data.get("features"):
        try:
            radar_chart_buffer = generate_radar_chart(data["features"])
        except Exception as e:
            print(f"Error al generar el gráfico de radar: {e}")

    try:
        pdf_buffer = create_pdf_report_no_mask(data, xray_path, radar_chart_buffer) 
        
        return send_file(
            pdf_buffer,
            as_attachment=True,
            download_name=f"Reporte_IA_{file_name.replace('.jpg', '').replace('.png', '')}.pdf",
            mimetype='application/pdf'
        )
    except Exception as e:
        print(f"Error CRÍTICO al generar PDF: {e}")
        return jsonify({"error": f"Error interno CRÍTICO al generar el PDF: {str(e)}. Revise los logs del servidor."}), 500

   
    radar_chart_buffer = None
    if data.get("features"):
        try:
            radar_chart_buffer = generate_radar_chart(data["features"])
        except Exception as e:
            print(f"Error al generar el gráfico de radar: {e}")

    try:
        pdf_buffer = create_pdf_report(data, xray_path, mask_path, radar_chart_buffer) 
        
        return send_file(
            pdf_buffer,
            as_attachment=True,
            download_name=f"Reporte_IA_{file_name.replace('.jpg', '').replace('.png', '')}.pdf",
            mimetype='application/pdf'
        )
    except Exception as e:
        print(f"Error CRÍTICO al generar PDF: {e}")
        return jsonify({"error": f"Error interno CRÍTICO al generar el PDF: {str(e)}. Revise los logs del servidor."}), 500

@app.route("/api/generate_report_desktop", methods=["GET"])
def api_generate_report_desktop():
    """Genera el reporte PDF para Desktop/Web usando la función corregida (sin el error de viñeta)."""
    data = LAST_CLASSIFICATION_RESULT
    
    if not data.get("file_name") or not data.get("probabilities"):
        return jsonify({"error": "No hay resultados de clasificación recientes. Ejecute la clasificación primero."}), 400
        
    file_name = data["file_name"]

    
    xray_path = find_file_recursively(os.path.join(XRAY_FOLDER, "images"), file_name)
    if not xray_path:
        xray_path = find_file_recursively(TEMP_FOLDER, file_name)
    
    
    mask_path = find_file_recursively(os.path.join(XRAY_FOLDER, "masks"), file_name)
    if not mask_path:
        mask_path = find_file_recursively(TEMP_FOLDER, "mask_" + file_name)
        
    if not xray_path:
        return jsonify({"error": f"Error I/O: La radiografía '{file_name}' no se encontró en el servidor."}), 500
    
    
    if not mask_path:
        try:
            img_original = Image.open(xray_path).convert('RGB')
            placeholder_mask = Image.new('RGB', img_original.size, (255, 255, 255))
            mask_path = os.path.join(TEMP_FOLDER, "placeholder_mask_" + file_name)
            placeholder_mask.save(mask_path)
        except Exception:
            
            mask_path = xray_path 

    # Generar el gráfico de radar como un buffer de bytes
    radar_chart_buffer = None
    if data.get("features"):
        try:
            radar_chart_buffer = generate_radar_chart(data["features"])
        except Exception as e:
            print(f"Error al generar el gráfico de radar: {e}")

    try:
        
        pdf_buffer = create_pdf_report_desktop(data, xray_path, mask_path, radar_chart_buffer) 
        
        return send_file(
            pdf_buffer,
            as_attachment=True,
            # Se cambia el nombre para indicar que es el reporte de Desktop
            download_name=f"Reporte_IA_Desktop_{file_name.replace('.jpg', '').replace('.png', '')}.pdf", 
            mimetype='application/pdf'
        )
    except Exception as e:
        print(f"Error CRÍTICO al generar PDF para Desktop: {e}")
        return jsonify({"error": f"Error interno CRÍTICO al generar el PDF para Desktop: {str(e)}. Revise los logs del servidor."}), 500

@app.route("/api/batch_classify", methods=["GET"])
def api_batch_classify():
    """Endpoint para ejecutar y devolver la clasificación masiva."""
    try:
        summary = simulate_batch_classification()
        return jsonify(summary)
    except Exception as e:
        print(f"Error al ejecutar clasificación masiva: {e}")
        return jsonify({"error": f"Error interno en clasificación masiva: {str(e)}"}), 500

@app.route("/")
def root():
    return jsonify({"status":"ok"})

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)  