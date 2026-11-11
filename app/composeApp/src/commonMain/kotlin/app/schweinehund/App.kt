package app.schweinehund

import androidx.compose.foundation.Canvas
import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.safeDrawingPadding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.Button
import androidx.compose.material3.ButtonDefaults
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Text
import androidx.compose.material3.lightColorScheme
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.Path
import androidx.compose.ui.graphics.StrokeCap
import androidx.compose.ui.graphics.StrokeJoin
import androidx.compose.ui.graphics.drawscope.Stroke
import androidx.compose.ui.text.SpanStyle
import androidx.compose.ui.text.buildAnnotatedString
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.font.FontStyle
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.withStyle
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import kotlinx.coroutines.launch
import kotlin.math.max
import kotlin.math.min
import kotlin.random.Random

/** Design „weiches Grau“ – Schiefer statt Schwarz, warmes Orange als Akzent. */
object Farben {
    val Grund = Color(0xFFF3F4F7)
    val Schiefer = Color(0xFF454B5A)
    val Tinte = Color(0xFF2E3340)
    val Grau = Color(0xFF6A6F7A)
    val Hell = Color(0xFFDDE0E6)
    val Orange = Color(0xFFEF7448)
    val OrangeHell = Color(0xFFFBE3D8)
    val Gruen = Color(0xFF9CC65A)
    val Weiss = Color(0xFFFFFFFF)
    val Schleier = Color(0x99454B5A)
}

private val QUELLEN_TEXT = mapOf("datei" to "Datei", "bild" to "Bild", "health-connect" to "Health Connect")

/** Ein geteilter Lauf, der auf Bestätigung wartet – oder ein Satz, warum er nicht gelesen werden konnte. */
private data class Wartend(val vorschau: Vorschau?, val fehler: String?, val name: String)

