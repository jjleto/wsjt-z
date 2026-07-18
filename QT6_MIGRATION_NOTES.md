# Qt6 Migration Notes — wsjt-z (SpudGunMan/wsjt-z fork, spud branch)

Complete reference of the changes needed to port wsjt-z from Qt5 to Qt6 on macOS (Apple Silicon, Homebrew). Useful both as documentation and as a checklist if the port needs to be repeated on a different fork/branch.

---

## 0. System prerequisites

```bash
brew install qtbase qtserialport qtmultimedia qtwebsockets qttools
brew install asciidoc          # for man pages (or use -DWSJT_SKIP_MANPAGES=ON)
```

**Hamlib**: a recent version is required (used here: **4.7.1/4.7.2**), built from source — Homebrew's stable release is too old and lacks the ABI-stable API the code requires (`rig_get_caps_int`, `rig_get_caps_cptr`, `rig_list_foreach_model`, etc.).

```bash
git clone https://github.com/Hamlib/Hamlib.git
cd Hamlib && ./bootstrap && ./configure --prefix=/opt/homebrew/opt/hamlib-471
make -j$(sysctl -n hw.ncpu) && sudo make install
```

**QCustomPlot**: the embedded copy in the repo (`qcustomplot-source/`) needs to be updated to **2.1.1+** (official Qt6 support). Copy `qcustomplot.h`/`.cpp` from a 2.1.1 release, or from a Qt6-ready fork (e.g. wsjt-x_improved), over the existing files.

---

## 1. Main CMakeLists.txt

| What | Before (Qt5) | After (Qt6) |
|---|---|---|
| find_package | `find_package (Qt5 COMPONENTS ...)` | `find_package (Qt6 COMPONENTS ...)` |
| AxContainer (Win) | `find_package (Qt5AxContainer REQUIRED)` | `find_package (Qt6 REQUIRED COMPONENTS AxContainer AxServer)` |
| C++ standard | (none, old default) | add `set (CMAKE_CXX_STANDARD 17)` + `set (CMAKE_CXX_STANDARD_REQUIRED ON)` |
| qmake/lconvert | `Qt5::qmake`, `Qt5::lconvert` | `Qt6::qmake`, `Qt6::lconvert` |
| target_link_libraries | every `Qt5::Xxx` | `Qt6::Xxx` (global sed) |
| AxBase (Win) | `Qt5::AxBase` | `Qt6::AxServer` (not a simple rename!) |
| Translation commands | `qt5_add_translation`, `qt5_create_translation` | `qt6_add_translation`, `qt6_create_translation` |
| UI/resources | `qt5_wrap_ui`, `qt5_add_resources` | `qt6_wrap_ui`, `qt6_add_resources` |
| Deprecations | `-Werror` blocks everything | add `add_compile_options ($<$<COMPILE_LANGUAGE:CXX>:-Wno-error=deprecated-declarations>)` — **saves dozens of individual fixes** |
| MinGW (optional) | — | `if(MINGW) add_compile_options(...-Wa,-mbig-obj) add_link_options(-Wa,-mbig-obj) endif()` |

Satellite files with the same `Qt5::`/`qt5_*` pattern to fix: `tests/CMakeLists.txt`, `qmap/CMakeLists.txt`, `qmap/libqmap/CMakeLists.txt`, `bundle_fixup/CMakeLists.txt`, `map65/CMakeLists.txt`, `map65/libm65/CMakeLists.txt`.

---

## 2. C++ compilation errors — catalog by category

### QRegExp → QRegularExpression
Completely removed in Qt6. Needs replacing everywhere, watch out for:
- `QRegExpValidator` → `QRegularExpressionValidator`
- If a class **inherits** from `QRegExpValidator`, the base class needs changing too, not just the include
- `QStringList::indexOf(QRegExp, from)` / `lastIndexOf` have no direct equivalent with `QRegularExpression` → rewrite with an explicit loop and `re.match(x).hasMatch()`

Files involved in this port: `Radio.cpp`, `widgets/mainwindow.cpp`, `widgets/displaytext.cpp`, `Network/wsprnet.cpp`, `UDPExamples/ClientWidget.cpp`, `Transceiver/HRDTransceiver.cpp/.hpp`, `validators/LiveFrequencyValidator.hpp/.cpp`, `GetUserId.cpp`, `item_delegates/MessageItemDelegate.cpp`.

