package app.schweinehund

import io.ktor.client.HttpClient
import io.ktor.client.request.get
import io.ktor.client.request.post
import io.ktor.client.request.setBody
import io.ktor.client.statement.bodyAsText
import io.ktor.http.ContentType
import io.ktor.http.contentType
import kotlinx.serialization.json.Json
import kotlinx.serialization.json.booleanOrNull
import kotlinx.serialization.json.jsonObject
import kotlinx.serialization.json.jsonPrimitive

/** Was die App über den Server weiß. */
sealed interface ServerZustand {
    data object Laedt : ServerZustand
    data class Erreichbar(val version: String, val push: String) : ServerZustand
    data class Fehler(val grund: String) : ServerZustand
}

fun statusText(zustand: ServerZustand): String = when (zustand) {
    ServerZustand.Laedt -> "Verbinde mit dem Server …"
    is ServerZustand.Erreichbar -> "Server erreichbar · v${zustand.version}"
    is ServerZustand.Fehler -> "Server nicht erreichbar"
}

/** Liest die Antwort von /api/status. */
fun statusLesen(json: String): ServerZustand {
    val obj = Json.parseToJsonElement(json).jsonObject
    val version = obj["version"]?.jsonPrimitive?.content ?: return ServerZustand.Fehler("Antwort ohne Version")
    return ServerZustand.Erreichbar(version, obj["push"]?.jsonPrimitive?.content ?: "unbekannt")
}

/** Liest die Antwort von /api/push/probe und macht daraus einen Satz für die Oberfläche. */
fun probeLesen(json: String, httpCode: Int): String {
    val obj = runCatching { Json.parseToJsonElement(json).jsonObject }.getOrNull()
        ?: return "Unerwartete Antwort vom Server ($httpCode)."
    return if (obj["ok"]?.jsonPrimitive?.booleanOrNull == true) "Test-Push ist unterwegs – gleich sollte es klingeln."
    else obj["fehler"]?.jsonPrimitive?.content ?: "Fehler $httpCode"
}

class ServerDienst(private val basis: String, private val client: HttpClient = HttpClient()) {

    suspend fun status(): ServerZustand = try {
        statusLesen(client.get("$basis/api/status").bodyAsText())
    } catch (e: Exception) {
        ServerZustand.Fehler(e.message ?: "Verbindung fehlgeschlagen")
    }

    suspend fun pushProbe(token: String): String = try {
        val antwort = client.post("$basis/api/push/probe") {
            contentType(ContentType.Application.Json)
            setBody("""{"token":"$token","plattform":"android"}""")
        }
        probeLesen(antwort.bodyAsText(), antwort.status.value)
    } catch (e: Exception) {
        "Server nicht erreichbar."
    }
}

/** Plattform-Teil: liefert das Geräte-Token für Push (Android: Firebase). */
interface PushQuelle {
    suspend fun token(): String?
}
