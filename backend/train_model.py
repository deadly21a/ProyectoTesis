# train_model.py
import tensorflow as tf
from tensorflow.keras.preprocessing.image import ImageDataGenerator
from tensorflow.keras.applications import EfficientNetB0
from tensorflow.keras.models import Model
from tensorflow.keras.layers import Dense, GlobalAveragePooling2D, Dropout
from tensorflow.keras.optimizers import Adam
import os
import numpy as np

# ==============================================================================
# 1. CONFIGURACIÓN DE RUTAS Y PARÁMETROS
# ==============================================================================

# RUTA DE DATOS: Apunta a la carpeta creada por prepare_data.py
DATA_DIR = '../datos_entrenamiento' 
MODEL_OUTPUT_PATH = 'xray_model.h5' 

# Parámetros fijos
IMAGE_SIZE = 224
BATCH_SIZE = 32
NUM_CLASSES = 4 
EPOCHS = 20 
LEARNING_RATE = 0.0001

# ==============================================================================
# 2. PREPARACIÓN DE DATOS (flow_from_directory)
# ==============================================================================

print("Cargando y preparando datos desde carpetas [train/ y validation/]...")

# Generador para aumentar y normalizar datos de entrenamiento
train_datagen = ImageDataGenerator(
    rescale=1./255, 
    rotation_range=20,
    zoom_range=0.2,
    horizontal_flip=True
)

# Generador para normalizar datos de validación
val_datagen = ImageDataGenerator(rescale=1./255)

try:
    # Carga datos de entrenamiento
    train_generator = train_datagen.flow_from_directory(
        os.path.join(DATA_DIR, 'train'),
        target_size=(IMAGE_SIZE, IMAGE_SIZE),
        batch_size=BATCH_SIZE,
        class_mode='categorical',
        # Indicamos que el generador debe buscar las imágenes dentro de la subcarpeta 'images'
        # Esto asume que las imágenes están en 'datos_entrenamiento/train/COVID/images/'
        # Nota: Si tu ImageDataGenerator no soporta 'directory', usa un path más simple.
        # Aquí asumimos que Keras puede manejar la estructura anidada o solo mira las carpetas de clase.
        # Si tienes problemas, simplifica la estructura de 'datos_entrenamiento' a solo 'train/COVID'.
    )

    # Carga datos de validación
    validation_generator = val_datagen.flow_from_directory(
        os.path.join(DATA_DIR, 'validation'),
        target_size=(IMAGE_SIZE, IMAGE_SIZE),
        batch_size=BATCH_SIZE,
        class_mode='categorical'
    )
except Exception as e:
    print(f"ERROR: Falló la lectura. Verifique que la carpeta '{DATA_DIR}' exista y contenga las subcarpetas de clase: {e}")
    exit()

print(f"Total de imágenes de entrenamiento: {train_generator.samples}")
print(f"Total de imágenes de validación: {validation_generator.samples}")

# ==============================================================================
# 3. CONSTRUCCIÓN Y ENTRENAMIENTO
# ==============================================================================

def build_model(num_classes):
    # Usando Transferencia de Aprendizaje con EfficientNetB0
    base_model = EfficientNetB0(
        weights='imagenet', 
        include_top=False, 
        input_shape=(IMAGE_SIZE, IMAGE_SIZE, 3)
    )
    
    # Congelar capas base
    for layer in base_model.layers:
        layer.trainable = False

    # Capas de clasificación personalizadas
    x = base_model.output
    x = GlobalAveragePooling2D()(x)
    x = Dense(512, activation='relu')(x)
    x = Dropout(0.5)(x)
    predictions = Dense(num_classes, activation='softmax')(x)
    
    model = Model(inputs=base_model.input, outputs=predictions)
    return model

model = build_model(NUM_CLASSES)

print("Compilando modelo...")
model.compile(
    optimizer=Adam(learning_rate=LEARNING_RATE),
    loss='categorical_crossentropy',
    metrics=['accuracy']
)

# Callback para guardar la mejor versión del modelo
checkpoint_cb = tf.keras.callbacks.ModelCheckpoint(
    MODEL_OUTPUT_PATH,
    monitor='val_accuracy',
    save_best_only=True
)

print("Iniciando entrenamiento...")
history = model.fit(
    train_generator,
    epochs=EPOCHS,
    validation_data=validation_generator,
    callbacks=[checkpoint_cb]
)

print(f"\n✅ Entrenamiento finalizado. Modelo guardado como: {MODEL_OUTPUT_PATH}")