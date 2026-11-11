package app.schweinehund

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
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.rememberScrollState
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
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.font.FontStyle
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp

private fun namenText(namen: List<String>) = when (namen.size) {
    0 -> "niemand"
    1 -> namen[0]
    else -> namen.dropLast(1).joinToString(", ") + " & " + namen.last()
}

/** Hinweis „Die Sonntagsshow ist da“ – oben in Familie und Rangliste, solange sie nicht angesehen wurde. */
@Composable
fun ShowHinweis(show: ShowDaten, oeffnen: () -> Unit) {
    Row(
        Modifier.fillMaxWidth().clip(RoundedCornerShape(22.dp)).background(Farben.Orange).clickable(onClick = oeffnen).padding(18.dp),
        verticalAlignment = Alignment.CenterVertically,
    ) {
        Text("🎬", fontSize = 30.sp)
        Spacer(Modifier.size(12.dp))
        Column(Modifier.weight(1f)) {
            Text("Die Sonntagsshow ist da!", color = Farben.Weiss, fontWeight = FontWeight.ExtraBold, fontSize = 18.sp)
            Text(show.titel.substringBefore(" ·") + " – wer ist Member of the Week?", color = Farben.Weiss, fontSize = 13.sp)
        }
        Text("›", color = Farben.Weiss, fontWeight = FontWeight.Bold, fontSize = 28.sp)
    }
}

/** Die Show: Karte für Karte enthüllt (REQ-005). */
@Composable
fun ShowSeite(show: ShowDaten, schliessen: () -> Unit) {
    val schritte = remember(show) { showSchritte(show) }
    var sichtbar by remember(show) { mutableStateOf(1) }
    val scroll = rememberScrollState()
    LaunchedEffect(sichtbar) { scroll.animateScrollTo(scroll.maxValue) }

    Column(Modifier.fillMaxSize().background(Farben.Schiefer)) {
        Column(
            Modifier.weight(1f).fillMaxWidth().verticalScroll(scroll).padding(horizontal = 20.dp, vertical = 22.dp),
            verticalArrangement = Arrangement.spacedBy(14.dp),
        ) {
            Row(verticalAlignment = Alignment.CenterVertically) {
                Text("SONNTAGSSHOW", color = Farben.Orange, fontWeight = FontWeight.ExtraBold, fontSize = 14.sp,
                    letterSpacing = 2.sp, modifier = Modifier.weight(1f))
                TextButton(onClick = schliessen) { Text("Schließen", color = Farben.Hell) }
            }
            Text(show.titel, color = Farben.Weiss, fontWeight = FontWeight.ExtraBold, fontSize = 26.sp)
            if (show.vorgezogen) Text("Vorschau – die echte Show kommt Sonntag um 19 Uhr.", color = Farben.Hell, fontSize = 12.sp)
            schritte.take(sichtbar).forEach { it() }
        }
        Box(Modifier.fillMaxWidth().padding(16.dp)) {
            if (sichtbar < schritte.size) {
                Button(onClick = { sichtbar++ }, modifier = Modifier.fillMaxWidth().height(54.dp), shape = RoundedCornerShape(16.dp),
                    colors = ButtonDefaults.buttonColors(containerColor = Farben.Orange)) {
                    Text("Weiter  (${sichtbar}/${schritte.size})", fontWeight = FontWeight.Bold, fontSize = 16.sp)
                }
            } else {
                OutlinedButton(onClick = schliessen, modifier = Modifier.fillMaxWidth().height(54.dp), shape = RoundedCornerShape(16.dp)) {
                    Text("Bis nächsten Sonntag!", color = Farben.Weiss, fontWeight = FontWeight.Bold)
                }
            }
        }
    }
}

