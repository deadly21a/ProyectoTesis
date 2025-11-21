// frontend/scripts.js
const API = "http://127.0.0.1:5000/api";

let currentData = null;
let currentColumns = [];
let dataTable = null;
let mapInstance = null;
let geoLayer = null;
let barChart, lineChart, histChart, scatterChart, differentiatorChart;
let availableCountries = []; 

$(document).ready(function(){
  loadCsvList();
  $("#btnReload").click(loadCsvList);
  $("#btnLoad").click(()=> {
    const name = $("#csvSelector").val();
    if(name) loadDataset(name);
  });

  // Handlers para Dashboard
  $("#colX").on("change", genCharts);
  $("#colY").on("change", genCharts);
  $("#countryFilter").on("change", genCharts); // Filtro de país

  // Handlers para Radiografías e IA
  loadXrays();
  $("#xraySelector").on("change", function(){ showXray($(this).val()); });
  $("#iaXraySelector").on("change", function(){ showIaXray($(this).val()); });
  $("#btnClassify").on("click", classifyXray);
  $("#btnGenerateReport").on("click", generateReport);
$("#btnBatchClassify").on("click", batchClassifyXrays);

  // Inicializar el gráfico diferenciador con datos dummy
  renderDifferentiatorChart({ glcm_value: 0.5, opacity_level: 0.5, lobe_pixel_dist: 0.5 });
  
  // 🛑 CORRECCIÓN CLAVE: Inicialización forzada de Leaflet al cambiar a la pestaña 'Mapa'
  $('#mainTabs button[data-bs-target="#tabMap"]').on('shown.bs.tab', function (e) {
      if (mapInstance) {
          mapInstance.invalidateSize(); 
          if (geoLayer) {
              mapInstance.fitBounds(geoLayer.getBounds(), { maxZoom: 3 });
          }
      } else {
          renderMapPlaceholder(); 
      }
  });
});

// ====================================================================
// CORE FUNCTIONS
// ====================================================================

function loadCsvList(){
  fetch(API + "/list_csv").then(r=>r.json()).then(json=>{
    const sel = $("#csvSelector");
    sel.empty();
    (json.files||[]).forEach(f => sel.append(`<option value="${f}">${f}</option>`));
  });
}

function loadDataset(name){
  $("#datasetTitle").text(name);
  
  fetch(API + "/data/csv?name="+encodeURIComponent(name)).then(r=>r.json()).then(json=>{
    currentColumns = json.columns;
    currentData = json.rows;
    renderTable(currentColumns, currentData);
    populateColumnSelectors(currentColumns, currentData);
    loadHeatmap(name);
    extractCountries(currentData); 
    renderMapPlaceholder(); 
    genCharts(); 
  }).catch(err=> alert("Error cargando CSV: "+err));
}

// --- Table ---
function renderTable(columns, rows){
  if($.fn.dataTable.isDataTable('#dataTable')) {
    $('#dataTable').DataTable().destroy();
  }
  const table = $("#dataTable");
  table.empty();
  let thead = $("<thead>");
  let tr = $("<tr>");
  columns.forEach(c => tr.append(`<th>${c}</th>`));
  thead.append(tr);
  table.append(thead);

  const tbody = $("<tbody>");
  rows.forEach(r => {
    const tr = $("<tr>");
    columns.forEach(c => tr.append(`<td>${(r[c]!==undefined && r[c]!==null)?r[c]:""}</td>`));
    tbody.append(tr);
  });
  table.append(tbody);

  dataTable = $('#dataTable').DataTable({
    pageLength: 10,
    lengthChange: true,
    order: []
  });
}

// --- Column selectors and Filters ---
function populateColumnSelectors(columns, rows){
  $("#colX").empty(); $("#colY").empty();
  columns.forEach(c=>{
    $("#colX").append(`<option value="${c}">${c}</option>`);
    const numeric = rows.every(r => r[c] === "" || r[c] === null || !isNaN(Number(r[c])));
    if(numeric) $("#colY").append(`<option value="${c}">${c}</option>`);
  });
  $("#colX").val(columns[0]);
  $("#colY").val($("#colY option").last().val());
}

