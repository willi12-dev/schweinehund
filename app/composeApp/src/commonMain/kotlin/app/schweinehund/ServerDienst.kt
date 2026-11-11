package app.schweinehund

import io.ktor.client.HttpClient
import io.ktor.client.plugins.HttpTimeout
import io.ktor.client.request.forms.formData
import io.ktor.client.request.forms.submitFormWithBinaryData
import io.ktor.client.request.get
import io.ktor.client.request.post
import io.ktor.client.request.setBody
import io.ktor.client.statement.HttpResponse
import io.ktor.client.statement.bodyAsText
import io.ktor.http.ContentType
import io.ktor.http.Headers
import io.ktor.http.HttpHeaders
import io.ktor.http.contentType
import kotlinx.serialization.json.Json
import kotlinx.serialization.json.JsonArray
import kotlinx.serialization.json.JsonElement
import kotlinx.serialization.json.JsonNull
import kotlinx.serialization.json.JsonObject
import kotlinx.serialization.json.JsonPrimitive
import kotlinx.serialization.json.booleanOrNull
import kotlinx.serialization.json.buildJsonObject
import kotlinx.serialization.json.floatOrNull
import kotlinx.serialization.json.intOrNull
import kotlinx.serialization.json.jsonArray
import kotlinx.serialization.json.jsonObject
import kotlinx.serialization.json.jsonPrimitive
import kotlinx.serialization.json.longOrNull
import kotlinx.serialization.json.put
import kotlinx.serialization.json.putJsonArray

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

/** Ein Lauf, so wie ihn der Server für die Anzeige aufbereitet. */
data class LaufAnzeige(
    val id: Long?,
    val startText: String,
    val distanzKm: String,
    val dauer: String,
    val tempo: String,
    val anstiegM: Int?,
    val puls: Int?,
    val kadenz: Int?,
    val schritte: Int?,
    val quellen: List<String>,
    val hatStrecke: Boolean,
    val kmZeiten: List<String>,
    val rest: String,
    val linie: List<Pair<Float, Float>>,
)

/** Antwort des Servers: entweder ein Wert oder ein Satz, was schiefging. */
data class Antwort<T>(val wert: T?, val fehler: String?)

data class Vorschau(val entwurf: String, val lauf: LaufAnzeige)

data class GeteilteDatei(val name: String, val mime: String, val daten: ByteArray) {
    val istBild: Boolean
        get() = mime.startsWith("image/") || name.lowercase().let { it.endsWith(".png") || it.endsWith(".jpg") || it.endsWith(".jpeg") }
}

data class HcSitzung(
    val start: String, val ende: String, val distanzM: Double?, val anstiegM: Double?, val pulsAvg: Long?, val art: String,
)

private fun JsonElement?.text(): String? = (this as? JsonPrimitive)?.takeIf { it !is JsonNull }?.content

fun statusLesen(json: String): ServerZustand {
    val obj = Json.parseToJsonElement(json).jsonObject
    val version = obj["version"].text() ?: return ServerZustand.Fehler("Antwort ohne Version")
    return ServerZustand.Erreichbar(version, obj["push"].text() ?: "unbekannt")
}

fun probeLesen(json: String, httpCode: Int): String {
    val obj = runCatching { Json.parseToJsonElement(json).jsonObject }.getOrNull()
        ?: return "Unerwartete Antwort vom Server ($httpCode)."
    return if (obj["ok"]?.jsonPrimitive?.booleanOrNull == true) "Test-Push ist unterwegs – gleich sollte es klingeln."
    else obj["fehler"].text() ?: "Fehler $httpCode"
}

