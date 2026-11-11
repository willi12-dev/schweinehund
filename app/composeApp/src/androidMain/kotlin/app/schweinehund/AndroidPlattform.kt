package app.schweinehund

import android.app.Notification
import android.app.NotificationManager
import android.content.Context
import android.graphics.Bitmap
import android.graphics.BitmapFactory
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
) : Plattform {

    private val einstellungen = context.getSharedPreferences("schweinehund", Context.MODE_PRIVATE)

    override fun lesen(schluessel: String): String? = einstellungen.getString(schluessel, null)

    override fun schreiben(schluessel: String, wert: String) {
        einstellungen.edit().putString(schluessel, wert).apply()
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
        val anzeige = Notification.Builder(this, MainActivity.KANAL_FAMILIE)
            .setSmallIcon(R.drawable.ic_benachrichtigung)
            .setContentTitle(n.title ?: "Schweinehund")
            .setContentText(n.body ?: "")
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
