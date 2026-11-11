package app.schweinehund

import io.ktor.client.HttpClient
import io.ktor.client.plugins.HttpTimeout
import io.ktor.client.request.forms.formData
import io.ktor.client.request.forms.submitFormWithBinaryData
import io.ktor.client.request.HttpRequestBuilder
import io.ktor.client.request.delete
import io.ktor.client.request.get
import io.ktor.client.request.header
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
import kotlinx.serialization.json.doubleOrNull
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
    data class Erreichbar(val version: String, val push: String, val familie: Boolean = true) : ServerZustand
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
    // REQ-003: wem der Lauf gehört, wer ihn sieht, Karte
    val mitgliedName: String = "",
    val mitgliedFarbe: String = "#8A94A6",
    val eigen: Boolean = true,
    val sichtbarkeit: String = "familie",
    val streckePrivat: Boolean = false,
    val karte: KartenDaten? = null,
    val lk: String = "",
)

/** Rangliste, Horst-o-Meter und eigener Fortschritt (REQ-004). */
data class RangZeile(val platz: Int, val mitglied: Mitglied, val lk: String, val km: String, val hm: Int, val laeufe: Int)

data class Horst(val ziel: String, val zielWert: Double, val ist: String, val prozent: Int, val spruch: String)

data class Woche(val name: String, val lkWert: Double, val lk: String)

data class Bestwert(val titel: String, val wert: String, val wann: String)

data class Punktestand(
    val titel: String,
    val zeilen: List<RangZeile>,
    val horst: Horst,
    val fortschritt: List<Woche>,
    val serie: Int,
    val dieseWoche: Boolean,
    val bestwerte: List<Bestwert>,
)

/** Ein Punkt der Strecke mit Tempo-Klasse (0 = langsamste … 4 = schnellste Abschnitte dieses Laufs). */
data class KartenPunkt(val lat: Double, val lon: Double, val klasse: Int)

data class KmMarke(val lat: Double, val lon: Double, val km: Int)

data class KartenDaten(val punkte: List<KartenPunkt>, val km: List<KmMarke>)

/** Antwort des Servers: entweder ein Wert oder ein Satz, was schiefging. abgemeldet = Schlüssel ungültig (401). */
data class Antwort<T>(val wert: T?, val fehler: String?, val abgemeldet: Boolean = false)

/** Ein Familienmitglied (REQ-002). */
data class Mitglied(
    val id: Long,
    val name: String,
    val farbe: String,
    val kuerzel: String,
    val rolle: String,
    val ich: Boolean = false,
    val beigetreten: Boolean = true,
    val einladungOffen: Boolean = false,
    val letzterLauf: String? = null,
    val kmWoche: String = "0",
    val laeufeWoche: Int = 0,
    val standardSichtbarkeit: String = "familie",
) {
    val istVerwalter: Boolean get() = rolle == "verwalter"
}

/** Ergebnis von Gründen oder Einlösen: der geheime Schlüssel für dieses Handy und wer man ist. */
data class Anmeldung(val schluessel: String, val ich: Mitglied)

data class Familienstand(val ich: Mitglied, val mitglieder: List<Mitglied>)

/** Fertiger Einladungstext für WhatsApp. */
data class Einladung(val text: String, val link: String, val code: String)

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
    val familie = (obj["familie"] as? JsonPrimitive)?.booleanOrNull ?: true
    return ServerZustand.Erreichbar(version, obj["push"].text() ?: "unbekannt", familie)
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
    mitgliedName = (obj["mitglied"] as? JsonObject)?.get("name").text() ?: "",
    mitgliedFarbe = (obj["mitglied"] as? JsonObject)?.get("farbe").text() ?: "#8A94A6",
    eigen = (obj["eigen"] as? JsonPrimitive)?.booleanOrNull ?: true,
    sichtbarkeit = obj["sichtbarkeit"].text() ?: "familie",
    streckePrivat = (obj["strecke_privat"] as? JsonPrimitive)?.booleanOrNull ?: false,
    lk = obj["lk"].text() ?: "",
    karte = (obj["karte"] as? JsonObject)?.let { k ->
        KartenDaten(
            punkte = (k["punkte"] as? JsonArray)?.mapNotNull { p ->
                val a = p.jsonArray
                val lat = a.getOrNull(0)?.jsonPrimitive?.doubleOrNull
                val lon = a.getOrNull(1)?.jsonPrimitive?.doubleOrNull
                if (lat != null && lon != null) KartenPunkt(lat, lon, a.getOrNull(2)?.jsonPrimitive?.intOrNull ?: 2) else null
            } ?: emptyList(),
            km = (k["km"] as? JsonArray)?.mapNotNull { p ->
                val a = p.jsonArray
                val lat = a.getOrNull(0)?.jsonPrimitive?.doubleOrNull
                val lon = a.getOrNull(1)?.jsonPrimitive?.doubleOrNull
                if (lat != null && lon != null) KmMarke(lat, lon, a.getOrNull(2)?.jsonPrimitive?.intOrNull ?: 0) else null
            } ?: emptyList(),
        )
    },
)

