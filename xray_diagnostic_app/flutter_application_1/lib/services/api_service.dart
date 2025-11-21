// lib/services/api_service.dart

import 'dart:io';
import 'package:http/http.dart' as http;
import 'dart:convert';
import 'package:path_provider/path_provider.dart';
import 'package:permission_handler/permission_handler.dart';

import '../models/diagnosis_result.dart'; 

// 🛑 CLAVE: DEBE REEMPLAZAR 'TU_IP_REAL_AQUI' con la IP de su PC (ej. 192.168.1.15).
const String API_HOST_BASE = 'http://10.105.210.3:5000';

Future<DiagnosisResult> uploadAndClassifyXray(String filePath, String model) async {
  var uri = Uri.parse('$API_HOST_BASE/api/segment_and_classify');
  
  var request = http.MultipartRequest('POST', uri)
    ..fields['model'] = model; 
    
  // Adjuntar el archivo de imagen
  request.files.add(await http.MultipartFile.fromPath('file', filePath));
  
  var streamedResponse = await request.send();
  final response = await http.Response.fromStream(streamedResponse);

  if (response.statusCode == 200) {
    final jsonResponse = json.decode(response.body);
    
    // Convertir URLs relativas a absolutas para Image.network en Flutter
    jsonResponse['temp_xray_url'] = '$API_HOST_BASE${jsonResponse['temp_xray_url']}';
    jsonResponse['temp_mask_url'] = '$API_HOST_BASE${jsonResponse['temp_mask_url']}';
    
    return DiagnosisResult.fromJson(jsonResponse);

  } else {
    final errorBody = json.decode(response.body);
    throw Exception('Fallo la clasificación (Status ${response.statusCode}): ${errorBody['error'] ?? response.reasonPhrase}');
  }
}

Future<String> downloadAndSaveReport(String fileName) async {
  // 1. Pedir permiso de almacenamiento
  final status = await Permission.storage.request();
  if (!status.isGranted) {
    throw Exception("Permiso de almacenamiento denegado.");
  }
  
  final url = Uri.parse('$API_HOST_BASE/api/generate_report?name=${Uri.encodeComponent(fileName)}');
  final response = await http.get(url);
  
  if (response.statusCode == 200) {
    // 2. Obtener directorio de descargas
    final directory = await getExternalStorageDirectory(); 
    final downloadsPath = '${directory!.path}/Diagnostico_IA/';
    
    // Crear el directorio si no existe
    if (!await Directory(downloadsPath).exists()) {
      await Directory(downloadsPath).create(recursive: true);
    }
    
    // 3. Guardar el archivo PDF
    final filePath = '$downloadsPath${fileName}_Reporte.pdf';
    final file = File(filePath);
    await file.writeAsBytes(response.bodyBytes);
    
    return filePath; 
    
  } else {
    throw Exception('Fallo la generación del reporte PDF.');
  }
}