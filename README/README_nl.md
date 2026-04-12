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

[← Terug naar taaloeverzicht](../README.md)

## Overzicht

**Energy Storage Control** is een Home Assistant custom integration voor prijsbewuste aansturing van een energieopslag. De integratie combineert Tibber-prijzen, netvermogensmetingen, SoC-grenzen, technische laad-/ontlaadlimieten en optioneel een schrijfbaar doel om daaruit een **gesigneerde vermogensopdracht** af te leiden.

Tekenconventie:

- **negatief** = laden
- **positief** = ontladen

## Belangrijkste functies

- actuele Tibber-prijzen per Tibber-home
- detectie van gunstige prijsfasen
- binaire status of het huidige tijdslot gunstig is
- berekening van de actuele netbalans
- samengevoegde minimum-, maximum- en actuele SoC
- configureerbare drempel, basisnetlast en batterijcapaciteit
- extra gebruikerslimieten voor laden en ontladen
- optionele synchronisatie naar een externe helper-entiteit
- persistente cache, dagstatistiek en geleerde laadefficiëntie

## Vereisten

Vooraf geconfigureerd in Home Assistant:

- `tibber`
- `zendure_ha`

Daarnaast zijn geschikte bronentiteiten nodig:

- minimaal **één** netimport-bron
- optioneel een of meer netexport-bronnen
- aparte entiteiten voor minimale, maximale en actuele SoC
- aparte entiteiten voor technische output- en inputlimiet
- optioneel een entiteit voor het **werkelijke laadvermogen in de batterij**
- optioneel een schrijfbare `number` of `input_number` als command target

## Standaardwaarden

- gunstige drempel: **20 %**
- vaste basisnetlast: **0 W**
- batterijcapaciteit: **2,44 kWh**
- SoC-hysterese: **2 %**
- standaard laadefficiëntie voor planning: **90 %**

## Repository-structuur

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

## Installatie

### Via HACS

1. Open HACS.
2. Voeg `https://github.com/Q14siX/energy_storage_control` toe als **Custom repository** van type **Integration**.
3. Installeer **Energy Storage Control**.
4. Herstart Home Assistant.
5. Voeg de integratie toe onder **Settings → Devices & Services**.

### Handmatige installatie

Kopieer `custom_components/energy_storage_control` naar `custom_components/` in je Home Assistant-configuratie.

## Configuratiestappen

1. **Price settings**: drempel en vaste basisnetlast  
2. **Grid sources**: import verplicht, export optioneel, meerdere bronnen toegestaan  
3. **SoC sources**: minimum, maximum en actuele SoC moeten drie verschillende entiteiten zijn  
4. **Charge feedback source**: werkelijk laadvermogen in de batterij  
5. **Battery settings**: batterijcapaciteit en hysterese  
6. **Technical power limits**: technische output- en inputlimiet  
7. **User limits**: extra gebruikersgrenzen, altijd begrensd door de technische limieten  
8. **Command target**: optionele schrijfbare entiteit met positief én negatief bereik

## Gemaakte entiteiten

### Sensoren

- `sensor.esc_<home>_current_price`
- `sensor.esc_<home>_favorable_phase`
- `sensor.esc_<primary_home>_state_of_charge`
- `sensor.esc_<primary_home>_grid_power_balance`
- `sensor.esc_<primary_home>_charge_discharge_power`

### Binaire sensor

- `binary_sensor.esc_<home>_favorable_now`

### Number-entiteiten

- `number.esc_<home>_favorable_threshold`
- `number.esc_<primary_home>_base_grid_power`
- `number.esc_<primary_home>_battery_capacity`
- `number.esc_<home>_soc_hysteresis`
- `number.esc_<primary_home>_user_output_power_limit`
- `number.esc_<primary_home>_user_input_power_limit`

### Switch

- `switch.esc_<primary_home>_command_target_update`

## Logica in detail

### Prijslogica

ESC haalt Tibber-prijzen op voor **vandaag en morgen** via `tibber.get_prices`. De dagdrempel is:

```text
threshold_price = min_price + ((max_price - min_price) * threshold_percent / 100)
```

Een prijs is gunstig wanneer:

```text
price <= threshold_price
```

### Selectie van de relevante gunstige fase

De keuzevolgorde is:

1. huidige gunstige blok van vandaag
2. volgende toekomstige gunstige blok van vandaag
3. eerste gunstige blok van morgen
4. als morgen nog niet beschikbaar is: meest recente gunstige blok van vandaag

### Netbalans

```text
grid_power_balance = import_watts - export_watts
```

Bij meerdere bronnen gebruikt ESC steeds de **meest recent bijgewerkte** geldige bron.

### Ontlaadlogica

```text
discharge_power = max(grid_power_balance - base_grid_power, 0)
```

Extra regels:

- geen ontlading wanneer `current_soc <= min_soc`
- begrensd door gebruikers-outputlimiet
- die limiet wordt op haar beurt begrensd door de technische outputbron

### Laadlogica

Laden gebeurt alleen tijdens een actieve gunstige fase. ESC berekent de ontbrekende energie tot het doel-SoC en verdeelt die behoefte over de resterende slots van de actuele gunstige fase. Goedkopere slots krijgen voorrang.

### Hysterese

Wanneer `current_soc >= max_soc`, activeert ESC een hold voor de huidige gunstige fase. Die hold blijft actief tot `current_soc <= max_soc - hysteresis`.

### Gesigneerde opdracht

```text
if current phase is favorable:
    command = -charge_power
else:
    command = discharge_power
```

### Leren van laadefficiëntie

ESC leert alleen uit echte laadsessies met positieve gemeten laadstroom. Een sample telt pas mee bij voldoende energie, voldoende duur en een efficiëntie tussen **70 %** en **100 %**.

## Persistente data en runtime

ESC bewaart prijsdata, dagstatistiek van de netbalans en geleerde efficiëntiewaarden in de Home Assistant store. Prijzen worden elk kwartier vernieuwd. Dagstatistieken resetten om middernacht.

## Multi-home

Prijsgerelateerde entiteiten bestaan per Tibber-home. Globale entiteiten zoals netbalans, SoC en charge/discharge zijn gekoppeld aan het **eerste** gevonden home.

## Probleemoplossing

- Geen vermogensbronnen: controleer numerieke waarde en juiste vermogenseenheid
- Geen SoC-bronnen: controleer `%`, `device_class: battery` of bereik `0..100`
- Target wordt niet bijgewerkt: controleer switch, bereik met negatieve én positieve waarden en dubbele bronconfiguratie
- Laden blijft `0`: geen gunstige fase, SoC al op maximum, hysterese-hold of inputlimiet `0`
- Ontladen blijft `0`: netbalans te laag, SoC op minimum of outputlimiet `0`
