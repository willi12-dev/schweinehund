package app.schweinehund

import android.app.Notification
import android.app.NotificationManager
import android.content.Context
import android.content.Intent
import android.graphics.Bitmap
import android.graphics.BitmapFactory
import android.graphics.Matrix
import android.media.ExifInterface
import android.net.Uri
import androidx.compose.ui.graphics.asImageBitmap
import java.io.ByteArrayOutputStream
import androidx.health.connect.client.HealthConnectClient
import androidx.health.connect.client.permission.HealthPermission
import androidx.health.connect.client.records.DistanceRecord
import androidx.health.connect.client.records.ElevationGainedRecord
import androidx.health.connect.client.records.ExerciseSessionRecord
import androidx.health.connect.client.records.HeartRateRecord
import androidx.health.connect.client.request.AggregateRequest
import androidx.health.connect.client.request.ReadRecordsRequest
import androidx.health.connect.client.time.TimeRangeFilter
import com.google.firebase.FirebaseApp
import com.google.firebase.messaging.FirebaseMessaging
import com.google.firebase.messaging.FirebaseMessagingService
import com.google.firebase.messaging.RemoteMessage
import com.google.mlkit.vision.common.InputImage
import com.google.mlkit.vision.text.TextRecognition
import com.google.mlkit.vision.text.latin.TextRecognizerOptions
import kotlinx.coroutines.CompletableDeferred
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.suspendCancellableCoroutine
import kotlinx.coroutines.withContext
import java.time.Instant
import java.time.temporal.ChronoUnit
import kotlin.coroutines.resume

/** Health-Connect-Rechte, die der Datentest braucht (nur lesen). */
val HC_RECHTE = setOf(
    HealthPermission.getReadPermission(ExerciseSessionRecord::class),
    HealthPermission.getReadPermission(DistanceRecord::class),
    HealthPermission.getReadPermission(ElevationGainedRecord::class),
    HealthPermission.getReadPermission(HeartRateRecord::class),
)

private val LAUFARTEN = setOf(
    ExerciseSessionRecord.EXERCISE_TYPE_RUNNING,
    ExerciseSessionRecord.EXERCISE_TYPE_RUNNING_TREADMILL,
)

