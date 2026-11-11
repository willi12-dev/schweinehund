package app.schweinehund

import kotlin.test.Test
import kotlinx.serialization.json.jsonObject
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

    @Test
    fun einladungscodeAusLinkOderEingabe() {
        assertEquals("ABCD234567", einladungsCode("https://x.eu.pythonanywhere.com/e/ABCD234567"))
        assertEquals("ABCD234567", einladungsCode(" abcd-2345 67 "))
        assertEquals("ABCD234567", einladungsCode("https://x/e/abcd234567?utm=1"))
    }

    @Test
    fun familieUndAnmeldungLesen() {
        val json = """{"ok": true, "ich": {"id": 1, "name": "Testläufer A", "farbe": "#EF7448", "kuerzel": "Te", "rolle": "verwalter"},
            "mitglieder": [{"id": 1, "name": "Testläufer A", "farbe": "#EF7448", "kuerzel": "Te", "rolle": "verwalter", "ich": true,
              "beigetreten": true, "einladung_offen": false, "letzter_lauf": {"start_text": "Mo 01.06. 06:13", "distanz_km": "4,93"},
              "km_woche": "8,21", "laeufe_woche": 2},
             {"id": 2, "name": "Testläufer B", "farbe": "#5B8DEF", "kuerzel": "Te", "rolle": "mitglied", "ich": false,
              "beigetreten": false, "einladung_offen": true, "letzter_lauf": null, "km_woche": "0", "laeufe_woche": 0}]}"""
        val f = familieLesen(json, 200).wert!!
        assertTrue(f.ich.istVerwalter)
        assertEquals("Mo 01.06. 06:13 · 4,93 km", f.mitglieder[0].letzterLauf)
        assertEquals("8,21", f.mitglieder[0].kmWoche)
        assertTrue(f.mitglieder[1].einladungOffen && !f.mitglieder[1].beigetreten)
        assertNull(f.mitglieder[1].letzterLauf)

        val a = anmeldungLesen("""{"ok": true, "schluessel": "geheim", "ich": {"id": 2, "name": "B", "farbe": "#5B8DEF", "kuerzel": "B", "rolle": "mitglied"}}""", 200)
        assertEquals("geheim", a.wert!!.schluessel)
        val weg = familieLesen("""{"ok": false, "fehler": "Nicht angemeldet"}""", 401)
        assertTrue(weg.abgemeldet && weg.wert == null)
    }

    @Test
    fun farbeAusHex() {
        assertEquals(farbe("#EF7448"), farbe("EF7448"))
        assertEquals(Farben.Grau, farbe("rot"))
    }

    @Test
    fun abschnitteNachTempo() {
        val p = listOf(KartenPunkt(0.0, 0.0, 1), KartenPunkt(0.0, 1.0, 1), KartenPunkt(0.0, 2.0, 1), KartenPunkt(0.0, 3.0, 4), KartenPunkt(0.0, 4.0, 4))
        val a = abschnitte(p)
        assertEquals(listOf(1, 4), a.map { it.first })
        assertEquals(3, a[0].second.size)
        assertEquals(p[2], a[1].second.first())          // nahtlos: neuer Abschnitt beginnt am Ende des alten
        assertTrue(abschnitte(p.take(1)).isEmpty())
    }

    @Test
    fun laufMitKarteUndMitgliedLesen() {
        val json = """{"id": 7, "start_text": "Mo 01.06. 06:13", "distanz_km": "4,93", "eigen": false, "sichtbarkeit": "familie",
            "strecke_privat": false, "mitglied": {"id": 2, "name": "Testläufer B", "farbe": "#5B8DEF"},
            "karte": {"punkte": [[50.1, 8.1, 0], [50.2, 8.2, 4]], "km": [[50.15, 8.15, 1]]}}"""
        val l = laufLesen(kotlinx.serialization.json.Json.parseToJsonElement(json).jsonObject)
        assertEquals("Testläufer B", l.mitgliedName)
        assertEquals(false, l.eigen)
        assertEquals(2, l.karte!!.punkte.size)
        assertEquals(1, l.karte!!.km.first().km)
    }

    @Test
    fun punktestandLesen() {
        val json = """{"ok": true,
          "rangliste": {"zeitraum": "woche", "titel": "KW 46 · 09.11. – 15.11.", "zeilen": [
            {"mitglied": {"id": 2, "name": "Testläufer B", "farbe": "#5B8DEF", "kuerzel": "Te"}, "lk_wert": 6.45, "lk": "6,45", "km": "6,11", "hm": 34, "laeufe": 1, "platz": 1},
            {"mitglied": {"id": 1, "name": "Testläufer A", "farbe": "#EF7448", "kuerzel": "Te"}, "lk_wert": 5.65, "lk": "5,65", "km": "4,93", "hm": 72, "laeufe": 1, "platz": 2}]},
          "horst": {"ziel": "40", "ziel_wert": 40.0, "ist": "12,10", "prozent": 30, "spruch": "Horst wird unruhig."},
          "ich": {"fortschritt": [{"woche": "KW 45", "lk_wert": 0, "lk": "0,0"}, {"woche": "KW 46", "lk_wert": 5.65, "lk": "5,7"}],
                  "serie": {"wochen": 1, "diese_woche": true},
                  "bestwerte": {"laengster": {"wert": "4,93 km", "wann": "10.11."}}}}"""
        val p = punktestandLesen(json, 200).wert!!
        assertEquals(listOf("Testläufer B", "Testläufer A"), p.zeilen.map { it.mitglied.name })
        assertEquals(30, p.horst.prozent)
        assertEquals(40.0, p.horst.zielWert)
        assertEquals(2, p.fortschritt.size)
        assertEquals(1, p.serie)
        assertEquals("Längster Lauf", p.bestwerte.single().titel)
    }
}
