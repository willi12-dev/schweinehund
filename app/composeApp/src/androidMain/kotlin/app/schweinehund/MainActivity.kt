package app.schweinehund

import android.Manifest
import android.app.NotificationChannel
import android.app.NotificationManager
import android.content.pm.PackageManager
import android.os.Build
import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.activity.enableEdgeToEdge
import androidx.activity.result.contract.ActivityResultContracts

class MainActivity : ComponentActivity() {

    private val erlaubnis = registerForActivityResult(ActivityResultContracts.RequestPermission()) { }

    override fun onCreate(savedInstanceState: Bundle?) {
        enableEdgeToEdge()
        super.onCreate(savedInstanceState)
        kanalAnlegen()
        if (Build.VERSION.SDK_INT >= 33 &&
            checkSelfPermission(Manifest.permission.POST_NOTIFICATIONS) != PackageManager.PERMISSION_GRANTED
        ) {
            erlaubnis.launch(Manifest.permission.POST_NOTIFICATIONS)
        }
        setContent {
            App(ServerDienst(BuildConfig.SERVER_URL), AndroidPush(applicationContext), BuildConfig.VERSION_NAME)
        }
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