class AndroidPlattform(
    private val context: Context,
    /** Startet den Erlaubnis-Dialog von Health Connect (MainActivity) und liefert die erteilten Rechte. */
    private val rechteAnfragen: suspend (Set<String>) -> Set<String>,
    /** REQ-013: Kamera (true) oder Bildauswahl (false) starten (MainActivity); null = abgebrochen. */
    private val bildHolen: suspend (Boolean) -> android.net.Uri? = { null },
) : Plattform {

    private val einstellungen = context.getSharedPreferences("schweinehund", Context.MODE_PRIVATE)

    override fun lesen(schluessel: String): String? = einstellungen.getString(schluessel, null)

    override fun schreiben(schluessel: String, wert: String) {
        einstellungen.edit().putString(schluessel, wert).apply()
    }

    /** Die sichtbare Activity – Teilen-Leisten öffnen sich zuverlässig nur von dort (MainActivity setzt sie). */
    var aktivitaet: android.app.Activity? = null

    override fun teilen(text: String): Boolean {
        val senden = Intent(Intent.ACTION_SEND).apply {
            type = "text/plain"
            putExtra(Intent.EXTRA_TEXT, text)
        }
        val auswahl = Intent.createChooser(senden, "Einladung verschicken")
        return try {
            val a = aktivitaet
            if (a != null && !a.isFinishing) a.startActivity(auswahl)
            else context.startActivity(auswahl.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK))
            true
        } catch (e: Exception) {
            false
        }
    }

    override fun kopieren(text: String) {
        val zwischenablage = context.getSystemService(Context.CLIPBOARD_SERVICE) as android.content.ClipboardManager
        zwischenablage.setPrimaryClip(android.content.ClipData.newPlainText("Schweinehund-Einladung", text))
    }

    override suspend fun pushToken(): String? = try {
        val bereit = FirebaseApp.getApps(context).isNotEmpty() || FirebaseApp.initializeApp(context) != null
        if (!bereit) null
        else suspendCancellableCoroutine { k ->
            FirebaseMessaging.getInstance().token.addOnCompleteListener { t -> k.resume(if (t.isSuccessful) t.result else null) }
        }
    } catch (e: Exception) {
        null
    }

    /** Texterkennung auf dem Handy. Lange Screenshots werden in Streifen zerlegt, damit kleine Schrift lesbar bleibt. */
    override suspend fun texterkennung(bild: GeteilteDatei): String? = withContext(Dispatchers.Default) {
        try {
            val bitmap = BitmapFactory.decodeByteArray(bild.daten, 0, bild.daten.size) ?: return@withContext null
            val erkenner = TextRecognition.getClient(TextRecognizerOptions.DEFAULT_OPTIONS)
            val streifen = 2000
            val teile = mutableListOf<String>()
            var y = 0
            while (y < bitmap.height) {
                val h = minOf(streifen + 120, bitmap.height - y)
                val stueck = if (y == 0 && h == bitmap.height) bitmap else Bitmap.createBitmap(bitmap, 0, y, bitmap.width, h)
                teile += erkennen(erkenner, InputImage.fromBitmap(stueck, 0))
                y += streifen
            }
            teile.joinToString("\n").ifBlank { null }
        } catch (e: Exception) {
            null
        }
    }

    private suspend fun erkennen(erkenner: com.google.mlkit.vision.text.TextRecognizer, bild: InputImage): String =
        suspendCancellableCoroutine { k ->
            erkenner.process(bild).addOnCompleteListener { t -> k.resume(if (t.isSuccessful) t.result.text else "") }
        }

    // ------------------------------------------------------------------ REQ-013: Fotos zum Lauf
    override suspend fun fotoAufnehmen(kamera: Boolean): FotoDaten? {
        val uri = bildHolen(kamera) ?: return null
        val jetzt = java.time.OffsetDateTime.now().withNano(0).toString()
        return withContext(Dispatchers.IO) {
            runCatching {
                val jpeg = fotoVerkleinern(context, uri) ?: return@runCatching null
                // REQ-014: Aufnahmezeit vor dem Entfernen der Zusatzdaten merken; frische Kamera-Aufnahme = jetzt
                FotoDaten(jpeg, aufnahmezeit(context, uri) ?: if (kamera) jetzt else null)
            }.getOrNull()
        }
    }

    override fun bildAnzeigen(daten: ByteArray): androidx.compose.ui.graphics.ImageBitmap? =
        BitmapFactory.decodeByteArray(daten, 0, daten.size)?.asImageBitmap()

    override suspend fun healthConnectVerfuegbar(): Boolean =
        HealthConnectClient.getSdkStatus(context) == HealthConnectClient.SDK_AVAILABLE

    override suspend fun healthConnectErlaubnis(): Boolean {
        val client = HealthConnectClient.getOrCreate(context)
        val vorhanden = client.permissionController.getGrantedPermissions()
        if (vorhanden.containsAll(HC_RECHTE)) return true
        return rechteAnfragen(HC_RECHTE).containsAll(HC_RECHTE)
    }

    override suspend fun healthConnectSitzungen(tage: Int): List<HcSitzung> {
        val client = HealthConnectClient.getOrCreate(context)
        val seit = Instant.now().minus(tage.toLong(), ChronoUnit.DAYS)
        val sitzungen = client.readRecords(
            ReadRecordsRequest(ExerciseSessionRecord::class, timeRangeFilter = TimeRangeFilter.after(seit))
        ).records.filter { it.exerciseType in LAUFARTEN }
        return sitzungen.map { s ->
            val summe = runCatching {
                client.aggregate(
                    AggregateRequest(
                        metrics = setOf(DistanceRecord.DISTANCE_TOTAL, ElevationGainedRecord.ELEVATION_GAINED_TOTAL, HeartRateRecord.BPM_AVG),
                        timeRangeFilter = TimeRangeFilter.between(s.startTime, s.endTime),
                    )
                )
            }.getOrNull()
            HcSitzung(
                start = s.startTime.toString(),
                ende = s.endTime.toString(),
                distanzM = summe?.get(DistanceRecord.DISTANCE_TOTAL)?.inMeters,
                anstiegM = summe?.get(ElevationGainedRecord.ELEVATION_GAINED_TOTAL)?.inMeters,
                pulsAvg = summe?.get(HeartRateRecord.BPM_AVG),
                art = "laufen",
            )
        }
    }
}