function extractCountries(rows){
    availableCountries = [];
    $("#countryFilter").empty().append('<option value="">Todos los Países</option>');
    const countryCol = currentColumns.includes("country") ? "country" : (currentColumns.includes("Entity") ? "Entity" : null);

    if(countryCol){
        const countries = new Set(rows.map(r => r[countryCol]).filter(c => c));
        availableCountries = Array.from(countries).sort();
        availableCountries.forEach(c => $("#countryFilter").append(`<option value="${c}">${c}</option>`));
    }
}

// --- Heatmap ---
function loadHeatmap(name){
  fetch(API + "/heatmap?name="+encodeURIComponent(name)).then(r=>r.json()).then(resp=>{
    if(resp.error){ $("#heatmapContainer").html("<div class='alert alert-warning'>No se pudo calcular la correlación</div>"); return; }
    const cols = resp.columns;
    const mat = resp.matrix;
    renderHeatmapTable(cols, mat);
  }).catch(err => {
    $("#heatmapContainer").html("<div class='alert alert-danger'>Error calculando heatmap</div>");
  });
}

function renderHeatmapTable(cols, mat){
  const container = $("#heatmapContainer");
  container.empty();
  const table = $("<table class='table table-sm'>");
  const thead = $(`<thead><tr><th></th>${cols.map(c=>`<th>${c}</th>`).join("")}</tr></thead>`);
  table.append(thead);
  const tbody = $("<tbody>");
  for(let i=0;i<cols.length;i++){
    const tr = $("<tr>");
    tr.append(`<th>${cols[i]}</th>`);
    for(let j=0;j<cols.length;j++){
      const v = mat[i][j];
      const color = heatColor(v);
      tr.append(`<td style='background:${color};color:${textColorForBackground(color)}'>${v.toFixed(2)}</td>`);
    }
    tbody.append(tr);
  }
  table.append(tbody);
  container.append(table);
}

function heatColor(value){
  const v = Math.max(-1, Math.min(1, value));
  const r = v>0 ? Math.round(255 * v) : 0;
  const b = v<0 ? Math.round(255 * -v) : 0;
  const g = 120;
  return `rgb(${r},${g},${b})`;
}
function textColorForBackground(rgb){
  const nums = rgb.match(/\d+/g).map(Number);
  const brightness = (nums[0]*299 + nums[1]*587 + nums[2]*114)/1000;
  return brightness > 150 ? "#111" : "#fff";
}