fun laufLesen(obj: JsonObject): LaufAnzeige = LaufAnzeige(
    id = (obj["id"] as? JsonPrimitive)?.longOrNull,
    startText = obj["start_text"].text() ?: "",
    distanzKm = obj["distanz_km"].text() ?: "–",
    dauer = obj["dauer"].text() ?: "–",
    tempo = obj["tempo"].text() ?: "–",
    anstiegM = (obj["anstieg_m"] as? JsonPrimitive)?.intOrNull,
    puls = (obj["puls_avg"] as? JsonPrimitive)?.intOrNull,
    kadenz = (obj["kadenz"] as? JsonPrimitive)?.intOrNull,
    schritte = (obj["schritte"] as? JsonPrimitive)?.intOrNull,
    quellen = (obj["quellen"] as? JsonArray)?.mapNotNull { it.text() } ?: emptyList(),
    hatStrecke = (obj["hat_strecke"] as? JsonPrimitive)?.booleanOrNull == true,
    kmZeiten = (obj["km_zeiten"] as? JsonArray)?.mapNotNull { it.text() } ?: emptyList(),
    rest = obj["rest"].text() ?: "",
    linie = (obj["linie"] as? JsonArray)?.mapNotNull { p ->
        val xy = p.jsonArray
        val x = xy.getOrNull(0)?.jsonPrimitive?.floatOrNull
        val y = xy.getOrNull(1)?.jsonPrimitive?.floatOrNull
        if (x != null && y != null) x to y else null
    } ?: emptyList(),
)

private fun <T> auswerten(json: String, code: Int, lesen: (JsonObject) -> T): Antwort<T> {
    val obj = runCatching { Json.parseToJsonElement(json).jsonObject }.getOrNull()
        ?: return Antwort(null, "Unerwartete Antwort vom Server ($code).")
    if (obj["ok"]?.jsonPrimitive?.booleanOrNull != true) return Antwort(null, obj["fehler"].text() ?: "Fehler $code")
    return runCatching { Antwort(lesen(obj), null) }.getOrElse { Antwort(null, "Antwort nicht lesbar.") }
}

fun vorschauLesen(json: String, code: Int): Antwort<Vorschau> =
    auswerten(json, code) { Vorschau(it["entwurf"].text()!!, laufLesen(it["lauf"]!!.jsonObject)) }

/** Klare Fehlermeldung statt „nicht erreichbar“ – hilft beim Datentest, die Ursache zu finden. */
fun verbindungsFehler(e: Throwable): String {
    val art = e::class.simpleName ?: "Fehler"
    return when {
        art.contains("Timeout", ignoreCase = true) -> "Der Server antwortet zu langsam ($art). Bitte gleich noch einmal teilen."
        art.contains("UnknownHost", ignoreCase = true) -> "Kein Internet oder Server-Adresse unbekannt ($art)."
        else -> "Verbindung fehlgeschlagen: $art – ${e.message?.take(160) ?: "ohne Text"}"
    }
}

fun standardClient(): HttpClient = HttpClient {
    install(HttpTimeout) {
        connectTimeoutMillis = 20_000
        socketTimeoutMillis = 90_000
        requestTimeoutMillis = 120_000
    }
}

class ServerDienst(private val basis: String, private val client: HttpClient = standardClient()) {

    private suspend fun <T> sicher(block: suspend () -> Antwort<T>): Antwort<T> =
        try { block() } catch (e: Exception) {
            if (e is kotlin.coroutines.cancellation.CancellationException) throw e
            // Ein zweiter Versuch hilft, wenn der Server (kostenloser Tarif) gerade erst aufwacht.
            try { block() } catch (e2: Exception) {
                if (e2 is kotlin.coroutines.cancellation.CancellationException) throw e2
                Antwort(null, verbindungsFehler(e2))
            }
        }

    private suspend fun HttpResponse.text() = bodyAsText() to status.value

    suspend fun status(): ServerZustand = try {
        statusLesen(client.get("$basis/api/status").bodyAsText())
    } catch (e: Exception) {
        ServerZustand.Fehler(e.message ?: "Verbindung fehlgeschlagen")
    }