/** Zeigt Nachrichten auch an, wenn die App gerade offen ist (im Hintergrund macht das Android selbst). */
class PushEmpfang : FirebaseMessagingService() {
    override fun onMessageReceived(nachricht: RemoteMessage) {
        val n = nachricht.notification ?: return
        // Antippen öffnet die App an der passenden Stelle (REQ-006: Chat, Lauf, Rangliste)
        val oeffnen = Intent(this, MainActivity::class.java).apply {
            flags = Intent.FLAG_ACTIVITY_SINGLE_TOP or Intent.FLAG_ACTIVITY_CLEAR_TOP
            nachricht.data.forEach { (k, v) -> putExtra(k, v) }
        }
        val absicht = android.app.PendingIntent.getActivity(
            this, System.currentTimeMillis().toInt(), oeffnen,
            android.app.PendingIntent.FLAG_IMMUTABLE or android.app.PendingIntent.FLAG_UPDATE_CURRENT,
        )
        val anzeige = Notification.Builder(this, MainActivity.KANAL_FAMILIE)
            .setSmallIcon(R.drawable.ic_benachrichtigung)
            .setContentTitle(n.title ?: "Schweinehund")
            .setContentText(n.body ?: "")
            .setContentIntent(absicht)
            .setAutoCancel(true)
            .build()
        getSystemService(NotificationManager::class.java).notify(System.currentTimeMillis().toInt(), anzeige)
    }

    override fun onNewToken(token: String) {
        // Ab REQ-002 meldet die App neue Tokens dem Server.
    }
}

/** Hilfe für MainActivity: wartet auf das Ergebnis eines Erlaubnis-Dialogs. */
class Warten<T> {
    private var offen: CompletableDeferred<T>? = null
    fun neu(): CompletableDeferred<T> = CompletableDeferred<T>().also { offen = it }
    fun fertig(wert: T) {
        offen?.complete(wert)
        offen = null
    }
}

/** REQ-013: Foto aus Kamera oder Galerie → JPEG mit höchstens 1280 px langer Seite, richtig gedreht.
 *  Bitmap.compress schreibt keine EXIF-Daten – Standort und Kameramodell fallen weg (der Server prüft das zusätzlich). */
fun fotoVerkleinern(context: Context, uri: Uri, maxSeite: Int = 1280): ByteArray? {
    val aufloesung = BitmapFactory.Options().apply { inJustDecodeBounds = true }
    context.contentResolver.openInputStream(uri)?.use { BitmapFactory.decodeStream(it, null, aufloesung) } ?: return null
    if (aufloesung.outWidth <= 0 || aufloesung.outHeight <= 0) return null
    var stichprobe = 1
    while (maxOf(aufloesung.outWidth, aufloesung.outHeight) / (stichprobe * 2) >= maxSeite) stichprobe *= 2
    val roh = context.contentResolver.openInputStream(uri)?.use {
        BitmapFactory.decodeStream(it, null, BitmapFactory.Options().apply { inSampleSize = stichprobe })
    } ?: return null
    val drehung = context.contentResolver.openInputStream(uri)?.use {
        when (ExifInterface(it).getAttributeInt(ExifInterface.TAG_ORIENTATION, ExifInterface.ORIENTATION_NORMAL)) {
            ExifInterface.ORIENTATION_ROTATE_90 -> 90f
            ExifInterface.ORIENTATION_ROTATE_180 -> 180f
            ExifInterface.ORIENTATION_ROTATE_270 -> 270f
            else -> 0f
        }
    } ?: 0f
    val faktor = minOf(1f, maxSeite.toFloat() / maxOf(roh.width, roh.height))
    val matrix = Matrix().apply { postScale(faktor, faktor); postRotate(drehung) }
    val fertig = Bitmap.createBitmap(roh, 0, 0, roh.width, roh.height, matrix, true)
    return ByteArrayOutputStream().use { aus ->
        fertig.compress(Bitmap.CompressFormat.JPEG, 85, aus)
        aus.toByteArray()
    }
}

/** REQ-014: Aufnahmezeit aus den EXIF-Daten als ISO-Text (mit Zeitzone, falls im Bild; sonst die des Handys). */
fun aufnahmezeit(context: Context, uri: Uri): String? = runCatching {
    context.contentResolver.openInputStream(uri)?.use { strom ->
        val exif = ExifInterface(strom)
        val text = exif.getAttribute(ExifInterface.TAG_DATETIME_ORIGINAL) ?: exif.getAttribute(ExifInterface.TAG_DATETIME)
            ?: return@use null
        val lokal = java.time.LocalDateTime.parse(text.trim(), java.time.format.DateTimeFormatter.ofPattern("yyyy:MM:dd HH:mm:ss"))
        val versatz = exif.getAttribute(ExifInterface.TAG_OFFSET_TIME_ORIGINAL)
            ?.let { runCatching { java.time.ZoneOffset.of(it.trim()) }.getOrNull() }
        if (versatz != null) lokal.atOffset(versatz).toString()
        else lokal.atZone(java.time.ZoneId.systemDefault()).toOffsetDateTime().toString()
    }
}.getOrNull()
