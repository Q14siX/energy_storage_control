[![Home Assistant](https://img.shields.io/badge/Home%20Assistant-Integration-41BDF5?style=flat&logo=home-assistant&logoColor=white)](https://www.home-assistant.io/)
[![HACS](https://img.shields.io/badge/HACS-Custom-41BDF5?style=flat&logo=hacs&logoColor=white)](https://hacs.xyz/)
[![Version](https://img.shields.io/github/v/release/Q14siX/energy_storage_control?style=flat&color=41BDF5&label=Version)](https://github.com/Q14siX/energy_storage_control/releases/latest)
[![Maintained](https://img.shields.io/badge/Maintained%3F-yes-41BDF5?style=flat)](#)
[![Stars](https://img.shields.io/github/stars/Q14siX/energy_storage_control?style=flat&logo=github&color=41BDF5&label=Stars)](https://github.com/Q14siX/energy_storage_control/stargazers)
[![Languages](https://img.shields.io/badge/Languages-DE%20%7C%20EN-41BDF5?style=flat&logo=translate&logoColor=white)](#)
[![License](https://img.shields.io/github/license/Q14siX/energy_storage_control?style=flat&color=41BDF5&label=License)](https://github.com/Q14siX/energy_storage_control/blob/main/LICENSE)
[![Downloads](https://img.shields.io/github/downloads/Q14siX/energy_storage_control/total?style=flat&color=41BDF5&label=Downloads)](https://github.com/Q14siX/energy_storage_control/releases/latest)
[![Issues](https://img.shields.io/github/issues/Q14siX/energy_storage_control?style=flat&color=41BDF5&label=Issues)](https://github.com/Q14siX/energy_storage_control/issues)

<p align="center"><img src="https://raw.githubusercontent.com/Q14siX/energy_storage_control/main/brand/logo.png" alt="Energy Storage Control logo" width="220"></p>

# Energy Storage Control

[← Til sprogoverblik](../README.md)

## Oversigt

**Energy Storage Control** er en Home Assistant custom integration til prisstyret kontrol af et energilager. Integrationen kombinerer Tibber-priser, neteffektmålinger, SoC-grænser, tekniske lade-/afladegrænser samt et valgfrit skrivbart mål og beregner derfra en **signeret effektkommando**.

Fortegnet er altid:

- **negativ** = opladning
- **positiv** = afladning

## Hovedfunktioner

- aktuelle Tibber-priser pr. Tibber-hjem
- registrering af favorable prisfaser
- binær status for om tidspunktet **lige nu** er favorabelt
- beregning af aktuel neteffektbalance
- samlet håndtering af minimum, maksimum og aktuel SoC
- konfigurerbare tærskler, fast netgrundlast og batterikapacitet
- ekstra brugergrænser for lade- og afladeeffekt
- valgfri synkronisering af den signerede kommando til en ekstern helper-entitet
- persistens for cache, dagsstatistik og lært ladevirkningsgrad

## Krav

Følgende integrationer skal allerede være konfigureret i Home Assistant:

- `tibber`
- `zendure_ha`

Derudover kræves passende kilder:

- mindst **én** sensor for netimport
- valgfrit en eller flere sensorer for neteksport
- separate entiteter for minimum, maksimum og aktuel SoC
- separate entiteter for teknisk output- og inputgrænse
- valgfrit en entitet for den **faktiske ladeeffekt ind i batteriet**
- valgfrit en skrivbar `number` eller `input_number` som command target

## Standardværdier

- favorabel tærskel: **20 %**
- fast netgrundlast: **0 W**
- batterikapacitet: **2,44 kWh**
- SoC-hysterese: **2 %**
- standard ladevirkningsgrad til planlægning: **90 %**

## Repository-struktur

```text
energy_storage_control/
├── .github/
│   └── workflows/
│       ├── hassfest.yml
│       └── validate.yml
├── brand/
│   ├── icon.png
│   └── logo.png
├── custom_components/
│   └── energy_storage_control/
│       ├── __init__.py
│       ├── binary_sensor.py
│       ├── brand/
│       │   ├── icon.png
│       │   └── logo.png
│       ├── config_flow.py
│       ├── const.py
│       ├── coordinator.py
│       ├── entity.py
│       ├── manifest.json
│       ├── number.py
│       ├── power.py
│       ├── sensor.py
│       ├── switch.py
│       └── translations/
├── README/
│   └── README_*.md
├── .gitignore
├── GITHUB_PUBLISHING_CHECKLIST.md
├── hacs.json
└── README.md
```

## Installation

### Via HACS

1. Åbn HACS.
2. Tilføj `https://github.com/Q14siX/energy_storage_control` som **Custom repository** af typen **Integration**.
3. Installer **Energy Storage Control**.
4. Genstart Home Assistant.
5. Tilføj integrationen under **Settings → Devices & Services**.

### Manuel installation

Kopiér `custom_components/energy_storage_control` til din Home Assistant-konfiguration under `custom_components/`.

## Konfigurationsflow

Flowet består af disse trin:

1. **Price settings**: tærskel og fast netgrundlast  
2. **Grid sources**: import er obligatorisk, eksport er valgfri, flere kilder er tilladt  
3. **SoC sources**: minimum, maksimum og aktuel SoC skal være tre forskellige entiteter  
4. **Charge feedback source**: faktisk ladeeffekt ind i batteriet  
5. **Battery settings**: batterikapacitet og SoC-hysterese  
6. **Technical power limits**: teknisk output- og inputgrænse  
7. **User limits**: ekstra brugergrænser, som altid klemmes til de tekniske grænser  
8. **Command target**: valgfri skrivbar entitet, som skal kunne modtage både negative og positive værdier

## Oprettede entiteter

### Sensorer

- `sensor.esc_<home>_current_price` – aktuel Tibber-pris med min/avg/max-attributter for i dag, i morgen og samlet
- `sensor.esc_<home>_favorable_phase` – starttid for den aktuelt relevante favorable fase
- `sensor.esc_<primary_home>_state_of_charge` – samlet aktuel SoC med minimum- og maksimum-attributter
- `sensor.esc_<primary_home>_grid_power_balance` – signeret netbalance i watt
- `sensor.esc_<primary_home>_charge_discharge_power` – signeret effektkommando med detaljer om charge, discharge og virkningsgrad

### Binary sensor

- `binary_sensor.esc_<home>_favorable_now` – `on`, når nuværende tid ligger i den favorable fase

### Number-entiteter

- `number.esc_<home>_favorable_threshold`
- `number.esc_<primary_home>_base_grid_power`
- `number.esc_<primary_home>_battery_capacity`
- `number.esc_<home>_soc_hysteresis`
- `number.esc_<primary_home>_user_output_power_limit`
- `number.esc_<primary_home>_user_input_power_limit`

### Switch

- `switch.esc_<primary_home>_command_target_update`

## Styringslogik i detaljer

### Prislogik

ESC henter Tibber-priser for **i dag og i morgen** via `tibber.get_prices`. Daglig tærskel beregnes som:

```text
threshold_price = min_price + ((max_price - min_price) * threshold_percent / 100)
```

Afrunding sker til fire decimaler med `ROUND_HALF_UP`. En pris er favorabel, når:

```text
price <= threshold_price
```

### Valg af favorabel fase

Relevante blokke vælges i denne rækkefølge:

1. nuværende favorable blok i dag
2. næste fremtidige favorable blok i dag
3. første favorable blok i morgen
4. hvis i morgen endnu ikke findes: seneste favorable blok fra i dag

### Netbalance

```text
grid_power_balance = import_watts - export_watts
```

Hvis flere kilder er valgt, bruges den **senest opdaterede** gyldige kilde.

### Afladning

```text
discharge_power = max(grid_power_balance - base_grid_power, 0)
```

Derudover:

- ingen afladning hvis `current_soc <= min_soc`
- værdien klemmes til brugerens outputgrænse
- outputgrænsen klemmes til den tekniske outputkilde

### Opladning

Opladning sker kun i en aktiv favorabel fase. ESC beregner først manglende energi frem til målets SoC og fordeler derefter behovet på de resterende slots i den aktuelle favorable fase. Billigste slots prioriteres først. Hvis behovet er større end den resterende mulige energi i fasen, bruges fuld bruger-inputgrænse.

### Hysterese

Når `current_soc >= max_soc`, aktiveres et hold for den aktuelle favorable fase. Holdet frigives først, når `current_soc <= max_soc - hysteresis`.

### Signeret kommando

```text
if current phase is favorable:
    command = -charge_power
else:
    command = discharge_power
```

### Læring af ladevirkningsgrad

ESC lærer kun fra reelle opladninger med positiv faktisk ladeeffekt. Et sample accepteres kun ved mindst:

- **0,05 kWh** anmodet energi
- **0,01 kWh** lagret energi
- **300 sekunder** varighed
- beregnet virkningsgrad mellem **70 %** og **100 %**

## Persistens og drift

Integrationens cache gemmer blandt andet prisdata, dagsstatistik for netbalance og lærte virkningsgrader. Priser opdateres hvert kvarter. Dagsstatistik nulstilles ved midnat.

## Multi-home

Prisrelaterede entiteter oprettes pr. Tibber-hjem. Globale entiteter som netbalance, SoC og charge/discharge bindes til det **første** registrerede hjem.

## Fejlsøgning

- Ingen effektkilder: kontrollér numeriske værdier og korrekte effektenheder
- Ingen SoC-kilder: kontrollér `%`, `device_class: battery` eller område `0..100`
- Command target opdateres ikke: kontrollér switch, fortegnsområde og at målet ikke samtidig bruges som limit-kilde
- Opladning forbliver `0`: ingen favorabel fase, SoC er allerede ved maksimum, hysterese-hold eller inputgrænse er `0`
- Afladning forbliver `0`: netbalance er ikke høj nok, SoC er ved minimum, eller outputgrænse er `0`

## GitHub og HACS

ZIP-filen indeholder allerede `hacs.json`, brand-assets og workflows til HACS validation og hassfest. GitHub-indstillinger som beskrivelse, topics og releases skal stadig sættes direkte på GitHub.
