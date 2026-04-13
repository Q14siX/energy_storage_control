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

- [`Tibber`](https://www.home-assistant.io/integrations/tibber)
- [Zendure Home Assistant Integration](https://github.com/Zendure/Zendure-HA)

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
  Starttid for den valgte gunstige blokken. `favorable_from` og `favorable_until` beskriver fortsatt denne blokken. Attributtet `data` inneholder nå alle gunstige 15-minutters-slotter for den valgte dagen, og `all_favorable_blocks` viser alle gunstige tidsvinduer samme dag.
- `sensor.esc_<primary_home>_state_of_charge`
- `sensor.esc_<primary_home>_grid_power_balance`
- `sensor.esc_<primary_home>_charge_discharge_power`

Ytterligere attributter for denne sensoren:

- `planned_charge_start`: tidspunktet da lading faktisk forventes å starte ut fra den aktuelle beregningen.
- `planned_charge_start_power`: planlagt ladeeffekt i watt ved dette starttidspunktet.
- Hvis planlagt start faller i det gunstige tidsvinduet som allerede er aktivt, viser tidsstempelet til det nåværende tidspunktet, fordi ESC bare kan starte eller justere lading fra **nå**.
- Når SoC-hysterese blokkerer lading, eller når ingen ladestart er planlagt, er disse verdiene `null`.

### Binærsensor

- `binary_sensor.esc_<home>_favorable_now`

### Number-entiteter

- `number.esc_<home>_favorable_threshold`
- `number.esc_<primary_home>_base_grid_power`
- `number.esc_<primary_home>_battery_capacity`
- `number.esc_<home>_soc_hysteresis`
- `number.esc_<primary_home>_user_output_power_limit`
- `number.esc_<primary_home>_user_input_power_limit`

Ytterligere attributter:

- `number.esc_<home>_favorable_threshold` viser også `current_threshold_price`. Denne verdien er dagens nøyaktige strømprisgrense for når ESC vurderer strøm som gunstig.
- Prisattributter reduseres bevisst ikke til to desimaler, slik at beregningen kan etterprøves direkte i Home Assistant.

### Switch

- `switch.esc_<primary_home>_command_target_update`

## Logikk i detalj

### Prislogikk

ESC henter Tibber-priser for **i dag og i morgen** via `tibber.get_prices`. Prisattributter reduseres bevisst ikke til to desimaler, slik at beregningen kan etterprøves direkte i Home Assistant.

Attributtet `current_threshold_price` på `number.esc_<home>_favorable_threshold` viser den nøyaktige dagsprisen som markerer grensen for hva ESC vurderer som gunstig.

Terskelpris per dag:

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

Sensorstatusen peker fortsatt på én valgt blokk, mens `data` og `all_favorable_blocks` i tillegg viser hele oversikten over dagens gunstige slotter og blokker.

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

Lading skjer bare når **nåværende slot** ligger innenfor det gunstige prisområdet, altså når `price <= threshold_price`.

ESC beregner først hvor mye energi som mangler opp til maks SoC. Deretter planlegges det over **alle gjenværende gunstige 15-minutters-slotter på den relevante planleggingsdagen**. Så lenge det fortsatt finnes gunstige slotter i dag, brukes i dag; ellers faller ESC tilbake på i morgen.

For hver gunstige slot beregner ESC først en lineær prisfaktor mellom dagens minimumspris og terskelen:

```text
price_factor = (threshold_price - slot_price) / (threshold_price - min_price)
```

Det betyr:

- `min_price` → 100 % av tilgjengelig ladeeffekt
- `threshold_price` → 0 % ladeeffekt
- priser over terskelen brukes ikke til lading

Deretter fordeler ESC nødvendig inngangsenergi greedy over de gunstige slottene:

- billigste slotter først
- ved lik pris foretrekkes senere slotter
- nåværende slot får bare energi dersom de billigere gjenværende slottene ikke alene dekker behovet, eller dersom nåværende slot selv er blant de billigste slottene som fortsatt trengs

Tildelingen til nåværende slot blir `charge_power`. Dermed holdes ladingen strengt innenfor det gunstige området, samtidig som senere og billigere slotter prioriteres.

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
- Lading forblir `0`: nåværende slot er ikke gunstig, senere billigere gunstige slotter dekker allerede behovet, SoC på maks, hysterese-hold eller inputgrense `0`
- Utlading forblir `0`: nettbalanse for lav, SoC på minimum eller outputgrense `0`
