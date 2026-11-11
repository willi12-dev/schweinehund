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
import androidx.compose.material3.NavigationBar
import androidx.compose.material3.NavigationBarItem
import androidx.compose.material3.NavigationBarItemDefaults
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
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

/** Die vier Bereiche der App (REQ-002). */
enum class Bereich(val titel: String, val zeichen: String) {
    Familie("Familie", "👪"), Laeufe("Läufe", "🏃"), Rangliste("Rangliste", "🏆"), Ich("Ich", "🙂")
}

@Composable
fun App(
    server: ServerDienst,
    plattform: Plattform,
    appVersion: String,
    geteilt: List<GeteilteDatei>,
    geteiltErledigt: () -> Unit,
    einladung: String? = null,
    einladungErledigt: () -> Unit = {},
) {
    val geraetId = remember {
        plattform.lesen("geraet_id") ?: ("g-" + (1..24).map { "0123456789abcdef"[Random.nextInt(16)] }.joinToString(""))
            .also { plattform.schreiben("geraet_id", it) }
    }
    var schluessel by remember {
        mutableStateOf(plattform.lesen("schluessel")?.takeIf { it.isNotBlank() }.also { server.schluessel = it })
    }
    var zustand by remember { mutableStateOf<ServerZustand>(ServerZustand.Laedt) }
    var familie by remember { mutableStateOf<Familienstand?>(null) }
    var laeufe by remember { mutableStateOf<List<LaufAnzeige>>(emptyList()) }
    var familienLaeufe by remember { mutableStateOf<List<LaufAnzeige>>(emptyList()) }
    var reiter by remember { mutableStateOf(Reiter.Familie) }
    var person by remember { mutableStateOf<Mitglied?>(null) }          // Läufe eines bestimmten Mitglieds
    var personLaeufe by remember { mutableStateOf<List<LaufAnzeige>>(emptyList()) }
    var meldung by remember { mutableStateOf("") }
    var warteschlange by remember { mutableStateOf<List<Wartend>>(emptyList()) }
    var detail by remember { mutableStateOf<LaufAnzeige?>(null) }
    var beschaeftigt by remember { mutableStateOf(false) }
    var bereich by remember { mutableStateOf(Bereich.Familie) }
    var zeitraum by remember { mutableStateOf("woche") }
    var punktestand by remember { mutableStateOf<Punktestand?>(null) }
    val scope = rememberCoroutineScope()

    fun abmelden(grund: String) {
        schluessel = null
        server.schluessel = null
        plattform.schreiben("schluessel", "")
        familie = null
        laeufe = emptyList()
        meldung = grund
    }

    fun <T> pruefen(a: Antwort<T>): T? {
        if (a.abgemeldet) abmelden(a.fehler ?: "Bitte neu anmelden.")
        else if (a.wert == null && a.fehler != null) meldung = a.fehler
        return a.wert
    }

    suspend fun neuLaden() {
        if (schluessel == null) return
        pruefen(server.familie())?.let { familie = it }
        pruefen(server.liste())?.let { laeufe = it }
        pruefen(server.familienLaeufe())?.let { familienLaeufe = it }
        person?.let { p -> pruefen(server.liste(p.id))?.let { personLaeufe = it } }
        pruefen(server.rangliste(zeitraum))?.let { punktestand = it }
    }

    fun angemeldet(a: Anmeldung) {
        plattform.schreiben("schluessel", a.schluessel)
        server.schluessel = a.schluessel
        schluessel = a.schluessel
        meldung = "Willkommen in der Familie, ${a.ich.name}!"
        bereich = Bereich.Familie
        scope.launch { neuLaden() }
    }

    LaunchedEffect(Unit) {
        zustand = server.status()
        if (zustand is ServerZustand.Erreichbar) neuLaden()
    }

    LaunchedEffect(geteilt, schluessel) {
        if (geteilt.isEmpty() || schluessel == null) return@LaunchedEffect
        val dateien = geteilt.toList()
        // Eigene Coroutine: geteiltErledigt() ändert den Schlüssel dieses Effekts und würde ihn sonst abbrechen.
        scope.launch {
            bereich = Bereich.Laeufe
            for (datei in dateien) {
                meldung = "Lese ${datei.name} …"
                val antwort = if (datei.istBild) {
                    val text = plattform.texterkennung(datei)
                    if (text.isNullOrBlank()) Antwort(null, "Auf dem Bild wurde kein Text erkannt.") else server.vorschauText(text)
                } else server.vorschauDatei(datei)
                if (antwort.abgemeldet) { abmelden(antwort.fehler ?: ""); break }
                warteschlange = warteschlange + Wartend(antwort.wert, antwort.fehler, datei.name)
            }
            meldung = ""
        }
        geteiltErledigt()
    }

    MaterialTheme(colorScheme = lightColorScheme(primary = Farben.Orange, background = Farben.Grund, onSurface = Farben.Tinte)) {
        Box(Modifier.fillMaxSize().background(Farben.Grund).safeDrawingPadding()) {
            val offen = detail
            when {
                schluessel == null -> Willkommen(
                    server = server, zustand = zustand, geraetId = geraetId, einladung = einladung,
                    einladungErledigt = einladungErledigt, meldung = meldung, angemeldet = { angemeldet(it) },
                    nochmal = { scope.launch { zustand = ServerZustand.Laedt; zustand = server.status() } },
                )
                offen != null -> LaufDetail(
                    lauf = offen, beschaeftigt = beschaeftigt, zurueck = { detail = null },
                    sichtbarkeit = { wert ->
                        scope.launch {
                            val id = offen.id ?: return@launch
                            pruefen(server.sichtbarkeit(id, wert))?.let { detail = it }
                            neuLaden()
                        }
                    },
                    loeschen = {
                        scope.launch {
                            val id = offen.id ?: return@launch
                            beschaeftigt = true
                            if (pruefen(server.loeschen(id)) == true) { detail = null; meldung = "Lauf gelöscht." }
                            neuLaden()
                            beschaeftigt = false
                        }
                    },
                )
                else -> Column(Modifier.fillMaxSize()) {
                    Column(
                        Modifier.weight(1f).fillMaxWidth().verticalScroll(rememberScrollState())
                            .padding(horizontal = 20.dp, vertical = 22.dp),
                        verticalArrangement = Arrangement.spacedBy(16.dp),
                    ) {
                        Kopf(zustand)
                        Text(if (bereich == Bereich.Laeufe) "Meine Läufe" else bereich.titel,
                            color = Farben.Tinte, fontWeight = FontWeight.ExtraBold, fontSize = 32.sp)
                        if (zustand is ServerZustand.Fehler) {
                            Button(onClick = { scope.launch { zustand = ServerZustand.Laedt; zustand = server.status(); neuLaden() } },
                                colors = ButtonDefaults.buttonColors(containerColor = Farben.Orange)) { Text("Nochmal verbinden") }
                        }
                        if (meldung.isNotBlank()) Hinweis(meldung) { meldung = "" }
                        when (bereich) {
                            Bereich.Familie -> FamilieSeite(
                                familie = familie, beschaeftigt = beschaeftigt,
                                anlegen = { name ->
                                    scope.launch {
                                        beschaeftigt = true
                                        pruefen(server.mitgliedAnlegen(name))?.let { plattform.teilen(it.text); meldung = "Einladung für $name erstellt." }
                                        neuLaden()
                                        beschaeftigt = false
                                    }
                                },
                                oeffnen = { m ->
                                    person = m
                                    personLaeufe = emptyList()
                                    bereich = Bereich.Laeufe
                                    scope.launch { pruefen(server.liste(m.id))?.let { personLaeufe = it } }
                                },
                                einladen = { m ->
                                    scope.launch {
                                        beschaeftigt = true
                                        pruefen(server.neueEinladung(m.id))?.let { plattform.teilen(it.text) }
                                        neuLaden()
                                        beschaeftigt = false
                                    }
                                },
                            )
                            Bereich.Laeufe -> LaeufeSeite(
                                laeufe = when {
                                    person != null -> personLaeufe
                                    reiter == Reiter.Familie -> familienLaeufe
                                    else -> laeufe
                                },
                                reiter = reiter, person = person,
                                reiterWaehlen = { reiter = it; person = null },
                                zustand = zustand, beschaeftigt = beschaeftigt,
                                laufOeffnen = { lauf ->
                                    scope.launch {
                                        val id = lauf.id ?: return@launch
                                        pruefen(server.detail(id))?.let { detail = it }
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
                                                else server.healthConnect(geraetId, sitzungen).let { pruefen(it) ?: meldung }
                                            }
                                        }
                                        neuLaden()
                                        beschaeftigt = false
                                    }
                                },
                            )
                            Bereich.Rangliste -> RanglisteSeite(
                                stand = punktestand, zeitraum = zeitraum,
                                verwalter = familie?.ich?.istVerwalter == true, beschaeftigt = beschaeftigt,
                                zeitraumWaehlen = { z ->
                                    zeitraum = z
                                    punktestand = null
                                    scope.launch { pruefen(server.rangliste(z))?.let { punktestand = it } }
                                },
                                zielSetzen = { lk ->
                                    scope.launch {
                                        beschaeftigt = true
                                        pruefen(server.zielSetzen(lk))
                                        pruefen(server.rangliste(zeitraum))?.let { punktestand = it }
                                        beschaeftigt = false
                                    }
                                },
                            )
                            Bereich.Ich -> IchSeite(
                                ich = familie?.ich, appVersion = appVersion, beschaeftigt = beschaeftigt,
                                standardWaehlen = { wert ->
                                    scope.launch { pruefen(server.standardSichtbarkeit(wert)); neuLaden() }
                                },
                                farbeWaehlen = { farbe ->
                                    scope.launch { pruefen(server.farbeAendern(farbe)); neuLaden() }
                                },
                                testPush = {
                                    scope.launch {
                                        beschaeftigt = true
                                        val token = plattform.pushToken()
                                        meldung = if (token == null) "Push ist in dieser App-Version nicht eingerichtet." else server.pushProbe(token)
                                        beschaeftigt = false
                                    }
                                },
                                abmelden = { abmelden("Abgemeldet. Zum Wiederkommen brauchst du einen neuen Einladungslink.") },
                            )
                        }
                    }
                    Navigation(bereich) {
                        if (it == Bereich.Laeufe && bereich != Bereich.Laeufe) person = null
                        bereich = it
                        if (it != Bereich.Ich) scope.launch { neuLaden() }
                    }
                }
            }

            val oben = warteschlange.firstOrNull()
            if (oben != null && schluessel != null) {
                Kontrollkarte(
                    eintrag = oben, appVersion = appVersion, beschaeftigt = beschaeftigt,
                    standard = familie?.ich?.standardSichtbarkeit ?: "familie",
                    speichern = { v, sicht ->
                        scope.launch {
                            beschaeftigt = true
                            val a = server.bestaetigen(v.entwurf, geraetId, plattform.pushToken(), sicht)
                            pruefen(a)?.let { meldung = it }
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
fun Kopf(zustand: ServerZustand) {
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
}

@Composable
fun Hinweis(text: String, weg: (() -> Unit)? = null) {
    Text(text, color = Farben.Tinte, fontSize = 14.sp,
        modifier = Modifier.fillMaxWidth().clip(RoundedCornerShape(14.dp)).background(Farben.OrangeHell)
            .let { if (weg != null) it.clickable(onClick = weg) else it }.padding(12.dp))
}

@Composable
private fun Navigation(aktiv: Bereich, waehlen: (Bereich) -> Unit) {
    NavigationBar(containerColor = Farben.Weiss, tonalElevation = 0.dp) {
        Bereich.entries.forEach { b ->
            NavigationBarItem(
                selected = b == aktiv,
                onClick = { waehlen(b) },
                icon = { Text(b.zeichen, fontSize = 20.sp) },
                label = { Text(b.titel, fontSize = 12.sp, fontWeight = if (b == aktiv) FontWeight.Bold else FontWeight.Normal) },
                colors = NavigationBarItemDefaults.colors(
                    selectedTextColor = Farben.Tinte, unselectedTextColor = Farben.Grau, indicatorColor = Farben.OrangeHell),
            )
        }
    }
}

@Composable
private fun LaeufeSeite(
    laeufe: List<LaufAnzeige>,
    reiter: Reiter,
    person: Mitglied?,
    reiterWaehlen: (Reiter) -> Unit,
    zustand: ServerZustand,
    beschaeftigt: Boolean,
    laufOeffnen: (LaufAnzeige) -> Unit,
    healthConnect: () -> Unit,
) {
    Karte(dunkel = true) {
        Text("SO KOMMT EIN LAUF REIN", color = Farben.Hell, fontWeight = FontWeight.Bold, fontSize = 12.sp, letterSpacing = 1.4.sp)
        Text("Huawei Health: Lauf öffnen → Route exportieren → GPX → Teilen → Schweinehund.",
            color = Farben.Weiss, fontSize = 15.sp, lineHeight = 21.sp)
        Text("Garmin: Zahlen über Health Connect abgleichen; die Strecke als GPX von connect.garmin.com teilen. " +
            "Das Huawei-Teilen-Bild bringt Puls, Kadenz und Schritte dazu.",
            color = Farben.Hell, fontSize = 13.sp, lineHeight = 19.sp)
        Button(onClick = healthConnect, enabled = !beschaeftigt, shape = RoundedCornerShape(12.dp),
            colors = ButtonDefaults.buttonColors(containerColor = Farben.Orange)) { Text("Health Connect abgleichen") }
    }
    Row(horizontalArrangement = Arrangement.spacedBy(8.dp), verticalAlignment = Alignment.CenterVertically) {
        Reiter.entries.forEach { r ->
            Auswahl(r.titel, gewaehlt = person == null && r == reiter) { reiterWaehlen(r) }
        }
        if (person != null) Auswahl(person.name + "  ✕", gewaehlt = true, farbe = farbe(person.farbe)) { reiterWaehlen(reiter) }
    }
    if (laeufe.isEmpty() && zustand is ServerZustand.Erreichbar) {
        Text(if (person != null) "${person.name} hat noch keine Läufe." else
            "Noch keine Läufe. Teile deinen ersten Lauf an Schweinehund – Horst wartet (ungern).",
            color = Farben.Grau, fontFamily = FontFamily.Serif, fontStyle = FontStyle.Italic, fontSize = 16.sp)
    }
    laeufe.forEach { lauf -> LaufZeile(lauf, mitName = person == null && reiter == Reiter.Familie) { laufOeffnen(lauf) } }
}

@Composable
fun Karte(dunkel: Boolean = false, inhalt: @Composable () -> Unit) {
    Column(
        Modifier.fillMaxWidth().clip(RoundedCornerShape(22.dp)).background(if (dunkel) Farben.Schiefer else Farben.Weiss).padding(18.dp),
        verticalArrangement = Arrangement.spacedBy(10.dp),
    ) { inhalt() }
}

@Composable
private fun LaufZeile(lauf: LaufAnzeige, mitName: Boolean = false, oeffnen: () -> Unit) {
    Column(
        Modifier.fillMaxWidth().clip(RoundedCornerShape(18.dp)).background(Farben.Weiss).clickable(onClick = oeffnen).padding(16.dp),
        verticalArrangement = Arrangement.spacedBy(4.dp),
    ) {
        if (mitName && lauf.mitgliedName.isNotBlank()) {
            Row(verticalAlignment = Alignment.CenterVertically) {
                Box(Modifier.size(10.dp).clip(CircleShape).background(farbe(lauf.mitgliedFarbe)))
                Spacer(Modifier.size(6.dp))
                Text(if (lauf.eigen) "Du" else lauf.mitgliedName, color = Farben.Tinte, fontWeight = FontWeight.Bold, fontSize = 13.sp)
            }
        }
        Row(verticalAlignment = Alignment.Bottom) {
            Text("${lauf.distanzKm} km", color = Farben.Tinte, fontWeight = FontWeight.ExtraBold, fontSize = 24.sp, modifier = Modifier.weight(1f))
            Text(lauf.startText, color = Farben.Grau, fontSize = 13.sp)
        }
        Text(listOfNotNull(lauf.dauer, lauf.tempo, lauf.anstiegM?.let { "↑ $it m" }, lauf.puls?.let { "♥ $it" },
            lauf.lk.takeIf { it.isNotBlank() }?.let { "$it LK" }).joinToString("  ·  "),
            color = Farben.Tinte, fontSize = 14.sp)
        val strecke = when {
            lauf.hatStrecke && lauf.eigen && lauf.sichtbarkeit == "ich" -> "  ·  Strecke nur für dich"
            lauf.hatStrecke -> "  ·  mit Strecke"
            lauf.streckePrivat -> "  ·  Strecke privat"
            else -> ""
        }
        Text(lauf.quellen.joinToString(" + ") { QUELLEN_TEXT[it] ?: it } + strecke, color = Farben.Grau, fontSize = 12.sp)
    }
}

@Composable
private fun Kontrollkarte(
    eintrag: Wartend,
    appVersion: String,
    beschaeftigt: Boolean,
    standard: String,
    speichern: (Vorschau, String) -> Unit,
    verwerfen: () -> Unit,
) {
    var sicht by remember(eintrag) { mutableStateOf(standard) }
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
            if (l.linie.size >= 2) SichtbarkeitWahl(sicht, !beschaeftigt) { sicht = it }
            Row(horizontalArrangement = Arrangement.spacedBy(10.dp)) {
                OutlinedButton(onClick = verwerfen, enabled = !beschaeftigt, modifier = Modifier.weight(1f).height(50.dp)) {
                    Text("Verwerfen", color = Farben.Tinte)
                }
                Button(onClick = { speichern(v, sicht) }, enabled = !beschaeftigt,
                    modifier = Modifier.weight(1f).height(50.dp), shape = RoundedCornerShape(14.dp),
                    colors = ButtonDefaults.buttonColors(containerColor = Farben.Orange)) { Text("Speichern", fontWeight = FontWeight.Bold) }
            }
        }
    }
}

/** Reiter im Bereich „Läufe“ (REQ-003). */
enum class Reiter(val titel: String) { Familie("Familie"), Meine("Meine") }

@Composable
fun Auswahl(text: String, gewaehlt: Boolean, farbe: Color = Farben.Schiefer, aktiv: Boolean = true, waehlen: () -> Unit) {
    Text(text, color = if (gewaehlt) Farben.Weiss else Farben.Tinte, fontWeight = FontWeight.Bold, fontSize = 14.sp,
        modifier = Modifier.clip(RoundedCornerShape(20.dp)).background(if (gewaehlt) farbe else Farben.Hell)
            .clickable(enabled = aktiv, onClick = waehlen).padding(horizontal = 14.dp, vertical = 8.dp))
}

@Composable
fun SichtbarkeitWahl(wert: String, aktiv: Boolean, waehlen: (String) -> Unit) {
    Column(verticalArrangement = Arrangement.spacedBy(6.dp)) {
        Text("Wer sieht die Strecke?", color = Farben.Grau, fontSize = 13.sp)
        Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
            Auswahl("Familie", wert == "familie", aktiv = aktiv) { waehlen("familie") }
            Auswahl("Nur ich", wert == "ich", aktiv = aktiv) { waehlen("ich") }
        }
        if (wert == "ich") Text("Die Familie sieht Kilometer und Zeit, aber keine Karte. Der Lauf zählt trotzdem.",
            color = Farben.Grau, fontSize = 12.sp)
    }
}

@Composable
private fun LaufDetail(
    lauf: LaufAnzeige,
    beschaeftigt: Boolean,
    zurueck: () -> Unit,
    sichtbarkeit: (String) -> Unit,
    loeschen: () -> Unit,
) {
    var nachfragen by remember(lauf.id) { mutableStateOf(false) }
    Column(
        Modifier.fillMaxSize().verticalScroll(rememberScrollState()).padding(horizontal = 20.dp, vertical = 22.dp),
        verticalArrangement = Arrangement.spacedBy(14.dp),
    ) {
        OutlinedButton(onClick = zurueck) { Text("‹ Zurück", color = Farben.Tinte) }
        Row(verticalAlignment = Alignment.CenterVertically) {
            if (!lauf.eigen && lauf.mitgliedName.isNotBlank()) {
                Box(Modifier.size(10.dp).clip(CircleShape).background(farbe(lauf.mitgliedFarbe)))
                Spacer(Modifier.size(6.dp))
                Text(lauf.mitgliedName + "  ·  ", color = Farben.Tinte, fontWeight = FontWeight.Bold, fontSize = 13.sp)
            }
            Text(lauf.startText, color = Farben.Orange, fontWeight = FontWeight.Bold, fontSize = 13.sp)
        }
        Row(verticalAlignment = Alignment.Bottom) {
            Text("${lauf.distanzKm} km", color = Farben.Tinte, fontWeight = FontWeight.ExtraBold, fontSize = 40.sp, modifier = Modifier.weight(1f))
            if (lauf.lk.isNotBlank()) Text("${lauf.lk} LK", color = Farben.Orange, fontWeight = FontWeight.ExtraBold, fontSize = 20.sp,
                modifier = Modifier.padding(bottom = 8.dp))
        }
        Text(listOfNotNull(lauf.dauer, lauf.tempo, lauf.anstiegM?.let { "↑ $it m" }).joinToString("  ·  "), color = Farben.Tinte, fontSize = 16.sp)
        val extra = listOfNotNull(lauf.puls?.let { "Puls Ø $it" }, lauf.kadenz?.let { "Kadenz $it" }, lauf.schritte?.let { "${tausender(it)} Schritte" })
        if (extra.isNotEmpty()) Text(extra.joinToString("  ·  "), color = Farben.Grau, fontSize = 14.sp)
        val karte = lauf.karte
        when {
            karte != null && karte.punkte.size >= 2 -> {
                LaufKarte(karte, Modifier.fillMaxWidth().height(340.dp).clip(RoundedCornerShape(22.dp)))
                TempoLegende()
            }
            lauf.linie.size >= 2 ->
                Strecke(lauf.linie, Modifier.fillMaxWidth().height(280.dp).clip(RoundedCornerShape(22.dp)).background(Farben.Weiss))
            lauf.streckePrivat -> Text("${lauf.mitgliedName} zeigt die Strecke dieses Laufs nur sich selbst.",
                color = Farben.Grau, fontSize = 14.sp)
            else -> Text("Für diesen Lauf gibt es noch keine Strecke. Teile die GPX-Datei, dann erscheint sie hier.",
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
        if (lauf.eigen) {
            if (lauf.hatStrecke) SichtbarkeitWahl(lauf.sichtbarkeit, !beschaeftigt, sichtbarkeit)
            if (!nachfragen) {
                TextButton(onClick = { nachfragen = true }) { Text("Lauf löschen", color = Farben.Grau) }
            } else {
                Hinweis("Lauf wirklich löschen? Das lässt sich nicht rückgängig machen.")
                Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                    TextButton(onClick = { nachfragen = false }) { Text("Abbrechen", color = Farben.Grau) }
                    TextButton(onClick = loeschen, enabled = !beschaeftigt) { Text("Ja, löschen", color = Farben.Orange) }
                }
            }
        }
        Text("Quelle: " + lauf.quellen.joinToString(" + ") { QUELLEN_TEXT[it] ?: it } + "  ·  Karte © OpenStreetMap, OpenFreeMap",
            color = Farben.Grau, fontSize = 12.sp)
    }
}

@Composable
private fun TempoLegende() {
    Row(verticalAlignment = Alignment.CenterVertically) {
        Text("langsamer", color = Farben.Grau, fontSize = 12.sp)
        Spacer(Modifier.size(8.dp))
        TEMPO_FARBEN.forEach { Box(Modifier.size(width = 22.dp, height = 6.dp).clip(RoundedCornerShape(3.dp)).background(farbe(it))); Spacer(Modifier.size(3.dp)) }
        Spacer(Modifier.size(5.dp))
        Text("schneller", color = Farben.Grau, fontSize = 12.sp)
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


/** Ganze Zahl mit deutschem Tausenderpunkt: 6280 → „6.280“. */
fun tausender(n: Int): String = n.toString().reversed().chunked(3).joinToString(".").reversed()
