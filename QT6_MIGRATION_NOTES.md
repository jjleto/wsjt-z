# Diario di migrazione Qt6 — wsjt-z (fork SpudGunMan/wsjt-z, branch spud)

Riferimento completo delle modifiche necessarie per portare wsjt-z da Qt5 a Qt6 su macOS (Apple Silicon, Homebrew). Utile sia come documentazione sia come checklist se il porting va ripetuto su un fork/branch diverso.

---

## 0. Prerequisiti di sistema

```bash
brew install qtbase qtserialport qtmultimedia qtwebsockets qttools
brew install asciidoc          # per le man page (o usa -DWSJT_SKIP_MANPAGES=ON)
```

**Hamlib**: serve una versione recente (usata: **4.7.1/4.7.2**) compilata da sorgente — la versione stabile di Homebrew è troppo vecchia e non ha l'API ABI-stable richiesta dal codice (`rig_get_caps_int`, `rig_get_caps_cptr`, `rig_list_foreach_model`, ecc.).

```bash
git clone https://github.com/Hamlib/Hamlib.git
cd Hamlib && ./bootstrap && ./configure --prefix=/opt/homebrew/opt/hamlib-471
make -j$(sysctl -n hw.ncpu) && sudo make install
```

**QCustomPlot**: la copia embedded nel repo (`qcustomplot-source/`) va aggiornata a **2.1.1+** (supporto Qt6 ufficiale). Copiare `qcustomplot.h`/`.cpp` da una release 2.1.1 o da un fork Qt6-ready (es. wsjt-x_improved) sopra i file esistenti.

---

## 1. CMakeLists.txt principale

| Cosa | Prima (Qt5) | Dopo (Qt6) |
|---|---|---|
| find_package | `find_package (Qt5 COMPONENTS ...)` | `find_package (Qt6 COMPONENTS ...)` |
| AxContainer (Win) | `find_package (Qt5AxContainer REQUIRED)` | `find_package (Qt6 REQUIRED COMPONENTS AxContainer AxServer)` |
| Standard C++ | (nessuno, default vecchio) | aggiungere `set (CMAKE_CXX_STANDARD 17)` + `set (CMAKE_CXX_STANDARD_REQUIRED ON)` |
| qmake/lconvert | `Qt5::qmake`, `Qt5::lconvert` | `Qt6::qmake`, `Qt6::lconvert` |
| target_link_libraries | ogni `Qt5::Xxx` | `Qt6::Xxx` (sed globale) |
| AxBase (Win) | `Qt5::AxBase` | `Qt6::AxServer` (non è un semplice rename!) |
| Comandi traduzione | `qt5_add_translation`, `qt5_create_translation` | `qt6_add_translation`, `qt6_create_translation` |
| UI/risorse | `qt5_wrap_ui`, `qt5_add_resources` | `qt6_wrap_ui`, `qt6_add_resources` |
| Deprecazioni | `-Werror` blocca tutto | aggiungere `add_compile_options ($<$<COMPILE_LANGUAGE:CXX>:-Wno-error=deprecated-declarations>)` — **risparmia decine di fix singoli** |
| MinGW (opzionale) | — | `if(MINGW) add_compile_options(...-Wa,-mbig-obj) add_link_options(-Wa,-mbig-obj) endif()` |

File satellite con lo stesso pattern `Qt5::`/`qt5_*` da sistemare: `tests/CMakeLists.txt`, `qmap/CMakeLists.txt`, `qmap/libqmap/CMakeLists.txt`, `bundle_fixup/CMakeLists.txt`, `map65/CMakeLists.txt`, `map65/libm65/CMakeLists.txt`.

---

## 2. Errori di compilazione C++ — catalogo per categoria

### QRegExp → QRegularExpression
Rimossa completamente in Qt6. Da sostituire ovunque, con attenzione a:
- `QRegExpValidator` → `QRegularExpressionValidator`
- Se la classe **eredita** da `QRegExpValidator`, va cambiata anche la base class, non solo l'include
- `QStringList::indexOf(QRegExp, from)` / `lastIndexOf` non hanno equivalente diretto con `QRegularExpression` → riscrivere con ciclo esplicito e `re.match(x).hasMatch()`