### qRegisterMetaTypeStreamOperators — removed in Qt6
Qt6 automatically detects custom stream operators (no explicit registration needed) — **but only if the type actually has a hand-written `operator<<`/`operator>>`**. For complex struct types (frequency lists, station lists, color palettes) nothing else is likely needed. For **plain enums** (with no custom operator), registration used to hook into a generic mechanism that no longer exists in Qt6: the robust fix is to **save/read from QSettings as an explicit `int`** (`static_cast<int>(...)` / `.toInt()`), rather than relying on `QVariant::fromValue`/`.value<T>()`.

⚠️ **Runtime bug discovered**: if such an enum is read back "dirty" from preferences saved with the old serialization, `QButtonGroup::button(id)` can return `nullptr` → crash on `setChecked()`. Recommended defensive fix everywhere: `if (auto * btn = group->button(id)) btn->setChecked(true);` instead of chaining `->setChecked()` without a check.

### QAudioFormat (manual setup, recurring in several files)
```cpp
// Qt5
format.setCodec ("audio/pcm");           // REMOVE (PCM is now implicit)
format.setSampleType (QAudioFormat::SignedInt);
format.setSampleSize (16);
format.setByteOrder (QAudioFormat::Endian (QSysInfo::ByteOrder));  // REMOVE (native-endian is now implicit)
// Qt6
format.setSampleFormat (QAudioFormat::Int16);   // replaces the two lines above
```
If you need to track the original byte order (e.g. for WAV/BWF files with non-native data), add a custom member (e.g. `bool big_endian_`) since `QAudioFormat` no longer exposes it.

### QtMultimedia — class renames
| Qt5 | Qt6 |
|---|---|
| `QAudioDeviceInfo` | `QAudioDevice` |
| `QAudioInput` (stream) | `QAudioSource` |
| `QAudioOutput` (stream) | `QAudioSink` |
| `QAudioDeviceInfo::availableDevices(QAudio::Mode)` | `QMediaDevices::audioInputs()` / `audioOutputs()` |
| `device.deviceName()` | `device.description()` |
| `QAudio::Mode`, `QAudio::AudioInput/Output` | `QAudioDevice::Mode`, `QAudioDevice::Input/Output` |
| `device.supportedChannelCounts()` | removed — use a fixed list `{1,2}` if the app only uses mono/stereo |

APIs removed with no direct replacement (simply delete the calls): `setNotifyInterval()`, the `notify()` signal, `setCategory()` (PulseAudio/Linux-specific), `QAudio::InterruptedState` (either remove it from the enum handling or narrow the `#if QT_VERSION ... < QT_VERSION_CHECK(6,0,0)` block).

⚠️ **Subtle runtime bug — sequential QIODevice in push mode**: if a class (e.g. a tone-generator like `Modulator`) overrides `isSequential() → true` but **does not override `bytesAvailable()`**, in Qt6 `QAudioSink::start(QIODevice*)` may decide never to call `readData()` (because the default `bytesAvailable()` is 0) and silently stop, with no error. Fix:
```cpp
qint64 bytesAvailable () const override {return std::numeric_limits<qint64>::max ();}
```

### Qt::AlignXxx + Qt::AlignYyy → `|` operator
The `+` operator between flags was **deliberately removed** in Qt6 (it was a misuse). Replace with `|`. If the result is assigned to a `QVariant` (typical in item model `data()`), an explicit cast is also needed:
```cpp
item = int (Qt::AlignHCenter | Qt::AlignVCenter);   // not just "|", also the cast
```

### Narrowing qsizetype → int
`QString::size()`/`count()` return `qsizetype` (64-bit) in Qt6. In brace-initializer lists (`int x {expr};`), the implicit narrowing is an error. Add an explicit `int (...)` cast around the expression.