fun mitgliedLesen(obj: JsonObject): Mitglied {
    val letzter = obj["letzter_lauf"] as? JsonObject
    return Mitglied(
        id = obj["id"]!!.jsonPrimitive.longOrNull ?: 0,
        name = obj["name"].text() ?: "?",
        farbe = obj["farbe"].text() ?: "#8A94A6",
        kuerzel = obj["kuerzel"].text() ?: "?",
        rolle = obj["rolle"].text() ?: "mitglied",
        ich = (obj["ich"] as? JsonPrimitive)?.booleanOrNull ?: false,
        beigetreten = (obj["beigetreten"] as? JsonPrimitive)?.booleanOrNull ?: true,
        einladungOffen = (obj["einladung_offen"] as? JsonPrimitive)?.booleanOrNull ?: false,
        letzterLauf = letzter?.let { "${it["start_text"].text() ?: ""} · ${it["distanz_km"].text() ?: "–"} km" },
        kmWoche = obj["km_woche"].text() ?: "0",
        laeufeWoche = (obj["laeufe_woche"] as? JsonPrimitive)?.intOrNull ?: 0,
        standardSichtbarkeit = obj["standard_sichtbarkeit"].text() ?: "familie",
    )
}

fun anmeldungLesen(json: String, code: Int): Antwort<Anmeldung> =
    auswerten(json, code) { Anmeldung(it["schluessel"].text()!!, mitgliedLesen(it["ich"]!!.jsonObject)) }

fun familieLesen(json: String, code: Int): Antwort<Familienstand> =
    auswerten(json, code) { o ->
        Familienstand(mitgliedLesen(o["ich"]!!.jsonObject).copy(ich = true), o["mitglieder"]!!.jsonArray.map { mitgliedLesen(it.jsonObject) })
    }

fun einladungLesen(json: String, code: Int): Antwort<Einladung> =
    auswerten(json, code) { Einladung(it["text"].text()!!, it["link"].text()!!, it["code"].text()!!) }

private fun JsonElement?.zahl(): Double = (this as? JsonPrimitive)?.doubleOrNull ?: 0.0
private fun JsonElement?.ganz(): Int = (this as? JsonPrimitive)?.intOrNull ?: 0

