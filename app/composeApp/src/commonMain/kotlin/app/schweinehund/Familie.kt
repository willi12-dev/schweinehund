package app.schweinehund

import androidx.compose.foundation.background
import androidx.compose.foundation.border
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
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.Button
import androidx.compose.material3.ButtonDefaults
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
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
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.font.FontStyle
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.coerceAtLeast
import androidx.compose.ui.unit.sp
import kotlinx.coroutines.launch

/** Farben, aus denen jedes Mitglied seine wählt (gleiche Liste wie auf dem Server). */
val MITGLIEDSFARBEN = listOf("#EF7448", "#5B8DEF", "#9CC65A", "#B07CE0", "#E8B33F", "#3FB8AF", "#E06A8C", "#8A94A6")

/** "#RRGGBB" → Farbe; Unsinn wird Grau. */
fun farbe(hex: String): Color =
    hex.removePrefix("#").takeIf { it.length == 6 }?.toLongOrNull(16)?.let { Color(0xFF000000 or it) } ?: Farben.Grau

@Composable
fun Kreis(mitglied: Mitglied, groesse: Int = 44) {
    Box(Modifier.size(groesse.dp).clip(CircleShape).background(farbe(mitglied.farbe)), contentAlignment = Alignment.Center) {
        Text(mitglied.kuerzel, color = Farben.Weiss, fontWeight = FontWeight.Bold, fontSize = (groesse * 0.36).sp)
    }
}