private fun showSchritte(show: ShowDaten): List<@Composable () -> Unit> {
    val liste = mutableListOf<@Composable () -> Unit>()
    liste += {
        ShowKarte("Horsts Wochenbilanz", "😈") {
            Text("${show.horst.ist} von ${show.horst.ziel} LK · ${show.horst.prozent} %", color = Farben.Tinte,
                fontWeight = FontWeight.ExtraBold, fontSize = 22.sp)
            Text(show.horst.spruch, color = Farben.Grau, fontFamily = FontFamily.Serif, fontStyle = FontStyle.Italic, fontSize = 16.sp)
        }
    }
    show.preise.forEach { p ->
        liste += {
            ShowKarte(p.titel, p.zeichen) {
                Text(namenText(p.gewinner), color = Farben.Tinte, fontWeight = FontWeight.ExtraBold, fontSize = 24.sp)
                Text("${p.text}: ${p.wert}", color = Farben.Grau, fontSize = 14.sp)
            }
        }
    }
    val gelaufen = show.zeilen.filter { it.laeufe > 0 }
    listOf(3, 2).forEach { platz ->
        val auf = gelaufen.filter { it.platz == platz }
        if (auf.isNotEmpty()) liste += {
            ShowKarte("Platz $platz", if (platz == 3) "🥉" else "🥈") {
                auf.forEach { z -> PlatzZeile(z) }
            }
        }
    }
    liste += {
        Column(
            Modifier.fillMaxWidth().clip(RoundedCornerShape(24.dp)).background(Farben.Orange).padding(22.dp),
            horizontalAlignment = Alignment.CenterHorizontally, verticalArrangement = Arrangement.spacedBy(8.dp),
        ) {
            Text("🏆", fontSize = 48.sp)
            Text("MEMBER OF THE WEEK", color = Farben.Weiss, fontWeight = FontWeight.Bold, fontSize = 13.sp, letterSpacing = 2.sp)
            if (show.memberOfWeek.isEmpty()) {
                Text("Horst", color = Farben.Weiss, fontWeight = FontWeight.ExtraBold, fontSize = 32.sp)
                Text("Niemand ist gelaufen. Horst hat gewonnen – diesmal.", color = Farben.Weiss, textAlign = TextAlign.Center)
            } else {
                Text(namenText(show.memberOfWeek), color = Farben.Weiss, fontWeight = FontWeight.ExtraBold, fontSize = 32.sp,
                    textAlign = TextAlign.Center)
                show.zeilen.firstOrNull { it.platz == 1 }?.let {
                    Text("${it.lk} LK · ${it.km} km · ↑ ${it.hm} m", color = Farben.Weiss, fontSize = 15.sp)
                }
            }
        }
    }
    if (show.zeilen.size > 3) liste += {
        ShowKarte("Alle Plätze", "📋") { show.zeilen.forEach { PlatzZeile(it) } }
    }
    show.wette?.let { w ->
        liste += {
            ShowKarte("Einsatz der Woche", "🎲") {
                Text("„${w.text}“", color = Farben.Grau, fontFamily = FontFamily.Serif, fontStyle = FontStyle.Italic, fontSize = 16.sp)
                Text("Das trifft: ${namenText(w.verlierer)}", color = Farben.Tinte, fontWeight = FontWeight.ExtraBold, fontSize = 20.sp)
            }
        }
    }
    show.monat?.let { m ->
        liste += {
            ShowKarte("Monatsrangliste ${m.titel}", "📅") { m.zeilen.forEach { PlatzZeile(it) } }
        }
        liste += {
            Column(
                Modifier.fillMaxWidth().clip(RoundedCornerShape(24.dp)).background(Farben.Weiss).padding(22.dp),
                horizontalAlignment = Alignment.CenterHorizontally, verticalArrangement = Arrangement.spacedBy(8.dp),
            ) {
                Text("👑", fontSize = 48.sp)
                Text("MEMBER OF THE MONTH", color = Farben.Orange, fontWeight = FontWeight.Bold, fontSize = 13.sp, letterSpacing = 2.sp)
                Text(if (m.sieger.isEmpty()) "Horst" else namenText(m.sieger), color = Farben.Tinte,
                    fontWeight = FontWeight.ExtraBold, fontSize = 32.sp, textAlign = TextAlign.Center)
                Text(m.titel, color = Farben.Grau, fontSize = 14.sp)
            }
        }
    }
    return liste
}