fun punktestandLesen(json: String, code: Int): Antwort<Punktestand> = auswerten(json, code) { o ->
    val r = o["rangliste"]!!.jsonObject
    val h = o["horst"]!!.jsonObject
    val ich = o["ich"]!!.jsonObject
    val serie = ich["serie"] as? JsonObject
    val best = ich["bestwerte"] as? JsonObject
    val titel = mapOf("laengster" to "Längster Lauf", "hoechster" to "Meiste Höhenmeter", "schnellster_km" to "Schnellster Kilometer")
    Punktestand(
        titel = r["titel"].text() ?: "",
        zeilen = r["zeilen"]!!.jsonArray.map { z ->
            val zo = z.jsonObject
            val m = zo["mitglied"]!!.jsonObject
            RangZeile(
                platz = zo["platz"].ganz(),
                mitglied = Mitglied(m["id"].zahl().toLong(), m["name"].text() ?: "?", m["farbe"].text() ?: "#8A94A6",
                    m["kuerzel"].text() ?: "?", "mitglied"),
                lk = zo["lk"].text() ?: "0", km = zo["km"].text() ?: "0", hm = zo["hm"].ganz(), laeufe = zo["laeufe"].ganz(),
            )
        },
        horst = Horst(h["ziel"].text() ?: "40", h["ziel_wert"].zahl(), h["ist"].text() ?: "0", h["prozent"].ganz(), h["spruch"].text() ?: ""),
        fortschritt = (ich["fortschritt"] as? JsonArray)?.map { w ->
            val wo = w.jsonObject
            Woche(wo["woche"].text() ?: "", wo["lk_wert"].zahl(), wo["lk"].text() ?: "0")
        } ?: emptyList(),
        serie = serie?.get("wochen").ganz(),
        dieseWoche = (serie?.get("diese_woche") as? JsonPrimitive)?.booleanOrNull ?: false,
        bestwerte = titel.mapNotNull { (schluessel, name) ->
            (best?.get(schluessel) as? JsonObject)?.let { Bestwert(name, it["wert"].text() ?: "", it["wann"].text() ?: "") }
        },
    )
}

/** Einladungscode aus einem Link („…/e/ABCD…“) oder einer Eingabe – nur Großbuchstaben und Ziffern. */
fun einladungsCode(eingabe: String): String =
    eingabe.substringAfterLast("/e/").substringBefore("?").uppercase().filter { it in 'A'..'Z' || it in '0'..'9' }

