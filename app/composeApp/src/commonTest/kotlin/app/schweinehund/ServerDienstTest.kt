package app.schweinehund

import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertNull
import kotlin.test.assertTrue

class ServerDienstTest {

    @Test
    fun statusWirdGelesen() {
        val z = statusLesen("""{"server":"ok","version":"0.2.0","push":"bereit"}""")
        assertEquals(ServerZustand.Erreichbar("0.2.0", "bereit"), z)
        assertEquals("Server erreichbar · v0.2.0", statusText(z))
    }

    @Test
    fun statusOhneVersionIstFehler() {
        assertTrue(statusLesen("""{"server":"ok"}""") is ServerZustand.Fehler)
    }

    @Test
    fun probeErfolgUndFehler() {
        assertTrue(probeLesen("""{"ok":true}""", 200).startsWith("Test-Push ist unterwegs"))
        assertEquals("Zu viele Proben", probeLesen("""{"ok":false,"fehler":"Zu viele Proben"}""", 429))
        assertTrue(probeLesen("<html>", 500).contains("500"))
    }

    @Test
    fun vorschauWirdGelesen() {
        val json = """{"ok":true,"entwurf":"abc","lauf":{"id":null,"start_text":"Mo 01.06. 06:13","distanz_km":"4,93",
            "dauer":"42:12","tempo":"8:34 /km","anstieg_m":72,"puls_avg":null,"kadenz":148,"schritte":null,
            "quellen":["datei"],"hat_strecke":true,"km_zeiten":["8:09","8:55"],"rest":"930 m in 7:45",
            "linie":[[0.0,0.5],[1.0,0.25]]}}"""
        val a = vorschauLesen(json, 200)
        assertNull(a.fehler)
        val l = a.wert!!.lauf
        assertEquals("abc", a.wert!!.entwurf)
        assertEquals("4,93", l.distanzKm)
        assertEquals(72, l.anstiegM)
        assertNull(l.puls)
        assertEquals(148, l.kadenz)
        assertEquals(listOf(0.0f to 0.5f, 1.0f to 0.25f), l.linie)
        assertEquals(listOf("8:09", "8:55"), l.kmZeiten)
    }

    @Test
    fun vorschauFehlerKommtAlsText() {
        val a = vorschauLesen("""{"ok":false,"fehler":"Die Datei ist leer."}""", 422)
        assertNull(a.wert)
        assertEquals("Die Datei ist leer.", a.fehler)
    }

    @Test
    fun bildOderDatei() {
        assertTrue(GeteilteDatei("Lauf.png", "", ByteArray(0)).istBild)
        assertTrue(GeteilteDatei("x", "image/jpeg", ByteArray(0)).istBild)
        assertTrue(!GeteilteDatei("20260601Laufen (Outdoor).gpx", "application/octet-stream", ByteArray(0)).istBild)
    }

    @Test
    fun tausenderpunkt() {
        assertEquals("6.280", tausender(6280))
        assertEquals("83", tausender(83))
        assertEquals("12.345.678", tausender(12345678))
    }
}
