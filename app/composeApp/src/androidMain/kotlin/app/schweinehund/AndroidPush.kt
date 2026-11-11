package app.schweinehund

import android.app.Notification
import android.app.NotificationManager
import android.content.Context
import com.google.firebase.FirebaseApp
import com.google.firebase.messaging.FirebaseMessaging
import com.google.firebase.messaging.FirebaseMessagingService
import com.google.firebase.messaging.RemoteMessage
import kotlinx.coroutines.suspendCancellableCoroutine
import kotlin.coroutines.resume

/** Geräte-Token von Firebase – null, wenn die App ohne Firebase-Konfiguration gebaut wurde. */
class AndroidPush(private val context: Context) : PushQuelle {
    override suspend fun token(): String? = try {
        val bereit = FirebaseApp.getApps(context).isNotEmpty() || FirebaseApp.initializeApp(context) != null
        if (!bereit) null
        else suspendCancellableCoroutine { fortsetzung ->
            FirebaseMessaging.getInstance().token.addOnCompleteListener { aufgabe ->
                fortsetzung.resume(if (aufgabe.isSuccessful) aufgabe.result else null)
            }
        }
    } catch (e: Exception) {
        null
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
        // Ab REQ-002 meldet die App neue Tokens dem Server; für die Probe genügt das Abholen auf Knopfdruck.
    }
}