@Composable
private fun ShowKarte(titel: String, zeichen: String, inhalt: @Composable () -> Unit) {
    Column(
        Modifier.fillMaxWidth().clip(RoundedCornerShape(22.dp)).background(Farben.Weiss).padding(18.dp),
        verticalArrangement = Arrangement.spacedBy(6.dp),
    ) {
        Row(verticalAlignment = Alignment.CenterVertically) {
            Text(zeichen, fontSize = 26.sp)
            Spacer(Modifier.size(10.dp))
            Text(titel.uppercase(), color = Farben.Orange, fontWeight = FontWeight.Bold, fontSize = 13.sp, letterSpacing = 1.4.sp)
        }
        inhalt()
    }
}

@Composable
private fun PlatzZeile(z: RangZeile) {
    Row(verticalAlignment = Alignment.CenterVertically, modifier = Modifier.padding(vertical = 2.dp)) {
        Text("${z.platz}.", color = Farben.Grau, fontWeight = FontWeight.Bold, modifier = Modifier.size(width = 30.dp, height = 22.dp))
        Kreis(z.mitglied, 30)
        Spacer(Modifier.size(10.dp))
        Text(z.mitglied.name, color = Farben.Tinte, fontWeight = FontWeight.Bold, modifier = Modifier.weight(1f))
        Text("${z.lk} LK", color = Farben.Tinte, fontWeight = FontWeight.ExtraBold)
    }
}

/** Unter der Rangliste: Ruhmeshalle und – für den Verwalter – Familienwette und Show vorziehen. */
@Composable
fun ShowBereich(
    ruhm: List<RuhmEintrag>,
    wette: String,
    verwalter: Boolean,
    beschaeftigt: Boolean,
    oeffnen: (String) -> Unit,
    wetteSetzen: (String) -> Unit,
    vorziehen: () -> Unit,
) {
    Karte {
        Text("Einsatz der Woche", color = Farben.Tinte, fontWeight = FontWeight.ExtraBold, fontSize = 18.sp)
        if (verwalter) {
            var text by remember(wette) { mutableStateOf(wette) }
            OutlinedTextField(value = text, onValueChange = { text = it.take(140) }, label = { Text("z. B. Wer Letzter wird, backt Kuchen") },
                modifier = Modifier.fillMaxWidth())
            Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                Button(onClick = { wetteSetzen(text.trim()) }, enabled = !beschaeftigt && text.trim() != wette,
                    colors = ButtonDefaults.buttonColors(containerColor = Farben.Orange)) { Text("Einsatz festlegen") }
                TextButton(onClick = vorziehen, enabled = !beschaeftigt) { Text("Show jetzt vorziehen", color = Farben.Grau) }
            }
        } else {
            Text(if (wette.isBlank()) "Diese Woche ohne Einsatz." else "„$wette“", color = Farben.Grau,
                fontFamily = FontFamily.Serif, fontStyle = FontStyle.Italic, fontSize = 16.sp)
        }
    }
    if (ruhm.isNotEmpty()) {
        Karte {
            Text("Ruhmeshalle", color = Farben.Tinte, fontWeight = FontWeight.ExtraBold, fontSize = 18.sp)
            ruhm.forEach { r ->
                Column(Modifier.fillMaxWidth().clickable { oeffnen(r.woche) }.padding(vertical = 4.dp)) {
                    Text(r.titel, color = Farben.Grau, fontSize = 12.sp)
                    Text("🏆 " + (if (r.memberOfWeek.isEmpty()) "Horst" else namenText(r.memberOfWeek)) +
                        (if (r.memberOfMonth.isNotEmpty()) "   👑 ${namenText(r.memberOfMonth)} (${r.monat})" else ""),
                        color = Farben.Tinte, fontWeight = FontWeight.Bold, fontSize = 15.sp)
                }
            }
        }
    }
}
