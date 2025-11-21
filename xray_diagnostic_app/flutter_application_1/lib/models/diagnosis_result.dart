// lib/models/diagnosis_result.dart

class DiagnosisResult {
  final String status;
  final String fileName;
  final String model;
  final Map<String, double> probabilities;
  final Map<String, double> features;
  final String dominantClass;
  final String recommendations;
  final List<String> medications;
  final String displayedXrayUrl; 
  final String displayedMaskUrl;

  DiagnosisResult({
    required this.status,
    required this.fileName,
    required this.model,
    required this.probabilities,
    required this.features,
    required this.dominantClass,
    required this.displayedXrayUrl,
    required this.displayedMaskUrl,
    required this.recommendations,
    required this.medications,
  });

  factory DiagnosisResult.fromJson(Map<String, dynamic> json) {
    
    // Función auxiliar de recomendaciones (basada en el backend)
    Map<String, dynamic> _getRecommendations(String dominantClass) {
        dominantClass = dominantClass.toLowerCase();
        switch (dominantClass) {
            case 'covid':
                return {'recommendations': 'Se requiere aislamiento inmediato. Iniciar tratamiento antiviral bajo supervisión médica.', 'medications': ['Antivirales específicos', 'Dexametasona', 'Paracetamol']};
            case 'viral_pneumonia':
                return {'recommendations': 'Tratamiento de soporte. Monitorear la función respiratoria para prevenir complicaciones.', 'medications': ['Oxígeno y Ventilación', 'Antipiréticos', 'Hidratación y reposo']};
            case 'lung_opacity':
                return {'recommendations': 'La opacidad requiere evaluación adicional (posible TAC o seguimiento).', 'medications': ['Analgésicos (si hay dolor)', 'Pendiente de evaluación médica completa.']};
            case 'normal':
            default:
                return {'recommendations': 'Radiografía limpia. No hay evidencia de patología pulmonar aguda.', 'medications': ['Ninguno.']};
        }
    }
    
    final dominant = json['dominant_class'] as String;
    final recs = _getRecommendations(dominant);
    
    return DiagnosisResult(
      status: json['status'] as String,
      fileName: json['file'] as String,
      model: json['model'] as String,
      dominantClass: dominant,
      
      probabilities: (json['probabilities'] as Map<String, dynamic>).map((k, v) => MapEntry(k, v is int ? v.toDouble() : v as double)),
      features: (json['features'] as Map<String, dynamic>).map((k, v) => MapEntry(k, v is int ? v.toDouble() : v as double)),
      
      displayedXrayUrl: json['temp_xray_url'] as String? ?? 'Error: URL not found', 
      displayedMaskUrl: json['temp_mask_url'] as String? ?? 'Error: URL not found', 

      recommendations: recs['recommendations']!,
      medications: (recs['medications'] as List<dynamic>).map((e) => e.toString()).toList(),
    );
  }
}