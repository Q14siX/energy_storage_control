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

## Översikt

**Energy Storage Control** är en Home Assistant custom integration för prisstyrd kontroll av energilagring. Integrationen kombinerar Tibber-priser, nätmätvärden, SoC-gränser, tekniska laddnings-/urladdningsgränser och ett valfritt skrivbart mål för att beräkna ett **signerat effektkommando**.

Teckenkonvention:

- **negativt** = laddning
- **positivt** = urladdning

## Funktioner

- aktuella Tibber-priser per Tibber-hem
- identifiering av gynnsamma prisfaser
- binär indikator för om tidsfönstret **just nu** är gynnsamt
- beräkning av aktuell nätbalans
- samlad hantering av minsta, högsta och aktuell SoC
- konfigurerbara trösklar, fast grundlast och batterikapacitet
- extra användargränser för laddning och urladdning
- valfri synkronisering till en extern helper-entitet
- persistent cache, dagsstatistik och inlärd laddningsverkningsgrad

## Krav

Följande integrationer måste redan vara konfigurerade:

- [`Tibber`](https://www.home-assistant.io/integrations/tibber)
- [Zendure Home Assistant Integration](https://github.com/Zendure/Zendure-HA)

Dessutom krävs lämpliga entiteter för:

- nätimport
- valfri nätexport
- minimum, maximum och aktuell SoC
- teknisk output- och inputgräns
- faktisk laddningseffekt in i batteriet
- valfritt skrivbart command target

## Standardvärden

- gynnsam tröskel: **20 %**
- fast nätgrundlast: **0 W**
- batterikapacitet: **2,44 kWh**
- SoC-hysteres: **2 %**
- standardiserad laddningsverkningsgrad: **90 %**

## Installation

### Via HACS

Lägg till `https://github.com/Q14siX/energy_storage_control` som **Custom repository** av typen **Integration**, installera integrationen, starta om Home Assistant och lägg sedan till den under **Settings → Devices & Services**.

### Manuell installation

Kopiera `custom_components/energy_storage_control` till Home Assistants `custom_components/`.

## Konfigurationsflöde

1. **Price settings**
2. **Grid sources**
3. **SoC sources**
4. **Charge feedback source**
5. **Battery settings**
6. **Technical power limits**
7. **User limits**
8. **Command target**

Regler som valideras:

- minst en importkälla krävs
- samma entitet får inte användas för både import och export
- min/max/aktuell SoC måste vara tre olika entiteter
- teknisk input och output får inte vara samma entitet
- command target måste kunna lagra både negativa och positiva värden

## Entiteter

### Sensorer

- `sensor.esc_<home>_current_price`
- `sensor.esc_<home>_favorable_phase`  
  Starttid för det valda gynnsamma blocket. `favorable_from` och `favorable_until` beskriver fortfarande just det blocket. Attributet `data` innehåller nu alla gynnsamma 15-minutersslotar för den valda dagen, och `all_favorable_blocks` visar alla gynnsamma tidsfönster samma dag.
- `sensor.esc_<primary_home>_state_of_charge`
- `sensor.esc_<primary_home>_grid_power_balance`
- `sensor.esc_<primary_home>_charge_discharge_power`

Ytterligare attribut för denna sensor:

- `planned_charge_start`: tidpunkt då laddning enligt den aktuella beräkningen faktiskt förväntas börja.
- `planned_charge_start_power`: planerad laddningseffekt i watt vid denna starttidpunkt.
- Om den planerade starten ligger i det förmånliga slot som redan är aktivt, avser tidsstämpeln den aktuella tidpunkten, eftersom ESC bara kan starta eller justera laddning från **nu**.
- När SoC-hysteres blockerar laddning, eller när ingen laddstart är planerad, är dessa värden `null`.

### Binär sensor

- `binary_sensor.esc_<home>_favorable_now`

### Number

- `number.esc_<home>_favorable_threshold`
- `number.esc_<primary_home>_base_grid_power`
- `number.esc_<primary_home>_battery_capacity`
- `number.esc_<home>_soc_hysteresis`
- `number.esc_<primary_home>_user_output_power_limit`
- `number.esc_<primary_home>_user_input_power_limit`

Ytterligare attribut:

- `number.esc_<home>_favorable_threshold` visar även `current_threshold_price`. Detta värde är den exakta elprisgränsen för den aktuella dagen upp till vilken ESC bedömer el som gynnsam.
- Prisattribut avrundas medvetet inte till två decimaler, så att beräkningen kan följas direkt i Home Assistant.

### Switch

- `switch.esc_<primary_home>_command_target_update`

## Styrlogik i detalj

### Prislogik

ESC hämtar Tibber-priser för **idag och imorgon** och behåller prisattributen med beräkningsprecision i stället för att kapa dem till två decimaler.

Attributet `current_threshold_price` på `number.esc_<home>_favorable_threshold` visar det exakta dagspriset upp till vilket ESC bedömer el som gynnsam.

```text
threshold_price = min_price + ((max_price - min_price) * threshold_percent / 100)
```

Ett pris är gynnsamt när:

```text
price <= threshold_price
```

### Val av gynnsam fas

1. aktuell gynnsam block idag
2. nästa framtida gynnsamma block idag
3. första gynnsamma block imorgon
4. annars senaste gynnsamma block idag om morgondatan saknas

### Nätbalans

```text
grid_power_balance = import_watts - export_watts
```

Om flera källor är valda används den **senast uppdaterade** giltiga källan.

### Urladdning

```text
discharge_power = max(grid_power_balance - base_grid_power, 0)
```

Ingen urladdning sker när SoC ligger vid eller under minimum. Värdet begränsas också av användargräns och teknisk gräns.

### Laddning

Laddning sker bara när **det aktuella slotet** ligger inom det gynnsamma prisområdet, alltså när `price <= threshold_price`.

ESC beräknar först hur mycket energi som saknas upp till max SoC. Därefter planerar ESC över **alla återstående gynnsamma 15-minutersslotar under den relevanta planeringsdagen**. Så länge det fortfarande finns gynnsamma slotar i dag används i dag, annars faller ESC tillbaka på i morgon.

För varje gynnsamt slot beräknar ESC först en linjär prisfaktor mellan dagens lägsta pris och tröskeln:

```text
price_factor = (threshold_price - slot_price) / (threshold_price - min_price)
```

Det betyder:

- `min_price` → 100 % av tillgänglig laddningseffekt
- `threshold_price` → 0 % laddningseffekt
- priser över tröskeln används inte för laddning

Därefter fördelar ESC nödvändig ingångsenergi greedy över de gynnsamma slotarna:

- billigaste slotar först
- vid samma pris prioriteras senare slotar
- det aktuella slotet får bara energi om de billigare återstående slotarna inte ensamma räcker, eller om det aktuella slotet självt hör till de billigaste slotar som fortfarande behövs

Tilldelningen för det aktuella slotet blir `charge_power`. På så sätt hålls laddningen strikt inom det gynnsamma området samtidigt som senare och billigare slotar prioriteras.

### Hysteres

När SoC når maximum aktiveras ett hold tills SoC åter är under `max_soc - hysteresis`.

### Signerat kommando

```text
if current phase is favorable:
    command = -charge_power
else:
    command = discharge_power
```

### Inlärning av verkningsgrad

Integrationen lär sig endast från verkliga laddningar med positiv faktisk laddningseffekt och godkänner bara sessioner som uppfyller definierade energi-, tids- och effektivitetsgränser.

## Persistens och drift

Prisdata, nätstatistik och inlärda verkningsgrader sparas i Home Assistant store. Priser uppdateras varje kvart och dagsstatistik återställs vid midnatt.

## Multi-home

Prisrelaterade entiteter skapas per Tibber-hem. Globala entiteter knyts till det **första** upptäckta hemmet.

## Felsökning

- Inga effektkällor: kontrollera numeriskt värde och effektenhet
- Inga SoC-källor: kontrollera `%`, `device_class: battery` eller intervallet `0..100`
- Target uppdateras inte: kontrollera switch, teckenintervall och konflikt med limit-källor
- Laddning är `0`: aktuellt slot ligger inte i det gynnsamma prisområdet, senare billigare gynnsamma slotar täcker redan behovet, SoC redan vid maximum eller inputgräns `0`
- Urladdning är `0`: för låg nätbalans, SoC vid minimum eller outputgräns `0`