File coinvolti in questo porting: `Radio.cpp`, `widgets/mainwindow.cpp`, `widgets/displaytext.cpp`, `Network/wsprnet.cpp`, `UDPExamples/ClientWidget.cpp`, `Transceiver/HRDTransceiver.cpp/.hpp`, `validators/LiveFrequencyValidator.hpp/.cpp`, `GetUserId.cpp`, `item_delegates/MessageItemDelegate.cpp`.

### qRegisterMetaTypeStreamOperators — rimossa in Qt6
Qt6 rileva automaticamente gli stream operator custom (nessuna registrazione esplicita necessaria) — **ma solo se il tipo ha davvero un `operator<<`/`operator>>` scritto a mano**. Per i tipi struct complessi (liste di frequenze, stazioni, palette colori) probabilmente non serve fare altro. Per gli **enum semplici** (senza operator custom), la registrazione andava a un meccanismo generico che in Qt6 non esiste più: la soluzione robusta è **salvare/leggere da QSettings come `int` esplicito** (`static_cast<int>(...)` / `.toInt()`), non affidarsi a `QVariant::fromValue`/`.value<T>()`.

⚠️ **Bug runtime scoperto**: se un enum come questo viene letto "sporco" da preferenze salvate con la vecchia serializzazione, `QButtonGroup::button(id)` può restituire `nullptr` → crash su `setChecked()`. Fix difensivo raccomandato ovunque: `if (auto * btn = group->button(id)) btn->setChecked(true);` invece di incatenare `->setChecked()` senza controllo.

### QAudioFormat (setup manuale, ricorre in più file)
```cpp
// Qt5
format.setCodec ("audio/pcm");           // RIMUOVERE (PCM implicito)
format.setSampleType (QAudioFormat::SignedInt);
format.setSampleSize (16);
format.setByteOrder (QAudioFormat::Endian (QSysInfo::ByteOrder));  // RIMUOVERE (native-endian implicito)
// Qt6
format.setSampleFormat (QAudioFormat::Int16);   // sostituisce le due righe sopra
```
Se serve tracciare il byte-order originale (es. per file WAV/BWF con dati non-nativi), aggiungere un membro custom (es. `bool big_endian_`) perché `QAudioFormat` non lo espone più.

### QtMultimedia — rinominazioni di classi
| Qt5 | Qt6 |
|---|---|
| `QAudioDeviceInfo` | `QAudioDevice` |
| `QAudioInput` (stream) | `QAudioSource` |
| `QAudioOutput` (stream) | `QAudioSink` |
| `QAudioDeviceInfo::availableDevices(QAudio::Mode)` | `QMediaDevices::audioInputs()` / `audioOutputs()` |
| `device.deviceName()` | `device.description()` |
| `QAudio::Mode`, `QAudio::AudioInput/Output` | `QAudioDevice::Mode`, `QAudioDevice::Input/Output` |
| `device.supportedChannelCounts()` | rimosso — usare una lista fissa `{1,2}` se l'app usa solo mono/stereo |

