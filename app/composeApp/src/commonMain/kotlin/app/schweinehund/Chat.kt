package app.schweinehund

import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.widthIn
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.Button
import androidx.compose.material3.ButtonDefaults
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Switch
import androidx.compose.material3.SwitchDefaults
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
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
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp

/** Familienchat (REQ-006): Menschen, Horst und ein Eingabefeld. */
@Composable
fun ChatSeite(
    nachrichten: List<Nachricht>,
    beschaeftigt: Boolean,
    senden: (String) -> Unit,
    loeschen: (Nachricht) -> Unit,
    laufOeffnen: (Long) -> Unit,
) {
    if (nachrichten.isEmpty()) {
        Text("Noch ist es still. Schreib der Familie – Horst hört mit.", color = Farben.Grau,
            fontFamily = FontFamily.Serif, fontStyle = FontStyle.Italic, fontSize = 16.sp)
    }
    nachrichten.forEach { n -> Blase(n, { loeschen(n) }, { n.laufId?.let(laufOeffnen) }) }
    var text by remember { mutableStateOf("") }
    Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(8.dp)) {
        OutlinedTextField(value = text, onValueChange = { text = it.take(500) }, placeholder = { Text("Nachricht an die Familie") },
            modifier = Modifier.weight(1f), maxLines = 4)
        Button(onClick = { senden(text.trim()); text = "" }, enabled = !beschaeftigt && text.isNotBlank(),
            shape = RoundedCornerShape(14.dp), colors = ButtonDefaults.buttonColors(containerColor = Farben.Orange)) {
            Text("Senden", fontWeight = FontWeight.Bold)
        }
    }
}

@Composable
private fun Blase(n: Nachricht, loeschen: () -> Unit, oeffnen: () -> Unit) {
    var fragen by remember(n.id) { mutableStateOf(false) }
    val rechts = n.eigen
    Row(Modifier.fillMaxWidth(), horizontalArrangement = if (rechts) Arrangement.End else Arrangement.Start,
        verticalAlignment = Alignment.Top) {
        if (!rechts) {
            if (n.horst) {
                Box(Modifier.size(32.dp).clip(CircleShape).background(Farben.Schiefer), contentAlignment = Alignment.Center) {
                    Text("🐷", fontSize = 16.sp)
                }
            } else n.absender?.let { KleinerKreis(it) }
            Spacer(Modifier.size(8.dp))
        }
        Column(
            Modifier.widthIn(max = 290.dp).clip(RoundedCornerShape(16.dp))
                .background(when { n.horst -> Farben.Hell; rechts -> Farben.Orange; else -> Farben.Weiss })
                .clickable { if (n.horst) oeffnen() else if (rechts) fragen = !fragen }
                .padding(horizontal = 12.dp, vertical = 8.dp),
        ) {
            if (!rechts) Text(if (n.horst) "Horst" else n.absender?.name ?: "?", color = if (n.horst) Farben.Schiefer else
                farbe(n.absender?.farbe ?: "#8A94A6"), fontWeight = FontWeight.Bold, fontSize = 12.sp)
            Text(n.text, color = if (rechts) Farben.Weiss else Farben.Tinte, fontSize = 15.sp,
                fontStyle = if (n.horst) FontStyle.Italic else FontStyle.Normal)
            Text(n.zeit + if (n.horst && n.laufId != null) "  · Lauf ansehen ›" else "",
                color = if (rechts) Farben.Weiss else Farben.Grau, fontSize = 10.sp)
            if (fragen) TextButton(onClick = { fragen = false; loeschen() }) { Text("Löschen", color = Farben.Weiss, fontSize = 12.sp) }
        }
    }
}

@Composable
private fun KleinerKreis(a: Absender) {
    Box(Modifier.size(32.dp).clip(CircleShape).background(farbe(a.farbe)), contentAlignment = Alignment.Center) {
        Text(a.kuerzel, color = Farben.Weiss, fontWeight = FontWeight.Bold, fontSize = 11.sp)
    }
}