### Other point deprecations/removals encountered
- `QDateTime::fromTime_t()` → `fromSecsSinceEpoch()`
- `QLocale::countryToString()`/`.country()` → `territoryToString()`/`.territory()`
- `QSortFilterProxyModel::invalidateFilter()` → deprecated (Qt 6.13+), left as-is via the global `-Wno-error=deprecated-declarations` flag
- `QStandardPaths::DataLocation` → `AppLocalDataLocation`
- `Qt::ItemIsTristate` → `Qt::ItemIsAutoTristate`
- `QFormLayout::setMargin(n)` → `setContentsMargins(n,n,n,n)`
- `QNetworkRequest::FollowRedirectsAttribute` → `setAttribute(RedirectPolicyAttribute, NoLessSafeRedirectPolicy)`
- `enterEvent(QEvent*)` → signature changed to `enterEvent(QEnterEvent*)`
- `QFile::open()` is now `[[nodiscard]]` → wrap with `(void)` if the return value isn't used
- `std::random_shuffle` (removed in C++17) → `std::shuffle(..., std::mt19937{std::random_device{}()})`
- Non-exhaustive switch on `QFont::Weight` (Qt6 added Thin/ExtraLight/Medium/...) → add a `default:` case
- `QAbstractItemModel`/enums saved as `QVariant` with `operator+` → same story as Qt::Align above

---

## 3. Runtime bugs discovered after compilation succeeded

1. **Startup crash in `Configuration::impl::initialize_models()`** on `button(id)->setChecked()` — caused by a "dirty" enum value read from `QSettings` (see the qRegisterMetaTypeStreamOperators note above). Fix: cast to int on read/write + guard with `if (auto* btn = ...)`.

2. **Crash in `CPlotter::draw()`** on `g_ColorTbl[y1]` — the color palette (`WFPalette`) can silently fail to load (the `catch` block only showed a warning but never set a fallback), leaving `g_ColorTbl` empty. Two-part fix: (a) an explicit fallback in `WideGraph::readPalette()`'s `catch` block, (b) a `y1 < g_ColorTbl.size()` guard before the access in `CPlotter::draw()`.

3. **No audio on transmit** — see the `bytesAvailable()` bug above. Diagnosed with direct `fprintf(stderr, ...)` calls (normal `qDebug()` output was being intercepted by a custom boost::log-based message handler and never showed up in the console).

---

## 4. macOS bundle (.app) — fixup_bundle

- **`CMAKE_BUILD_TYPE` must be exactly `Release`** (case-sensitive!) — if it's `RELEASE` (all caps), the `install(... CONFIGURATIONS Release ...)` rules are silently skipped, and plugins never get copied into the bundle.
- **Homebrew's Qt6 plugins are relative symlinks** (e.g. `libqgif.dylib -> ../../../../Cellar/qtbase/.../libqgif.dylib`). `install(DIRECTORY/FILES ...)` copies them "as-is," which results in broken links once moved inside the bundle (the relative path no longer resolves). Fix: replace `install(DIRECTORY ...)` with `install(CODE "file(COPY ... FOLLOW_SYMLINK_CHAIN ...)")`, which resolves the symlink chain by copying the real file.
- **`otool -l failed`** in the `fixup_bundle` error is almost always a symptom of this broken-symlink issue, not of genuinely missing plugins.

---

## 5. Recommended workflow for repeating this port