API rimosse senza sostituto diretto (semplicemente eliminare le chiamate): `setNotifyInterval()`, segnale `notify()`, `setCategory()` (specifico PulseAudio/Linux), `QAudio::InterruptedState` (va tolto dall'enum o va ristretto il blocco `#if QT_VERSION ... < QT_VERSION_CHECK(6,0,0)`).

⚠️ **Bug runtime sottile — QIODevice sequenziale in modalità push**: se una classe (es. un generatore di toni tipo `Modulator`) sovrascrive `isSequential() → true` ma **non sovrascrive `bytesAvailable()`**, in Qt6 `QAudioSink::start(QIODevice*)` può decidere di non chiamare mai `readData()` (perché il default di `bytesAvailable()` è 0) e fermarsi silenziosamente, senza errore. Fix:
```cpp
qint64 bytesAvailable () const override {return std::numeric_limits<qint64>::max ();}
```

### Qt::AlignXxx + Qt::AlignYyy → operatore `|`
L'operatore `+` tra flag è stato **eliminato di proposito** in Qt6 (era un uso improprio). Sostituire con `|`. Se il risultato va assegnato a un `QVariant` (tipico in `data()` di modelli item), serve anche un cast esplicito:
```cpp
item = int (Qt::AlignHCenter | Qt::AlignVCenter);   // non solo "|", anche il cast
```

### Narrowing qsizetype → int
`QString::size()`/`count()` restituiscono `qsizetype` (64-bit) in Qt6. Negli initializer-list con parentesi graffe (`int x {expr};`), il narrowing implicito è un errore. Aggiungere `int (...)` esplicito attorno all'espressione.

### Altre deprecazioni/rimozioni puntuali incontrate
- `QDateTime::fromTime_t()` → `fromSecsSinceEpoch()`
- `QLocale::countryToString()`/`.country()` → `territoryToString()`/`.territory()`
- `QSortFilterProxyModel::invalidateFilter()` → deprecato (Qt 6.13+), lasciato passare con il flag `-Wno-error=deprecated-declarations` globale
- `QStandardPaths::DataLocation` → `AppLocalDataLocation`
- `Qt::ItemIsTristate` → `Qt::ItemIsAutoTristate`
- `QFormLayout::setMargin(n)` → `setContentsMargins(n,n,n,n)`
- `QNetworkRequest::FollowRedirectsAttribute` → `setAttribute(RedirectPolicyAttribute, NoLessSafeRedirectPolicy)`
- `enterEvent(QEvent*)` → firma cambiata a `enterEvent(QEnterEvent*)`
- `QFile::open()` ora `[[nodiscard]]` → avvolgere con `(void)` se il valore di ritorno non serve
- `std::random_shuffle` (rimosso da C++17) → `std::shuffle(..., std::mt19937{std::random_device{}()})`
- Switch su `QFont::Weight` non esaustivo (Qt6 ha aggiunto Thin/ExtraLight/Medium/...) → aggiungere `default:`
- `QAbstractItemModel`/enum salvati come `QVariant` con operator+ → stessa storia di Qt::Align sopra

---

## 3. Bug runtime scoperti dopo la compilazione

1. **Crash all'avvio in `Configuration::impl::initialize_models()`** su `button(id)->setChecked()` — causato da un valore enum "sporco" letto da `QSettings` (vedi punto qRegisterMetaTypeStreamOperators sopra). Fix: cast a int in lettura/scrittura + guardia `if (auto* btn = ...)`.

2. **Crash in `CPlotter::draw()`** su `g_ColorTbl[y1]` — la palette colori (`WFPalette`) può fallire silenziosamente nel caricamento (il blocco `catch` mostrava solo un warning ma non impostava un fallback), lasciando `g_ColorTbl` vuota. Fix doppio: (a) fallback esplicito nel `catch` di `WideGraph::readPalette()`, (b) guardia `y1 < g_ColorTbl.size()` prima dell'accesso in `CPlotter::draw()`.

3. **Nessun audio in trasmissione** — vedi il bug `bytesAvailable()` sopra. Diagnosticato con `fprintf(stderr, ...)` diretti (i normali `qDebug()` erano intercettati da un message handler custom basato su boost::log e non comparivano in console).

---

## 4. Bundle macOS (.app) — fixup_bundle

- **`CMAKE_BUILD_TYPE` deve essere esattamente `Release`** (case-sensitive!) — se è `RELEASE` (maiuscolo), le regole `install(... CONFIGURATIONS Release ...)` vengono saltate silenziosamente, e i plugin non vengono copiati nel bundle.
- **I plugin Qt6 di Homebrew sono symlink relativi** (es. `libqgif.dylib -> ../../../../Cellar/qtbase/.../libqgif.dylib`). `install(DIRECTORY/FILES ...)` li copia "così come sono", risultando in link rotti una volta spostati dentro il bundle (percorso relativo non più valido). Fix: sostituire `install(DIRECTORY ...)` con `install(CODE "file(COPY ... FOLLOW_SYMLINK_CHAIN ...)")`, che risolve la catena di symlink copiando il file reale.
- **`otool -l failed`** nell'errore di `fixup_bundle` è quasi sempre sintomo di questo problema di symlink rotti, non di plugin realmente mancanti.

---

## 5. Metodo di lavoro consigliato per ripetere il porting

1. Prima passata: `find_package`, target_link_libraries, standard C++17 → arrivare a un errore di compilazione.
2. Aggiungere subito `-Wno-error=deprecated-declarations` per non perdere tempo su ogni singola deprecazione — occuparsi solo degli errori "duri" (API rimosse, non solo deprecate).
3. Compilare iterativamente: un errore alla volta, category by category (spesso lo stesso errore si ripete identico in molti file — conviene fare `grep -rn` del pattern e sistemarli tutti insieme prima di ricompilare).
4. Una volta compilato: testare a runtime con `lldb` per i crash, e log `fprintf(stderr,...)` mirati se `qDebug()` non è visibile (message handler custom).
5. Solo alla fine: sistemare il bundle/packaging (`CMAKE_BUILD_TYPE`, symlink dei plugin).

---

## 6. Git — mettere in sicurezza il lavoro e gestire aggiornamenti upstream

**Appena finito il porting, committa subito** (`git add -A && git commit -m "..."`) — ma **prima** crea un `.gitignore` adeguato, altrimenti il commit si porta dietro l'intera cartella `build/` (centinaia di MB di artefatti CMake/moc), eventuali cartelle di bundle `stage/`, `.DS_Store`, e tutti i file `.bak-*` creati durante il debug:

```gitignore
# Build artifacts
/build/
/stage/

# macOS
.DS_Store

# File di backup creati durante il porting Qt6
*.bak-qt5
*.bak-debug
*.bak-conflict
*.bak-manual
*.bak-v2

# Log di build
*.log
```

Se te ne accorgi *dopo* aver già committato, ripulisci con un commit successivo (non serve riscrivere la history):
```bash
git rm -r --cached build stage
git rm --cached *.bak-* 2>/dev/null
git add .gitignore
git commit -m "Rimuovi artefatti di build dal repository"
```

**Quando il repository upstream (`sq9fve/wsjt-z`, branch `spud` via `SpudGunMan`) riceve nuovi commit:**

```bash
git fetch origin
git log HEAD..origin/spud --oneline   # vedi cosa arriva, prima di toccare nulla
git rebase origin/spud
```

Se emergono conflitti, Git si ferma commit per commit. Procedura standard per ciascuno:
```bash
grep -n "<<<<<<<\|=======\|>>>>>>>" <file-in-conflitto>
# guarda il contesto, decidi (tieni HEAD/upstream, tieni il tuo, o unisci)
# risolvi manualmente o con un piccolo script python che sostituisce il blocco esatto
git add <file-risolto>
git rebase --continue   # potrebbe aprire l'editor per il messaggio di commit: Esc, :wq, Invio
```

Nel nostro caso i conflitti erano quasi sempre banali: numeri di versione (`VERSION_Z`) bumpati da vecchi commit locali (basta tenere il valore più recente/HEAD), o una feature UDP arricchita in parallelo sia da noi che da upstream (spesso si possono unire entrambe le versioni).

⚠️ **Trappola scoperta sul campo: un `git rebase --continue` può "risolvere" un conflitto lasciando i marcatori `<<<<<<<`/`=======`/`>>>>>>>` scritti letteralmente nel file**, se il passaggio precedente non è stato ripulito del tutto prima del `git add`. Questo non dà errore al momento del commit — emerge solo dopo, come errore di parsing CMake o come dichiarazione duplicata in C++. **Dopo ogni rebase con conflitti, esegui sempre una scansione completa del repository**, non fidarti del solo file su cui hai lavorato:
```bash
grep -rn "<<<<<<<\|^=======$\|>>>>>>>" --include="*.cpp" --include="*.hpp" --include="*.h" --include="*.txt" . | grep -v build
```

Dopo un rebase, **ricompila sempre da zero** (`rm -rf build`) e testa a runtime tutte le funzionalità principali (waterfall, decodifica, PTT, audio TX) — un rebase può reintrodurre silenziosamente codice Qt5 se un conflitto viene risolto scegliendo la versione sbagliata.

---

## 7. Bug aggiuntivi scoperti dopo il rebase (non presenti nel porting originale)

### `QComboBox::activated(const QString&)` rimosso in Qt6
Qt5 aveva due overload del segnale `activated`: `activated(int)` e `activated(const QString&)`. Il meccanismo di **auto-connessione per nome** di Qt (`on_<oggetto>_<segnale>`, senza bisogno di `connect()` esplicito) si affidava all'overload `QString` per gli slot con quella firma. **Qt6 ha rimosso l'overload `QString`** — resta solo `activated(int index)`. Se uno slot `on_xxxComboBox_activated(QString const&)` esisteva nel codice Qt5, l'auto-connessione ora fallisce **silenziosamente** (nessun errore di compilazione, solo un warning runtime spesso filtrato da logger custom) e il combo box smette di funzionare.

Fix:
```cpp
// Qt5
void MyClass::on_myComboBox_activated (QString const& text) { ... }
// Qt6
void MyClass::on_myComboBox_activated (int index)
{
  auto text = ui->myComboBox->itemText (index);
  ...
}
```
(cambiare la firma anche nell'header/dichiarazione dello slot)

**Come diagnosticarlo:** se un controllo UI smette di reagire senza errori né crash, e la firma dello slot coinvolto prende una `QString` da un segnale `activated`/`currentIndexChanged`/simili, sospetta subito questo pattern — è silenzioso e facile da perdere.

### Rendering nativo macOS di `QSlider` con `invertedAppearance` cambiato tra Qt5/Qt6
Uno slider verticale con `invertedAppearance="true"` (per far salire il valore verso l'alto invece che verso il basso) può risultare con il riempimento colorato (blu/grigio) **invertito** rispetto a Qt5, perché `QMacStyle` in Qt6 disegna i controlli nativi macOS (`NSSlider`) in modo leggermente diverso. Non è un bug del codice, è un cambiamento di comportamento del tema nativo.

Fix più affidabile: **forzare uno stylesheet Qt esplicito** sul widget, bypassando il rendering nativo:
```css
QSlider::groove:vertical { background: #b0b0b0; width: 6px; border-radius: 3px; }
QSlider::handle:vertical { background: white; border: 1px solid #5c5c5c; height: 16px; margin: 0 -8px; border-radius: 8px; }
QSlider::sub-page:vertical { background: #b0b0b0; border-radius: 3px; }   /* verso il minimo */
QSlider::add-page:vertical { background: #2f7fd6; border-radius: 3px; }   /* verso il massimo */
```
Se il risultato appare ancora invertito rispetto a quanto voluto, scambia semplicemente i colori tra `sub-page` e `add-page` (dipende dalla combinazione di `orientation`/`invertedAppearance`/`invertedControls` del widget specifico — più semplice provare empiricamente che calcolare a priori).

---

## 8. `CMAKE_PREFIX_PATH` — Homebrew keg-only e percorso "ombrello"

Passare i singoli prefix keg-only di ogni modulo Qt6 (`/opt/homebrew/opt/qtbase;/opt/homebrew/opt/qtserialport;...`) ha funzionato per settimane, poi **ha smesso di funzionare da un giorno all'altro** (in particolare, `find_package` non trovava più `Qt6SerialPort`, pur essendo il pacchetto installato e aggiornato). Causa sospetta: un cambiamento in come Homebrew organizza/linka i file CMake di alcuni moduli tra un aggiornamento e l'altro.

**Soluzione più robusta**: usare il prefix "ombrello" di Homebrew invece dei singoli percorsi `opt/<formula>`:
```bash
# Invece di:
-DCMAKE_PREFIX_PATH="/opt/homebrew/opt/qtbase;/opt/homebrew/opt/qtserialport;/opt/homebrew/opt/qtmultimedia;/opt/homebrew/opt/qtwebsockets;/opt/homebrew/opt/qttools;/opt/homebrew/opt/hamlib-471"

# Usa:
-DCMAKE_PREFIX_PATH="/opt/homebrew;/opt/homebrew/opt/hamlib-471"
```
Il percorso singolo `/opt/homebrew` attraversa i link simbolici centralizzati di Homebrew e trova comunque tutti i moduli Qt6, in modo più resiliente ai cambi di struttura interna di una singola formula.

**Nota su `sudo` e permessi**: ogni `sudo cmake --build . --target install` lascia alcuni file dentro `build/CMakeFiles/git-data/` di proprietà di `root`. Se poi si tenta di ricompilare **senza** `sudo`, si ottiene un errore criptico tipo `Operation not permitted` sul target `revisiontag` (che tenta di aggiornare l'hash Git). Soluzione più semplice: **non riusare mai una cartella `build/` che ha visto un `sudo`** — cancellarla e ricrearla da zero (`rm -rf build && mkdir build`) prima della prossima compilazione normale.

---

*Compilato durante il porting di wsjt-z (branch spud) a Qt6 su macOS Apple Silicon, luglio 2026.*