// --- Charts generation ---
function genCharts(){
  if(!currentData || !currentColumns) return;
  const xcol = $("#colX").val();
  const ycol = $("#colY").val();
  const countryFilter = $("#countryFilter").val();

  if(!xcol || !ycol){ return; }

  const countryCol = currentColumns.includes("country") ? "country" : (currentColumns.includes("Entity") ? "Entity" : null);

  let filteredData = currentData;
  if(countryFilter && countryCol){
    const filterLower = countryFilter.toLowerCase();
    
    filteredData = currentData.filter(r => {
        const countryValue = r[countryCol];
        return countryValue && String(countryValue).toLowerCase() === filterLower;
    });
  }
  
  // 1. DATA PARA GRÁFICOS CATEGÓRICOS (Barras, Histograma): Agrupada y ordenada por valor
  const grouped = {};
  filteredData.forEach(r => {
    const k = (r[xcol]===null||r[xcol]==="") ? "__null" : String(r[xcol]);
    const v = Number(r[ycol]) || 0;
    if(!grouped[k]) grouped[k]=0;
    grouped[k] += v; 
  });

  const sortedEntries = Object.entries(grouped).sort(([, a], [, b]) => b - a);
  const labels = sortedEntries.map(([label]) => label);
  const values = sortedEntries.map(([, value]) => value);
  
  // 2. DATA PARA GRÁFICO DE LÍNEAS (Serie Temporal)
  const isTimeSeries = xcol.toLowerCase().includes('date') || xcol.toLowerCase().includes('day');
  let lineData = [];
  
  if (isTimeSeries) {
      lineData = filteredData
                  .map(r => ({ x: r[xcol], y: Number(r[ycol]) || 0 }))
                  .sort((a, b) => new Date(a.x) - new Date(b.x));
  } else {
      lineData = sortedEntries.map(([x, y]) => ({ x, y }));
  }


  // Limpiar gráficos existentes
  if(barChart) barChart.destroy();
  if(lineChart) lineChart.destroy();
  if(histChart) histChart.destroy();
  if(scatterChart) scatterChart.destroy();

  const filterLabel = countryFilter ? ` en ${countryFilter}` : "";

  // 1. 🛑 GRÁFICO DE BARRAS HORIZONTAL (como en Imagen 5)
  const ctxBar = document.getElementById("chartBar").getContext("2d");
  barChart = new Chart(ctxBar, {
    type: "bar",
    data: { 
      labels: labels, 
      datasets: [{ 
        label: ycol + filterLabel, 
        data: values, 
        backgroundColor: 'rgba(54,162,235,0.7)' 
      }] 
    },
    options: { 
        indexAxis: 'y', // CLAVE: Barras horizontales
        responsive:true, 
        maintainAspectRatio: false,
        scales: {
            x: { 
                beginAtZero: true,
                title: { display: true, text: ycol }
            },
            y: { 
                title: { display: true, text: xcol }
            }
        },
        plugins: {
            tooltip: {
                callbacks: {
                    label: function(context) {
                        return `${context.label}: ${context.raw.toFixed(2)}`;
                    }
                }
            }
        }
    }
  });

  // 2. 🛑 GRÁFICO DE LÍNEAS (Serie Temporal si hay fecha, como en Imagen 4)
  const ctxLine = document.getElementById("chartLine").getContext("2d");
  lineChart = new Chart(ctxLine, {
    type: "line",
    data: { 
      labels: isTimeSeries ? null : labels, 
      datasets: [{ 
        label: ycol + filterLabel, 
        data: isTimeSeries ? lineData : lineData.map(p => p.y), 
        borderColor: 'rgba(255,99,132,0.8)', 
        backgroundColor: 'rgba(255,99,132,0.2)', 
        fill: true,
        tension: 0.3 
      }] 
    },
    options: { 
        responsive:true, 
        maintainAspectRatio: false,
        scales: {
            x: { 
                type: isTimeSeries ? 'time' : 'category', 
                time: isTimeSeries ? { 
                    unit: 'month',
                    tooltipFormat: 'MMM d, yyyy'
                } : {},
                title: { display: true, text: xcol }
            },
            y: { 
                beginAtZero: true,
                title: { display: true, text: ycol }
            }
        },
        plugins: {
            legend: { display: false },
            tooltip: { mode: 'index', intersect: false }
        }
    }
  });

  // 3. Histograma (Mantenido)
  const ctxHist = document.getElementById("chartHist").getContext("2d");
  histChart = new Chart(ctxHist, {
    type: "bar",
    data: { labels: labels, datasets: [{ label: "Distribución de " + ycol, data: values, backgroundColor: 'rgba(75,192,192,0.7)' }] },
    options: { responsive:true, maintainAspectRatio: false }
  });

  // 4. Scatter Chart (Mantenido)
  const scatterData = filteredData.map(r => ({ x: r[xcol], y: Number(r[ycol]) })).filter(p => !isNaN(Number(p.y)));
  const ctxScatter = document.getElementById("chartScatter").getContext("2d");
  scatterChart = new Chart(ctxScatter, {
    type: "scatter",
    data: { datasets: [{ label: `${ycol} vs ${xcol}` + filterLabel, data: scatterData, backgroundColor:'rgba(153,102,255,0.7)'}] },
    options: { 
        responsive:true, 
        maintainAspectRatio: false, 
        scales:{ x:{ type:'category' } } 
    }
  });
}