1. First pass: `find_package`, target_link_libraries, C++17 standard → get to a compilation error.
2. Immediately add `-Wno-error=deprecated-declarations` to avoid wasting time on every single deprecation — deal only with the "hard" errors (removed APIs, not merely deprecated ones).
3. Compile iteratively: one error at a time, category by category (the same error often repeats identically across many files — it's worth doing a `grep -rn` for the pattern and fixing them all together before recompiling).
4. Once it compiles: test at runtime with `lldb` for crashes, and targeted `fprintf(stderr,...)` logging if `qDebug()` isn't visible (custom message handler).
5. Only at the end: fix up the bundle/packaging (`CMAKE_BUILD_TYPE`, plugin symlinks).

---

## 6. Git — securing the work and handling upstream updates

**As soon as the port is done, commit right away** (`git add -A && git commit -m "..."`) — but **first** create a proper `.gitignore`, otherwise the commit drags along the entire `build/` directory (hundreds of MB of CMake/moc artifacts), any `stage/` bundle folders, `.DS_Store`, and all the `.bak-*` files created during debugging:

```gitignore
# Build artifacts
/build/
/stage/

# macOS
.DS_Store

# Backup files created during the Qt6 port
*.bak-qt5
*.bak-debug
*.bak-conflict
*.bak-manual
*.bak-v2

# Build logs
*.log
```

If you notice this *after* already committing, clean it up with a follow-up commit (no need to rewrite history):
```bash
git rm -r --cached build stage
git rm --cached *.bak-* 2>/dev/null
git add .gitignore
git commit -m "Remove build artifacts from the repository"
```

**When the upstream repository (`sq9fve/wsjt-z`, `spud` branch via `SpudGunMan`) receives new commits:**

```bash
git fetch origin
git log HEAD..origin/spud --oneline   # see what's coming in before touching anything
git rebase origin/spud
```

If conflicts come up, Git stops commit by commit. Standard procedure for each one:
```bash
grep -n "<<<<<<<\|=======\|>>>>>>>" <conflicting-file>
# look at the context, decide (keep HEAD/upstream, keep yours, or merge both)
# resolve manually or with a small python script that replaces the exact block
git add <resolved-file>
git rebase --continue   # may open an editor for the commit message: Esc, :wq, Enter
```

In our case the conflicts were almost always trivial: version numbers (`VERSION_Z`) bumped by old local commits (just keep the newer/HEAD value), or a UDP feature enriched in parallel both by us and upstream (often both versions can be merged).

⚠️ **Trap discovered in the field: a `git rebase --continue` can "resolve" a conflict while leaving the `<<<<<<<`/`=======`/`>>>>>>>` markers literally written into the file**, if the previous step wasn't fully cleaned up before the `git add`. This doesn't produce an error at commit time — it only surfaces later, as a CMake parse error or a duplicate declaration in C++. **After every rebase involving conflicts, always run a full repository scan**, don't just trust the one file you were working on:
```bash
grep -rn "<<<<<<<\|^=======$\|>>>>>>>" --include="*.cpp" --include="*.hpp" --include="*.h" --include="*.txt" . | grep -v build
```

After a rebase, **always rebuild from scratch** (`rm -rf build`) and test all the main functionality at runtime (waterfall, decoding, PTT, TX audio) — a rebase can silently reintroduce Qt5 code if a conflict gets resolved by picking the wrong version.

---

## 7. Additional bugs discovered after the rebase (not present in the original port)

### `QComboBox::activated(const QString&)` removed in Qt6
Qt5 had two overloads of the `activated` signal: `activated(int)` and `activated(const QString&)`. Qt's **name-based auto-connection** mechanism (`on_<object>_<signal>`, no explicit `connect()` needed) relied on the `QString` overload for slots with that signature. **Qt6 removed the `QString` overload** entirely — only `activated(int index)` remains. If a slot `on_xxxComboBox_activated(QString const&)` existed in the Qt5 code, the auto-connection now fails **silently** (no compile error, just a runtime warning that's often filtered out by custom loggers), and the combo box stops working.

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
(also change the signature in the header/slot declaration)

**How to diagnose it:** if a UI control stops responding with no errors or crashes, and the slot's signature involved takes a `QString` from an `activated`/`currentIndexChanged`/similar signal, suspect this pattern right away — it's silent and easy to miss.

### macOS native `QSlider` rendering with `invertedAppearance` changed between Qt5/Qt6
A vertical slider with `invertedAppearance="true"` (to make the value increase upward instead of downward) can end up with the colored fill (blue/gray) **inverted** compared to Qt5, because `QMacStyle` in Qt6 draws native macOS controls (`NSSlider`) slightly differently. This isn't a code bug, it's a native theme behavior change.

