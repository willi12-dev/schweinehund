package app.schweinehund

import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier

/** Tempo-Farben von langsam (0) nach schnell (4) – sanft, passend zu „weiches Grau“. */
val TEMPO_FARBEN = listOf("#5B8DEF", "#3FB8AF", "#9CC65A", "#E8B33F", "#EF7448")

/** Kartenstil von OpenFreeMap (kostenlos, ohne Schlüssel) – „Positron“ ist hell und grau. */
const val KARTEN_STIL = "https://tiles.openfreemap.org/styles/positron"

/** Echte Karte mit der Strecke (REQ-003) – Android: MapLibre; iPhone folgt mit REQ-012. */
@Composable
expect fun LaufKarte(karte: KartenDaten, modifier: Modifier)

/** Strecke in zusammenhängende Abschnitte gleicher Tempo-Klasse zerlegen (jeder Abschnitt beginnt am Ende des vorigen). */
fun abschnitte(punkte: List<KartenPunkt>): List<Pair<Int, List<KartenPunkt>>> {
    if (punkte.size < 2) return emptyList()
    val ergebnis = mutableListOf<Pair<Int, List<KartenPunkt>>>()
    var aktuell = mutableListOf(punkte[0])
    var klasse = punkte[1].klasse
    for (i in 1 until punkte.size) {
        val p = punkte[i]
        if (p.klasse != klasse) {
            ergebnis += klasse to aktuell
            aktuell = mutableListOf(punkte[i - 1])
            klasse = p.klasse
        }
        aktuell += p
    }
    ergebnis += klasse to aktuell
    return ergebnis
}
