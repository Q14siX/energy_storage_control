[![Home Assistant](https://img.shields.io/badge/Home%20Assistant-Integration-41BDF5?style=flat&logo=home-assistant&logoColor=white)](https://www.home-assistant.io/)
[![HACS](https://img.shields.io/badge/HACS-Custom-41BDF5?style=flat&logo=hacs&logoColor=white)](https://hacs.xyz/)
[![Version](https://img.shields.io/github/v/release/Q14siX/energy_storage_control?style=flat&color=41BDF5&label=Version)](https://github.com/Q14siX/energy_storage_control/releases/latest)
[![Maintained](https://img.shields.io/badge/Maintained%3F-yes-41BDF5?style=flat)](#)
[![Stars](https://img.shields.io/github/stars/Q14siX/energy_storage_control?style=flat&logo=github&color=41BDF5&label=Stars)](https://github.com/Q14siX/energy_storage_control/stargazers)
[![Languages](https://img.shields.io/badge/Languages-DE%20%7C%20EN%20%7C%20DA%20%7C%20NL%20%7C%20NO%20%7C%20SV-41BDF5?style=flat&logo=translate&logoColor=white)](#)
[![License](https://img.shields.io/github/license/Q14siX/energy_storage_control?style=flat&color=41BDF5&label=License)](https://github.com/Q14siX/energy_storage_control/blob/main/LICENSE)
[![Downloads](https://img.shields.io/github/downloads/Q14siX/energy_storage_control/total?style=flat&color=41BDF5&label=Downloads)](https://github.com/Q14siX/energy_storage_control/releases/latest)
[![Issues](https://img.shields.io/github/issues/Q14siX/energy_storage_control?style=flat&color=41BDF5&label=Issues)](https://github.com/Q14siX/energy_storage_control/issues)

<p align="center"><img src="https://raw.githubusercontent.com/Q14siX/energy_storage_control/main/brand/logo.png" alt="Energy Storage Control logo"></p>

# Energy Storage Control

## Überblick

**Energy Storage Control** ist eine Home-Assistant-Custom-Integration zur preisabhängigen Steuerung eines Energiespeichers. Die Integration kombiniert Tibber-Preisfenster, Netzleistungswerte, SoC-Grenzen, technische Lade-/Entladegrenzen sowie optionale Zielentitäten und berechnet daraus einen **signierten Leistungs-Sollwert**.

Die interne Logik ist bewusst klar getrennt:

- **Preislogik** entscheidet, ob ein Zeitraum günstig ist.
- **Entladelogik** reagiert auf reale Netzlast.
- **Ladelogik** verteilt die fehlende Energie über alle verbleibenden günstigen Zeitslots des relevanten Planungstags.
- **SoC-Logik** schützt Mindest- und Höchstgrenzen.
- **Hysterese** verhindert Schwingen am oberen SoC-Limit.
- **Lernlogik** ermittelt den realen Ladewirkungsgrad aus echten Ladevorgängen.
- **Command-Target-Synchronisierung** kann den signierten Sollwert optional in eine externe `number`- oder `input_number`-Entität schreiben.

Wichtig: In dieser Integration bedeutet der berechnete Leistungswert:

- **negativ** = Laden
- **positiv** = Entladen

## Funktionsumfang

Diese Integration liefert nicht nur einen einzelnen Steuerwert, sondern eine ganze technische Auswertungsebene für Home Assistant:

- aktuelle Tibber-Preise pro Zuhause
- Erkennung günstiger Preisphasen
- boolesche Aussage, ob **jetzt** ein günstiger Zeitraum aktiv ist
- Berechnung der aktuellen Netzleistungsbilanz
- Zusammenführung von Mindest-, Maximal- und aktuellem SoC
- konfigurierbare Schwellenwerte, Grundlast und Batteriekapazität
- zusätzliche Benutzergrenzen für Lade- und Entladeleistung
- optionales Schreiben des signierten Sollwerts in eine externe Hilfsentität
- automatische Speicherung von Cache, Tagesstatistiken und Lernwerten

## Voraussetzungen

Vor der Einrichtung müssen in Home Assistant bereits folgende Integrationen konfiguriert sein:

- [`tibber`](https://www.home-assistant.io/integrations/tibber)
- [Zendure Home Assistant Integration](https://github.com/Zendure/Zendure-HA)

Außerdem erwartet Energy Storage Control passende Quellentitäten:

- mindestens **eine Netzimport-Leistung**
- optional **eine oder mehrere Netzeinspeise-/Export-Leistungen**
- je **eine eigene Entität** für minimalen, maximalen und aktuellen SoC
- je **eine Entität** für technisches Entlade- und Ladeleistungs-Limit
- optional eine Entität für die **tatsächliche Ladeleistung in die Batterie**
- optional eine beschreibbare `number`/`input_number`-Entität als Command Target

Unterstützte Leistungsquellen dürfen in `sensor` oder `number` vorliegen und typische Leistungseinheiten wie `mW`, `W`, `kW`, `MW`, `GW` oder `TW` verwenden. Alternativ akzeptiert die Integration Entitäten mit `device_class: power`.

Für SoC-Quellen akzeptiert die Integration:

- `sensor` oder `number`
- `device_class: battery`
- Prozentwerte mit `%`
- Zahlenbereiche, die logisch auf `0..100` abbildbar sind

## Standardwerte

Ab Werk verwendet die Integration folgende Defaults:

- günstiger Schwellenwert: **20 %**
- feste Netzgrundlast: **0 W**
- Batteriekapazität: **2,44 kWh**
- SoC-Hysterese: **2 %**
- Standard-Ladewirkungsgrad für die Planung: **90 %**
- Benutzergrenze Ausgangsleistung: **0 W** bis zur jeweiligen technischen Maximalgrenze
- Benutzergrenze Eingangsleistung: **0 W** bis zur jeweiligen technischen Maximalgrenze

## Installation

### Installation über HACS

1. HACS öffnen.
2. **Custom repositories** öffnen.
3. `https://github.com/Q14siX/energy_storage_control` hinzufügen.
4. Typ **Integration** wählen.
5. **Energy Storage Control** installieren.
6. Home Assistant neu starten.
7. Die Integration unter **Einstellungen → Geräte & Dienste** hinzufügen.

### Manuelle Installation

1. Den Ordner `custom_components/energy_storage_control` aus diesem Repository kopieren.
2. In Home Assistant unter `config/custom_components/` einfügen.
3. Home Assistant neu starten.
4. Integration über die Oberfläche hinzufügen.

## Einrichtungsablauf im Detail

Die Config Flow Logik arbeitet schrittweise und validiert jede Auswahl.

### 1. Price settings
Hier werden zwei zentrale Werte erfasst:

- **Favorable threshold**: Prozentwert zur Ermittlung günstiger Preise
- **Base grid power**: feste Netzgrundlast in Watt

### 2. Grid sources
Hier werden die Leistungsquellen für Netzbezug und optional Netzeinspeisung gewählt.

Wichtig dabei:

- mindestens **eine Import-Quelle** ist Pflicht
- Export ist optional
- mehrere Quellen sind erlaubt
- verwendet wird jeweils die **zuletzt aktualisierte** gültige Quelle
- dieselbe Entität darf nicht gleichzeitig Import und Export sein

### 3. SoC sources
Hier müssen drei unterschiedliche Entitäten ausgewählt werden:

- minimaler SoC
- maximaler SoC
- aktueller SoC

Alle drei müssen verschieden sein. Die Integration prüft explizit, ob die Entitäten als SoC-Quellen geeignet sind.

### 4. Charge feedback source
Diese Entität liefert die **tatsächliche Ladeleistung in die Batterie**. Sie wird nicht nur zur Anzeige verwendet, sondern für die Lernlogik des realen Ladewirkungsgrads.

### 5. Battery settings
Hier werden gesetzt:

- nutzbare Batteriekapazität in `kWh`
- SoC-Hysterese in `%`

### 6. Technical power limits
Hier werden die externen Quellen für die technischen Maximalgrenzen ausgewählt:

- **Output limit** = technische Entladegrenze
- **Input limit** = technische Ladegrenze

Dieselben Entitäten dürfen nicht doppelt verwendet werden.

### 7. User limits
Zusätzlich zu den technischen Quellen können Benutzergrenzen gesetzt werden:

- Benutzergrenze Entladung
- Benutzergrenze Ladung

Diese Werte werden immer auf die jeweilige technische Quellenbegrenzung geklemmt.

### 8. Command target
Optional kann eine externe `number`- oder `input_number`-Entität gewählt werden.

Diese Zielentität muss:

- beschreibbar sein
- positive **und** negative Werte erlauben
- keine intern von ESC erzeugte Entität sein
- nicht gleichzeitig als technische Leistungsquelle verwendet werden

## Erzeugte Entitäten

Die Integration erzeugt Home-Assistant-Entitäten mit einem stabilen `esc_`-Präfix.

### Sensoren

- `sensor.esc_<home>_current_price`  
  Aktueller Tibber-Preis in `€/kWh`. Attribute enthalten Min/Avg/Max für heute, morgen und gesamt sowie die Rohdaten.

- `sensor.esc_<home>_favorable_phase`  
  Startzeitpunkt der aktuell relevanten günstigen Phase. Attribute enthalten Start, Ende, Schwellenwerte sowie Min/Avg/Max des ausgewählten Blocks. Das Attribut `data` enthält alle günstigen 15-Minuten-Slots des ausgewählten Tages, und `all_favorable_blocks` listet alle günstigen Zeitfenster dieses Tages auf.

- `sensor.esc_<primary_home>_state_of_charge`  
  Zusammengeführter aktueller SoC. Attribute enthalten minimalen und maximalen SoC.

- `sensor.esc_<primary_home>_grid_power_balance`  
  Signierte Netzbilanz in Watt. Attribute enthalten Import, optional Export sowie Min/Max/Avg des aktuellen Tages.

- `sensor.esc_<primary_home>_charge_discharge_power`  
  Signierter Sollwert. Attribute enthalten `charge_power`, `discharge_power`, gelernte Wirkungsgrade, Sample-Anzahl, Informationen zum Command Target sowie die unten beschriebenen Planungsattribute.

Zusätzliche Attribute dieses Sensors:

- `planned_charge_start`: Zeitpunkt, ab dem aus der aktuellen Berechnung tatsächlich mit dem Laden begonnen wird.
- `planned_charge_start_power`: geplante Ladeleistung in Watt zu diesem Startzeitpunkt.
- Fällt der geplante Start in den aktuell laufenden günstigen Slot, bezieht sich der Zeitstempel auf den aktuellen Moment, weil ESC das Laden nur ab **jetzt** beginnen oder anpassen kann.
- Wenn die SoC-Hysterese das Laden aktuell blockiert oder derzeit kein Ladebeginn geplant ist, sind diese Werte `null`.

### Binärsensor

- `binary_sensor.esc_<home>_favorable_now`  
  `on`, wenn sich die aktuelle Uhrzeit innerhalb der aktuell relevanten günstigen Phase befindet.

### Number-Entitäten

- `number.esc_<home>_favorable_threshold`
- `number.esc_<primary_home>_base_grid_power`
- `number.esc_<primary_home>_battery_capacity`
- `number.esc_<home>_soc_hysteresis`
- `number.esc_<primary_home>_user_output_power_limit`
- `number.esc_<primary_home>_user_input_power_limit`

Zusätzliche Attribute:

- `number.esc_<home>_favorable_threshold` liefert zusätzlich `current_threshold_price`. Dieser Wert ist der tagesaktuelle Strompreis, bis zu dem ESC Strom als günstig bewertet.
- Preisattribute werden bewusst nicht auf zwei Nachkommastellen gekürzt, damit sich die Berechnung direkt in Home Assistant nachvollziehen lässt.
- Batteriekapazität liefert auch aktuelle Energie sowie Energie bei Mindest- und Maximal-SoC.
- Benutzergrenzen zeigen jeweils den aktuell wirksamen technischen Quellwert an.

### Switch

- `switch.esc_<primary_home>_command_target_update`

Ist der Switch aktiv, wird der berechnete signierte Sollwert in die konfigurierte Zielentität geschrieben. Ist der Switch aus, schreibt ESC gezielt `0`.

## Steuerlogik im Detail

### Preislogik und günstiger Schwellenwert

Die Integration lädt Tibber-Preise für **heute und morgen** über den Home-Assistant-Service `tibber.get_prices`. Anschließend werden die Daten in lokale Zeit umgerechnet. Preisattribute werden dabei bewusst nicht auf zwei Nachkommastellen reduziert, damit die interne Berechnung direkt nachvollziehbar bleibt.

Das Attribut `current_threshold_price` der Entität `number.esc_<home>_favorable_threshold` zeigt den exakten Strompreis des aktuellen Tages, bis zu dem ESC Strom als günstig bewertet.

Der Grenzpreis für einen günstigen Zeitraum wird pro Tag so berechnet:

```text
threshold_price = min_price + ((max_price - min_price) * threshold_percent / 100)
```

Ein Preis ist günstig, wenn gilt:

```text
price <= threshold_price
```

### Auswahl der relevanten günstigen Phase

Die Integration bildet zusammenhängende günstige Blöcke pro Tag. Für die Auswahl gilt exakt diese Reihenfolge:

1. aktueller günstiger Block von heute
2. nächster zukünftiger günstiger Block von heute
3. erster günstiger Block von morgen
4. falls morgen noch keine Daten verfügbar sind: letzter günstiger Block von heute

Das ist wichtig, weil die Integration **heute priorisiert** und morgen nur als Fallback verwendet. Der Sensorzustand zeigt weiterhin genau einen ausgewählten günstigen Block, während `data` und `all_favorable_blocks` zusätzlich die vollständige Tagesübersicht aller günstigen Slots bzw. Zeitfenster bereitstellen.

### Netzleistungsbilanz

Die Netzbilanz wird so berechnet:

```text
grid_power_balance = import_watts - export_watts
```

Wenn keine Exportquelle konfiguriert ist, entspricht die Bilanz einfach der Importleistung.

Sind mehrere Import- oder Exportsensoren konfiguriert, verwendet ESC jeweils die **zuletzt aktualisierte** gültige Quelle.

### Entladelogik

Die Entladung folgt bewusst direkt der dokumentierten ESC-Regel:

```text
discharge_power = max(grid_power_balance - base_grid_power, 0)
```

Zusätzlich gelten diese Schutzregeln:

- wenn `current_soc <= min_soc`, dann keine Entladung
- die Entladeleistung wird auf die Benutzergrenze geklemmt
- die Benutzergrenze wird wiederum auf die technische Ausgangsgrenze geklemmt

### Ladelogik

Laden findet nur statt, wenn der **aktuelle Slot** im günstigen Preisbereich liegt, also `price <= threshold_price` gilt.

Grundvoraussetzungen:

- aktueller SoC verfügbar
- maximaler SoC verfügbar
- Batteriekapazität > 0
- Benutzergrenze Eingang > 0
- Ladewirkungsgrad > 0

Zuerst berechnet ESC, wie viel Energie bis zum Ziel-SoC noch fehlt:

```text
missing_soc_percent = max_soc - current_soc
required_stored_energy_kwh = battery_capacity_kwh * missing_soc_percent / 100
required_input_energy_kwh = required_stored_energy_kwh / (charge_efficiency_percent / 100)
```

Danach erstellt ESC den Ladeplan aus **allen verbleibenden günstigen 15-Minuten-Slots des relevanten Planungstags**. Solange heute noch günstige Slots verfügbar sind, wird heute geplant; nur sonst fällt ESC auf morgen zurück.

Für jeden günstigen Slot wird zunächst ein preisabhängiger Leistungsfaktor berechnet:

```text
price_factor = (threshold_price - slot_price) / (threshold_price - min_price)
```

Damit gilt:

- `min_price` → 100 % der verfügbaren Ladeleistung
- `threshold_price` → 0 % Ladeleistung
- Preise oberhalb der Schwelle werden für das Laden nicht verwendet

Anschließend verteilt ESC die noch benötigte Eingangsenergie **greedy** über diese günstigen Slots:

- zuerst die billigsten Slots
- bei gleichem Preis werden spätere Slots bevorzugt
- der aktuelle Slot erhält nur dann Energie, wenn die billigeren verbleibenden Slots allein nicht ausreichen oder der aktuelle Slot selbst zu den billigsten noch benötigten Slots gehört

Aus der dem aktuellen Slot zugewiesenen Energiemenge ergibt sich dann die Ladeleistung `charge_power`.

So bleibt das Laden strikt auf den günstigen Bereich begrenzt, während spätere und billigere Slots Vorrang vor früheren, nur noch ausreichend günstigen Slots bekommen.

### SoC-Hysterese

Die Hysterese verhindert ständiges Ein- und Ausschalten am oberen SoC-Limit.

Logik:

- sobald `current_soc >= max_soc`, wird für die **aktuelle günstige Phase** ein Lade-Hold aktiviert
- dieser Hold bleibt bestehen, bis `current_soc <= max_soc - hysteresis`
- der Hold gilt nur für dieselbe günstige Phase
- beginnt eine neue günstige Phase, wird neu bewertet

### Signierter Sollwert

Der finale Sollwert lautet:

- **negativ**, wenn gerade geladen wird
- **positiv**, wenn gerade entladen wird

Formal:

```text
if current phase is favorable:
    command = -charge_power
else:
    command = discharge_power
```

### Lernlogik für den Ladewirkungsgrad

Die Integration kann ihren Planungswirkungsgrad aus realen Ladevorgängen lernen. Dafür nutzt sie die konfigurierte Entität für die tatsächliche Ladeleistung in die Batterie.

Eine Lernsitzung läuft nur, wenn echte positive Ladeleistung gemessen wird. Beim Abschluss wird geprüft:

- angeforderte Energie mindestens **0,05 kWh**
- tatsächlich gespeicherte Energie mindestens **0,01 kWh**
- Dauer mindestens **300 Sekunden**
- berechneter Wirkungsgrad zwischen **70 %** und **100 %**

Dann gilt:

```text
efficiency_percent = stored_energy / requested_energy * 100
```

Der neue Gesamtwirkungsgrad wird als gleitender Mittelwert über alle akzeptierten Samples gespeichert.

### Synchronisierung des Command Targets

Wenn ein Command Target konfiguriert wurde, kann ESC den signierten Sollwert über `number.set_value` oder `input_number.set_value` in diese Entität schreiben.

Sicherheitsregeln:

- keine ESC-internen Entitäten als Ziel
- keine Zielentität, die gleichzeitig Leistungsquelle ist
- Ziel muss negative und positive Werte zulassen
- Wert wird vor dem Schreiben auf die Min-/Max-Grenzen der Zielentität geklemmt

Ist das Schreiben deaktiviert, setzt ESC das Ziel auf `0`.

## Persistenz und Laufzeitverhalten

Die Integration speichert über den Home-Assistant-Store unter anderem:

- Preis-Cache pro Tibber-Home
- Tagesstatistik der Netzleistungsbilanz
- gelernte Wirkungsgrade und Power-Command-Zustände

Beim Start werden volatile Live-Werte bewusst zurückgesetzt, damit keine veralteten Sollwerte aus dem Cache weiterverwendet werden.

Geplante Aktionen:

- Preisaktualisierung zu jeder Viertelstunde
- Reset der Tagesstatistik um Mitternacht
- State-Listener für Netzleistung, SoC, Ladefeedback und Leistungsgrenzen
- debounctes Speichern der Grid-Statistik

## Multi-Home-Verhalten

Die Integration unterstützt mehrere Tibber-Homes in Bezug auf Preisdaten. Das ist in den home-spezifischen Entitäten sichtbar:

- aktueller Preis
- günstige Phase
- favorable now
- günstiger Schwellenwert

Globale Entitäten wie Netzbilanz, SoC, Lade-/Entladeleistung und Benutzergrenzen werden jedoch an das **erste erkannte Tibber-Home** gebunden.

Das sollte man insbesondere dann wissen, wenn ein Tibber-Account mehrere Homes enthält.

## Fehlersuche

### Es werden keine Leistungsquellen angeboten
Prüfen, ob die Entitäten numerisch sind und eine passende Leistungseinheit oder `device_class: power` besitzen.

### Es werden keine SoC-Quellen angeboten
Prüfen, ob die Entität `%`, `device_class: battery` oder einen sinnvollen Bereich `0..100` besitzt.

### Der Sollwert wird nicht in die Zielentität geschrieben
Prüfen:

- Command Target konfiguriert?
- Switch `command_target_update` eingeschaltet?
- Ziel erlaubt negative **und** positive Werte?
- Ziel ist nicht gleichzeitig Input-/Output-Limit-Quelle?

### Laden bleibt bei 0 W
Typische Ursachen:

- der aktuelle Slot liegt nicht im günstigen Preisbereich
- spätere günstigere Slots decken den Restbedarf bereits ab
- aktueller SoC bereits am Maximum
- Hysterese-Hold noch aktiv
- Benutzergrenze Eingang = 0
- technische Eingangsgrenze = 0
- keine gültige Charge-Feedback-/SoC-/Kapazitätsbasis

### Entladen bleibt bei 0 W
Typische Ursachen:

- Netzbilanz liegt unter oder gleich der Grundlast
- aktueller SoC ist am Minimum
- Benutzergrenze Ausgang = 0
- technische Ausgangsgrenze = 0

## Support

- Repository Owner: **Q14siX**
- Repository: **energy_storage_control**

Fehlerberichte und Weiterentwicklungen sollten später direkt über das GitHub-Repository gepflegt werden.