/** Reaktionen am Lauf: fünf Emojis zum An- und Abschalten, mit Zahl. */
@Composable
fun ReaktionenLeiste(reaktionen: List<Reaktion>, aktiv: Boolean, tippen: (String) -> Unit) {
    Row(horizontalArrangement = Arrangement.spacedBy(6.dp)) {
        REAKTIONEN.forEach { e ->
            val r = reaktionen.firstOrNull { it.emoji == e }
            Row(
                Modifier.clip(RoundedCornerShape(20.dp)).background(if (r?.ich == true) Farben.OrangeHell else Farben.Weiss)
                    .clickable(enabled = aktiv) { tippen(e) }.padding(horizontal = 10.dp, vertical = 6.dp),
                verticalAlignment = Alignment.CenterVertically,
            ) {
                Text(e, fontSize = 18.sp)
                if (r != null) Text(" ${r.anzahl}", color = Farben.Tinte, fontWeight = FontWeight.Bold, fontSize = 13.sp)
            }
        }
    }
    val wer = reaktionen.flatMap { r -> r.namen.map { "$it ${r.emoji}" } }
    if (wer.isNotEmpty()) Text(wer.joinToString(" · "), color = Farben.Grau, fontSize = 12.sp)
}

/** Kommentare am Lauf mit Eingabe. */
@Composable
fun KommentareBereich(kommentare: List<Kommentar>, aktiv: Boolean, senden: (String) -> Unit, loeschen: (Kommentar) -> Unit) {
    Karte {
        Text("Kommentare", color = Farben.Tinte, fontWeight = FontWeight.ExtraBold, fontSize = 18.sp)
        if (kommentare.isEmpty()) Text("Noch keiner. Sag was Nettes – oder was Ehrliches.", color = Farben.Grau, fontSize = 13.sp)
        kommentare.forEach { k ->
            Row(verticalAlignment = Alignment.Top) {
                KleinerKreis(k.absender)
                Spacer(Modifier.size(8.dp))
                Column(Modifier.weight(1f)) {
                    Text("${k.absender.name} · ${k.zeit}", color = Farben.Grau, fontSize = 11.sp)
                    Text(k.text, color = Farben.Tinte, fontSize = 15.sp)
                }
                if (k.eigen) TextButton(onClick = { loeschen(k) }, enabled = aktiv) { Text("✕", color = Farben.Grau) }
            }
        }
        var text by remember { mutableStateOf("") }
        Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(8.dp)) {
            OutlinedTextField(value = text, onValueChange = { text = it.take(500) }, placeholder = { Text("Kommentar") },
                modifier = Modifier.weight(1f), maxLines = 3)
            TextButton(onClick = { senden(text.trim()); text = "" }, enabled = aktiv && text.isNotBlank()) {
                Text("Senden", color = Farben.Orange, fontWeight = FontWeight.Bold)
            }
        }
    }
}

/** Push-Einstellungen im Bereich „Ich“. */
@Composable
fun PushEinstellungen(arten: Map<String, Boolean>, aktiv: Boolean, umschalten: (String, Boolean) -> Unit) {
    Karte {
        Text("Benachrichtigungen", color = Farben.Tinte, fontWeight = FontWeight.Bold, fontSize = 16.sp)
        PUSH_ARTEN.forEach { (art, text) ->
            val an = arten[art] ?: true
            Row(verticalAlignment = Alignment.CenterVertically, modifier = Modifier.fillMaxWidth().padding(vertical = 2.dp)) {
                Text(text, color = Farben.Tinte, fontSize = 14.sp, modifier = Modifier.weight(1f))
                Switch(checked = an, onCheckedChange = { umschalten(art, it) }, enabled = aktiv,
                    colors = SwitchDefaults.colors(checkedTrackColor = Farben.Orange))
            }
        }
        Text("Die Sonntagsshow kommt immer.", color = Farben.Grau, fontSize = 12.sp)
    }
}
