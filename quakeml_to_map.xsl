<?xml version="1.0" encoding="UTF-8"?>
<!--
  XSLT Transformation: QuakeML XML → Interactive Earthquake Map (HTML)
  
  Input:  USGS QuakeML XML (earthquakes.xml)
  Output: Standalone HTML page with Leaflet/OpenStreetMap interactive map
  
  Usage:
    1. Add this processing instruction to earthquakes.xml (line 2):
       <?xml-stylesheet type="text/xsl" href="quakeml_to_map.xsl"?>
    2. Open earthquakes.xml in a browser
    
    Or use a command-line XSLT processor:
       xsltproc quakeml_to_map.xsl earthquakes.xml > earthquake_map.html
-->
<xsl:stylesheet version="1.0"
  xmlns:xsl="http://www.w3.org/1999/XSL/Transform"
  xmlns:q="http://quakeml.org/xmlns/quakeml/1.2"
  xmlns:bed="http://quakeml.org/xmlns/bed/1.2">

  <xsl:output method="html" encoding="UTF-8" indent="yes"/>

  <!-- ════════════════════════════════════════════════════════ -->
  <!-- Root template                                           -->
  <!-- ════════════════════════════════════════════════════════ -->
  <xsl:template match="/">
    <html lang="en">
      <head>
        <meta charset="UTF-8"/>
        <meta name="viewport" content="width=device-width, initial-scale=1.0"/>
        <title>Global Earthquake Map — USGS Data</title>

        <!-- Leaflet CSS -->
        <link rel="stylesheet"
              href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css"
              integrity="sha256-p4NxAoJBhIIN+hmNHrzRCf9tD/miZyoHS5obTRR9BMY="
              crossorigin=""/>

        <style>
          /* ── Reset ── */
          * { margin: 0; padding: 0; box-sizing: border-box; }

          body {
            font-family: 'Segoe UI', system-ui, -apple-system, sans-serif;
            background: #0f172a;
            color: #e2e8f0;
          }

          /* ── Header ── */
          .header {
            background: linear-gradient(135deg, #1e293b 0%, #0f172a 100%);
            padding: 1.25rem 2rem;
            display: flex;
            align-items: center;
            justify-content: space-between;
            border-bottom: 1px solid #334155;
          }
          .header h1 {
            font-size: 1.4rem;
            font-weight: 600;
            background: linear-gradient(90deg, #38bdf8, #818cf8);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
          }
          .header .stats {
            font-size: 0.85rem;
            color: #94a3b8;
          }
          .header .stats span {
            color: #38bdf8;
            font-weight: 600;
          }

          /* ── Map ── */
          #map {
            width: 100%;
            height: calc(100vh - 64px);
          }

          /* ── Legend ── */
          .legend {
            background: rgba(15, 23, 42, 0.92);
            border: 1px solid #334155;
            border-radius: 8px;
            padding: 12px 16px;
            font-size: 0.8rem;
            line-height: 1.6;
            backdrop-filter: blur(8px);
          }
          .legend h4 {
            margin-bottom: 6px;
            color: #e2e8f0;
            font-size: 0.85rem;
          }
          .legend-item {
            display: flex;
            align-items: center;
            gap: 8px;
          }
          .legend-dot {
            width: 12px;
            height: 12px;
            border-radius: 50%;
            display: inline-block;
            border: 1px solid rgba(255,255,255,0.2);
          }

          /* ── Table ── */
          .info-table {
            width: 100%;
            border-collapse: collapse;
            font-size: 0.85rem;
          }
          .info-table th {
            text-align: left;
            color: #94a3b8;
            padding: 2px 6px 2px 0;
            font-weight: 500;
          }
          .info-table td {
            padding: 2px 0;
            color: #e2e8f0;
          }

          /* ── Leaflet popup override ── */
          .leaflet-popup-content-wrapper {
            background: #1e293b !important;
            color: #e2e8f0 !important;
            border: 1px solid #334155 !important;
            border-radius: 8px !important;
            box-shadow: 0 8px 32px rgba(0,0,0,0.4) !important;
          }
          .leaflet-popup-tip {
            background: #1e293b !important;
            border: 1px solid #334155 !important;
          }
          .leaflet-popup-content {
            margin: 10px 14px !important;
          }
          .popup-title {
            font-weight: 600;
            font-size: 0.95rem;
            margin-bottom: 6px;
            color: #38bdf8;
          }
        </style>
      </head>

      <body>
        <!-- Header -->
        <div class="header">
          <h1>🌍 Global Earthquake Map</h1>
          <div class="stats">
            <span><xsl:value-of select="count(//bed:event)"/></span> earthquakes ·
            Source: USGS Earthquake Catalog API
          </div>
        </div>

        <!-- Map container -->
        <div id="map"></div>

        <!-- Leaflet JS -->
        <script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"
                integrity="sha256-20nQCchB9co0qIjJZRGuk2/Z9VM+kNiyxNV1lvTlZBo="
                crossorigin=""></script>

        <!-- Build earthquake data array from XML via XSLT -->
        <script>
          var quakes = [
            <xsl:for-each select="//bed:event">
              <xsl:variable name="lat"  select="bed:origin/bed:latitude/bed:value"/>
              <xsl:variable name="lon"  select="bed:origin/bed:longitude/bed:value"/>
              <xsl:variable name="mag"  select="bed:magnitude/bed:mag/bed:value"/>
              <xsl:variable name="dep"  select="bed:origin/bed:depth/bed:value"/>
              <xsl:variable name="time" select="bed:origin/bed:time/bed:value"/>
              <xsl:variable name="place" select="bed:description/bed:text"/>
              <xsl:variable name="mtype" select="bed:magnitude/bed:type"/>
              {
                lat: <xsl:value-of select="$lat"/>,
                lon: <xsl:value-of select="$lon"/>,
                mag: <xsl:value-of select="$mag"/>,
                depth: <xsl:value-of select="round($dep div 1000)"/>,
                time: "<xsl:value-of select="$time"/>",
                place: "<xsl:call-template name="escape-js">
                          <xsl:with-param name="text" select="$place"/>
                        </xsl:call-template>",
                magType: "<xsl:value-of select="$mtype"/>"
              }<xsl:if test="position() != last()">,</xsl:if>
            </xsl:for-each>
          ];
        </script>

        <!-- Map initialisation -->
        <script>
          // Initialise map centred on (0, 0) with zoom level 2
          var map = L.map('map', {
            center: [20, 0],
            zoom: 2,
            zoomControl: true,
            preferCanvas: true
          });

          // Dark tile layer (CartoDB Dark Matter)
          L.tileLayer('https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png', {
            attribution: '© OpenStreetMap contributors · © CARTO',
            subdomains: 'abcd',
            maxZoom: 19
          }).addTo(map);

          // Colour based on magnitude
          function magColor(m) {
            if (m >= 7)   return '#ef4444';   // red
            if (m >= 5.5) return '#f97316';   // orange
            if (m >= 4)   return '#facc15';   // yellow
            if (m >= 3)   return '#22c55e';   // green
            return '#3b82f6';                  // blue
          }

          // Radius based on magnitude
          function magRadius(m) {
            if (m >= 7)   return 16;
            if (m >= 5.5) return 12;
            if (m >= 4)   return 8;
            if (m >= 3)   return 5;
            return 4;
          }

          // Add markers
          quakes.forEach(function(q) {
            var color = magColor(q.mag);
            var marker = L.circleMarker([q.lat, q.lon], {
              radius: magRadius(q.mag),
              fillColor: color,
              color: color,
              weight: 1,
              opacity: 0.8,
              fillOpacity: 0.55
            }).addTo(map);

            var popup =
              '<div class="popup-title">' + q.place + '</div>' +
              '<table class="info-table">' +
              '<tr><th>Magnitude</th><td>' + q.mag + ' ' + q.magType + '</td></tr>' +
              '<tr><th>Depth</th><td>' + q.depth + ' km</td></tr>' +
              '<tr><th>Time (UTC)</th><td>' + q.time.replace('T', ' ').replace('Z', '') + '</td></tr>' +
              '<tr><th>Coordinates</th><td>' + q.lat.toFixed(2) + '°, ' + q.lon.toFixed(2) + '°</td></tr>' +
              '</table>';

            marker.bindPopup(popup, { maxWidth: 300 });
          });

          // Legend control
          var legend = L.control({ position: 'bottomright' });
          legend.onAdd = function() {
            var div = L.DomUtil.create('div', 'legend');
            div.innerHTML =
              '<h4>Magnitude</h4>' +
              '<div class="legend-item"><span class="legend-dot" style="background:#ef4444"></span> 7.0+  (Major)</div>' +
              '<div class="legend-item"><span class="legend-dot" style="background:#f97316"></span> 5.5–6.9 (Strong)</div>' +
              '<div class="legend-item"><span class="legend-dot" style="background:#facc15"></span> 4.0–5.4 (Moderate)</div>' +
              '<div class="legend-item"><span class="legend-dot" style="background:#22c55e"></span> 3.0–3.9 (Light)</div>' +
              '<div class="legend-item"><span class="legend-dot" style="background:#3b82f6"></span> &lt; 3.0 (Minor)</div>';
            return div;
          };
          legend.addTo(map);

          // Auto-fit bounds if we have data
          if (quakes.length > 0) {
            var bounds = L.latLngBounds(quakes.map(function(q) { return [q.lat, q.lon]; }));
            map.fitBounds(bounds, { padding: [50, 50], maxZoom: 6 });
          }
        </script>
      </body>
    </html>
  </xsl:template>

  <!-- ════════════════════════════════════════════════════════ -->
  <!-- Helper: escape quotes for JavaScript strings            -->
  <!-- ════════════════════════════════════════════════════════ -->
  <xsl:template name="escape-js">
    <xsl:param name="text"/>
    <xsl:choose>
      <xsl:when test="contains($text, '&quot;')">
        <xsl:value-of select="substring-before($text, '&quot;')"/>
        <xsl:text>\"</xsl:text>
        <xsl:call-template name="escape-js">
          <xsl:with-param name="text" select="substring-after($text, '&quot;')"/>
        </xsl:call-template>
      </xsl:when>
      <xsl:otherwise>
        <xsl:value-of select="$text"/>
      </xsl:otherwise>
    </xsl:choose>
  </xsl:template>

</xsl:stylesheet>
