package app.schweinehund

import androidx.compose.animation.AnimatedVisibility
import androidx.compose.animation.core.tween
import androidx.compose.animation.fadeIn
import androidx.compose.animation.fadeOut
import androidx.compose.foundation.Canvas
import androidx.compose.foundation.Image
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
import androidx.compose.foundation.gestures.detectTapGestures
import androidx.compose.foundation.gestures.rememberTransformableState
import androidx.compose.foundation.gestures.transformable
import androidx.compose.foundation.horizontalScroll
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.aspectRatio
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.offset
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.CompositionLocalProvider
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableFloatStateOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.produceState
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.runtime.staticCompositionLocalOf
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.draw.shadow
import androidx.compose.ui.graphics.Path
import androidx.compose.ui.graphics.StrokeCap
import androidx.compose.ui.graphics.StrokeJoin
import androidx.compose.ui.graphics.drawscope.Stroke
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.ImageBitmap
import androidx.compose.ui.graphics.graphicsLayer
import androidx.compose.ui.input.pointer.pointerInput
import androidx.compose.ui.layout.ContentScale
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp

/** Holt Fotos vom Server und macht daraus anzeigbare Bilder (REQ-013). Fertige Bilder bleiben im Speicher. */
class BildLader(private val server: ServerDienst, private val plattform: Plattform) {
    private val fertig = mutableMapOf<String, ImageBitmap>()

    fun schonDa(pfad: String): ImageBitmap? = fertig[pfad]

    suspend fun laden(pfad: String): ImageBitmap? {
        fertig[pfad]?.let { return it }
        val daten = server.bild(pfad) ?: return null
        return plattform.bildAnzeigen(daten)?.also { if (fertig.size > 60) fertig.clear(); fertig[pfad] = it }
    }

    fun anzeigen(daten: ByteArray): ImageBitmap? = plattform.bildAnzeigen(daten)
}

val LocalBildLader = staticCompositionLocalOf<BildLader?> { null }

@Composable
fun MitBildLader(lader: BildLader, inhalt: @Composable () -> Unit) =
    CompositionLocalProvider(LocalBildLader provides lader, content = inhalt)

/** Ein Foto vom Server – bis es da ist, eine ruhige graue Fläche. */
@Composable
fun FotoBild(pfad: String, modifier: Modifier, beschreibung: String = "Foto zum Lauf", fuellen: Boolean = true) {
    val lader = LocalBildLader.current
    val bild by produceState(lader?.schonDa(pfad), pfad) { if (value == null) value = lader?.laden(pfad) }
    Box(modifier.background(Farben.Hell), contentAlignment = Alignment.Center) {
        AnimatedVisibility(bild != null, enter = fadeIn(tween(280)), exit = fadeOut()) {
            bild?.let {
                Image(it, beschreibung, Modifier.fillMaxSize(), contentScale = if (fuellen) ContentScale.Crop else ContentScale.Fit)
            }
        }
    }
}

/** Lauf-Liste: kleine runde Vorschaubilder, leicht überlappend. */
@Composable
fun FotoVorschauen(fotos: List<Foto>, groesse: Int = 46) {
    if (fotos.isEmpty()) return
    Box(Modifier.width((groesse + (fotos.size - 1) * groesse * 0.55f).dp).height(groesse.dp)) {
        fotos.forEachIndexed { i, f ->
            FotoBild(f.vorschau, Modifier.offset(x = (i * groesse * 0.55f).dp).size(groesse.dp).clip(CircleShape)
                .border(2.dp, Farben.Weiss, CircleShape))
        }
    }
}

