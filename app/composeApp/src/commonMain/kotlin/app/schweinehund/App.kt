package app.schweinehund

import androidx.compose.foundation.background
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
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.Button
import androidx.compose.material3.ButtonDefaults
import androidx.compose.material3.MaterialTheme
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
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.SpanStyle
import androidx.compose.ui.text.buildAnnotatedString
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.font.FontStyle
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.withStyle
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import kotlinx.coroutines.launch

/** Design „weiches Grau“ – Schiefer statt Schwarz, warmes Orange als Akzent. */
object Farben {
    val Grund = Color(0xFFF3F4F7)
    val Schiefer = Color(0xFF454B5A)
    val Tinte = Color(0xFF2E3340)
    val Grau = Color(0xFF6A6F7A)
    val Hell = Color(0xFFDDE0E6)
    val Orange = Color(0xFFEF7448)
    val Gruen = Color(0xFF9CC65A)
    val Weiss = Color(0xFFFFFFFF)
}

@Composable
fun App(server: ServerDienst, push: PushQuelle, appVersion: String) {
    var zustand by remember { mutableStateOf<ServerZustand>(ServerZustand.Laedt) }
    var pushText by remember { mutableStateOf("") }
    var pushLaeuft by remember { mutableStateOf(false) }
    val scope = rememberCoroutineScope()

    LaunchedEffect(Unit) { zustand = server.status() }

    MaterialTheme(colorScheme = lightColorScheme(primary = Farben.Orange, background = Farben.Grund, onSurface = Farben.Tinte)) {
        Box(Modifier.fillMaxSize().background(Farben.Grund).safeDrawingPadding()) {
            Column(Modifier.fillMaxSize().padding(horizontal = 22.dp, vertical = 24.dp), verticalArrangement = Arrangement.spacedBy(18.dp)) {
                Text(
                    buildAnnotatedString {
                        append("SCHWEINEHUND")
                        withStyle(SpanStyle(color = Farben.Orange)) { append(".") }
                    },
                    color = Farben.Tinte, fontWeight = FontWeight.ExtraBold, fontSize = 15.sp, letterSpacing = 1.4.sp,
                )
                Column(verticalArrangement = Arrangement.spacedBy(6.dp)) {
                    Text("Horst ist eingezogen.", color = Farben.Tinte, fontWeight = FontWeight.ExtraBold, fontSize = 34.sp, lineHeight = 36.sp)
                    Text(
                        "Das Fundament steht. Bald landen hier eure Läufe.",
                        color = Farben.Grau, fontFamily = FontFamily.Serif, fontStyle = FontStyle.Italic, fontSize = 17.sp,
                    )
                }

                Column(
                    Modifier.fillMaxWidth().clip(RoundedCornerShape(22.dp)).background(Farben.Schiefer).padding(18.dp),
                    verticalArrangement = Arrangement.spacedBy(8.dp),
                ) {
                    Text("SERVER", color = Farben.Hell, fontWeight = FontWeight.Bold, fontSize = 12.sp, letterSpacing = 1.6.sp)
                    Row(verticalAlignment = Alignment.CenterVertically) {
                        val punkt = when (zustand) {
                            is ServerZustand.Erreichbar -> Farben.Gruen
                            is ServerZustand.Fehler -> Farben.Orange
                            ServerZustand.Laedt -> Farben.Hell
                        }
                        Box(Modifier.size(10.dp).clip(CircleShape).background(punkt))
                        Spacer(Modifier.size(10.dp))
                        Text(statusText(zustand), color = Farben.Weiss, fontWeight = FontWeight.Bold, fontSize = 20.sp)
                    }
                    val z = zustand
                    if (z is ServerZustand.Erreichbar) {
                        Text("Push auf dem Server: ${z.push}", color = Farben.Hell, fontSize = 14.sp)
                    }
                    if (z is ServerZustand.Fehler) {
                        Text(z.grund, color = Farben.Hell, fontSize = 13.sp)
                        Button(
                            onClick = { scope.launch { zustand = ServerZustand.Laedt; zustand = server.status() } },
                            colors = ButtonDefaults.buttonColors(containerColor = Farben.Orange),
                        ) { Text("Nochmal versuchen") }
                    }
                }

                Column(
                    Modifier.fillMaxWidth().clip(RoundedCornerShape(22.dp)).background(Farben.Weiss).padding(18.dp),
                    verticalArrangement = Arrangement.spacedBy(10.dp),
                ) {
                    Text("Test-Push", color = Farben.Tinte, fontWeight = FontWeight.ExtraBold, fontSize = 20.sp)
                    Text(
                        "Der Server schickt eine Nachricht an dieses Handy. So prüfen wir, ob Benachrichtigungen ankommen.",
                        color = Farben.Grau, fontSize = 15.sp, lineHeight = 21.sp,
                    )
                    Button(
                        onClick = {
                            scope.launch {
                                pushLaeuft = true
                                pushText = "Frage Firebase nach dem Geräte-Token …"
                                val token = push.token()
                                pushText = if (token == null) "Push ist in dieser App-Version noch nicht eingerichtet (Firebase fehlt)."
                                else server.pushProbe(token)
                                pushLaeuft = false
                            }
                        },
                        enabled = !pushLaeuft,
                        modifier = Modifier.fillMaxWidth().height(52.dp),
                        shape = RoundedCornerShape(14.dp),
                        colors = ButtonDefaults.buttonColors(containerColor = Farben.Orange),
                    ) { Text("Test-Push anfordern", fontWeight = FontWeight.Bold, fontSize = 16.sp) }
                    if (pushText.isNotEmpty()) Text(pushText, color = Farben.Tinte, fontSize = 14.sp)
                }

                Spacer(Modifier.weight(1f))
                Text(
                    "„Fundament? Klingt anstrengend.“ – Horst",
                    color = Farben.Grau, fontFamily = FontFamily.Serif, fontStyle = FontStyle.Italic, fontSize = 15.sp,
                )
                Text("App v$appVersion", color = Farben.Grau, fontSize = 12.sp)
            }
        }
    }
}
