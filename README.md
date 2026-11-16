# Hakuchat

Paikallinen web-chat, jossa kielimalli (Nemotron OpenRouterin kautta) voi hakea
tietoa verkosta `web_search`-työkalulla. Haku tehdään DuckDuckGosta. Jos
DuckDuckGo ei vastaa tai ei löydä mitään, haetaan suomenkielisestä ja sitten
englanninkielisestä Wikipediasta.

## Vaatimukset

- Python 3.10 tai uudempi (kehitetty versiolla 3.14)
- `curl` (Linuxissa ja macOS:ssä yleensä valmiina)
- OpenRouter-tili ja API-avain: <https://openrouter.ai/keys>

## Asennus

```bash
git clone <repon-osoite> hakuchat
cd hakuchat

python3 -m venv .venv
source .venv/bin/activate
pip install openai flask
```

Jos käytät uv:tä, sama onnistuu komennolla `uv sync`.

## Ympäristömuuttujat

API-avainta ei kirjoiteta koodiin. Se annetaan ympäristömuuttujana:

```bash
export OPENROUTER_API_KEY="sk-or-..."
export NEMOTRON_MODEL="nvidia/nemotron-3.5-super-vl:free"
```

| Muuttuja | Pakollinen | Oletus |
|---|---|---|
| `OPENROUTER_API_KEY` | kyllä | – |
| `NEMOTRON_MODEL` | kyllä | – |
| `NEMOTRON_BASE_URL` | ei | `https://openrouter.ai/api/v1` |
| `PORT` | ei | `5000` |

Muuttujat voi tallentaa myös `.env`-tiedostoon ja ladata ennen käynnistystä
komennolla `set -a; source .env; set +a`. `.env` on `.gitignore`-tiedostossa,
joten avain ei päädy gittiin.

## Käynnistys

```bash
source .venv/bin/activate
python app.py
```

Avaa selaimessa <http://127.0.0.1:5000>. Palvelin kuuntelee vain omaa konetta
(`127.0.0.1`), joten muut verkon koneet eivät pääse käyttämään avaintasi.
Pysäytä palvelin näppäimillä Ctrl+C.

### Käyttö

- Kirjoita kysymys ja paina Enter tai Lähetä.
- Viestin yläpuolella näkyy, hakiko malli verkosta, millä hakusanalla ja mistä
  lähteestä (esim. `🔍 Haku: "WSL2 docker" – DuckDuckGo, 5 tulosta`).
- Vastauksen linkit ovat klikattavia.
- Keskustelu muistetaan selainvälilehden ajan, joten voit jatkaa
  esimerkiksi kysymällä "Etsi vielä suomenkielisiä". Uusi keskustelu -painike
  tyhjentää historian.

## Osien testaus komentoriviltä

```bash
python search.py "WSL2 docker" 5        # pelkkä haku, tulostaa JSONin
python chat_core.py "Mikä on WSL2?"      # yksi kysymys mallille
python chat_core.py                      # keskustelu terminaalissa
```

## Vianetsintä

- **`Aseta ympäristömuuttuja OPENROUTER_API_KEY`**: avainta ei ole asetettu
  siinä terminaalissa, jossa palvelin käynnistettiin.
- **`KeyError: 'NEMOTRON_MODEL'`**: mallin nimi puuttuu.
- **401**: API-avain on väärä.
- **429**: ilmaisen mallin käyttöraja on täynnä. Virheilmoitus kertoo, milloin
  raja nollautuu.
- **Haku palauttaa Wikipedia-tuloksia DuckDuckGon sijaan**: DuckDuckGo
  estää välillä automaattiset haut (CAPTCHA). Silloin käytetään Wikipediaa.

## Tiedostot

| Tiedosto | Sisältö |
|---|---|
| `app.py` | Flask-palvelin: `index.html` ja `POST /api/chat` |
| `chat_core.py` | Mallikutsut ja työkalusilmukka (enintään 5 kierrosta) |
| `search.py` | Haku curlilla: DuckDuckGo → Wikipedia fi → Wikipedia en |
| `index.html` | Käyttöliittymä ilman kehyksiä |
| `weather.py` | Alkuperäinen työkalukutsuesimerkki |

## Tool use -silmukan selitys
- Rivit 139–141: Luodaan asiakas ja valitaan malli. Funktiolle voi myös antaa ne parametreina, mikä helpottaa testaamista. `searches` kerää tehdyt haut käyttöliittymää varten.
- Silmukka rivi 143: Silmukka kiertää enintään 6 kertaa: viisi kierrosta, joilla saa hakea, ja yksi viimeinen, jolla on pakko vastata tekstinä.
- Rivit 144–147: Malli ei muista mitään. Siksi jokaisella kierroksella lähetetään koko keskustelu: system-prompt ja kaikki aikaisemmat viestit. Viimeisellä kierroksella loppuun lisätään käsky vastata.
- Rivit 148–155: `tools` kertoo mallille, että `web_search` on käytettävissä. `tool_choice` määrää, miten sitä saa käyttää:

"auto": malli päättää itse, hakeeko vai vastaako.
"none": työkalua ei saa käyttää, malli vastaa tekstinä.

Malli palauttaa joko tekstiä `msg.content` tai pyynnön työkalukutsusta `msg.tool_calls`.

- Rivit 157-163: Jos malli ei pyytänyt työkalua tai kierrokset loppuivat, vastaus siivotaan, tallennetaan historiaan ja palautetaan.
Rivit 165-169: Mallin pyyntö tallennetaan historiaan. Jokainen pyydetty kutsu suoritetaan. Malli voi pyytää useaa hakua kerralla.
Tulos lisätään historiaan `tool`-roolilla. `tool_call_id` kertoo, mihin pyyntöön tulos vastaa. Sen jälkeen silmukka palaa alkuun, ja malli saa seuraavalla kierroksella nähdä hakutulokset.
Rivi 171: Tänne ei koskaan pitäisi päästä. Rivin tarkoituksena on olla varmistuksena jos jokin rikkoutuu.