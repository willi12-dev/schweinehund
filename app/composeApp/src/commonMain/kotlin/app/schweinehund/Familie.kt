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
    einladen: (Mitglied) -> Unit,
) {
    if (familie == null) {
        Text("Lade die Familie …", color = Farben.Grau)
        return
    }
    val verwalter = familie.ich.istVerwalter
    familie.mitglieder.forEach { m -> MitgliedKarte(m, verwalter, beschaeftigt) { einladen(m) } }

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
private fun MitgliedKarte(m: Mitglied, verwalter: Boolean, beschaeftigt: Boolean, einladen: () -> Unit) {
    var nachfragen by remember { mutableStateOf(false) }
    Column(
        Modifier.fillMaxWidth().clip(RoundedCornerShape(18.dp)).background(Farben.Weiss).padding(16.dp),
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

// ------------------------------------------------------------------ Rangliste (Platzhalter bis REQ-004)
@Composable
fun RanglisteSeite() {
    Karte(dunkel = true) {
        Text("KOMMT MIT v0.5.0", color = Farben.Hell, fontWeight = FontWeight.Bold, fontSize = 12.sp, letterSpacing = 1.4.sp)
        Text("Hier entsteht die Rangliste.", color = Farben.Weiss, fontWeight = FontWeight.ExtraBold, fontSize = 22.sp)
        Text("Gezählt werden Leistungskilometer: Jeder Kilometer zählt, und 100 Höhenmeter bergauf zählen wie ein " +
            "zusätzlicher Kilometer. Bis dahin: einfach laufen – Horst führt solange.",
            color = Farben.Hell, fontSize = 14.sp, lineHeight = 20.sp)
    }
}

// ------------------------------------------------------------------ Ich
@Composable
fun IchSeite(
    ich: Mitglied?,
    appVersion: String,
    beschaeftigt: Boolean,
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
    }
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