@Composable
fun App(
    server: ServerDienst,
    plattform: Plattform,
    appVersion: String,
    geteilt: List<GeteilteDatei>,
    geteiltErledigt: () -> Unit,
) {
    val geraetId = remember {
        plattform.lesen("geraet_id") ?: ("g-" + (1..24).map { "0123456789abcdef"[Random.nextInt(16)] }.joinToString(""))
            .also { plattform.schreiben("geraet_id", it) }
    }
    var name by remember { mutableStateOf(plattform.lesen("laeufer") ?: "") }
    var zustand by remember { mutableStateOf<ServerZustand>(ServerZustand.Laedt) }
    var laeufe by remember { mutableStateOf<List<LaufAnzeige>>(emptyList()) }
    var meldung by remember { mutableStateOf("") }
    var warteschlange by remember { mutableStateOf<List<Wartend>>(emptyList()) }
    var detail by remember { mutableStateOf<LaufAnzeige?>(null) }
    var beschaeftigt by remember { mutableStateOf(false) }
    val scope = rememberCoroutineScope()

    suspend fun neuLaden() {
        server.liste(geraetId).let { a -> if (a.wert != null) laeufe = a.wert else if (a.fehler != null) meldung = a.fehler }
    }

    LaunchedEffect(Unit) {
        zustand = server.status()
        if (zustand is ServerZustand.Erreichbar) neuLaden()
    }

    LaunchedEffect(geteilt) {
        if (geteilt.isEmpty()) return@LaunchedEffect
        val dateien = geteilt.toList()
        // Eigene Coroutine: geteiltErledigt() ändert den Schlüssel dieses Effekts und würde ihn sonst abbrechen.
        scope.launch {
        for (datei in dateien) {
            meldung = "Lese ${datei.name} …"
            val antwort = if (datei.istBild) {
                val text = plattform.texterkennung(datei)
                if (text.isNullOrBlank()) Antwort(null, "Auf dem Bild wurde kein Text erkannt.") else server.vorschauText(text)
            } else server.vorschauDatei(datei)
            warteschlange = warteschlange + Wartend(antwort.wert, antwort.fehler, datei.name)
        }
        meldung = ""
        }
        geteiltErledigt()
    }

    MaterialTheme(colorScheme = lightColorScheme(primary = Farben.Orange, background = Farben.Grund, onSurface = Farben.Tinte)) {
        Box(Modifier.fillMaxSize().background(Farben.Grund).safeDrawingPadding()) {
            val offen = detail
            if (offen != null) {
                LaufDetail(offen) { detail = null }
            } else {
                Startseite(
                    zustand = zustand, laeufe = laeufe, name = name, meldung = meldung, beschaeftigt = beschaeftigt,
                    appVersion = appVersion,
                    nameAendern = { name = it; plattform.schreiben("laeufer", it.trim()) },
                    laufOeffnen = { lauf ->
                        scope.launch {
                            val id = lauf.id ?: return@launch
                            server.detail(id, geraetId).let { a -> if (a.wert != null) detail = a.wert else meldung = a.fehler ?: "" }
                        }
                    },
                    healthConnect = {
                        scope.launch {
                            beschaeftigt = true
                            meldung = when {
                                !plattform.healthConnectVerfuegbar() -> "Health Connect ist auf diesem Handy nicht verfügbar."
                                !plattform.healthConnectErlaubnis() -> "Ohne Erlaubnis kann die App keine Läufe aus Health Connect lesen."
                                else -> {
                                    val sitzungen = plattform.healthConnectSitzungen(60)
                                    if (sitzungen.isEmpty()) "In Health Connect wurden keine Läufe der letzten 60 Tage gefunden."
                                    else server.healthConnect(geraetId, name.trim(), sitzungen).let { it.wert ?: it.fehler ?: "" }
                                }
                            }
                            neuLaden()
                            beschaeftigt = false
                        }
                    },
                    testPush = {
                        scope.launch {
                            beschaeftigt = true
                            val token = plattform.pushToken()
                            meldung = if (token == null) "Push ist in dieser App-Version nicht eingerichtet." else server.pushProbe(token)
                            beschaeftigt = false
                        }
                    },
                    nochmal = { scope.launch { zustand = ServerZustand.Laedt; zustand = server.status(); neuLaden() } },
                )
            }

            val oben = warteschlange.firstOrNull()
            if (oben != null) {
                Kontrollkarte(
                    eintrag = oben, appVersion = appVersion, name = name, beschaeftigt = beschaeftigt,
                    nameAendern = { name = it; plattform.schreiben("laeufer", it.trim()) },
                    speichern = { v ->
                        scope.launch {
                            beschaeftigt = true
                            val a = server.bestaetigen(v.entwurf, geraetId, name.trim(), plattform.pushToken())
                            meldung = a.wert ?: a.fehler ?: ""
                            warteschlange = warteschlange.drop(1)
                            neuLaden()
                            beschaeftigt = false
                        }
                    },
                    verwerfen = { warteschlange = warteschlange.drop(1) },
                )
            }
        }
    }
}