// ------------------------------------------------------------------ Willkommen (noch nicht angemeldet)
@Composable
fun Willkommen(
    server: ServerDienst,
    zustand: ServerZustand,
    geraetId: String,
    einladung: String?,
    einladungErledigt: () -> Unit,
    meldung: String,
    angemeldet: (Anmeldung) -> Unit,
    nochmal: () -> Unit,
) {
    val scope = rememberCoroutineScope()
    var code by remember { mutableStateOf("") }
    var fuer by remember { mutableStateOf<String?>(null) }          // Name aus der Einladung („Du bist … ?“)
    var name by remember { mutableStateOf("") }
    var fehler by remember { mutableStateOf("") }
    var beschaeftigt by remember { mutableStateOf(false) }

    fun ansehen(roh: String) {
        val sauber = einladungsCode(roh)
        if (sauber.length < 6) { fehler = "Der Code hat zehn Zeichen – bitte prüfen."; return }
        code = sauber
        scope.launch {
            beschaeftigt = true
            server.einladungAnsehen(sauber).let { a -> fuer = a.wert; fehler = a.fehler ?: "" }
            beschaeftigt = false
        }
    }

    LaunchedEffect(einladung) {
        if (einladung != null) { ansehen(einladung); einladungErledigt() }
    }

    Column(
        Modifier.fillMaxSize().verticalScroll(rememberScrollState()).padding(horizontal = 20.dp, vertical = 22.dp),
        verticalArrangement = Arrangement.spacedBy(16.dp),
    ) {
        Kopf(zustand)
        Text("Willkommen", color = Farben.Tinte, fontWeight = FontWeight.ExtraBold, fontSize = 32.sp)
        Text("Die Familien-Challenge gegen den inneren Schweinehund. Horst ist schon da – leider.",
            color = Farben.Grau, fontFamily = FontFamily.Serif, fontStyle = FontStyle.Italic, fontSize = 17.sp)
        if (meldung.isNotBlank()) Hinweis(meldung)
        if (zustand is ServerZustand.Fehler) {
            Button(onClick = nochmal, colors = ButtonDefaults.buttonColors(containerColor = Farben.Orange)) { Text("Nochmal verbinden") }
        }
        if (fehler.isNotBlank()) Hinweis(fehler)

        val bestaetigen = fuer
        if (bestaetigen != null) {
            Karte(dunkel = true) {
                Text("EINLADUNG", color = Farben.Hell, fontWeight = FontWeight.Bold, fontSize = 12.sp, letterSpacing = 1.4.sp)
                Text("Du bist $bestaetigen – stimmt das?", color = Farben.Weiss, fontWeight = FontWeight.ExtraBold, fontSize = 24.sp)
                Row(horizontalArrangement = Arrangement.spacedBy(10.dp)) {
                    OutlinedButton(onClick = { fuer = null; code = "" }, enabled = !beschaeftigt, modifier = Modifier.weight(1f)) {
                        Text("Nein", color = Farben.Weiss)
                    }
                    Button(
                        onClick = {
                            scope.launch {
                                beschaeftigt = true
                                val a = server.einloesen(code, geraetId)
                                beschaeftigt = false
                                if (a.wert != null) angemeldet(a.wert) else fehler = a.fehler ?: "Das hat nicht geklappt."
                            }
                        },
                        enabled = !beschaeftigt, modifier = Modifier.weight(1f),
                        colors = ButtonDefaults.buttonColors(containerColor = Farben.Orange),
                    ) { Text("Ja, das bin ich", fontWeight = FontWeight.Bold) }
                }
            }
            return@Column
        }

        Karte {
            Text("Mit Einladung beitreten", color = Farben.Tinte, fontWeight = FontWeight.ExtraBold, fontSize = 18.sp)
            Text("Tippe den Link aus WhatsApp an – oder gib hier den Code ein.", color = Farben.Grau, fontSize = 14.sp)
            OutlinedTextField(value = code, onValueChange = { code = it.uppercase().take(40) }, singleLine = true,
                label = { Text("Einladungscode") }, modifier = Modifier.fillMaxWidth())
            Button(onClick = { ansehen(code) }, enabled = !beschaeftigt && code.isNotBlank(), shape = RoundedCornerShape(12.dp),
                colors = ButtonDefaults.buttonColors(containerColor = Farben.Orange)) { Text("Beitreten") }
        }

        if (zustand is ServerZustand.Erreichbar && !zustand.familie) {
            Karte {
                Text("Neue Familie gründen", color = Farben.Tinte, fontWeight = FontWeight.ExtraBold, fontSize = 18.sp)
                Text("Wer gründet, wird Verwalter und lädt die anderen ein.", color = Farben.Grau, fontSize = 14.sp)
                OutlinedTextField(value = name, onValueChange = { name = it.take(30) }, singleLine = true,
                    label = { Text("Dein Name") }, modifier = Modifier.fillMaxWidth())
                Button(
                    onClick = {
                        scope.launch {
                            beschaeftigt = true
                            val a = server.gruenden(name.trim(), null, geraetId)
                            beschaeftigt = false
                            if (a.wert != null) angemeldet(a.wert) else fehler = a.fehler ?: "Das hat nicht geklappt."
                        }
                    },
                    enabled = !beschaeftigt && name.trim().length >= 2, shape = RoundedCornerShape(12.dp),
                    colors = ButtonDefaults.buttonColors(containerColor = Farben.Orange),
                ) { Text("Familie gründen") }
            }
        }
    }
}

// ------------------------------------------------------------------ Familie
@Composable
fun FamilieSeite(
    familie: Familienstand?,
    beschaeftigt: Boolean,
    anlegen: (String) -> Unit,
    oeffnen: (Mitglied) -> Unit,
    einladen: (Mitglied) -> Unit,
) {
    if (familie == null) {
        Text("Lade die Familie …", color = Farben.Grau)
        return
    }
    val verwalter = familie.ich.istVerwalter
    familie.mitglieder.forEach { m -> MitgliedKarte(m, verwalter, beschaeftigt, { oeffnen(m) }) { einladen(m) } }

    if (verwalter) {
        var name by remember { mutableStateOf("") }
        Karte {
            Text("Familienmitglied einladen", color = Farben.Tinte, fontWeight = FontWeight.ExtraBold, fontSize = 18.sp)
            Text("Die App erstellt einen Link, den du per WhatsApp verschickst. Er gilt 7 Tage und nur einmal.",
                color = Farben.Grau, fontSize = 14.sp)
            OutlinedTextField(value = name, onValueChange = { name = it.take(30) }, singleLine = true,
                label = { Text("Name") }, modifier = Modifier.fillMaxWidth())
            Button(onClick = { anlegen(name.trim()); name = "" }, enabled = !beschaeftigt && name.trim().length >= 2,
                shape = RoundedCornerShape(12.dp), colors = ButtonDefaults.buttonColors(containerColor = Farben.Orange)) {
                Text("Einladung verschicken")
            }
        }
    }
}

