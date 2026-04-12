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

[← Tilbake til språkoversikt](../README.md)

## Oversikt

**Energy Storage Control** er en Home Assistant custom integration for prisstyrt kontroll av et energilager. Integrasjonen kombinerer Tibber-priser, nettmålinger, SoC-grenser, tekniske lade-/utladinggrenser og et valgfritt skrivbart mål for å beregne en **signert effektkommando**.

Tegnforklaring:

- **negativ** = lading
- **positiv** = utlading

## Funksjoner

- aktuelle Tibber-priser per Tibber-hjem
- identifisering av gunstige prisfaser
- binærsensor for om tidspunktet **nå** er gunstig
- beregning av aktuell nettbalanse
- sammenslått minimum, maksimum og nåværende SoC
- konfigurerbare terskler, grunnlast og batterikapasitet
- ekstra brukergrenser for lading og utlading
- valgfri synkronisering til ekstern helper
- vedvarende cache, dagsstatistikk og lært ladevirkningsgrad

## Krav

Følgende integrasjoner må allerede være satt opp:

- `tibber`
- `zendure_ha`

Nødvendige kilder:

- minst **én** importkilde for nett
- valgfritt en eller flere eksportkilder
- egne entiteter for minimum, maksimum og aktuell SoC
- egne entiteter for teknisk utgangs- og inngangsgrense
- valgfritt en entitet for **faktisk ladeeffekt inn i batteriet**
- valgfritt en skrivbar `number` eller `input_number` som command target

## Standardverdier

- gunstig terskel: **20 %**
- fast nettgrunnlast: **0 W**
- batterikapasitet: **2,44 kWh**
- SoC-hysterese: **2 %**
- standard ladevirkningsgrad: **90 %**

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

## Installasjon

### Via HACS

1. Åpne HACS.
2. Legg til `https://github.com/Q14siX/energy_storage_control` som **Custom repository** av typen **Integration**.
3. Installer **Energy Storage Control**.
4. Start Home Assistant på nytt.
5. Legg til integrasjonen under **Settings → Devices & Services**.

### Manuell installasjon

Kopier `custom_components/energy_storage_control` til `custom_components/` i Home Assistant-konfigurasjonen.

## Oppsettstrinn

1. **Price settings**
2. **Grid sources**
3. **SoC sources**
4. **Charge feedback source**
5. **Battery settings**
6. **Technical power limits**
7. **User limits**
8. **Command target**

Viktige regler:

- minst én importkilde må velges
- eksport er valgfritt
- minimum, maksimum og nåværende SoC må være tre ulike entiteter
- teknisk output og input kan ikke bruke samme entitet
- command target må kunne lagre både negative og positive verdier

## Opprettede entiteter

### Sensorer

- `sensor.esc_<home>_current_price`
- `sensor.esc_<home>_favorable_phase`
- `sensor.esc_<primary_home>_state_of_charge`
- `sensor.esc_<primary_home>_grid_power_balance`
- `sensor.esc_<primary_home>_charge_discharge_power`

### Binærsensor

- `binary_sensor.esc_<home>_favorable_now`

### Number-entiteter

- `number.esc_<home>_favorable_threshold`
- `number.esc_<primary_home>_base_grid_power`
- `number.esc_<primary_home>_battery_capacity`
- `number.esc_<home>_soc_hysteresis`
- `number.esc_<primary_home>_user_output_power_limit`
- `number.esc_<primary_home>_user_input_power_limit`

### Switch

- `switch.esc_<primary_home>_command_target_update`

## Logikk i detalj

### Prislogikk

ESC henter Tibber-priser for **i dag og i morgen** via `tibber.get_prices`. Terskelpris per dag:

```text
threshold_price = min_price + ((max_price - min_price) * threshold_percent / 100)
```

Pris regnes som gunstig når:

```text
price <= threshold_price
```

### Valg av gunstig fase

Prioriteten er:

1. nåværende gunstige blokk i dag
2. neste fremtidige gunstige blokk i dag
3. første gunstige blokk i morgen
4. hvis morgendata mangler: siste gunstige blokk i dag

### Nettbalanse

```text
grid_power_balance = import_watts - export_watts
```

Ved flere kilder brukes den **sist oppdaterte** gyldige kilden.

### Utlading

```text
discharge_power = max(grid_power_balance - base_grid_power, 0)
```

Ingen utlading når `current_soc <= min_soc`. Verdien klemmes til brukergrense og videre til teknisk utgangsgrense.

### Lading

Lading skjer bare i aktiv gunstig fase. ESC beregner energibehovet opp til maks SoC og fordeler energibehovet over de resterende slottene i gjeldende gunstige fase. Billigste slotter prioriteres.

### Hysterese

Når `current_soc >= max_soc`, aktiveres et hold for den aktuelle gunstige fasen. Holdet oppheves først når `current_soc <= max_soc - hysteresis`.

### Signert kommando

```text
if current phase is favorable:
    command = -charge_power
else:
    command = discharge_power
```

### Læring av ladevirkningsgrad

Integrasjonen lærer bare fra ekte lading med positiv faktisk ladeeffekt. Et sample må oppfylle energi-, tids- og effektivitetsgrenser før det blir akseptert.

## Persistens og drift

Prisdata, dagsstatistikk for nettbalanse og lærte virkningsgrader lagres i Home Assistant store. Prisene oppdateres hvert kvarter. Dagsstatistikk nullstilles ved midnatt.

## Multi-home

Prisrelaterte entiteter opprettes per Tibber-hjem. Globale entiteter som nettbalanse, SoC og charge/discharge knyttes til det **første** oppdagede hjemmet.

## Feilsøking

- Ingen effektkilder: kontroller enhet, numerisk verdi og effektmåleenhet
- Ingen SoC-kilder: kontroller `%`, `device_class: battery` eller område `0..100`
- Target oppdateres ikke: kontroller switch, gyldig fortegnsområde og at target ikke samtidig brukes som limit-kilde
- Lading forblir `0`: ingen gunstig fase, SoC på maks, hysterese-hold eller inputgrense `0`
- Utlading forblir `0`: nettbalanse for lav, SoC på minimum eller outputgrense `0`