// --- MAP ---
function renderMapPlaceholder(){
  if(!currentData) return;
  
  const countryCol = currentColumns.includes("country") ? "country" : (currentColumns.includes("Entity") ? "Entity" : null);
  if (!countryCol) {
    console.warn("No se encontró columna 'country' o 'Entity' para el mapa.");
    if(mapInstance) { mapInstance.remove(); mapInstance = null; }
    $("#map").html("<div class='alert alert-warning'>No hay datos de país para mostrar el mapa.</div>");
    return;
  }

  const numericCol = currentColumns.find(c => currentData.every(r => r[c] === "" || r[c] === null || !isNaN(Number(r[c]))));
  if (!numericCol) {
    console.warn("No se encontró columna numérica para el mapa.");
    if(mapInstance) { mapInstance.remove(); mapInstance = null; }
    $("#map").html("<div class='alert alert-warning'>No hay datos numéricos para colorear el mapa.</div>");
    return;
  }

  // --- 1. PROCESAR Y NORMALIZAR DATA DEL CSV ---
  // 🛑 CLAVE: Cambiar la agregación a VALOR MÁXIMO (último acumulado) por país.
  const mapDataMax = {};
  currentData.forEach(r => {
    const countryName = r[countryCol];
    const value = Number(r[numericCol] || 0);
    if (countryName) {
      const normalizedKey = String(countryName).trim().toLowerCase(); 
      
      // Usa el valor máximo (simula el último/total acumulado)
      if (value > (mapDataMax[normalizedKey] || 0)) {
        mapDataMax[normalizedKey] = value;
      }
    }
  });
  const processedMapData = mapDataMax;


  const values = Object.values(processedMapData).filter(v => v !== 0);
  const min = values.length > 0 ? Math.min(...values) : 0;
  const max = values.length > 0 ? Math.max(...values) : 1; 

  // --- 2. CONFIGURACIÓN DEL MAPA ---
  if(!mapInstance){
    mapInstance = L.map("map").setView([30, 0], 2); 
    L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
      attribution: '© OpenStreetMap contributors'
    }).addTo(mapInstance);
  }
  if(geoLayer) { geoLayer.remove(); geoLayer = null; }

  d3.json("https://cdn.jsdelivr.net/npm/world-atlas@2/countries-110m.json").then(world => {
    const geo = topojson.feature(world, world.objects.countries);
    
    const colorScale = d3.scaleSequential(d3.interpolateGreens).domain([min, max]);

    geoLayer = L.geoJSON(geo, {
      style: function(feature){
        const name = feature.properties.name;
        let normalizedName = String(name).trim().toLowerCase(); 
        
        // Mapeo de nombres TopoJSON problemáticos a claves comunes del CSV
        if (normalizedName.includes("united states") || normalizedName.includes("usa")) {
             normalizedName = "united states"; // Asumir clave 'united states' en CSV
        }
        if (normalizedName === "antigua and barb.") { // Ejemplo de mapeo para asegurar cobertura
           normalizedName = "antigua and barbuda"; 
        }
        // ... (agregar más mappings si se identifican otros países problemáticos) ...
        
        const v = processedMapData[normalizedName] || 0; 

        return { 
          fillColor: v ? colorScale(v) : "#ddd", 
          fillOpacity: 0.8, 
          color:'#999', 
          weight:0.5 
        };
      },
      onEachFeature: function(feature, layer){
        const name = feature.properties.name;
        const normalizedName = String(name).trim().toLowerCase();
        
        let displayV = "Sin datos";
        
        // Usar el mismo mapeo para el popup
        let key = normalizedName;
        if (key.includes("united states") || key.includes("usa")) { key = "united states"; }

        const v = processedMapData[key];

        if (v !== undefined) {
            displayV = v.toFixed(2);
        }
        
        // 🛑 LÓGICA DEL POPUP Y RESALTADO
        layer.bindPopup(`
          <strong>${name}</strong><br/>
          ${numericCol}: ${displayV}
        `);

        layer.on({
            mouseover: function(e) {
                const layer = e.target;
                layer.setStyle({ weight: 3, color: '#333' }); 
                if (!L.Browser.ie && !L.Browser.opera && !L.Browser.edge) {
                    layer.bringToFront();
                }
            },
            mouseout: function(e) {
                geoLayer.resetStyle(e.target); 
            },
            click: function(e) {
                layer.openPopup(e.latlng); 
            }
        });
      }
    }).addTo(mapInstance);
    
    // Ajustar el zoom inicial (mantener la vista estable)
    if (geoLayer) {
        mapInstance.setView([30, 0], 2); 
    }
  }).catch(err => {
    console.error("Error cargando topojson para el mapa:", err);
    $("#map").html("<div class='alert alert-danger'>Error al cargar los datos del mapa.</div>");
  });
}


// ====================================================================
// XRAY & AI CLASSIFICATION (Mantener)
// ====================================================================

