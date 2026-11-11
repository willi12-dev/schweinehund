package app.schweinehund

import android.Manifest
import android.app.NotificationChannel
import android.app.NotificationManager
import android.content.Intent
import android.content.pm.PackageManager
import android.net.Uri
import android.os.Build
import android.os.Bundle
import android.provider.OpenableColumns
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.activity.enableEdgeToEdge
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.runtime.mutableStateOf
import androidx.health.connect.client.PermissionController

class MainActivity : ComponentActivity() {

    private val benachrichtigungErlaubnis = registerForActivityResult(ActivityResultContracts.RequestPermission()) { }
    private val hcWarten = Warten<Set<String>>()
    private val hcErlaubnis = registerForActivityResult(PermissionController.createRequestPermissionResultContract()) { rechte ->
        hcWarten.fertig(rechte)
    }

    /** Dateien, die gerade über „Teilen“ hereinkamen – die App verarbeitet und leert die Liste. */
    private val geteilt = mutableStateOf<List<GeteilteDatei>>(emptyList())

    /** Einladungscode aus einem angetippten Link (https://…/e/CODE). */
    private val einladung = mutableStateOf<String?>(null)

    /** Ziel aus einer angetippten Push-Nachricht (REQ-006): chat, rangliste oder lauf:<id>. */
    private val pushZiel = mutableStateOf<String?>(null)

    override fun onCreate(savedInstanceState: Bundle?) {
        enableEdgeToEdge()
        super.onCreate(savedInstanceState)
        kanalAnlegen()
        if (Build.VERSION.SDK_INT >= 33 &&
            checkSelfPermission(Manifest.permission.POST_NOTIFICATIONS) != PackageManager.PERMISSION_GRANTED
        ) {
            benachrichtigungErlaubnis.launch(Manifest.permission.POST_NOTIFICATIONS)
        }
        uebernehmen(intent)
        val plattform = AndroidPlattform(applicationContext) { rechte ->
            val warten = hcWarten.neu()
            hcErlaubnis.launch(rechte)
            warten.await()
        }
        setContent {
            App(
                server = ServerDienst(BuildConfig.SERVER_URL),
                plattform = plattform,
                appVersion = "${BuildConfig.VERSION_NAME} · Bau ${BuildConfig.BAU}",
                geteilt = geteilt.value,
                geteiltErledigt = { geteilt.value = emptyList() },
                einladung = einladung.value,
                einladungErledigt = { einladung.value = null },
                pushZiel = pushZiel.value,
                pushZielErledigt = { pushZiel.value = null },
            )
        }
    }

    override fun onNewIntent(intent: Intent) {
        super.onNewIntent(intent)
        uebernehmen(intent)
    }

    private fun uebernehmen(intent: Intent?) {
        if (intent == null) return
        // Push angetippt: Firebase (App im Hintergrund) bzw. PushEmpfang (App offen) legen die Daten als Extras ab.
        intent.getStringExtra("ziel")?.let { ziel ->
            pushZiel.value = if (ziel == "lauf") "lauf:${intent.getStringExtra("lauf_id") ?: ""}" else ziel
            intent.removeExtra("ziel")
        }
        if (intent.action == Intent.ACTION_VIEW) {
            val code = intent.data?.toString()?.let { einladungsCode(it) }
            if (!code.isNullOrBlank()) einladung.value = code
            return
        }
        val uris: List<Uri> = when (intent.action) {
            Intent.ACTION_SEND -> listOfNotNull(
                if (Build.VERSION.SDK_INT >= 33) intent.getParcelableExtra(Intent.EXTRA_STREAM, Uri::class.java)
                else @Suppress("DEPRECATION") intent.getParcelableExtra(Intent.EXTRA_STREAM)
            )
            Intent.ACTION_SEND_MULTIPLE -> (
                if (Build.VERSION.SDK_INT >= 33) intent.getParcelableArrayListExtra(Intent.EXTRA_STREAM, Uri::class.java)
                else @Suppress("DEPRECATION") intent.getParcelableArrayListExtra(Intent.EXTRA_STREAM)
                ) ?: emptyList()
            else -> emptyList()
        }
        val dateien = uris.take(20).mapNotNull { lesen(it) }
        if (dateien.isNotEmpty()) geteilt.value = geteilt.value + dateien
    }

    private fun lesen(uri: Uri): GeteilteDatei? = try {
        var name = uri.lastPathSegment ?: "datei"
        contentResolver.query(uri, arrayOf(OpenableColumns.DISPLAY_NAME), null, null, null)?.use { c ->
            if (c.moveToFirst()) c.getString(0)?.let { name = it }
        }
        val mime = contentResolver.getType(uri) ?: ""
        val daten = contentResolver.openInputStream(uri)?.use { it.readBytes() }
        if (daten == null || daten.size > 15 * 1024 * 1024) null else GeteilteDatei(name, mime, daten)
    } catch (e: Exception) {
        null
    }

    private fun kanalAnlegen() {
        val kanal = NotificationChannel(KANAL_FAMILIE, "Familie", NotificationManager.IMPORTANCE_HIGH).apply {
            description = "Neuigkeiten aus der Familie: Läufe, Chat, Sonntagsshow"
        }
        getSystemService(NotificationManager::class.java).createNotificationChannel(kanal)
    }

    companion object {
        const val KANAL_FAMILIE = "familie"
    }
}
