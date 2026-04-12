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

**Energy Storage Control** er en Home Assistant custom integration for prisbevisst styring av et energilager. Integrasjonen kombinerer Tibber-priser, nettmålinger, SoC-grenser, tekniske lade- og utladingsgrenser og eventuelt et skrivbart mål for å beregne en **signert effektkommando**.

Fortegn:

- **negativ** = lading
- **positiv** = utlading

## Hovedpunkter

- nåværende Tibber-priser per Tibber-hjem
- registrering av gunstige prisperioder
- binær indikator for om tidsrommet akkurat nå er gunstig
- beregning av nåværende nettbalanse
- samlet håndtering av minimum, maksimum og gjeldende SoC
- konfigurerbare terskler, fast grunnlast og batterikapasitet
- ekstra brukergrenser for lading og utlading
- valgfri synkronisering til en ekstern helper-entitet
- vedvarende cache, dagsstatistikk og lært ladevirkningsgrad

## Krav

Må være konfigurert på forhånd:

- `tibber`
- `zendure_ha`

I tillegg trengs passende entiteter for:

- nettimport
- valgfri netteksport
- minimum, maksimum og aktuell SoC
- teknisk output- og inputgrense
- faktisk ladeeffekt inn i batteriet
- eventuelt et skrivbart command target

## Standardverdier

- gunstig terskel: **20 %**
- fast grunnlast fra nett: **0 W**
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

### HACS

Legg til `https://github.com/Q14siX/energy_storage_control` som egendefinert repository av typen **Integration**, installer pakken, start Home Assistant på nytt og legg deretter til integrasjonen.

### Manuell

Kopier `custom_components/energy_storage_control` til Home Assistant-konfigurasjonens `custom_components/`.

## Konfigurasjon

Oppsettet går gjennom prisinnstillinger, nettkilder, SoC-kilder, charge feedback, batteriinnstillinger, tekniske grenser, brukergrenser og valgfritt command target. Alle valg blir validert underveis.

Viktige regler:

- minst én importkilde er påkrevd
- import og eksport kan ikke være samme entitet
- SoC min/maks/aktuell må være tre forskjellige entiteter
- teknisk input og output kan ikke være samme entitet
- command target må kunne motta både negative og positive verdier

## Entiteter

### Sensorer

- `sensor.esc_<home>_current_price`
- `sensor.esc_<home>_favorable_phase`
- `sensor.esc_<primary_home>_state_of_charge`
- `sensor.esc_<primary_home>_grid_power_balance`
- `sensor.esc_<primary_home>_charge_discharge_power`

### Binærsensor

- `binary_sensor.esc_<home>_favorable_now`

### Number

- `number.esc_<home>_favorable_threshold`
- `number.esc_<primary_home>_base_grid_power`
- `number.esc_<primary_home>_battery_capacity`
- `number.esc_<home>_soc_hysteresis`
- `number.esc_<primary_home>_user_output_power_limit`
- `number.esc_<primary_home>_user_input_power_limit`

### Switch

- `switch.esc_<primary_home>_command_target_update`

## Teknisk logikk

### Pris og terskel

```text
threshold_price = min_price + ((max_price - min_price) * threshold_percent / 100)
```

En pris er gunstig når:

```text
price <= threshold_price
```

### Valg av gunstig blokk

1. nåværende blokk i dag
2. neste blokk i dag
3. første blokk i morgen
4. ellers siste blokk i dag hvis morgendata mangler

### Nettbalanse

```text
grid_power_balance = import_watts - export_watts
```

Ved flere kilder brukes den **sist oppdaterte** gyldige kilden.

### Utlading

```text
discharge_power = max(grid_power_balance - base_grid_power, 0)
```

Ingen utlading når SoC er ved eller under minimum. Verdien begrenses også av brukergrense og teknisk grense.

### Lading

Lading skjer bare i aktiv gunstig fase. ESC beregner energibehovet opp til maks SoC og fordeler behovet over de resterende tidsslotsene i fasen, med prioritet til de billigste slottene.

### Hysterese

Når SoC når maksimum, holdes ladingen tilbake til SoC igjen ligger under `max_soc - hysteresis`.

### Signert kommando

```text
if current phase is favorable:
    command = -charge_power
else:
    command = discharge_power
```

### Ladingseffektivitet

Læring skjer bare ved reell positiv ladeeffekt og bare dersom energi, varighet og beregnet effektivitet ligger innenfor de definerte grensene.

## Persistens og runtime

Prisdata, nettstatistikk og lærte effektivitetsverdier lagres. Prisene oppdateres hvert kvarter, og dagens statistikk nullstilles ved midnatt.

## Multi-home

Prisrelaterte entiteter finnes per Tibber-hjem. Globale entiteter knyttes til det **første** oppdagede hjemmet.

## Feilsøking

- Manglende kilder: sjekk måleenhet og numerisk verdi
- Ingen SoC-kilder: sjekk `%`, `device_class: battery` eller `0..100`
- Target oppdateres ikke: sjekk switch, fortegnsområde og konflikt med limit-kilder
- Lading er `0`: ingen gunstig fase, SoC på maks eller inputgrense `0`
- Utlading er `0`: for lav nettbalanse, SoC på minimum eller outputgrense `0`