function loadXrays(){
  fetch(API + "/xrays").then(r=>r.json()).then(json=>{
    const sel = $("#xraySelector");
    const iaSel = $("#iaXraySelector");
    sel.empty(); iaSel.empty();
    
    if((json.images||[]).length === 0){
        sel.append('<option value="">No hay radiografías</option>');
        iaSel.append('<option value="">No hay radiografías</option>');
        return;
    }
    
    (json.images||[]).forEach(name => {
      sel.append(`<option value="${name}">${name}</option>`);
      iaSel.append(`<option value="${name}">${name}</option>`);
    });
    showXray(sel.val());
    showIaXray(iaSel.val());
  });
}

function showXray(name){
  if(!name) return;
  $("#xrayImg").attr("src", API + "/xray/" + encodeURIComponent(name));
  $("#xrayMask").attr("src", API + "/mask/" + encodeURIComponent(name));
}

function showIaXray(name){
    if(!name) return;
    $("#iaXrayImg").attr("src", API + "/xray/" + encodeURIComponent(name));
    $("#iaResults").html('<li class="list-group-item text-muted">Aún no hay resultados de clasificación.</li>');
    $("#btnGenerateReport").prop('disabled', true);
}


function classifyXray(){
    const name = $("#iaXraySelector").val();
    const model = $("#modelSelector").val();
    if(!name || !model) { alert("Selecciona una radiografía y un modelo."); return; }
    
    $("#btnClassify").prop("disabled", true).text("Clasificando...");

    fetch(API + `/classify?name=${encodeURIComponent(name)}&model=${encodeURIComponent(model)}`).then(r => r.json()).then(json => {
        
        $("#btnClassify").prop("disabled", false).text("Clasificar");
        
        if(json.error) {
            $("#iaResults").html(`<li class="list-group-item list-group-item-danger">Error: ${json.error}</li>`);
            $("#btnGenerateReport").prop('disabled', true);
            return;
        }

        const probabilities = json.probabilities;
        const results = [
            { label: "COVID", prob: probabilities.covid },
            { label: "Neumonía Viral", prob: probabilities.viral_pneumonia },
            { label: "Opacidad Pulmonar", prob: probabilities.lung_opacity },
            { label: "Normal", prob: probabilities.normal },
        ].sort((a,b) => b.prob - a.prob);

        let html = '';
        results.forEach((r, i) => {
            const classType = i === 0 ? 'list-group-item-success' : '';
            html += `<li class="list-group-item ${classType}">
                <strong>✔ Probabilidad de ${r.label}</strong>: ${(r.prob * 100).toFixed(2)}%
                <div class="progress" role="progressbar" style="height: 5px;">
                  <div class="progress-bar" style="width: ${r.prob * 100}%"></div>
                </div>
            </li>`;
        });
        $("#iaResults").html(html);
        $("#btnGenerateReport").prop('disabled', false); 
        
        renderDifferentiatorChart(json.features);

    }).catch(err => {
        $("#btnClassify").prop("disabled", false).text("Clasificar");
        $("#iaResults").html('<li class="list-group-item list-group-item-danger">Error de conexión con el clasificador.</li>');
    });
}