@Composable
private fun Startseite(
    zustand: ServerZustand,
    laeufe: List<LaufAnzeige>,
    name: String,
    meldung: String,
    beschaeftigt: Boolean,
    appVersion: String,
    nameAendern: (String) -> Unit,
    laufOeffnen: (LaufAnzeige) -> Unit,
    healthConnect: () -> Unit,
    testPush: () -> Unit,
    nochmal: () -> Unit,
) {
    Column(
        Modifier.fillMaxSize().verticalScroll(rememberScrollState()).padding(horizontal = 20.dp, vertical = 22.dp),
        verticalArrangement = Arrangement.spacedBy(16.dp),
    ) {
        Row(verticalAlignment = Alignment.CenterVertically) {
            Text(
                buildAnnotatedString { append("SCHWEINEHUND"); withStyle(SpanStyle(color = Farben.Orange)) { append(".") } },
                color = Farben.Tinte, fontWeight = FontWeight.ExtraBold, fontSize = 15.sp, letterSpacing = 1.4.sp,
                modifier = Modifier.weight(1f),
            )
            val punkt = when (zustand) {
                is ServerZustand.Erreichbar -> Farben.Gruen
                is ServerZustand.Fehler -> Farben.Orange
                ServerZustand.Laedt -> Farben.Hell
            }
            Box(Modifier.size(8.dp).clip(CircleShape).background(punkt))
            Spacer(Modifier.size(6.dp))
            Text(statusText(zustand), color = Farben.Grau, fontSize = 12.sp)
        }
        Text("Meine Läufe", color = Farben.Tinte, fontWeight = FontWeight.ExtraBold, fontSize = 32.sp)

        if (zustand is ServerZustand.Fehler) {
            Button(onClick = nochmal, colors = ButtonDefaults.buttonColors(containerColor = Farben.Orange)) { Text("Nochmal verbinden") }
        }
        if (meldung.isNotBlank()) {
            Text(meldung, color = Farben.Tinte, fontSize = 14.sp,
                modifier = Modifier.fillMaxWidth().clip(RoundedCornerShape(14.dp)).background(Farben.OrangeHell).padding(12.dp))
        }

        Karte(dunkel = true) {
            Text("SO KOMMT EIN LAUF REIN", color = Farben.Hell, fontWeight = FontWeight.Bold, fontSize = 12.sp, letterSpacing = 1.4.sp)
            Text("Huawei Health: Lauf öffnen → Route exportieren → GPX → Teilen → Schweinehund.",
                color = Farben.Weiss, fontSize = 15.sp, lineHeight = 21.sp)
            Text("Garmin: läuft über Health Connect – einmal abgleichen genügt. Das Teilen-Bild bringt Puls und Kadenz dazu.",
                color = Farben.Hell, fontSize = 13.sp, lineHeight = 19.sp)
            Button(onClick = healthConnect, enabled = !beschaeftigt, shape = RoundedCornerShape(12.dp),
                colors = ButtonDefaults.buttonColors(containerColor = Farben.Orange)) { Text("Health Connect abgleichen") }
        }

        OutlinedTextField(value = name, onValueChange = nameAendern, singleLine = true,
            label = { Text("Dein Name in der Familie") }, modifier = Modifier.fillMaxWidth())

        if (laeufe.isEmpty() && zustand is ServerZustand.Erreichbar) {
            Text("Noch keine Läufe. Teile deinen ersten Lauf an Schweinehund – Horst wartet (ungern).",
                color = Farben.Grau, fontFamily = FontFamily.Serif, fontStyle = FontStyle.Italic, fontSize = 16.sp)
        }
        laeufe.forEach { lauf -> LaufZeile(lauf) { laufOeffnen(lauf) } }

        Spacer(Modifier.height(8.dp))
        OutlinedButton(onClick = testPush, enabled = !beschaeftigt) { Text("Test-Push anfordern", color = Farben.Tinte) }
        Text("App v$appVersion", color = Farben.Grau, fontSize = 12.sp)
    }
}

@Composable
private fun Karte(dunkel: Boolean = false, inhalt: @Composable () -> Unit) {
    Column(
        Modifier.fillMaxWidth().clip(RoundedCornerShape(22.dp)).background(if (dunkel) Farben.Schiefer else Farben.Weiss).padding(18.dp),
        verticalArrangement = Arrangement.spacedBy(10.dp),
    ) { inhalt() }
}

