package app.schweinehund

import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.DisposableEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.draw.shadow
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.viewinterop.AndroidView
import androidx.lifecycle.Lifecycle
import androidx.lifecycle.LifecycleEventObserver
import androidx.lifecycle.compose.LocalLifecycleOwner
import org.maplibre.android.MapLibre
import org.maplibre.android.camera.CameraUpdateFactory
import org.maplibre.android.geometry.LatLng
import org.maplibre.android.geometry.LatLngBounds
import org.maplibre.android.maps.MapLibreMap
import org.maplibre.android.maps.MapView
import org.maplibre.android.maps.Style
import org.maplibre.android.style.expressions.Expression
import org.maplibre.android.style.layers.CircleLayer
import org.maplibre.android.style.layers.LineLayer
import org.maplibre.android.style.layers.Property
import org.maplibre.android.style.layers.PropertyFactory
import org.maplibre.android.style.layers.SymbolLayer
import org.maplibre.android.style.sources.GeoJsonSource
import org.maplibre.geojson.Feature
import org.maplibre.geojson.FeatureCollection
import org.maplibre.geojson.LineString
import org.maplibre.geojson.Point

@Composable
actual fun LaufKarte(karte: KartenDaten, modifier: Modifier) {
    val context = LocalContext.current
    val lebenszyklus = LocalLifecycleOwner.current.lifecycle
    val ansicht = remember {
        MapLibre.getInstance(context)
        MapView(context).apply { onCreate(null) }
    }

    DisposableEffect(lebenszyklus, ansicht) {
        val beobachter = LifecycleEventObserver { _, ereignis ->
            when (ereignis) {
                Lifecycle.Event.ON_START -> ansicht.onStart()
                Lifecycle.Event.ON_RESUME -> ansicht.onResume()
                Lifecycle.Event.ON_PAUSE -> ansicht.onPause()
                Lifecycle.Event.ON_STOP -> ansicht.onStop()
                else -> Unit
            }
        }
        lebenszyklus.addObserver(beobachter)
        if (lebenszyklus.currentState.isAtLeast(Lifecycle.State.STARTED)) ansicht.onStart()
        if (lebenszyklus.currentState.isAtLeast(Lifecycle.State.RESUMED)) ansicht.onResume()
        onDispose {
            lebenszyklus.removeObserver(beobachter)
            ansicht.onPause()
            ansicht.onStop()
            ansicht.onDestroy()
        }
    }

    var karteBereit by remember { mutableStateOf<MapLibreMap?>(null) }
    Box(modifier) {
        AndroidView(factory = { ansicht }, modifier = Modifier.fillMaxSize())
        // Zoom-Knöpfe (zusätzlich zu den zwei Fingern)
        Column(Modifier.align(Alignment.TopEnd).padding(10.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
            ZoomKnopf("+") { karteBereit?.animateCamera(CameraUpdateFactory.zoomIn()) }
            ZoomKnopf("−") { karteBereit?.animateCamera(CameraUpdateFactory.zoomOut()) }
        }
    }

    DisposableEffect(karte) {
        ansicht.getMapAsync { map ->
            karteBereit = map
            map.uiSettings.isRotateGesturesEnabled = false
            map.uiSettings.isTiltGesturesEnabled = false
            map.uiSettings.isCompassEnabled = false
            map.setStyle(Style.Builder().fromUri(KARTEN_STIL)) { stil -> zeichnen(stil, karte) }
            val punkte = karte.punkte.map { LatLng(it.lat, it.lon) }.distinct()
            if (punkte.size >= 2) {
                val grenzen = LatLngBounds.Builder().includes(punkte).build()
                ansicht.post { map.moveCamera(CameraUpdateFactory.newLatLngBounds(grenzen, 60)) }
            } else if (punkte.size == 1) {
                map.moveCamera(CameraUpdateFactory.newLatLngZoom(punkte[0], 14.0))
            }
        }
        onDispose { }
    }
}

@Composable
private fun ZoomKnopf(zeichen: String, tippen: () -> Unit) {
    Box(
        Modifier.size(40.dp).shadow(3.dp, RoundedCornerShape(12.dp)).clip(RoundedCornerShape(12.dp))
            .background(Farben.Weiss).clickable(onClick = tippen),
        contentAlignment = Alignment.Center,
    ) { Text(zeichen, color = Farben.Tinte, fontWeight = FontWeight.Bold, fontSize = 22.sp) }
}

private fun zeichnen(stil: Style, karte: KartenDaten) {
    val linien = abschnitte(karte.punkte).map { (klasse, teil) ->
        Feature.fromGeometry(LineString.fromLngLats(teil.map { Point.fromLngLat(it.lon, it.lat) })).apply {
            addNumberProperty("k", klasse)
        }
    }
    stil.addSource(GeoJsonSource("strecke", FeatureCollection.fromFeatures(linien)))
    // weißer Rand unter der Strecke, damit sie auf jeder Karte gut lesbar ist
    stil.addLayer(LineLayer("strecke-rand", "strecke").withProperties(
        PropertyFactory.lineColor("#FFFFFF"), PropertyFactory.lineWidth(8f),
        PropertyFactory.lineCap(Property.LINE_CAP_ROUND), PropertyFactory.lineJoin(Property.LINE_JOIN_ROUND)))
    TEMPO_FARBEN.forEachIndexed { klasse, farbe ->
        stil.addLayer(LineLayer("strecke-$klasse", "strecke").withProperties(
            PropertyFactory.lineColor(farbe), PropertyFactory.lineWidth(5f),
            PropertyFactory.lineCap(Property.LINE_CAP_ROUND), PropertyFactory.lineJoin(Property.LINE_JOIN_ROUND),
        ).withFilter(Expression.eq(Expression.get("k"), Expression.literal(klasse))))
    }

    val start = karte.punkte.firstOrNull()
    val ziel = karte.punkte.lastOrNull()
    if (start != null && ziel != null) {
        val ende = listOf(
            Feature.fromGeometry(Point.fromLngLat(ziel.lon, ziel.lat)).apply { addStringProperty("art", "ziel") },
            Feature.fromGeometry(Point.fromLngLat(start.lon, start.lat)).apply { addStringProperty("art", "start") },
        )
        stil.addSource(GeoJsonSource("enden", FeatureCollection.fromFeatures(ende)))
        stil.addLayer(CircleLayer("enden", "enden").withProperties(
            PropertyFactory.circleRadius(7f), PropertyFactory.circleStrokeWidth(3f), PropertyFactory.circleStrokeColor("#FFFFFF"),
            PropertyFactory.circleColor(Expression.match(Expression.get("art"), Expression.literal("start"),
                Expression.color(android.graphics.Color.parseColor("#454B5A")),
                Expression.color(android.graphics.Color.parseColor("#2E3340")))),
        ))
    }

    val marken = karte.km.map { m ->
        Feature.fromGeometry(Point.fromLngLat(m.lon, m.lat)).apply { addStringProperty("km", m.km.toString()) }
    }
    stil.addSource(GeoJsonSource("km", FeatureCollection.fromFeatures(marken)))
    stil.addLayer(CircleLayer("km-punkt", "km").withProperties(
        PropertyFactory.circleRadius(9f), PropertyFactory.circleColor("#FFFFFF"),
        PropertyFactory.circleStrokeWidth(2f), PropertyFactory.circleStrokeColor("#454B5A")))
    stil.addLayer(SymbolLayer("km-text", "km").withProperties(
        PropertyFactory.textField(Expression.get("km")), PropertyFactory.textSize(11f),
        PropertyFactory.textColor("#2E3340"), PropertyFactory.textAllowOverlap(true), PropertyFactory.textIgnorePlacement(true)))
}
