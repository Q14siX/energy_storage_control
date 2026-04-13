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

- [`Tibber`](https://www.home-assistant.io/integrations/tibber)
- [Zendure Home Assistant Integration](https://github.com/Zendure/Zendure-HA)

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
  Starttid for den valde gunstige blokka. `favorable_from` og `favorable_until` skildrar framleis denne blokka. Attributtet `data` inneheld no alle gunstige 15-minuttsslotar for den valde dagen, og `all_favorable_blocks` viser alle gunstige tidsvindauge same dag.
- `sensor.esc_<primary_home>_state_of_charge`
- `sensor.esc_<primary_home>_grid_power_balance`
- `sensor.esc_<primary_home>_charge_discharge_power`

Ytterlegare attributt for denne sensoren:

- `planned_charge_start`: tidspunktet då lading faktisk er venta å starte ut frå den aktuelle berekninga.
- `planned_charge_start_power`: planlagd ladeeffekt i watt ved dette starttidspunktet.
- Dersom planlagd start fell i det gunstige tidsrommet som alt er aktivt, viser tidsstempelet til det noverande tidspunktet, fordi ESC berre kan starte eller justere lading frå **no**.
- Når SoC-hysterese blokkerer lading, eller når ingen ladestart er planlagd, er desse verdiane `null`.

### Binærsensor

- `binary_sensor.esc_<home>_favorable_now`

### Number

- `number.esc_<home>_favorable_threshold`
- `number.esc_<primary_home>_base_grid_power`
- `number.esc_<primary_home>_battery_capacity`
- `number.esc_<home>_soc_hysteresis`
- `number.esc_<primary_home>_user_output_power_limit`
- `number.esc_<primary_home>_user_input_power_limit`

Ytterlegare attributt:

- `number.esc_<home>_favorable_threshold` viser òg `current_threshold_price`. Denne verdien er den nøyaktige straumprisgrensa for dagen, altså prisen opp til der ESC vurderer straum som gunstig.
- Prisattributt blir medvite ikkje reduserte til to desimalar, slik at utrekninga kan etterprøvast direkte i Home Assistant.

### Switch

- `switch.esc_<primary_home>_command_target_update`

## Teknisk logikk

### Pris og terskel

ESC hentar Tibber-prisar for **i dag og i morgon** og held prisattributta på berekningspresisjon i staden for å kutte dei til to desimalar.

Attributtet `current_threshold_price` på `number.esc_<home>_favorable_threshold` viser den eksakte dagsprisen opp til der ESC vurderer straum som gunstig.

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

Lading skjer berre når **gjeldande slot** ligg innanfor det gunstige prisområdet, altså når `price <= threshold_price`.

ESC reknar først ut kor mykje energi som manglar opp til maks SoC. Deretter planlegg ESC over **alle attverande gunstige 15-minuttsslotar på den relevante planleggingsdagen**. Så lenge det finst gunstige slotar i dag, blir i dag brukt; elles fell ESC tilbake på morgondagen.

For kvar gunstig slot reknar ESC først ut ein lineær prisfaktor mellom dagens minimumspris og terskelen:

```text
price_factor = (threshold_price - slot_price) / (threshold_price - min_price)
```

Det betyr:

- `min_price` → 100 % av tilgjengeleg ladeeffekt
- `threshold_price` → 0 % ladeeffekt
- prisar over terskelen blir ikkje brukte til lading

Deretter fordeler ESC nødvendig inngangsenergi greedy over dei gunstige slotane:

- billigaste slotar først
- ved lik pris blir seinare slotar prioriterte
- gjeldande slot får berre energi dersom dei billegare attverande slotane ikkje aleine dekkjer behovet, eller dersom gjeldande slot sjølv er mellom dei billegaste slotane som framleis trengst

Tildelinga til gjeldande slot blir `charge_power`. Dermed held ladinga seg strengt innanfor det gunstige området, samstundes som seinare og billegare slotar blir prioriterte.

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
- Lading er `0`: gjeldende slot er ikke gunstig, seinare billigare gunstige slotar dekkjer alt behovet, SoC på maks eller inputgrense `0`
- Utlading er `0`: for lav nettbalanse, SoC på minimum eller outputgrense `0`