function renderDifferentiatorChart(features){
    if(differentiatorChart) differentiatorChart.destroy();
    
    const labels = ['Valores de textura (GLCM)', 'Niveles de opacidad', 'Dist. Pixeles Lóbulo'];
    const data = [features.glcm_value, features.opacity_level, features.lobe_pixel_dist];
    
    const ctx = document.getElementById("differentiatorChart").getContext("2d");
    differentiatorChart = new Chart(ctx, {
        type: 'radar',
        data: {
            labels: labels,
            datasets: [{
                label: 'Características de la Radiografía',
                data: data,
                backgroundColor: 'rgba(255, 159, 64, 0.2)',
                borderColor: 'rgb(255, 159, 64)',
                pointBackgroundColor: 'rgb(255, 159, 64)',
                pointBorderColor: '#fff',
                pointHoverBackgroundColor: '#fff',
                pointHoverBorderColor: 'rgb(255, 159, 64)'
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            elements: { line: { borderWidth: 3 } },
            scales: {
                r: {
                    angleLines: { display: false },
                    suggestedMin: 0,
                    suggestedMax: 1, 
                    pointLabels: { font: { size: 14 } }
                }
            },
            plugins: { legend: { display: false } }
        }
    });
}

function generateReport(){
const name = $("#iaXraySelector").val();
if(!name) return;

$("#btnGenerateReport").prop("disabled", true).text("Generando PDF...");

    // 🛑 CAMBIO CLAVE: Usa el nuevo endpoint '/generate_report_desktop' 
fetch(API + `/generate_report_desktop?name=${encodeURIComponent(name)}`).then(r => {
        $("#btnGenerateReport").prop("disabled", false).text("Generar Reporte Automático (PDF)");
        
        if(r.ok){
        r.blob().then(blob => {
                const url = window.URL.createObjectURL(blob);
                const a = document.createElement('a');
                a.style.display = 'none';
                a.href = url;
                // Opcional: puedes cambiar el nombre del archivo si quieres que diga 'Web'
                a.download = `Reporte_IA_${name.replace(/\..+$/, '')}.pdf`; 
                document.body.appendChild(a);
                a.click();
                window.URL.revokeObjectURL(url);
        });
        } else {
        alert("Error al generar el reporte PDF. Asegúrate de haber clasificado la imagen.");
        }
}).catch(err => {
        $("#btnGenerateReport").prop("disabled", false).text("Generar Reporte Automático (PDF)");
        alert("Error de conexión al servidor al generar el reporte.");
});
}


function batchClassifyXrays() {
    const btn = $("#btnBatchClassify");
    const container = $("#batchResultsContainer");
    
    btn.prop("disabled", true).text("Analizando todas las imágenes...");
    container.html('<div class="alert alert-info">Cargando resultados...</div>');

    fetch(API + "/batch_classify").then(r => r.json()).then(json => {
        btn.prop("disabled", false).text("Ejecutar Análisis Masivo");

        if(json.error) {
            container.html(`<div class="alert alert-danger">Error al obtener resultados: ${json.error}</div>`);
            return;
        }

        const { total_images, analyzed_count, unanalyzed_count, class_counts } = json;
        
        // Calcular porcentajes de distribución de patologías (basado en imágenes analizadas)
        const totalAnalyzed = analyzed_count > 0 ? analyzed_count : 1; // Evitar división por cero
        
        let html = `
            <table class="table table-striped table-sm mt-3">
                <thead class="table-warning">
                    <tr>
                        <th colspan="2" class="text-center">Resumen de Clasificación Masiva</th>
                    </tr>
                </thead>
                <tbody>
                    <tr>
                        <td><strong>Total de Imágenes Detectadas:</strong></td>
                        <td class="text-end">${total_images}</td>
                    </tr>
                    <tr>
                        <td><strong>Imágenes Analizadas:</strong></td>
                        <td class="text-end">${analyzed_count} (${(analyzed_count / total_images * 100).toFixed(1)}%)</td>
                    </tr>
                    <tr>
                        <td><strong>Imágenes No Analizadas:</strong></td>
                        <td class="text-end">${unanalyzed_count} (${(unanalyzed_count / total_images * 100).toFixed(1)}%)</td>
                    </tr>
                    <tr><td colspan="2" class="text-center bg-light"><strong>Distribución de Patologías (del ${analyzed_count} Analizado)</strong></td></tr>
                    <tr>
                        <td>COVID:</td>
                        <td class="text-end">${class_counts.covid} (${(class_counts.covid / totalAnalyzed * 100).toFixed(1)}%)</td>
                    </tr>
                    <tr>
                        <td>Neumonía Viral:</td>
                        <td class="text-end">${class_counts.viral_pneumonia} (${(class_counts.viral_pneumonia / totalAnalyzed * 100).toFixed(1)}%)</td>
                    </tr>
                    <tr>
                        <td>Opacidad Pulmonar:</td>
                        <td class="text-end">${class_counts.lung_opacity} (${(class_counts.lung_opacity / totalAnalyzed * 100).toFixed(1)}%)</td>
                    </tr>
                    <tr>
                        <td>Normal:</td>
                        <td class="text-end">${class_counts.normal} (${(class_counts.normal / totalAnalyzed * 100).toFixed(1)}%)</td>
                    </tr>
                </tbody>
            </table>
        `;

        container.html(html);

    }).catch(err => {
        btn.prop("disabled", false).text("Ejecutar Análisis Masivo");
        container.html('<div class="alert alert-danger">Error de conexión con el servidor.</div>');
    });
}