@Composable
private fun MitgliedKarte(m: Mitglied, verwalter: Boolean, beschaeftigt: Boolean, oeffnen: () -> Unit, einladen: () -> Unit) {
    var nachfragen by remember { mutableStateOf(false) }
    Column(
        Modifier.fillMaxWidth().clip(RoundedCornerShape(18.dp)).background(Farben.Weiss)
            .clickable(enabled = m.beigetreten, onClick = oeffnen).padding(16.dp),
        verticalArrangement = Arrangement.spacedBy(8.dp),
    ) {
        Row(verticalAlignment = Alignment.CenterVertically) {
            Kreis(m)
            Spacer(Modifier.size(12.dp))
            Column(Modifier.weight(1f)) {
                Text(m.name + if (m.ich) " (du)" else "", color = Farben.Tinte, fontWeight = FontWeight.Bold, fontSize = 17.sp)
                val unter = when {
                    !m.beigetreten && m.einladungOffen -> "Einladung verschickt – noch nicht beigetreten"
                    !m.beigetreten -> "noch nicht dabei"
                    m.letzterLauf != null -> "Zuletzt: ${m.letzterLauf}"
                    else -> "noch kein Lauf"
                }
                Text(unter, color = Farben.Grau, fontSize = 13.sp)
            }
            Column(horizontalAlignment = Alignment.End) {
                Text(m.kmWoche, color = Farben.Tinte, fontWeight = FontWeight.ExtraBold, fontSize = 22.sp)
                Text("km Woche", color = Farben.Grau, fontSize = 11.sp)
            }
        }
        if (verwalter && !m.ich) {
            if (!m.beigetreten) {
                TextButton(onClick = einladen, enabled = !beschaeftigt) {
                    Text(if (m.einladungOffen) "Einladung erneut verschicken" else "Einladen", color = Farben.Orange)
                }
            } else if (!nachfragen) {
                TextButton(onClick = { nachfragen = true }) { Text("Neues Handy?", color = Farben.Grau, fontSize = 13.sp) }
            } else {
                Text("Ein neuer Link meldet das bisherige Handy von ${m.name} ab.", color = Farben.Tinte, fontSize = 13.sp)
                Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                    TextButton(onClick = { nachfragen = false }) { Text("Abbrechen", color = Farben.Grau) }
                    TextButton(onClick = { nachfragen = false; einladen() }, enabled = !beschaeftigt) {
                        Text("Neuen Link verschicken", color = Farben.Orange)
                    }
                }
            }
        }
    }
}

