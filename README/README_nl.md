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

- [`tibber`](https://www.home-assistant.io/integrations/tibber)
- [Zendure Home Assistant Integration](https://github.com/Zendure/Zendure-HA)

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
  Starttijd van het geselecteerde gunstige blok. `favorable_from` en `favorable_until` beschrijven nog steeds dat gekozen blok. Het attribuut `data` bevat nu alle gunstige slots van 15 minuten van de gekozen dag, en `all_favorable_blocks` toont alle gunstige tijdvakken van diezelfde dag.
- `sensor.esc_<primary_home>_state_of_charge`
- `sensor.esc_<primary_home>_grid_power_balance`
- `sensor.esc_<primary_home>_charge_discharge_power`

Aanvullende attributen van deze sensor:

- `planned_charge_start`: tijdstip waarop laden volgens de huidige berekening daadwerkelijk zal beginnen.
- `planned_charge_start_power`: het geplande laadvermogen in watt op dat startmoment.
- Valt de geplande start binnen het momenteel actieve gunstige slot, dan verwijst de tijdstempel naar het huidige moment, omdat ESC laden alleen vanaf **nu** kan starten of bijsturen.
- Wanneer SoC-hysterese het laden op dat moment blokkeert, of wanneer er geen laadstart gepland is, zijn deze waarden `null`.

### Binaire sensor

- `binary_sensor.esc_<home>_favorable_now`

### Number-entiteiten

- `number.esc_<home>_favorable_threshold`
- `number.esc_<primary_home>_base_grid_power`
- `number.esc_<primary_home>_battery_capacity`
- `number.esc_<home>_soc_hysteresis`
- `number.esc_<primary_home>_user_output_power_limit`
- `number.esc_<primary_home>_user_input_power_limit`

Aanvullende attributen:

- `number.esc_<home>_favorable_threshold` geeft ook `current_threshold_price` weer. Dit is de exacte stroomprijsgrens van de huidige dag tot waar ESC stroom als gunstig beoordeelt.
- Prijsattributen worden bewust niet teruggebracht naar twee decimalen, zodat de berekening direct in Home Assistant te volgen blijft.

### Switch

- `switch.esc_<primary_home>_command_target_update`

## Logica in detail

### Prijslogica

ESC haalt Tibber-prijzen op voor **vandaag en morgen** via `tibber.get_prices`. Prijsattributen worden bewust niet teruggebracht naar twee decimalen, zodat de berekening direct in Home Assistant te volgen blijft.

Het attribuut `current_threshold_price` van `number.esc_<home>_favorable_threshold` toont de exacte prijs van de huidige dag tot waar ESC stroom als gunstig beoordeelt.

De dagdrempel is:

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

De sensorstatus verwijst dus nog steeds naar één gekozen blok, terwijl `data` en `all_favorable_blocks` aanvullend het volledige overzicht van alle gunstige slots en blokken van die dag tonen.

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

Laden gebeurt alleen wanneer het **huidige slot** in het gunstige prijsbereik valt, dus wanneer `price <= threshold_price`.

ESC berekent eerst hoeveel energie nog ontbreekt tot max SoC. Daarna plant ESC over **alle resterende gunstige slots van 15 minuten van de relevante planningsdag**. Zolang er vandaag nog gunstige slots beschikbaar zijn, wordt vandaag gebruikt; anders valt ESC terug op morgen.

Voor elk gunstig slot berekent ESC eerst een lineaire prijsfactor tussen de dagminimumprijs en de drempel:

```text
price_factor = (threshold_price - slot_price) / (threshold_price - min_price)
```

Dat betekent:

- `min_price` → 100 % van het beschikbare laadvermogen
- `threshold_price` → 0 % laadvermogen
- prijzen boven de drempel worden niet gebruikt voor laden

Daarna verdeelt ESC de benodigde ingangsenergie greedy over de gunstige slots:

- goedkoopste slots eerst
- bij gelijke prijs krijgen latere slots voorrang
- het huidige slot krijgt alleen energie als de goedkopere resterende slots samen niet genoeg zijn, of als het huidige slot zelf tot de goedkoopste nog benodigde slots behoort

De toewijzing voor het huidige slot wordt `charge_power`. Zo blijft laden strikt binnen het gunstige bereik en krijgen latere, goedkopere slots voorrang.

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
- Laden blijft `0`: huidige slot ligt niet in het gunstige prijsbereik, latere goedkopere gunstige slots dekken de vraag al, SoC al op maximum, hysterese-hold of inputlimiet `0`
- Ontladen blijft `0`: netbalans te laag, SoC op minimum of outputlimiet `0`