@Composable
private fun LaufZeile(lauf: LaufAnzeige, oeffnen: () -> Unit) {
    Column(
        Modifier.fillMaxWidth().clip(RoundedCornerShape(18.dp)).background(Farben.Weiss).clickable(onClick = oeffnen).padding(16.dp),
        verticalArrangement = Arrangement.spacedBy(4.dp),
    ) {
        Row(verticalAlignment = Alignment.Bottom) {
            Text("${lauf.distanzKm} km", color = Farben.Tinte, fontWeight = FontWeight.ExtraBold, fontSize = 24.sp, modifier = Modifier.weight(1f))
            Text(lauf.startText, color = Farben.Grau, fontSize = 13.sp)
        }
        Text(listOfNotNull(lauf.dauer, lauf.tempo, lauf.anstiegM?.let { "↑ $it m" }, lauf.puls?.let { "♥ $it" }).joinToString("  ·  "),
            color = Farben.Tinte, fontSize = 14.sp)
        Text(lauf.quellen.joinToString(" + ") { QUELLEN_TEXT[it] ?: it } + if (lauf.hatStrecke) "  ·  mit Strecke" else "",
            color = Farben.Grau, fontSize = 12.sp)
    }
}

@Composable
private fun Kontrollkarte(
    eintrag: Wartend,
    appVersion: String,
    name: String,
    beschaeftigt: Boolean,
    nameAendern: (String) -> Unit,
    speichern: (Vorschau) -> Unit,
    verwerfen: () -> Unit,
) {
    Box(Modifier.fillMaxSize().background(Farben.Schleier).clickable(enabled = false) {}, contentAlignment = Alignment.BottomCenter) {
        Column(
            Modifier.fillMaxWidth().clip(RoundedCornerShape(topStart = 28.dp, topEnd = 28.dp)).background(Farben.Weiss).padding(22.dp),
            verticalArrangement = Arrangement.spacedBy(12.dp),
        ) {
            val v = eintrag.vorschau
            if (v == null) {
                Text("Das hat nicht geklappt", color = Farben.Tinte, fontWeight = FontWeight.ExtraBold, fontSize = 22.sp)
                Text("${eintrag.name}: ${eintrag.fehler ?: "unbekannter Fehler"}", color = Farben.Tinte, fontSize = 15.sp)
                Text("App v$appVersion", color = Farben.Grau, fontSize = 12.sp)
                Button(onClick = verwerfen, colors = ButtonDefaults.buttonColors(containerColor = Farben.Orange)) { Text("Okay") }
                return@Column
            }
            val l = v.lauf
            Text("LAUF ERKANNT", color = Farben.Orange, fontWeight = FontWeight.Bold, fontSize = 12.sp, letterSpacing = 1.4.sp)
            Text("${l.distanzKm} km · ${l.dauer}", color = Farben.Tinte, fontWeight = FontWeight.ExtraBold, fontSize = 28.sp)
            Text(listOfNotNull(l.startText, l.tempo, l.anstiegM?.let { "↑ $it m" }, l.puls?.let { "Puls $it" }, l.kadenz?.let { "Kadenz $it" })
                .joinToString("  ·  "), color = Farben.Grau, fontSize = 14.sp)
            if (l.linie.size >= 2) Strecke(l.linie, Modifier.fillMaxWidth().height(180.dp).clip(RoundedCornerShape(16.dp)).background(Farben.Grund))
            if (name.isBlank()) {
                OutlinedTextField(value = name, onValueChange = nameAendern, singleLine = true,
                    label = { Text("Wer ist gelaufen? (dein Name)") }, modifier = Modifier.fillMaxWidth())
            }
            Row(horizontalArrangement = Arrangement.spacedBy(10.dp)) {
                OutlinedButton(onClick = verwerfen, enabled = !beschaeftigt, modifier = Modifier.weight(1f).height(50.dp)) {
                    Text("Verwerfen", color = Farben.Tinte)
                }
                Button(onClick = { speichern(v) }, enabled = !beschaeftigt && name.isNotBlank(),
                    modifier = Modifier.weight(1f).height(50.dp), shape = RoundedCornerShape(14.dp),
                    colors = ButtonDefaults.buttonColors(containerColor = Farben.Orange)) { Text("Speichern", fontWeight = FontWeight.Bold) }
            }
        }
    }
}