    suspend fun pushProbe(token: String): String = try {
        val (text, code) = client.post("$basis/api/push/probe") {
            contentType(ContentType.Application.Json)
            setBody(buildJsonObject { put("token", token); put("plattform", "android") }.toString())
        }.text()
        probeLesen(text, code)
    } catch (e: Exception) {
        "Server nicht erreichbar."
    }

    suspend fun vorschauDatei(datei: GeteilteDatei): Antwort<Vorschau> = sicher {
        val (text, code) = client.submitFormWithBinaryData(
            url = "$basis/api/laeufe/vorschau",
            formData = formData {
                append("datei", datei.daten, Headers.build {
                    append(HttpHeaders.ContentType, datei.mime.ifBlank { "application/octet-stream" })
                    append(HttpHeaders.ContentDisposition, "filename=\"${datei.name.replace("\"", "")}\"")
                })
            },
        ).text()
        vorschauLesen(text, code)
    }

    suspend fun vorschauText(erkannt: String): Antwort<Vorschau> = sicher {
        val (text, code) = client.post("$basis/api/laeufe/vorschau") {
            contentType(ContentType.Application.Json)
            setBody(buildJsonObject { put("text", erkannt) }.toString())
        }.text()
        vorschauLesen(text, code)
    }

    suspend fun bestaetigen(entwurf: String, geraetId: String, laeufer: String, pushToken: String?): Antwort<String> = sicher {
        val (text, code) = client.post("$basis/api/laeufe/bestaetigen") {
            contentType(ContentType.Application.Json)
            setBody(buildJsonObject {
                put("entwurf", entwurf); put("geraet_id", geraetId); put("laeufer", laeufer)
                if (pushToken != null) put("push_token", pushToken)
            }.toString())
        }.text()
        auswerten(text, code) { it["text"].text() ?: "Gespeichert." }
    }

    suspend fun healthConnect(geraetId: String, laeufer: String, sitzungen: List<HcSitzung>): Antwort<String> = sicher {
        val (text, code) = client.post("$basis/api/laeufe/health-connect") {
            contentType(ContentType.Application.Json)
            setBody(buildJsonObject {
                put("geraet_id", geraetId); put("laeufer", laeufer)
                putJsonArray("sitzungen") {
                    sitzungen.forEach { s ->
                        add(buildJsonObject {
                            put("start", s.start); put("ende", s.ende); put("art", s.art)
                            s.distanzM?.let { put("distanz_m", it) }
                            s.anstiegM?.let { put("anstieg_m", it) }
                            s.pulsAvg?.let { put("puls_avg", it) }
                        })
                    }
                }
            }.toString())
        }.text()
        auswerten(text, code) {
            val neu = it["neu"]?.jsonPrimitive?.intOrNull ?: 0
            val ergaenzt = it["ergaenzt"]?.jsonPrimitive?.intOrNull ?: 0
            "Health Connect: $neu neue Läufe, $ergaenzt ergänzt."
        }
    }

    suspend fun liste(geraetId: String): Antwort<List<LaufAnzeige>> = sicher {
        val (text, code) = client.get("$basis/api/laeufe?geraet_id=$geraetId").text()
        auswerten(text, code) { o -> o["laeufe"]!!.jsonArray.map { laufLesen(it.jsonObject) } }
    }

    suspend fun detail(id: Long, geraetId: String): Antwort<LaufAnzeige> = sicher {
        val (text, code) = client.get("$basis/api/laeufe/$id?geraet_id=$geraetId").text()
        auswerten(text, code) { laufLesen(it["lauf"]!!.jsonObject) }
    }
}

/** Was die App vom Handy braucht – auf Android umgesetzt in AndroidPlattform. */
interface Plattform {
    fun lesen(schluessel: String): String?
    fun schreiben(schluessel: String, wert: String)
    suspend fun pushToken(): String?
    suspend fun texterkennung(bild: GeteilteDatei): String?
    suspend fun healthConnectVerfuegbar(): Boolean
    suspend fun healthConnectErlaubnis(): Boolean
    suspend fun healthConnectSitzungen(tage: Int): List<HcSitzung>
}