More reliable fix: **force an explicit Qt stylesheet** on the widget, bypassing native rendering:
```css
QSlider::groove:vertical { background: #b0b0b0; width: 6px; border-radius: 3px; }
QSlider::handle:vertical { background: white; border: 1px solid #5c5c5c; height: 16px; margin: 0 -8px; border-radius: 8px; }
QSlider::sub-page:vertical { background: #b0b0b0; border-radius: 3px; }   /* toward the minimum */
QSlider::add-page:vertical { background: #2f7fd6; border-radius: 3px; }   /* toward the maximum */
```
If the result still looks inverted relative to what you want, simply swap the colors between `sub-page` and `add-page` (it depends on the specific widget's combination of `orientation`/`invertedAppearance`/`invertedControls` — easier to test empirically than to calculate ahead of time).

---

## 8. `CMAKE_PREFIX_PATH` — Homebrew keg-only and the "umbrella" path

Passing the individual keg-only prefixes for each Qt6 module (`/opt/homebrew/opt/qtbase;/opt/homebrew/opt/qtserialport;...`) worked for weeks, then **stopped working overnight** (specifically, `find_package` could no longer find `Qt6SerialPort`, even though the package was installed and up to date). Suspected cause: a change in how Homebrew organizes/links the CMake files for some modules between updates.

**More robust solution**: use Homebrew's "umbrella" prefix instead of the individual `opt/<formula>` paths:
```bash
# Instead of:
-DCMAKE_PREFIX_PATH="/opt/homebrew/opt/qtbase;/opt/homebrew/opt/qtserialport;/opt/homebrew/opt/qtmultimedia;/opt/homebrew/opt/qtwebsockets;/opt/homebrew/opt/qttools;/opt/homebrew/opt/hamlib-471"

# Use:
-DCMAKE_PREFIX_PATH="/opt/homebrew;/opt/homebrew/opt/hamlib-471"
```
The single `/opt/homebrew` path traverses Homebrew's centralized symlinks and still finds all the Qt6 modules, in a way that's more resilient to internal structure changes in any single formula.

**Note on `sudo` and permissions**: every `sudo cmake --build . --target install` leaves some files inside `build/CMakeFiles/git-data/` owned by `root`. If you then try to rebuild **without** `sudo`, you get a cryptic `Operation not permitted` error on the `revisiontag` target (which tries to update the Git hash). Simplest fix: **never reuse a `build/` directory that has seen a `sudo` build** — delete it and recreate it from scratch (`rm -rf build && mkdir build`) before the next normal build.

---

## 9. `QVariant` and templated containers of native types (e.g. `QList<QColor>`)

Even after confirming that Qt6's automatic stream-operator detection works fine for simple types (see §2, `qRegisterMetaTypeStreamOperators`), a **more subtle case** surfaced: a `QList<QColor>` (used here as a custom user-defined color palette, `WFPalette::Colours`) saved via `QVariant::fromValue()` and read back via `.value<WFPalette::Colours>()` **silently failed to round-trip** through `QSettings` on macOS.

**Symptoms:** the value written on save was correct (confirmed with `fprintf` diagnostics — a save right before quitting showed the expected number of colors), but on the next launch, reading it back always produced an empty list, and `QVariant::canConvert<WFPalette::Colours>()` returned `false`. No error, no warning — the data was just gone.

**Root cause:** `QColor` itself has native, well-known stream operators, and simple aggregate types generally round-trip fine. But a **templated container of such a type** (`QList<QColor>`), especially when stored to a native macOS settings backend (a `.plist` file, not a plain text `.ini`), doesn't reliably survive the `QVariant`-based serialization path in Qt6 — likely because the type-erasure/registration Qt6 relies on for "automatic" detection doesn't cover templated containers the same way it covers plain structs with hand-written operators.

**Fix — bypass `QVariant`'s automatic serialization entirely for this case, using an explicit, portable string format:**

```cpp
// Save
{
  QStringList colour_strings;
  for (auto const& c : m_userPalette.colours ())
    {
      colour_strings << QString ("%1,%2,%3").arg (c.red ()).arg (c.green ()).arg (c.blue ());
    }
  m_settings->setValue ("UserPalette", colour_strings);
}

// Load
{
  WFPalette::Colours restored_colours;
  auto const colour_strings = m_settings->value ("UserPalette").toStringList ();
  for (auto const& s : colour_strings)
    {
      auto const parts = s.split (',');
      if (3 == parts.size ())
        {
          restored_colours << QColor (parts[0].toInt (), parts[1].toInt (), parts[2].toInt ());
        }
    }
  m_userPalette = WFPalette {restored_colours};
}
```

`QStringList` is a plain, well-understood type for `QSettings` on every platform and backend — no ambiguity, no silent failures.

**How to diagnose this class of bug:** if a setting round-trips correctly *within the same session* (e.g. an immediate preview after changing it works) but is lost specifically *across an app restart*, and the setting in question is a custom type or a container of a custom/complex type (not a plain `int`/`QString`/`bool`), suspect this exact issue. A quick diagnostic is to log both `.size()` on save and `QVariant::canConvert<T>()` on load — if `canConvert` is `false` on load despite a successful save, this is almost certainly it.

⚠️ **Also worth checking nearby**: an explicit `m_settings->sync ()` call after writing values that matter at shutdown time is good practice regardless — Qt normally flushes `QSettings` automatically on destruction, but if the application exits very quickly after emitting a "finished"/close signal chain (as WSJT-X's `MainWindow::closeEvent` → `Q_EMIT finished()` → child window `close()` → child `saveSettings()` chain does), there's a narrow window where the last write in that chain might not hit disk before the process exits. It didn't turn out to be the root cause here, but it's a cheap, harmless safety net to add at the end of any `saveSettings()` that runs late in the shutdown sequence.

---

## 10. `QVariant`/`FrequencyList_v2_101::FrequencyItems` and a locale pitfall in the JSON fix itself

Same underlying disease as §9 (`QVariant` failing to reliably round-trip a templated container of a custom type through `QSettings` on Qt6/macOS), but this time on the frequency table (`FrequenciesForRegionModes_v2`), and with an extra twist worth documenting on its own.

**Symptom:** editing an entry in the frequency table and saving settings appeared to work, but the change (and eventually the *entire* table) was lost on the next app launch.

**Root cause, part 1 (same as §9):** `settings_->value("FrequenciesForRegionModes_v2").value<FrequencyList_v2_101::FrequencyItems>()` silently returned an empty list on Qt6/macOS, exactly like the `QList<QColor>` case.

**Fix attempt, and the trap it walked into:** the class already had a `QJsonObject Item::toJson() const` method, used for the existing manual import/export-to-file feature. The natural fix looked like: serialize the whole list to a compact JSON string and store *that* string in `QSettings` instead of relying on `QVariant::fromValue()`.

**Root cause, part 2 (the actual bug in the fix):** `Item::toJson()` writes the frequency field via `Radio::frequency_MHz_string()`, which formats the number **according to the current locale** — on a system set to Italian, that means a comma as the decimal separator (`"0,198000"`) instead of a dot. When reading it back, `QString::toDouble()` always expects a dot regardless of locale, so parsing silently produced `0.0` for every entry, and each item was then discarded by the `isSane()` sanity check — hence an empty table after "successfully" round-tripping through JSON.

**Correct fix:** for the internal `QSettings` round-trip (as opposed to the user-facing import/export-to-file feature, which is free to keep the human-readable MHz string), store the frequency as a **plain integer number of Hz** — locale-independent by construction:

```cpp
// Save
QJsonObject obj;
obj["frequency_hz"] = static_cast<qint64> (item.frequency_);   // Hz, not a locale-formatted MHz string
obj["mode"] = Modes::name (item.mode_);
obj["region"] = IARURegions::name (item.region_);
// ... other fields via QJsonObject, same idea as Item::toJson()

// Load
freq.frequency_ = static_cast<Radio::Frequency> (obj["frequency_hz"].toDouble ());
```

**How to diagnose this class of bug:** if a JSON-based settings round-trip "works" on the machine you tested it on but you suspect locale sensitivity, test explicitly with a non-English system locale (or just inspect the raw JSON string via a diagnostic print) and look for decimal separators, date formats, or thousands separators that don't match what a strict `QJsonValue`/`QString::toDouble()` parser expects. `QString::toDouble()` and `QJsonValue`-based parsing are locale-independent by design (always dot-decimal), but *anything* that goes through a locale-aware formatter first (like the MHz-string helper here) breaks that guarantee the moment it's read back on a differently-configured machine — including, notably, the very same machine, if any locale-aware formatting was involved in producing the string in the first place, regardless of what locale is active at read time.

⚠️ **A second, unrelated trap hit while working on this fix, worth flagging for anyone repeating this kind of change**: `Configuration.cpp` (like a few other files in this codebase) has **mixed CRLF/LF line endings**. A naive Python text-mode edit (`open(path, 'r')` / `open(path, 'w')`, i.e. universal newlines) silently normalizes every line ending to `\n`, which makes `git diff` show the *entire file* as changed even when the actual content edit was a handful of lines. This doesn't break anything functionally, but it produces a huge, misleading diff that's unpleasant to review. Fix: read the file in a way that preserves its existing line endings, do the text replacement, then write it back forcing the *original* line-ending style:
```python
with open(path, 'r') as f:      # universal-newline read is fine for the string match itself
    content = f.read()
# ... do the .replace() on content, using \n line endings in the old/new blocks ...
with open(path, 'w', newline='\r\n') as f:   # force CRLF back if that's what the file originally had
    f.write(content)
```
Check first with `grep -c $'\r' <file>` (or `file <file>`) whether the file is predominantly CRLF or LF before choosing which one to force on write.

---

## 11. The same `QVariant` pattern recurs — a checklist for finding every instance

After fixing the waterfall palette (§9), the frequency table (§10), and — following the same pattern — the decode-highlighting color table and the station list (antenna/offset per band), it became clear this is a **systemic** issue, not an isolated one: **any custom type or templated container of a custom type saved via `QVariant::fromValue()` and read back via `.value<T>()` into `QSettings` is at risk on Qt6/macOS**, regardless of which specific type it is.

**Two more instances fixed with the identical technique** (explicit JSON serialization instead of `QVariant`):

- **Decode highlighting colors** (`DecodeHighlightingModel::HighlightItems`, key `"DecodeHighlighting"`) — same fix pattern as the palette, but with an extra subtlety: `HighlightInfo` stores `QBrush` (not `QColor`) for foreground/background, and some default entries (e.g. the "LoTW User" row) intentionally use an **unset brush** (`Qt::NoBrush` style) rather than a real color, to mean "no highlight". A naive `.color().name(...)` serialization collapses that distinction into a real (black) color. Fix: store an explicit `"..._unset"` boolean flag alongside the color string, and reconstruct `QBrush {}` (default, `Qt::NoBrush`) instead of a colored brush when that flag is set:
  ```cpp
  // Save
  obj["foreground_unset"] = (Qt::NoBrush == info.foreground_.style ());
  obj["foreground"] = info.foreground_.color ().name (QColor::HexArgb);
  // Load
  info.foreground_ = obj["foreground_unset"].toBool () ? QBrush {} : QBrush {QColor {obj["foreground"].toString ()}};
  ```

- **Station list** (`StationList::Stations`, antenna/offset per band, key `"stations"`) — simplest of the lot (a `QString`, a numeric offset, another `QString`), fixed with the same JSON pattern, no locale concerns since the offset is stored as a plain integer.

**How to find every instance of this bug class in one pass, instead of discovering them one at a time through user reports:**
```bash
grep -n "QVariant::fromValue\|\.value<.*::.*>" Configuration.cpp | grep -v "int\|bool\|QString\|double\|float\|qint\|quint"
```
This surfaces every `QVariant` round-trip involving a type with a `::` in its name (a strong signal of a custom enum/struct/container, as opposed to a plain built-in type). **Not every hit is actually at risk**, though — filter out:
- Values that only round-trip **within the same session** (e.g. populating a combo box's item data in memory, never written to `QSettings`) — `QVariant` handles same-session round-trips of custom types fine; the bug is specific to persisting through the macOS `.plist` backend across app restarts.
- Reads of genuinely obsolete/legacy setting keys used only for one-time migration from an older version's format — low priority, since a failure there just means old data isn't migrated forward, not that current data is lost.

For everything else — anything read from and written to `QSettings` on every normal save/load cycle — assume it's affected until proven otherwise, and apply the same fix: replace `QVariant::fromValue()`/`.value<T>()` with an explicit `QJsonArray`/`QJsonObject` serialization, one field at a time, taking care that no field passes through a locale-aware formatter (see §10's locale pitfall) before being written.

---

*Compiled during the port of wsjt-z (spud branch) to Qt6 on macOS Apple Silicon, July 2026, with assistance from Claude (Anthropic).*