@Composable
private fun LaufDetail(lauf: LaufAnzeige, zurueck: () -> Unit) {
    Column(
        Modifier.fillMaxSize().verticalScroll(rememberScrollState()).padding(horizontal = 20.dp, vertical = 22.dp),
        verticalArrangement = Arrangement.spacedBy(14.dp),
    ) {
        OutlinedButton(onClick = zurueck) { Text("‹ Zurück", color = Farben.Tinte) }
        Text(lauf.startText, color = Farben.Orange, fontWeight = FontWeight.Bold, fontSize = 13.sp)
        Text("${lauf.distanzKm} km", color = Farben.Tinte, fontWeight = FontWeight.ExtraBold, fontSize = 40.sp)
        Text(listOfNotNull(lauf.dauer, lauf.tempo, lauf.anstiegM?.let { "↑ $it m" }).joinToString("  ·  "), color = Farben.Tinte, fontSize = 16.sp)
        val extra = listOfNotNull(lauf.puls?.let { "Puls Ø $it" }, lauf.kadenz?.let { "Kadenz $it" }, lauf.schritte?.let { "$it Schritte" })
        if (extra.isNotEmpty()) Text(extra.joinToString("  ·  "), color = Farben.Grau, fontSize = 14.sp)
        if (lauf.linie.size >= 2) {
            Strecke(lauf.linie, Modifier.fillMaxWidth().height(280.dp).clip(RoundedCornerShape(22.dp)).background(Farben.Weiss))
        } else {
            Text("Für diesen Lauf gibt es noch keine Strecke. Teile die GPX-Datei, dann erscheint sie hier.",
                color = Farben.Grau, fontSize = 14.sp)
        }
        if (lauf.kmZeiten.isNotEmpty()) {
            Karte {
                Text("Kilometer", color = Farben.Tinte, fontWeight = FontWeight.ExtraBold, fontSize = 18.sp)
                lauf.kmZeiten.forEachIndexed { i, zeit ->
                    Row { Text("km ${i + 1}", color = Farben.Grau, modifier = Modifier.weight(1f)); Text(zeit, color = Farben.Tinte, fontWeight = FontWeight.Bold) }
                }
                if (lauf.rest.isNotBlank()) Text("Rest: ${lauf.rest}", color = Farben.Grau, fontSize = 13.sp)
            }
        }
        Text("Quelle: " + lauf.quellen.joinToString(" + ") { QUELLEN_TEXT[it] ?: it }, color = Farben.Grau, fontSize = 12.sp)
    }
}

/** Strecke als Linie (ohne Kartenkacheln – die echte Karte folgt mit REQ-003). */
@Composable
fun Strecke(linie: List<Pair<Float, Float>>, modifier: Modifier) {
    Canvas(modifier) {
        if (linie.size < 2) return@Canvas
        val rand = 18.dp.toPx()
        val breite = size.width - 2 * rand
        val hoehe = size.height - 2 * rand
        val maxX = max(linie.maxOf { it.first }, 0.001f)
        val maxY = max(linie.maxOf { it.second }, 0.001f)
        val s = min(breite / maxX, hoehe / maxY)
        val ox = rand + (breite - maxX * s) / 2
        val oy = rand + (hoehe - maxY * s) / 2
        val pfad = Path()
        linie.forEachIndexed { i, (x, y) -> if (i == 0) pfad.moveTo(ox + x * s, oy + y * s) else pfad.lineTo(ox + x * s, oy + y * s) }
        drawPath(pfad, Farben.Orange, style = Stroke(width = 4.dp.toPx(), cap = StrokeCap.Round, join = StrokeJoin.Round))
        val (sx, sy) = linie.first()
        drawCircle(Farben.Schiefer, radius = 6.dp.toPx(), center = Offset(ox + sx * s, oy + sy * s))
    }
}
