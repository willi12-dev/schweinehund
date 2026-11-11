package app.schweinehund

import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertTrue

class ServerDienstTest {

    @Test
    fun statusWirdGelesen() {
        val z = statusLesen("""{"server":"ok","version":"0.1.0","push":"bereit"}""")
        assertEquals(ServerZustand.Erreichbar("0.1.0", "bereit"), z)
        assertEquals("Server erreichbar · v0.1.0", statusText(z))
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
}