// ------------------------------------------------------------------ Rangliste (REQ-004)
@Composable
fun RanglisteSeite(
    stand: Punktestand?,
    zeitraum: String,
    verwalter: Boolean,
    beschaeftigt: Boolean,
    zeitraumWaehlen: (String) -> Unit,
    zielSetzen: (Double) -> Unit,
) {
    Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
        Auswahl("Woche", zeitraum == "woche") { zeitraumWaehlen("woche") }
        Auswahl("Monat", zeitraum == "monat") { zeitraumWaehlen("monat") }
    }
    if (stand == null) {
        Text("Horst rechnet noch …", color = Farben.Grau, fontFamily = FontFamily.Serif, fontStyle = FontStyle.Italic)
        return
    }
    Text(stand.titel, color = Farben.Grau, fontSize = 13.sp)

    // Horst-o-Meter: gemeinsames Wochenziel
    Karte(dunkel = true) {
        Text("HORST-O-METER · DIESE WOCHE", color = Farben.Hell, fontWeight = FontWeight.Bold, fontSize = 12.sp, letterSpacing = 1.4.sp)
        Row(verticalAlignment = Alignment.Bottom) {
            Text(stand.horst.ist, color = Farben.Weiss, fontWeight = FontWeight.ExtraBold, fontSize = 30.sp)
            Text("  von ${stand.horst.ziel} LK", color = Farben.Hell, fontSize = 15.sp, modifier = Modifier.padding(bottom = 4.dp))
            Spacer(Modifier.weight(1f))
            Text("${stand.horst.prozent} %", color = Farben.Orange, fontWeight = FontWeight.ExtraBold, fontSize = 20.sp)
        }
        Box(Modifier.fillMaxWidth().height(12.dp).clip(RoundedCornerShape(6.dp)).background(Farben.Tinte)) {
            Box(Modifier.fillMaxWidth((stand.horst.prozent.coerceIn(0, 100) / 100f)).height(12.dp)
                .clip(RoundedCornerShape(6.dp)).background(Farben.Orange))
        }
        Text(stand.horst.spruch, color = Farben.Weiss, fontFamily = FontFamily.Serif, fontStyle = FontStyle.Italic, fontSize = 16.sp)
        if (verwalter) {
            Row(verticalAlignment = Alignment.CenterVertically) {
                Text("Familienziel", color = Farben.Hell, fontSize = 13.sp, modifier = Modifier.weight(1f))
                TextButton(onClick = { zielSetzen((stand.horst.zielWert - 5).coerceAtLeast(5.0)) }, enabled = !beschaeftigt) {
                    Text("− 5", color = Farben.Weiss, fontWeight = FontWeight.Bold)
                }
                TextButton(onClick = { zielSetzen(stand.horst.zielWert + 5) }, enabled = !beschaeftigt) {
                    Text("+ 5", color = Farben.Weiss, fontWeight = FontWeight.Bold)
                }
            }
        }
    }

    // Rangliste
    stand.zeilen.forEach { z ->
        Row(
            Modifier.fillMaxWidth().clip(RoundedCornerShape(18.dp)).background(Farben.Weiss).padding(14.dp),
            verticalAlignment = Alignment.CenterVertically,
        ) {
            Text("${z.platz}.", color = if (z.platz == 1 && z.laeufe > 0) Farben.Orange else Farben.Grau,
                fontWeight = FontWeight.ExtraBold, fontSize = 20.sp, modifier = Modifier.size(width = 34.dp, height = 28.dp))
            Kreis(z.mitglied, 38)
            Spacer(Modifier.size(10.dp))
            Column(Modifier.weight(1f)) {
                Text(z.mitglied.name, color = Farben.Tinte, fontWeight = FontWeight.Bold, fontSize = 16.sp)
                Text(if (z.laeufe == 0) "noch kein Lauf – Horst grüßt" else
                    "${z.laeufe} ${if (z.laeufe == 1) "Lauf" else "Läufe"} · ${z.km} km · ↑ ${z.hm} m",
                    color = Farben.Grau, fontSize = 12.sp)
            }
            Column(horizontalAlignment = Alignment.End) {
                Text(z.lk, color = Farben.Tinte, fontWeight = FontWeight.ExtraBold, fontSize = 20.sp)
                Text("LK", color = Farben.Grau, fontSize = 11.sp)
            }
        }
    }
    Text("LK = Leistungskilometer: Kilometer + Höhenmeter ÷ 100. Es zählen Läufe ab 1 km.", color = Farben.Grau, fontSize = 12.sp)

    // Eigener Fortschritt
    Karte {
        Text("Dein Fortschritt", color = Farben.Tinte, fontWeight = FontWeight.ExtraBold, fontSize = 18.sp)
        Text(when {
            stand.serie == 0 -> "Noch keine Serie. Eine Woche mit Lauf – und Horst hat ein Problem."
            stand.serie == 1 -> "1 Woche dabei${if (stand.dieseWoche) "" else " – lauf diese Woche, sonst reißt die Serie"}."
            else -> "${stand.serie} Wochen in Folge dabei${if (stand.dieseWoche) "" else " – diese Woche fehlt noch ein Lauf"}."
        }, color = Farben.Tinte, fontSize = 14.sp)
        val hoechster = (stand.fortschritt.maxOfOrNull { it.lkWert } ?: 0.0).coerceAtLeast(1.0)
        Row(Modifier.fillMaxWidth().height(110.dp), horizontalArrangement = Arrangement.spacedBy(6.dp), verticalAlignment = Alignment.Bottom) {
            stand.fortschritt.forEachIndexed { i, w ->
                Column(Modifier.weight(1f), horizontalAlignment = Alignment.CenterHorizontally) {
                    if (w.lkWert > 0) Text(w.lk, color = Farben.Grau, fontSize = 9.sp)
                    Box(Modifier.fillMaxWidth().height((70 * w.lkWert / hoechster).dp.coerceAtLeast(3.dp))
                        .clip(RoundedCornerShape(4.dp))
                        .background(if (i == stand.fortschritt.lastIndex) Farben.Orange else Farben.Schiefer))
                    Text(w.name.removePrefix("KW "), color = Farben.Grau, fontSize = 9.sp)
                }
            }
        }
        stand.bestwerte.forEach { b ->
            Row {
                Text(b.titel, color = Farben.Grau, fontSize = 14.sp, modifier = Modifier.weight(1f))
                Text(b.wert, color = Farben.Tinte, fontWeight = FontWeight.Bold, fontSize = 14.sp)
                Text("  ${b.wann}", color = Farben.Grau, fontSize = 12.sp)
            }
        }
    }
}