/** REQ-014: Lauf-Liste – kleine Streckenzeichnung, die Fotos sitzen als Mini-Bilder an ihrer Stelle. */
@Composable
fun MiniStrecke(linie: List<Pair<Float, Float>>, fotos: List<Foto>, breite: Int = 112, hoehe: Int = 92) {
    val rand = 14f
    val maxX = linie.maxOf { it.first }.coerceAtLeast(0.001f)
    val maxY = linie.maxOf { it.second }.coerceAtLeast(0.001f)
    val s = minOf((breite - 2 * rand) / maxX, (hoehe - 2 * rand) / maxY)
    val ox = rand + (breite - 2 * rand - maxX * s) / 2
    val oy = rand + (hoehe - 2 * rand - maxY * s) / 2
    Box(Modifier.width(breite.dp).height(hoehe.dp).clip(RoundedCornerShape(14.dp)).background(Farben.Grund)) {
        Canvas(Modifier.fillMaxSize()) {
            val d = density
            val pfad = Path()
            linie.forEachIndexed { i, (x, y) ->
                val px = (ox + x * s) * d
                val py = (oy + y * s) * d
                if (i == 0) pfad.moveTo(px, py) else pfad.lineTo(px, py)
            }
            drawPath(pfad, Farben.Orange, style = Stroke(width = 3.dp.toPx(), cap = StrokeCap.Round, join = StrokeJoin.Round))
            val (sx, sy) = linie.first()
            drawCircle(Farben.Schiefer, radius = 3.5.dp.toPx(), center = Offset((ox + sx * s) * d, (oy + sy * s) * d))
        }
        val g = 26
        fotos.forEach { f ->
            val (x, y) = f.mini ?: return@forEach
            FotoBild(f.vorschau, Modifier.offset(x = (ox + x * s - g / 2f).dp, y = (oy + y * s - g / 2f).dp).size(g.dp)
                .shadow(3.dp, CircleShape).clip(CircleShape).border(2.dp, Farben.Weiss, CircleShape))
        }
    }
}

/** Lauf-Detail: Fotos groß oben; beim eigenen Lauf Knöpfe zum Hinzufügen. */
@Composable
fun FotoStreifen(
    lauf: LaufAnzeige,
    beschaeftigt: Boolean,
    hinzufuegen: (kamera: Boolean) -> Unit,
    oeffnen: (Int) -> Unit,
) {
    val fotos = lauf.fotos
    when {
        fotos.size == 1 -> {
            val f = fotos.first()
            val verhaeltnis = if (f.breite > 0 && f.hoehe > 0) (f.breite.toFloat() / f.hoehe).coerceIn(0.75f, 1.6f) else 1f
            FotoBild(f.url, Modifier.fillMaxWidth().aspectRatio(verhaeltnis).clip(RoundedCornerShape(22.dp)).clickable { oeffnen(0) })
        }
        fotos.size > 1 -> Row(Modifier.horizontalScroll(rememberScrollState()), horizontalArrangement = Arrangement.spacedBy(10.dp)) {
            fotos.forEachIndexed { i, f ->
                val breite = if (f.breite > 0 && f.hoehe > 0) (300f * f.breite / f.hoehe).coerceIn(220f, 400f) else 260f
                FotoBild(f.url, Modifier.width(breite.dp).height(300.dp).clip(RoundedCornerShape(20.dp)).clickable { oeffnen(i) })
            }
        }
    }
    if (lauf.eigen && fotos.size < MAX_FOTOS) {
        Row(horizontalArrangement = Arrangement.spacedBy(8.dp), verticalAlignment = Alignment.CenterVertically) {
            Auswahl(if (fotos.isEmpty()) "📷  Selfie aufnehmen" else "📷  Noch ein Foto", gewaehlt = false, aktiv = !beschaeftigt) { hinzufuegen(true) }
            Auswahl("🖼  Aus Galerie", gewaehlt = false, aktiv = !beschaeftigt) { hinzufuegen(false) }
        }
        if (fotos.isEmpty()) Text("Bis zu $MAX_FOTOS Fotos – die ganze Familie sieht sie.", color = Farben.Grau, fontSize = 12.sp)
    }
}

/** Kontrollkarte: Fotos, die nach dem Speichern mit hochgeladen werden. */
@Composable
fun FotoAuswahlKarte(fotos: List<FotoDaten>, aktiv: Boolean, hinzufuegen: (kamera: Boolean) -> Unit, entfernen: (Int) -> Unit) {
    val lader = LocalBildLader.current
    Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
        if (fotos.isNotEmpty()) Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
            fotos.forEachIndexed { i, foto ->
                val bild = remember(foto) { lader?.anzeigen(foto.jpeg) }
                Box(Modifier.size(64.dp).clip(RoundedCornerShape(14.dp)).background(Farben.Hell).clickable(enabled = aktiv) { entfernen(i) }) {
                    bild?.let { Image(it, "Ausgewähltes Foto", Modifier.fillMaxSize(), contentScale = ContentScale.Crop) }
                    Text("✕", color = Farben.Weiss, fontSize = 12.sp, fontWeight = FontWeight.Bold,
                        modifier = Modifier.align(Alignment.TopEnd).padding(4.dp).clip(CircleShape).background(Farben.Schleier)
                            .padding(horizontal = 5.dp, vertical = 1.dp))
                }
            }
        }
        if (fotos.size < MAX_FOTOS) Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
            Auswahl(if (fotos.isEmpty()) "📷  Selfie dazu" else "📷  Noch eins", gewaehlt = false, aktiv = aktiv) { hinzufuegen(true) }
            Auswahl("🖼  Galerie", gewaehlt = false, aktiv = aktiv) { hinzufuegen(false) }
        }
    }
}