private fun <T> auswerten(json: String, code: Int, lesen: (JsonObject) -> T): Antwort<T> {
    val obj = runCatching { Json.parseToJsonElement(json).jsonObject }.getOrNull()
        ?: return Antwort(null, "Unerwartete Antwort vom Server ($code).", abgemeldet = code == 401)
    if (obj["ok"]?.jsonPrimitive?.booleanOrNull != true) return Antwort(null, obj["fehler"].text() ?: "Fehler $code", abgemeldet = code == 401)
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

    /** Geheimer Schlüssel dieses Handys (nach Gründen oder Einladung); geht bei jeder Anfrage mit. */
    var schluessel: String? = null

    private fun HttpRequestBuilder.anmelden() {
        schluessel?.let { header(HttpHeaders.Authorization, "Bearer $it") }
    }

    private fun json(builder: HttpRequestBuilder, inhalt: JsonObject) {
        builder.anmelden()
        builder.contentType(ContentType.Application.Json)
        builder.setBody(inhalt.toString())
    }

    suspend fun gruenden(name: String, farbe: String?, geraetId: String): Antwort<Anmeldung> = sicher {
        val (text, code) = client.post("$basis/api/familie/gruenden") {
            json(this, buildJsonObject { put("name", name); put("geraet_id", geraetId); farbe?.let { put("farbe", it) } })
        }.text()
        anmeldungLesen(text, code)
    }

    suspend fun einladungAnsehen(code: String): Antwort<String> = sicher {
        val (text, status) = client.get("$basis/api/einladung/$code").text()
        auswerten(text, status) { it["name"].text() ?: "?" }
    }

    suspend fun einloesen(code: String, geraetId: String): Antwort<Anmeldung> = sicher {
        val (text, status) = client.post("$basis/api/einladung/$code") {
            json(this, buildJsonObject { put("geraet_id", geraetId) })
        }.text()
        anmeldungLesen(text, status)
    }

    suspend fun familie(): Antwort<Familienstand> = sicher {
        val (text, code) = client.get("$basis/api/familie") { anmelden() }.text()
        familieLesen(text, code)
    }

    suspend fun mitgliedAnlegen(name: String): Antwort<Einladung> = sicher {
        val (text, code) = client.post("$basis/api/mitglieder") { json(this, buildJsonObject { put("name", name) }) }.text()
        einladungLesen(text, code)
    }

    suspend fun neueEinladung(mitgliedId: Long): Antwort<Einladung> = sicher {
        val (text, code) = client.post("$basis/api/mitglieder/$mitgliedId/einladung") { json(this, buildJsonObject { }) }.text()
        einladungLesen(text, code)
    }

    suspend fun farbeAendern(farbe: String): Antwort<Mitglied> = ichAendern("farbe", farbe)

    suspend fun standardSichtbarkeit(wert: String): Antwort<Mitglied> = ichAendern("standard_sichtbarkeit", wert)

    private suspend fun ichAendern(feld: String, wert: String): Antwort<Mitglied> = sicher {
        val (text, code) = client.post("$basis/api/ich") { json(this, buildJsonObject { put(feld, wert) }) }.text()
        auswerten(text, code) { mitgliedLesen(it["ich"]!!.jsonObject) }
    }

    suspend fun rangliste(zeitraum: String): Antwort<Punktestand> = sicher {
        val (text, code) = client.get("$basis/api/rangliste?zeitraum=$zeitraum") { anmelden() }.text()
        punktestandLesen(text, code)
    }

    suspend fun zielSetzen(lk: Double): Antwort<Boolean> = sicher {
        val (text, code) = client.post("$basis/api/familie/ziel") { json(this, buildJsonObject { put("lk", lk) }) }.text()
        auswerten(text, code) { true }
    }

    suspend fun familienLaeufe(): Antwort<List<LaufAnzeige>> = sicher {
        val (text, code) = client.get("$basis/api/laeufe/familie") { anmelden() }.text()
        auswerten(text, code) { o -> o["laeufe"]!!.jsonArray.map { laufLesen(it.jsonObject) } }
    }

    suspend fun sichtbarkeit(id: Long, wert: String): Antwort<LaufAnzeige> = sicher {
        val (text, code) = client.post("$basis/api/laeufe/$id/sichtbarkeit") {
            json(this, buildJsonObject { put("sichtbarkeit", wert) })
        }.text()
        auswerten(text, code) { laufLesen(it["lauf"]!!.jsonObject) }
    }

    suspend fun loeschen(id: Long): Antwort<Boolean> = sicher {
        val (text, code) = client.delete("$basis/api/laeufe/$id") { anmelden() }.text()
        auswerten(text, code) { true }
    }

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
            block = { anmelden() },
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
            json(this, buildJsonObject { put("text", erkannt) })
        }.text()
        vorschauLesen(text, code)
    }

    suspend fun bestaetigen(entwurf: String, geraetId: String, pushToken: String?, sichtbarkeit: String? = null): Antwort<String> = sicher {
        val (text, code) = client.post("$basis/api/laeufe/bestaetigen") {
            json(this, buildJsonObject {
                put("entwurf", entwurf); put("geraet_id", geraetId)
                if (sichtbarkeit != null) put("sichtbarkeit", sichtbarkeit)
                if (pushToken != null) put("push_token", pushToken)
            })
        }.text()
        auswerten(text, code) { it["text"].text() ?: "Gespeichert." }
    }

    suspend fun healthConnect(geraetId: String, sitzungen: List<HcSitzung>): Antwort<String> = sicher {
        val (text, code) = client.post("$basis/api/laeufe/health-connect") {
            json(this, buildJsonObject {
                put("geraet_id", geraetId)
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
            })
        }.text()
        auswerten(text, code) {
            val neu = it["neu"]?.jsonPrimitive?.intOrNull ?: 0
            val ergaenzt = it["ergaenzt"]?.jsonPrimitive?.intOrNull ?: 0
            "Health Connect: $neu neue Läufe, $ergaenzt ergänzt."
        }
    }

    suspend fun liste(mitgliedId: Long? = null): Antwort<List<LaufAnzeige>> = sicher {
        val (text, code) = client.get("$basis/api/laeufe" + (mitgliedId?.let { "?mitglied=$it" } ?: "")) { anmelden() }.text()
        auswerten(text, code) { o -> o["laeufe"]!!.jsonArray.map { laufLesen(it.jsonObject) } }
    }

    suspend fun detail(id: Long): Antwort<LaufAnzeige> = sicher {
        val (text, code) = client.get("$basis/api/laeufe/$id") { anmelden() }.text()
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
    /** Text über die Teilen-Leiste verschicken (Einladung per WhatsApp). */
    fun teilen(text: String)
}
