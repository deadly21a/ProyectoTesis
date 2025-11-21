// lib/main.dart

import 'package:flutter/material.dart';
import 'package:image_picker/image_picker.dart'; 
import 'dart:io';

import 'models/diagnosis_result.dart';
import 'services/api_service.dart';

void main() => runApp(const MyApp());

class MyApp extends StatelessWidget {
  const MyApp({super.key});

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: 'X-Ray AI Diagnostic',
      theme: ThemeData(primarySwatch: Colors.teal),
      home: const DiagnosisScreen(),
    );
  }
}

class DiagnosisScreen extends StatefulWidget {
  const DiagnosisScreen({super.key});

  @override
  State<DiagnosisScreen> createState() => _DiagnosisScreenState();
}

class _DiagnosisScreenState extends State<DiagnosisScreen> {
  String? _imagePath; 
  String? _selectedModel = 'EfficientNet';
  DiagnosisResult? _results;
  bool _isLoading = false;
  final ImagePicker _picker = ImagePicker();

  Future<void> _pickImage() async {
    final XFile? image = await _picker.pickImage(source: ImageSource.gallery);
    if (image != null) {
      setState(() {
        _imagePath = image.path;
        _results = null; 
        _isLoading = false;
      });
    }
  }

  Future<void> _runDiagnosis() async {
    if (_imagePath == null) return;
    
    setState(() {
      _isLoading = true;
    });

    try {
      final result = await uploadAndClassifyXray(_imagePath!, _selectedModel!);
      
      setState(() {
        _results = result;
        _isLoading = false;
      });
      
    } catch (e) {
      setState(() {
        _results = null;
        _isLoading = false;
      });
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text('Error de diagnóstico: ${e.toString()}'), backgroundColor: Colors.red),
      );
    }
  }
  
  Future<void> _generateReport() async {
      if (_results == null) return;
      
      setState(() { _isLoading = true; });
      
      try {
          final savedPath = await downloadAndSaveReport(_results!.fileName);
          
          setState(() { _isLoading = false; });
          ScaffoldMessenger.of(context).showSnackBar(
              SnackBar(content: Text('✅ Reporte guardado en: $savedPath'), backgroundColor: Colors.green)
          );
      } catch (e) {
          setState(() { _isLoading = false; });
          ScaffoldMessenger.of(context).showSnackBar(
              SnackBar(content: Text('Error al guardar PDF: ${e.toString()}'), backgroundColor: Colors.red)
          );
      }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('X-Ray Diagnóstico IA')),
      body: SingleChildScrollView(
        padding: const EdgeInsets.all(16.0),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: <Widget>[
            // 1. Cargar Imagen y Clasificación
            const Text('1. Cargar y Clasificar', style: TextStyle(fontSize: 18, fontWeight: FontWeight.bold)),
            const SizedBox(height: 10),
            
            // Selector de Modelo
            DropdownButton<String>(
              value: _selectedModel,
              onChanged: (String? newValue) { setState(() { _selectedModel = newValue; }); },
              items: <String>['EfficientNet', 'ResNet'].map<DropdownMenuItem<String>>((String value) {
                return DropdownMenuItem<String>(value: value, child: Text(value));
              }).toList(),
            ),
            
            // Botones de Imagen y Clasificar
            Row(
              children: [
                ElevatedButton(onPressed: _pickImage, child: const Text('Seleccionar Imagen')),
                const SizedBox(width: 10),
                ElevatedButton(
                  onPressed: (_imagePath != null && !_isLoading) ? _runDiagnosis : null,
                  child: _isLoading 
                      ? const SizedBox(width: 20, height: 20, child: CircularProgressIndicator(color: Colors.white, strokeWidth: 2)) 
                      : const Text('Clasificar'),
                ),
              ],
            ),
            
            const Divider(height: 30),

            // 2. Visualización de Imágenes (Original y Máscara)
            const Text('2. Visualización y Máscara', style: TextStyle(fontSize: 18, fontWeight: FontWeight.bold)),
            const SizedBox(height: 10),
            
            Row(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                // Imagen Original
                Expanded(
                  child: Column(
                    children: [
                      const Text('Original', style: TextStyle(fontWeight: FontWeight.bold)),
                      _displayedImageWidget(context, _results?.displayedXrayUrl, _imagePath, placeholderText: 'Imagen Original'),
                    ],
                  ),
                ),
                const SizedBox(width: 10),
              ],
            ),
            
            const Divider(height: 30),

            // 3. Resultados y Reporte
            if (_results != null && !_isLoading) ...[
              const Text('3. Diagnóstico Detallado', style: TextStyle(fontSize: 18, fontWeight: FontWeight.bold)),
              
              const SizedBox(height: 15),

              // Probabilidades
              ...(_results!.probabilities.entries.map((entry) {
                return Padding(
                  padding: const EdgeInsets.only(bottom: 8.0),
                  child: Row(
                    children: [
                      // Mostrar la clase dominante en verde
                      Text('${entry.key.toUpperCase()}: ', style: TextStyle(fontWeight: FontWeight.bold, color: entry.key.toUpperCase() == _results!.dominantClass ? Colors.teal : Colors.black)),
                      Text('${(entry.value * 100).toStringAsFixed(2)}%', style: TextStyle(color: entry.key.toUpperCase() == _results!.dominantClass ? Colors.teal : Colors.black)),
                      if (entry.key.toUpperCase() == _results!.dominantClass)
                        const Icon(Icons.check_circle, color: Colors.teal, size: 16),
                    ],
                  ),
                );
              }).toList()),
              
              const Divider(height: 30),
              
              // Recomendaciones
              const Text('Recomendaciones:', style: TextStyle(fontSize: 16, fontWeight: FontWeight.w600)),
              Text(_results!.recommendations, style: const TextStyle(fontSize: 14)),

              const SizedBox(height: 10),
              
              const Text('Medicamentos Sugeridos:', style: TextStyle(fontSize: 16, fontWeight: FontWeight.w600)),
              ...(_results!.medications.map((med) => Text('• $med', style: const TextStyle(fontSize: 14)))),

              const SizedBox(height: 20),
              ElevatedButton.icon(
                onPressed: _generateReport,
                icon: const Icon(Icons.picture_as_pdf),
                label: const Text('Generar Reporte Automático (PDF)'),
                style: ElevatedButton.styleFrom(backgroundColor: Colors.blueGrey),
              ),
            ],
          ],
        ),
      ),
    );
  }
  
  // Widget auxiliar para manejar la visualización de imágenes (URL o archivo local)
  Widget _displayedImageWidget(BuildContext context, String? networkUrl, String? localPath, {String placeholderText = 'No image selected.'}) {
    const double imageSize = 200;
    
    // 1. Mostrar imagen desde Flask (URL) - Para clasificados
    if (networkUrl != null && !networkUrl.contains('Error')) {
      return Image.network(
        networkUrl,
        height: imageSize,
        fit: BoxFit.contain,
        errorBuilder: (context, error, stackTrace) => const Text('Error al cargar la imagen.'),
      );
    } 
    // 2. Mostrar imagen local (antes de subirla)
    else if (localPath != null && localPath.isNotEmpty) {
      return Image.file(
        File(localPath),
        height: imageSize,
        fit: BoxFit.contain,
        errorBuilder: (c, e, s) => Text('Error al leer $localPath'),
      );
    } 
    // 3. Placeholder
    else {
      return Container(
        height: imageSize,
        alignment: Alignment.center,
        color: Colors.grey[200],
        child: Text(placeholderText),
      );
    }
  }
}