/** Vollbild: Pfeile für das nächste Foto, zwei Finger zum Zoomen, doppelt tippen setzt zurück. */
@Composable
fun FotoVollbild(fotos: List<Foto>, start: Int, eigen: Boolean, beschaeftigt: Boolean, loeschen: (Foto) -> Unit, schliessen: () -> Unit) {
    if (fotos.isEmpty()) return
    var index by remember(fotos) { mutableStateOf(start.coerceIn(0, fotos.size - 1)) }
    var zoom by remember(index) { mutableFloatStateOf(1f) }
    var verschiebung by remember(index) { mutableStateOf(Offset.Zero) }
    var nachfragen by remember(index) { mutableStateOf(false) }
    val zustand = rememberTransformableState { z, v, _ ->
        zoom = (zoom * z).coerceIn(1f, 5f)
        verschiebung = if (zoom == 1f) Offset.Zero else verschiebung + v
    }
    val foto = fotos[index.coerceIn(0, fotos.size - 1)]
    Box(Modifier.fillMaxSize().background(Color(0xF22E3340)).clickable(enabled = false) {}) {
        FotoBild(
            foto.url,
            Modifier.fillMaxSize().padding(vertical = 64.dp)
                .pointerInput(foto.id) { detectTapGestures(onDoubleTap = { zoom = 1f; verschiebung = Offset.Zero }) }
                .transformable(zustand)
                .graphicsLayer(scaleX = zoom, scaleY = zoom, translationX = verschiebung.x, translationY = verschiebung.y),
            fuellen = false,
        )
        Row(Modifier.fillMaxWidth().padding(12.dp), verticalAlignment = Alignment.CenterVertically) {
            TextButton(onClick = schliessen) { Text("‹ Zurück", color = Farben.Weiss, fontSize = 16.sp) }
            Spacer(Modifier.weight(1f))
            val text = listOfNotNull(foto.ortText.ifBlank { null }, if (fotos.size > 1) "${index + 1} / ${fotos.size}" else null)
            if (text.isNotEmpty()) Text(text.joinToString("   ·   "), color = Farben.Hell, fontSize = 14.sp)
        }
        Column(Modifier.align(Alignment.BottomCenter).fillMaxWidth().padding(16.dp), horizontalAlignment = Alignment.CenterHorizontally,
            verticalArrangement = Arrangement.spacedBy(8.dp)) {
            if (fotos.size > 1) Row(horizontalArrangement = Arrangement.spacedBy(24.dp)) {
                TextButton(onClick = { index = (index - 1 + fotos.size) % fotos.size }) { Text("‹", color = Farben.Weiss, fontSize = 30.sp) }
                TextButton(onClick = { index = (index + 1) % fotos.size }) { Text("›", color = Farben.Weiss, fontSize = 30.sp) }
            }
            if (eigen) {
                if (!nachfragen) TextButton(onClick = { nachfragen = true }, enabled = !beschaeftigt) { Text("Foto löschen", color = Farben.Hell) }
                else Row(horizontalArrangement = Arrangement.spacedBy(8.dp), verticalAlignment = Alignment.CenterVertically) {
                    Text("Wirklich löschen?", color = Farben.Weiss, fontSize = 14.sp)
                    TextButton(onClick = { nachfragen = false }) { Text("Nein", color = Farben.Hell) }
                    TextButton(onClick = { loeschen(foto) }, enabled = !beschaeftigt) { Text("Ja, löschen", color = Farben.Orange) }
                }
            }
        }
    }
}