// ------------------------------------------------------------------ Ich
@Composable
fun IchSeite(
    ich: Mitglied?,
    appVersion: String,
    beschaeftigt: Boolean,
    pushArten: Map<String, Boolean>,
    pushUmschalten: (String, Boolean) -> Unit,
    standardWaehlen: (String) -> Unit,
    farbeWaehlen: (String) -> Unit,
    testPush: () -> Unit,
    abmelden: () -> Unit,
) {
    var nachfragen by remember { mutableStateOf(false) }
    if (ich != null) {
        Row(verticalAlignment = Alignment.CenterVertically) {
            Kreis(ich, 64)
            Spacer(Modifier.size(16.dp))
            Column {
                Text(ich.name, color = Farben.Tinte, fontWeight = FontWeight.ExtraBold, fontSize = 24.sp)
                Text(if (ich.istVerwalter) "Verwalter der Familie" else "Familienmitglied", color = Farben.Grau, fontSize = 14.sp)
            }
        }
        Karte {
            Text("Deine Farbe", color = Farben.Tinte, fontWeight = FontWeight.Bold, fontSize = 16.sp)
            Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                MITGLIEDSFARBEN.forEach { hex ->
                    val gewaehlt = hex.equals(ich.farbe, ignoreCase = true)
                    Box(
                        Modifier.size(32.dp).clip(CircleShape).background(farbe(hex))
                            .border(if (gewaehlt) 3.dp else 0.dp, Farben.Tinte, CircleShape)
                            .clickable(enabled = !beschaeftigt && !gewaehlt) { farbeWaehlen(hex) },
                    )
                }
            }
        }
        Karte {
            Text("Neue Läufe", color = Farben.Tinte, fontWeight = FontWeight.Bold, fontSize = 16.sp)
            SichtbarkeitWahl(ich.standardSichtbarkeit, !beschaeftigt, standardWaehlen)
        }
    }
    if (ich != null) PushEinstellungen(pushArten, !beschaeftigt, pushUmschalten)
    OutlinedButton(onClick = testPush, enabled = !beschaeftigt) { Text("Test-Push anfordern", color = Farben.Tinte) }
    Spacer(Modifier.height(8.dp))
    if (!nachfragen) {
        TextButton(onClick = { nachfragen = true }) { Text("Abmelden", color = Farben.Grau) }
    } else {
        Hinweis("Nach dem Abmelden brauchst du einen neuen Einladungslink vom Verwalter.")
        Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
            TextButton(onClick = { nachfragen = false }) { Text("Abbrechen", color = Farben.Grau) }
            TextButton(onClick = abmelden) { Text("Ja, abmelden", color = Farben.Orange) }
        }
    }
    Text("App v$appVersion", color = Farben.Grau, fontSize = 12.sp)
}
